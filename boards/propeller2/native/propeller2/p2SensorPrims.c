/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Bit-banged I2C and SPI primitives for the native Propeller 2 port.

#include <string.h>
#include <propeller2.h>
#include <smartpins.h>

#include "mem.h"
#include "interp.h"
#include "p2Board.h"

#define DEFAULT_I2C_SDA 8
#define DEFAULT_I2C_SCL 9
#define DEFAULT_SPI_MISO 4
#define DEFAULT_SPI_MOSI 5
#define DEFAULT_SPI_SCK 6

static int i2cSDA = DEFAULT_I2C_SDA;
static int i2cSCL = DEFAULT_I2C_SCL;
static int i2cHalfPeriod = 5; // 100 kHz

extern void invalidatePinModeTracking(int pin);

static int validPin(int pin) {
	return (0 <= pin) && (pin <= P2_LAST_USER_PIN);
}

// P2 pin modes can supply a weak internal pull-up while still driving low
// strongly. External I2C pull-ups are still recommended.
static void i2cRelease(int pin) {
	_wrpin(pin, P_HIGH_15K | P_LOW_FAST);
	_pinh(pin);
	invalidatePinModeTracking(pin);
}

static void i2cLow(int pin) {
	_pinl(pin);
	invalidatePinModeTracking(pin);
}

static int i2cRaiseClock(void) {
	i2cRelease(i2cSCL);
	uint32 deadline = microsecs() + 1000;
	while (!_pinr(i2cSCL)) {
		if ((int32_t) (microsecs() - deadline) >= 0) return false;
	}
	_waitus(i2cHalfPeriod);
	return true;
}

static int i2cStart(void) {
	// Synchronize with the I/O primitive's pin-role tracking before applying
	// the P2 open-drain pad configuration below.
	setPinMode(i2cSDA, 0); // input
	setPinMode(i2cSCL, 0); // input
	i2cRelease(i2cSDA);
	if (!i2cRaiseClock()) return false;
	i2cLow(i2cSDA);
	_waitus(i2cHalfPeriod);
	i2cLow(i2cSCL);
	return true;
}

static void i2cStop(void) {
	i2cLow(i2cSDA);
	_waitus(i2cHalfPeriod);
	i2cRaiseClock();
	i2cRelease(i2cSDA);
	_waitus(i2cHalfPeriod);
}

static int i2cWriteByte(int value) {
	for (int mask = 0x80; mask; mask >>= 1) {
		if (value & mask) i2cRelease(i2cSDA); else i2cLow(i2cSDA);
		_waitus(i2cHalfPeriod);
		if (!i2cRaiseClock()) return false;
		i2cLow(i2cSCL);
	}

	i2cRelease(i2cSDA);
	_waitus(i2cHalfPeriod);
	if (!i2cRaiseClock()) return false;
	int acknowledged = !_pinr(i2cSDA);
	i2cLow(i2cSCL);
	return acknowledged;
}

static int i2cReadByte(int sendAck) {
	int value = 0;
	i2cRelease(i2cSDA);
	for (int i = 0; i < 8; i++) {
		value <<= 1;
		_waitus(i2cHalfPeriod);
		if (!i2cRaiseClock()) {
			i2cLow(i2cSCL);
			i2cRelease(i2cSDA);
			return -1;
		}
		if (_pinr(i2cSDA)) value |= 1;
		i2cLow(i2cSCL);
	}
	if (sendAck) i2cLow(i2cSDA); else i2cRelease(i2cSDA);
	_waitus(i2cHalfPeriod);
	if (!i2cRaiseClock()) {
		i2cLow(i2cSCL);
		i2cRelease(i2cSDA);
		return -1;
	}
	i2cLow(i2cSCL);
	i2cRelease(i2cSDA);
	return value;
}

int hasI2CPullups(void) { return true; }

OBJ primI2cExists(int argCount, OBJ *args) {
	if ((argCount < 1) || !isInt(args[0])) return falseObj;
	int address = obj2int(args[0]);
	if ((address < 0) || (address > 127) || !i2cStart()) return falseObj;
	int result = i2cWriteByte(address << 1);
	i2cStop();
	return result ? trueObj : falseObj;
}

OBJ primI2cGet(OBJ *args) {
	if (!isInt(args[0]) || !isInt(args[1])) return fail(needsIntegerError);
	int address = obj2int(args[0]);
	int reg = obj2int(args[1]);
	if ((address < 0) || (address > 127)) return fail(i2cDeviceIDOutOfRange);
	if ((reg < 0) || (reg > 255)) return fail(i2cRegisterIDOutOfRange);

	if (!i2cStart() || !i2cWriteByte(address << 1) || !i2cWriteByte(reg)) {
		i2cStop();
		return zeroObj;
	}
	if (!i2cStart() || !i2cWriteByte((address << 1) | 1)) {
		i2cStop();
		return zeroObj;
	}
	int result = i2cReadByte(false);
	i2cStop();
	return (result < 0) ? zeroObj : int2obj(result);
}

OBJ primI2cSet(OBJ *args) {
	if (!isInt(args[0]) || !isInt(args[1]) || !isInt(args[2])) return fail(needsIntegerError);
	int address = obj2int(args[0]);
	int reg = obj2int(args[1]);
	int value = obj2int(args[2]);
	if ((address < 0) || (address > 127)) return fail(i2cDeviceIDOutOfRange);
	if ((reg < 0) || (reg > 255)) return fail(i2cRegisterIDOutOfRange);
	if ((value < 0) || (value > 255)) return fail(i2cValueOutOfRange);

	if (i2cStart()) {
		i2cWriteByte(address << 1);
		i2cWriteByte(reg);
		i2cWriteByte(value);
	}
	i2cStop();
	return falseObj;
}

int readI2CReg(int deviceID, int reg) {
	OBJ args[2] = {int2obj(deviceID), int2obj(reg)};
	OBJ result = primI2cGet(args);
	return isInt(result) ? obj2int(result) : 0;
}

void writeI2CReg(int deviceID, int reg, int value) {
	OBJ args[3] = {int2obj(deviceID), int2obj(reg), int2obj(value)};
	primI2cSet(args);
}

static OBJ primI2cRead(int argCount, OBJ *args) {
	if ((argCount < 2) || !isInt(args[0])) return zeroObj;
	int address = obj2int(args[0]);
	OBJ destination = args[1];
	int count = 0;
	uint8 *bytes = NULL;

	if (IS_TYPE(destination, ListType)) {
		count = obj2int(FIELD(destination, 0));
	} else if (IS_TYPE(destination, ByteArrayType)) {
		count = BYTES(destination);
		bytes = (uint8 *) &FIELD(destination, 0);
	} else {
		return fail(needsByteArray);
	}
	if ((count <= 0) || (address < 0) || (address > 127)) return zeroObj;
	if (!i2cStart() || !i2cWriteByte((address << 1) | 1)) {
		i2cStop();
		return zeroObj;
	}
	int bytesRead = 0;
	for (int i = 0; i < count; i++) {
		int value = i2cReadByte(i < (count - 1));
		if (value < 0) break;
		if (bytes) bytes[i] = value; else FIELD(destination, i + 1) = int2obj(value);
		bytesRead++;
	}
	i2cStop();
	return int2obj(bytesRead);
}

static int i2cWriteObject(OBJ data) {
	if (isInt(data)) {
		int value = obj2int(data);
		if ((value < 0) || (value > 255)) return -1;
		return i2cWriteByte(value) ? 1 : 0;
	}
	if (IS_TYPE(data, ByteArrayType)) {
		uint8 *bytes = (uint8 *) &FIELD(data, 0);
		int count = BYTES(data);
		for (int i = 0; i < count; i++) if (!i2cWriteByte(bytes[i])) return i;
		return count;
	}
	if (IS_TYPE(data, StringType)) {
		uint8 *bytes = (uint8 *) obj2str(data);
		int count = strlen((char *) bytes);
		for (int i = 0; i < count; i++) if (!i2cWriteByte(bytes[i])) return i;
		return count;
	}
	if (IS_TYPE(data, ListType)) {
		int count = obj2int(FIELD(data, 0));
		for (int i = 0; i < count; i++) {
			OBJ item = FIELD(data, i + 1);
			if (!isInt(item)) return -1;
			int value = obj2int(item);
			if ((value < 0) || (value > 255)) return -1;
			if (!i2cWriteByte(value)) return i;
		}
		return count;
	}
	return -1;
}

static OBJ primI2cWrite(int argCount, OBJ *args) {
	if ((argCount < 2) || !isInt(args[0])) return zeroObj;
	int address = obj2int(args[0]);
	int sendStop = (argCount < 3) || (trueObj == args[2]);
	if ((address < 0) || (address > 127) || !i2cStart() || !i2cWriteByte(address << 1)) {
		i2cStop();
		return falseObj;
	}
	int result = i2cWriteObject(args[1]);
	if (sendStop || (result < 0)) i2cStop();
	if (result < 0) return fail(i2cValueOutOfRange);
	return falseObj;
}

static OBJ primI2cSetClockSpeed(int argCount, OBJ *args) {
	if ((argCount < 1) || !isInt(args[0])) return falseObj;
	int speed = obj2int(args[0]);
	if (speed > 0) {
		int halfPeriod = 500000 / speed;
		if (halfPeriod < 1) halfPeriod = 1;
		if (halfPeriod > 1000) halfPeriod = 1000;
		i2cHalfPeriod = halfPeriod;
	}
	return falseObj;
}

static OBJ primI2cSetPins(int argCount, OBJ *args) {
	if (argCount < 2) return fail(notEnoughArguments);
	if (!isInt(args[0]) || !isInt(args[1])) return fail(needsIntegerError);
	int sda = obj2int(args[0]);
	int scl = obj2int(args[1]);
	if (!validPin(sda) || !validPin(scl) || (sda == scl)) return fail(badPinError);
	setPinMode(i2cSDA, 0); // release the old bus pins
	setPinMode(i2cSCL, 0);
	_pinclear(i2cSDA);
	_pinf(i2cSDA);
	_pinclear(i2cSCL);
	_pinf(i2cSCL);
	invalidatePinModeTracking(i2cSDA);
	invalidatePinModeTracking(i2cSCL);
	setPinMode(sda, 0); // detach any smart-pin role on the new bus pins
	setPinMode(scl, 0);
	i2cSDA = sda;
	i2cSCL = scl;
	i2cRelease(i2cSDA);
	i2cRelease(i2cSCL);
	return falseObj;
}

// SPI uses P4=MISO, P5=MOSI, and P6=SCK by default. Chip-select is controlled
// separately with the normal digital pin blocks.

static int spiMISO = DEFAULT_SPI_MISO;
static int spiMOSI = DEFAULT_SPI_MOSI;
static int spiSCK = DEFAULT_SPI_SCK;
static int spiHalfPeriod = 1;
static int spiMode = 0;
static int spiLSBFirst = false;

static int spiExchangeByte(int output) {
	int input = 0;
	int clockIdle = (spiMode >> 1) & 1;
	int sampleTrailing = spiMode & 1;
	setPinMode(spiMISO, 0); // input
	setPinMode(spiMOSI, 1); // output
	setPinMode(spiSCK, 1); // output
	_pinw(spiSCK, clockIdle);
	for (int i = 0; i < 8; i++) {
		int bitIndex = spiLSBFirst ? i : (7 - i);
		if (!sampleTrailing) {
			// CPHA=0: data is valid before the leading edge and sampled
			// while the clock is active.
			_pinw(spiMOSI, (output >> bitIndex) & 1);
			_waitus(spiHalfPeriod);
			_pinw(spiSCK, !clockIdle);
			_waitus(spiHalfPeriod);
			if (_pinr(spiMISO)) input |= 1 << bitIndex;
			_pinw(spiSCK, clockIdle);
		} else {
			// CPHA=1: change data on the leading edge and sample after the
			// trailing edge.
			_pinw(spiSCK, !clockIdle);
			_pinw(spiMOSI, (output >> bitIndex) & 1);
			_waitus(spiHalfPeriod);
			_pinw(spiSCK, clockIdle);
			_waitus(spiHalfPeriod);
			if (_pinr(spiMISO)) input |= 1 << bitIndex;
		}
	}
	return input;
}

OBJ primSPISend(OBJ *args) {
	OBJ value = args[0];
	if (isInt(value)) {
		int byteValue = obj2int(value);
		if ((byteValue < 0) || (byteValue > 255)) return fail(i2cValueOutOfRange);
		spiExchangeByte(byteValue);
	} else if (IS_TYPE(value, ByteArrayType)) {
		uint8 *bytes = (uint8 *) &FIELD(value, 0);
		for (int i = 0; i < BYTES(value); i++) spiExchangeByte(bytes[i]);
	} else {
		return fail(needsIntegerError);
	}
	return falseObj;
}

OBJ primSPIRecv(OBJ *args) {
	(void) args;
	return int2obj(spiExchangeByte(0));
}

static OBJ primSPIExchange(int argCount, OBJ *args) {
	if ((argCount < 1) || !IS_TYPE(args[0], ByteArrayType)) return falseObj;
	uint8 *bytes = (uint8 *) &FIELD(args[0], 0);
	for (int i = 0; i < BYTES(args[0]); i++) bytes[i] = spiExchangeByte(bytes[i]);
	return falseObj;
}

static OBJ primSPISetup(int argCount, OBJ *args) {
	if ((argCount < 1) || !isInt(args[0])) return falseObj;
	int speed = obj2int(args[0]);
	if (speed > 0) {
		spiHalfPeriod = 500000 / speed;
		if (spiHalfPeriod < 1) spiHalfPeriod = 1;
	}
	spiMode = ((argCount > 1) && isInt(args[1])) ? obj2int(args[1]) & 3 : 0;
	spiLSBFirst = (argCount > 3) && IS_TYPE(args[3], StringType) &&
		(0 == strcmp(obj2str(args[3]), "LSB"));
	setPinMode(spiMISO, 0);
	setPinMode(spiMOSI, 1);
	setPinMode(spiSCK, 1);
	_pinw(spiSCK, (spiMode >> 1) & 1);
	return falseObj;
}

static OBJ primAcceleration(int argCount, OBJ *args) { (void) argCount; (void) args; return zeroObj; }
OBJ primMBTemp(int argCount, OBJ *args) { (void) argCount; (void) args; return zeroObj; }
OBJ primMBTiltX(int argCount, OBJ *args) { (void) argCount; (void) args; return zeroObj; }
OBJ primMBTiltY(int argCount, OBJ *args) { (void) argCount; (void) args; return zeroObj; }
OBJ primMBTiltZ(int argCount, OBJ *args) { (void) argCount; (void) args; return zeroObj; }
static OBJ primTouchRead(int argCount, OBJ *args) { (void) argCount; (void) args; return fail(primitiveNotImplemented); }
static OBJ primReadDHT(int argCount, OBJ *args) { (void) argCount; (void) args; return fail(primitiveNotImplemented); }
static OBJ primMicrophone(int argCount, OBJ *args) { (void) argCount; (void) args; return zeroObj; }
int readAnalogMicrophone(void) { return 0; }

static PrimEntry entries[] = {
	{"acceleration", primAcceleration},
	{"temperature", primMBTemp},
	{"tiltX", primMBTiltX},
	{"tiltY", primMBTiltY},
	{"tiltZ", primMBTiltZ},
	{"touchRead", primTouchRead},
	{"i2cExists", primI2cExists},
	{"i2cRead", primI2cRead},
	{"i2cWrite", primI2cWrite},
	{"i2cSetClockSpeed", primI2cSetClockSpeed},
	{"i2cSetPins", primI2cSetPins},
	{"spiExchange", primSPIExchange},
	{"spiSetup", primSPISetup},
	{"readDHT", primReadDHT},
	{"microphone", primMicrophone},
};

void addSensorPrims(void) {
	addPrimitiveSet(SensorPrims, "sensors", sizeof(entries) / sizeof(PrimEntry), entries);
}
