/* SPDX-License-Identifier: MPL-2.0 */
// Bounded software SPI block device for the P2 boot flash. FlexProp 7.7.0's
// bundled smart-pin driver stalled on the first page program on the tested
// EC32MB. Keep littlefs, but use this single-cog, single-owner transport.
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <sys/vfs.h>
#include <sys/ioctl.h>
#include <propeller2.h>

#define FLASH_MISO 58
#define FLASH_MOSI 59
#define FLASH_CLK 60
#define FLASH_CS 61
#define FLASH_BASE (2U * 1024U * 1024U)
#define FLASH_SIZE (6U * 1024U * 1024U)
#define FLASH_ERASE_SIZE 4096U

static uint32_t flashPosition;
static uint32_t flashJEDEC;
static int flashFault;
static vfs_file_t *flashHandle;

static unsigned transfer(unsigned value) {
	unsigned result = 0;
	for (int bit = 7; bit >= 0; bit--) {
		_pinw(FLASH_MOSI, (value >> bit) & 1);
		_waitx(8);
		_pinh(FLASH_CLK);
		_waitx(8);
		result = (result << 1) | _pinr(FLASH_MISO);
		_pinl(FLASH_CLK);
	}
	return result;
}

static void deselect(void) {
	_pinh(FLASH_CS);
	_waitus(1);
}

static void command(unsigned cmd) {
	_pinl(FLASH_CS);
	transfer(cmd);
}

static void address(uint32_t offset) {
	uint32_t addr = FLASH_BASE + offset;
	transfer(addr >> 16); transfer(addr >> 8); transfer(addr);
}

static int waitReady(void) {
	uint32_t start = _getms();
	for (;;) {
		command(0x05);
		unsigned status = transfer(0);
		deselect();
		if (!(status & 1)) return 1;
		if ((uint32_t) (_getms() - start) >= 3000) {
			flashFault = 1; return 0;
		}
		_waitus(50);
	}
}

static int writeEnable(void) {
	if (flashFault || !waitReady()) return 0;
	command(0x06); deselect();
	command(0x05); unsigned status = transfer(0); deselect();
	if (!(status & 2)) { flashFault = 1; return 0; }
	return 1;
}

static off_t deviceSeek(vfs_file_t *file, off_t offset, int whence) {
	(void) file;
	if (whence == 1) offset += flashPosition;
	else if (whence == 2) offset += FLASH_SIZE;
	else if (whence != 0) return -1;
	if (offset < 0 || offset > FLASH_SIZE) return -1;
	flashPosition = (uint32_t) offset;
	return offset;
}

static ssize_t deviceRead(vfs_file_t *file, void *buffer, size_t size) {
	(void) file;
	if (flashFault || (uint32_t) size > (uint32_t) (FLASH_SIZE - flashPosition) || !waitReady()) {
		memset(buffer, 0, size); return -1;
	}
	uint8_t *data = (uint8_t *) buffer;
	command(0x03); address(flashPosition);
	for (size_t i = 0; i < size; i++) data[i] = transfer(0);
	deselect(); flashPosition += size;
	return size;
}

static ssize_t deviceWrite(vfs_file_t *file, const void *buffer, size_t size) {
	(void) file;
	if (flashFault || (flashPosition & 255) || (size & 255) ||
		(uint32_t) size > (uint32_t) (FLASH_SIZE - flashPosition)) return -1;
	const uint8_t *data = (const uint8_t *) buffer;
	for (size_t pos = 0; pos < size; pos += 256) {
		if (!writeEnable()) return -1;
		command(0x02); address(flashPosition);
		for (int i = 0; i < 256; i++) transfer(data[pos + i]);
		deselect();
		if (!waitReady()) return -1;
		flashPosition += 256;
	}
	return size;
}

static int deviceErase(vfs_file_t *file, int request, void *arg) {
	(void) file;
	if (request != BLKIOCTLERASE || !arg || flashFault) return -1;
	struct _blkio_info *info = (struct _blkio_info *) arg;
	uint32_t pos = info->addr, remaining = info->size;
	if ((pos % FLASH_ERASE_SIZE) || (remaining % FLASH_ERASE_SIZE) ||
		pos > (uint32_t) FLASH_SIZE || remaining > (uint32_t) (FLASH_SIZE - pos)) return -1;
	while (remaining) {
		if (!writeEnable()) return -1;
		command(0x20); address(pos); deselect();
		if (!waitReady()) return -1;
		pos += FLASH_ERASE_SIZE; remaining -= FLASH_ERASE_SIZE;
	}
	return 0;
}

static int deviceFlush(vfs_file_t *file) {
	(void) file; return (!flashFault && waitReady()) ? 0 : -1;
}

uint32_t p2FlashJEDEC(void) { return flashJEDEC; }

vfs_file_t *p2OpenFlashDevice(void) {
	if (flashHandle) return flashFault ? NULL : flashHandle;
	for (int pin = FLASH_MISO; pin <= FLASH_CS; pin++) {
		_pinclear(pin); _pinf(pin);
	}
	_pinh(FLASH_CS); _pinl(FLASH_CLK); _pinl(FLASH_MOSI);
	command(0xab); deselect(); _waitms(1); // release deep power-down
	command(0x9f);
	flashJEDEC = transfer(0) << 16;
	flashJEDEC |= transfer(0) << 8;
	flashJEDEC |= transfer(0);
	deselect();
	unsigned capacity = flashJEDEC & 255;
	if (!flashJEDEC || flashJEDEC == 0xffffff || capacity < 0x17 || capacity > 0x20) {
		flashFault = 1; return NULL;
	}
	if (!waitReady()) return NULL;
	flashHandle = _get_vfs_file_handle();
	if (!flashHandle) return NULL;
	flashHandle->flags = O_RDWR;
	flashHandle->bufmode = _IONBF;
	flashHandle->state = _VFS_STATE_INUSE | _VFS_STATE_WROK | _VFS_STATE_RDOK;
	flashHandle->read = deviceRead; flashHandle->write = deviceWrite;
	flashHandle->lseek = deviceSeek; flashHandle->ioctl = deviceErase;
	flashHandle->flush = deviceFlush;
	return flashHandle;
}
