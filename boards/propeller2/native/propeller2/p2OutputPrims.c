/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Logical display primitives for P2 boards, which have no built-in 5x5 matrix.

#include "mem.h"
#include "interp.h"

int microBitDisplayBits = 0;
int mbDisplayColor = 0x00FF00;
int useTFT = false;

int displayIsActive(void) { return false; }
void updateMicrobitDisplay(void) {}
void turnOffInternalNeoPixels(void) {}

void tftInit(void) {}
void tftClear(void) {}
void tftSetHugePixel(int x, int y, int state) {
	(void) x;
	(void) y;
	(void) state;
}
void tftSetHugePixelBits(int bits) { (void) bits; }

void showMicroBitPixels(int bits, int x, int y) {
	(void) x;
	(void) y;
	microBitDisplayBits = bits;
}

void setAllNeoPixels(int pin, int ledCount, int color) {
	(void) pin;
	(void) ledCount;
	(void) color;
}

static OBJ primLightLevel(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return zeroObj;
}

static OBJ primMBSetColor(int argCount, OBJ *args) {
	if (argCount > 0) mbDisplayColor = evalInt(args[0]);
	return falseObj;
}

OBJ primMBDisplay(int argCount, OBJ *args) {
	if ((argCount > 0) && isInt(args[0])) microBitDisplayBits = evalInt(args[0]);
	return falseObj;
}

OBJ primMBDisplayOff(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	microBitDisplayBits = 0;
	return falseObj;
}

OBJ primMBEnableDisplay(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return falseObj;
}

OBJ primMBPlot(int argCount, OBJ *args) {
	if (argCount < 2) return fail(notEnoughArguments);
	int x = evalInt(args[0]);
	int y = evalInt(args[1]);
	if ((1 <= x) && (x <= 5) && (1 <= y) && (y <= 5)) {
		microBitDisplayBits |= 1 << ((5 * (y - 1)) + (x - 1));
	}
	return falseObj;
}

OBJ primMBUnplot(int argCount, OBJ *args) {
	if (argCount < 2) return fail(notEnoughArguments);
	int x = evalInt(args[0]);
	int y = evalInt(args[1]);
	if ((1 <= x) && (x <= 5) && (1 <= y) && (y <= 5)) {
		microBitDisplayBits &= ~(1 << ((5 * (y - 1)) + (x - 1)));
	}
	return falseObj;
}

static OBJ primMBShapeForLetter(int argCount, OBJ *args) {
	if (argCount < 1) return fail(notEnoughArguments);

	int codepoint = 0;
	if (isInt(args[0])) {
		codepoint = evalInt(args[0]);
	} else if (IS_TYPE(args[0], StringType) && (BYTES(args[0]) > 0)) {
		codepoint = unicodeCodePoint(obj2str(args[0]));
	}

	int glyph = codepointToCP437(codepoint) & 255;
	int result = 0;
	// mbFont stores five columns of seven bits. Keep the middle five rows for
	// compatibility with the MicroBlocks 5x5 shape reporter.
	for (int x = 0; x < 5; x++) {
		int column = mbFont[(5 * glyph) + x] >> 1;
		for (int y = 0; y < 5; y++) {
			if (column & (1 << y)) result |= 1 << ((5 * y) + x);
		}
	}
	return int2obj(result);
}

OBJ primMBDrawShape(int argCount, OBJ *args) {
	if (argCount < 1) return fail(notEnoughArguments);
	int shape = evalInt(args[0]);
	int x = (argCount >= 3) ? evalInt(args[1]) : 1;
	int y = (argCount >= 3) ? evalInt(args[2]) : 1;
	int sourceMask = 1;

	for (int dstY = y; dstY < (y + 5); dstY++) {
		for (int dstX = x; dstX < (x + 5); dstX++) {
			if ((1 <= dstX) && (dstX <= 5) && (1 <= dstY) && (dstY <= 5)) {
				int destinationMask = 1 << ((5 * (dstY - 1)) + (dstX - 1));
				if (shape & sourceMask) {
					microBitDisplayBits |= destinationMask;
				} else {
					microBitDisplayBits &= ~destinationMask;
				}
			}
			sourceMask <<= 1;
		}
	}
	return falseObj;
}

static OBJ primNeoPixelSend(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return fail(primitiveNotImplemented);
}

static OBJ primNeoPixelSetPin(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return fail(primitiveNotImplemented);
}

static PrimEntry entries[] = {
	{"lightLevel", primLightLevel},
	{"mbSetColor", primMBSetColor},
	{"mbDisplay", primMBDisplay},
	{"mbDisplayOff", primMBDisplayOff},
	{"mbPlot", primMBPlot},
	{"mbUnplot", primMBUnplot},
	{"mbDrawShape", primMBDrawShape},
	{"mbShapeForLetter", primMBShapeForLetter},
	{"mbEnableDisplay", primMBEnableDisplay},
	{"neoPixelSend", primNeoPixelSend},
	{"neoPixelSetPin", primNeoPixelSetPin},
};

void addDisplayPrims(void) {
	addPrimitiveSet(DisplayPrims, "display", sizeof(entries) / sizeof(PrimEntry), entries);
}
