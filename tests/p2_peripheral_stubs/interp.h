/* SPDX-License-Identifier: MIT */
#include "mem.h"
enum { needsIntegerError=13, indexOutOfRangeError=18, needsListError=11, needsBooleanError=12,
       badPinError=57, byteOutOfRange=40, primitiveNotImplemented=27, badColorPalette=52 };
OBJ fail(int error);
