/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Buffered secondary UART; P62/P63 remain dedicated to the IDE.

#include "mem.h"
#include "interp.h"
extern OBJ p2SerialOpen(int,OBJ*),p2SerialClose(int,OBJ*),p2SerialSetPins(int,OBJ*);
extern OBJ p2SerialRead(int,OBJ*),p2SerialReadInto(int,OBJ*),p2SerialWrite(int,OBJ*);
extern OBJ p2BufferedOpen(int,OBJ*),p2SerialAvailable(int,OBJ*),p2SerialDropped(int,OBJ*);
extern OBJ p2SerialReadByte(int,OBJ*),p2SerialWriteByte(int,OBJ*);

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
	{"open", p2SerialOpen}, {"close", p2SerialClose}, {"read", p2SerialRead},
	{"readInto", p2SerialReadInto}, {"write", p2SerialWrite},
	{"setPins", p2SerialSetPins}, {"writeBytes", p2SerialWrite},
	{"p2BufferedOpen", p2BufferedOpen}, {"p2Available", p2SerialAvailable},
	{"p2Dropped", p2SerialDropped}, {"p2ReadByte", p2SerialReadByte}, {"p2WriteByte", p2SerialWriteByte},
	{"midiSend", unsupported},
	{"midiRecv", unsupported},
	{"isDUELink", primIsDUELink},
	{"dueSend", unsupported},
	{"dueRecv", unsupported},
};

void addSerialPrims(void) {
	addPrimitiveSet(SerialPrims, "serial", sizeof(entries) / sizeof(PrimEntry), entries);
}
