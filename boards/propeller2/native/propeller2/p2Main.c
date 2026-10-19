/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Native FlexC platform layer for the Parallax Propeller 2.

#include <stdint.h>
#include <stdlib.h>
#include <propeller2.h>

#include "mem.h"
#include "interp.h"
#include "persist.h"
#include "p2Board.h"

// Standard P2 Eval and P2 Edge modules use a 20 MHz crystal. Parallax
// recommends 180 MHz or less for these boards. FlexC otherwise defaults the
// P2 serial link to 230400 baud, while MicroBlocks always connects at 115200.
enum {
	_clkfreq = 180000000,
	_xtlfreq = 20000000,
	HEAPSIZE = 32768,
};

#define IDE_BAUD 115200
#define IDE_RX_BUFFER_SIZE 2048U
#define IDE_RX_BUFFER_MASK (IDE_RX_BUFFER_SIZE - 1U)
#define IDE_RX_COG_STACK_WORDS 64

extern void _setbaud(int baudRate);
extern void _setrxtxflags(int flags);
extern int _rxpoll(void);
extern int _txraw(int value);

// FlexC's smart-pin UART has only a one-character receive buffer. Poll it from
// a dedicated cog so flash operations and long-running VM primitives cannot
// lose an entire IDE message. This is a single-producer/single-consumer ring:
// the receiver cog alone advances ideRxWrite and cog 0 alone advances
// ideRxRead, so no lock is needed.
static volatile uint8_t ideRxBuffer[IDE_RX_BUFFER_SIZE];
static volatile uint32_t ideRxRead = 0;
static volatile uint32_t ideRxWrite = 0;
static volatile uint32_t ideRxOverflowCount = 0;
static uint32_t ideRxCogStack[IDE_RX_COG_STACK_WORDS];
static int ideRxCog = -1;

static void ideSerialReceiver(void *arg) {
	(void) arg;
	for (;;) {
		int value = _rxpoll();
		if (value < 0) {
			// Poll several times per bit without monopolizing hub access.
			_waitx(64);
			continue;
		}

		uint32_t writeIndex = ideRxWrite;
		uint32_t next = (writeIndex + 1U) & IDE_RX_BUFFER_MASK;
		if (next == ideRxRead) {
			// Preserve the complete messages already queued; the VM protocol can
			// resynchronize after a timeout if the producer ever outruns 2 KB.
			ideRxOverflowCount++;
		} else {
			ideRxBuffer[writeIndex] = (uint8_t) value;
			ideRxWrite = next; // publish only after the byte has been stored
		}
	}
}

static void startIDESerialReceiver(void) {
	ideRxRead = 0;
	ideRxWrite = 0;
	ideRxOverflowCount = 0;
	ideRxCog = _cogstart_C(
		ideSerialReceiver, NULL, ideRxCogStack, sizeof(ideRxCogStack));
}

int resetDoubleTap = false;
char BLE_ThreeLetterID[4] = "";

// Timing

static uint32 microsecondHighBits = 0;
static uint32 lastMicrosecs = 0;

uint32 microsecs(void) {
	return _getus();
}

uint32 millisecs(void) {
	return _getms();
}

uint32 seconds(void) {
	return _getsec();
}

void handleMicosecondClockWrap(void) {
	uint32 now = microsecs();
	if (lastMicrosecs > now) microsecondHighBits++;
	lastMicrosecs = now;
}

uint64 totalMicrosecs(void) {
	handleMicosecondClockWrap();
	return (((uint64) microsecondHighBits) << 32) | microsecs();
}

void delay(unsigned long msecs) {
	_waitms((uint32_t) msecs);
}

// IDE transport. FlexC's default P2 terminal uses P63 for receive and P62 for
// transmit. Raw mode is essential because the MicroBlocks protocol is binary.

void restartSerial(void) {
	_setbaud(IDE_BAUD);
	_setrxtxflags(0);
}

int recvBytes(uint8 *buf, int count) {
	int byteCount = 0;
	if (ideRxCog >= 0) {
		uint32_t readIndex = ideRxRead;
		while ((byteCount < count) && (readIndex != ideRxWrite)) {
			buf[byteCount++] = ideRxBuffer[readIndex];
			readIndex = (readIndex + 1U) & IDE_RX_BUFFER_MASK;
			// Publish progress as bytes are copied so the producer can reuse ring
			// space even during a large 1 KB VM receive-buffer drain.
			ideRxRead = readIndex;
		}
		return byteCount;
	}

	// A cog is always available during normal startup, but retain the direct
	// polling path so a resource failure does not make the board unreachable.
	while (byteCount < count) {
		int value = _rxpoll();
		if (value < 0) break;
		buf[byteCount++] = value & 255;
	}
	return byteCount;
}

int sendBytes(uint8 *buf, int start, int end) {
	for (int i = start; i < end; i++) _txraw(buf[i]);
	return end - start;
}

// Platform identity and initialization

const char *boardType(void) {
	return P2_BOARD_NAME;
}

void hardwareInit(void) {
	srand(_rnd());
	// Clear every non-boot smart pin. On P2-EC32MB this leaves the reserved
	// P40-P57 PSRAM bus safely floating while MicroBlocks exposes only P0-P39.
	for (int pin = P2_FIRST_USER_PIN; pin <= P2_LAST_NON_BOOT_PIN; pin++) {
		_pinclear(pin);
		_pinf(pin);
	}
}

// Unsupported optional services. The first P2 port deliberately keeps the
// boot-flash pins private and does not claim BLE, radio, or IDE file transfer.

void resetRadio(void) {}
void processFileMessage(int msgType, int dataSize, char *data) {
	(void) msgType;
	(void) dataSize;
	(void) data;
}

void BLE_start(void) {}
int BLE_isEnabled(void) { return false; }
void BLE_setEnabled(int enableFlag) { (void) enableFlag; }

int main(void) {
	// Establish binary serial before any diagnostic can be queued by the VM.
	restartSerial();
	startIDESerialReceiver();
	memInit();
	primsInit();
	hardwareInit();
	outputString("Welcome to MicroBlocks!");
	restoreScripts();
	startAll();
	vmLoop();
	return 0;
}
