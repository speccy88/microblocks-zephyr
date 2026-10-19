/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Secondary UART primitives are not yet implemented. P62/P63 remain dedicated
// to the binary MicroBlocks IDE connection.

#include "mem.h"
#include "interp.h"

static OBJ unsupported(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return fail(primitiveNotImplemented);
}

static OBJ primIsDUELink(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return falseObj;
}

static PrimEntry entries[] = {
	{"open", unsupported},
	{"close", unsupported},
	{"read", unsupported},
	{"readInto", unsupported},
	{"write", unsupported},
	{"setPins", unsupported},
	{"writeBytes", unsupported},
	{"midiSend", unsupported},
	{"midiRecv", unsupported},
	{"isDUELink", primIsDUELink},
	{"dueSend", unsupported},
	{"dueRecv", unsupported},
};

void addSerialPrims(void) {
	addPrimitiveSet(SerialPrims, "serial", sizeof(entries) / sizeof(PrimEntry), entries);
}
