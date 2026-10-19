/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Persistent MicroBlocks code store on the standard P2 SPI flash.

#include <stdio.h>
#include <string.h>
#include <sys/vfs.h>

#include "mem.h"
#include "interp.h"

#define FILE_SYSTEM_MOUNT "/flash"
#define CODE_FILE "/flash/ublockscode"
#define CODE_FILE_TMP "/flash/ublockscode.tmp"

static int fileSystemInitialized = false;
static int fileSystemAvailable = false;
static FILE *codeFile = NULL;
extern vfs_file_t *p2OpenFlashDevice(void);

static void initFileSystem(void) {
	if (fileSystemInitialized) return;
	fileSystemInitialized = true;

	// FlexC littlefs defaults to 6 MB starting at offset 2 MB, beyond the boot
	// image. The first argument permits formatting when no valid littlefs volume
	// is present; the setup guide explicitly warns that this claims that region.
	// 4 KiB erase blocks bound metadata compaction latency for live edits.
	struct littlefs_flash_config cfg = {256, 4096, 2*1024*1024, 6*1024*1024, NULL, 0, 0};
	cfg.handle = p2OpenFlashDevice();
	if (!cfg.handle) return;
	struct vfs *flashFS = _vfs_open_littlefs_flash(1, &cfg);
	if (flashFS && (0 == mount(FILE_SYSTEM_MOUNT, flashFS))) {
		fileSystemAvailable = true;
	}
}

static void openCodeFileForAppend(void) {
	if (codeFile) fclose(codeFile);
	codeFile = fileSystemAvailable ? fopen(CODE_FILE, "ab") : NULL;
}

void writeCodeFile(uint8 *code, int byteCount);
void writeCodeFileWord(int word);
void clearCodeFile(int cycleCount);

void replaceCodeFile(int cycleCount, uint8 *code, int byteCount) {
	// Replace the complete code file via a temporary file. littlefs rename is
	// atomic, so a reset during compaction leaves either the old or new project.
	initFileSystem();
	if (!fileSystemAvailable) return;
	if (codeFile) {
		fclose(codeFile);
		codeFile = NULL;
	}

	remove(CODE_FILE_TMP);
	FILE *replacement = fopen(CODE_FILE_TMP, "wb");
	int headerWord = ('S' << 24) | (cycleCount & 0xFFFFFF);
	int ok = replacement &&
		(1 == fwrite(&headerWord, sizeof(headerWord), 1, replacement));
	if (ok && code && (byteCount > 0)) {
		ok = ((size_t) byteCount == fwrite(code, 1, byteCount, replacement));
	}
	if (replacement) {
		if (fflush(replacement)) ok = false;
		if (fclose(replacement)) ok = false;
	}

	if (!ok || rename(CODE_FILE_TMP, CODE_FILE)) {
		remove(CODE_FILE_TMP);
	}
	openCodeFileForAppend();
}

static int codeFilePrefixBytes(uint8 *data, int byteCount) {
	// Return the complete, valid prefix. An interrupted append may leave a
	// partial final record; retaining earlier records preserves the project.
	if (byteCount < 4) return 0;
	int header = 0;
	memcpy(&header, data, sizeof(header));
	if ('S' != ((header >> 24) & 0xFF)) return 0;

	int offset = 4;
	while (offset < byteCount) {
		if ((byteCount - offset) < 8) return offset;
		int recordHeader = 0;
		int wordCount = 0;
		memcpy(&recordHeader, &data[offset], sizeof(recordHeader));
		memcpy(&wordCount, &data[offset + 4], sizeof(wordCount));
		if (('R' != ((recordHeader >> 24) & 0xFF)) || (wordCount < 0)) return offset;
		if (wordCount > ((byteCount - offset - 8) / 4)) return offset;
		offset += 8 + (4 * wordCount);
	}
	return offset;
}

static int initializeEmptyStore(uint8 *flash, int flashByteCount, int cycleCount) {
	memset(flash, 0xFF, flashByteCount);
	int headerWord = ('S' << 24) | (cycleCount & 0xFFFFFF);
	memcpy(flash, &headerWord, sizeof(headerWord));
	replaceCodeFile(cycleCount, NULL, 0);
	return 4;
}

int initCodeFile(uint8 *flash, int flashByteCount) {
	initFileSystem();
	int fallbackHeader = 0;
	memcpy(&fallbackHeader, flash, sizeof(fallbackHeader));
	int fallbackCycle = ('S' == ((fallbackHeader >> 24) & 0xFF)) ?
		(fallbackHeader & 0xFFFFFF) : 1;
	if (!fileSystemAvailable) {
		return initializeEmptyStore(flash, flashByteCount, fallbackCycle);
	}

	FILE *input = fopen(CODE_FILE, "rb");
	if (!input) {
		return initializeEmptyStore(flash, flashByteCount, fallbackCycle);
	}
	int bytesRead = (int) fread(flash, 1, flashByteCount, input);
	int readFailed = ferror(input);
	int fileTooLarge = (EOF != fgetc(input));
	fclose(input);

	int validBytes = codeFilePrefixBytes(flash, bytesRead);
	if (validBytes < 4) {
		return initializeEmptyStore(flash, flashByteCount, fallbackCycle);
	}
	if (readFailed || fileTooLarge || (validBytes != bytesRead)) {
		int headerWord = 0;
		memcpy(&headerWord, flash, sizeof(headerWord));
		memset(&flash[validBytes], 0xFF, flashByteCount - validBytes);
		replaceCodeFile(headerWord & 0xFFFFFF, &flash[4], validBytes - 4);
		return validBytes;
	}
	openCodeFileForAppend();
	return bytesRead;
}

void writeCodeFile(uint8 *code, int byteCount) {
	if (!codeFile || (byteCount <= 0)) return;
	fwrite(code, 1, byteCount, codeFile);
	fflush(codeFile);
}

void writeCodeFileWord(int word) {
	writeCodeFile((uint8 *) &word, 4);
}

void clearCodeFile(int cycleCount) {
	replaceCodeFile(cycleCount, NULL, 0);
}

int hasStartupSnapshot(void) { return false; }
void loadCodeSnapshot(char *fileName) { (void) fileName; }
