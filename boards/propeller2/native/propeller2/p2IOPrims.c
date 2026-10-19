/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Native FlexC I/O primitives for the Parallax Propeller 2.

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <propeller2.h>
#include <smartpins.h>

#include "mem.h"
#include "interp.h"
#include "p2Board.h"

#define DEFAULT_TONE_PIN 0

#define ANALOG_MAX 1023
#define ANALOG_SAMPLE_BITS 14
#define ANALOG_SAMPLE_CYCLES (1U << (ANALOG_SAMPLE_BITS - 1))
#define ANALOG_CALIBRATION_CYCLES (ANALOG_SAMPLE_CYCLES << 2)
#define ANALOG_SETTLE_CYCLES (ANALOG_SAMPLE_CYCLES << 1)
#define PWM_FREQUENCY 20000U

enum {
	P2_MODE_FLOATING = 0,
	P2_MODE_OUTPUT,
	P2_MODE_INPUT,
	P2_MODE_PULLUP,
	P2_MODE_PULLDOWN,
	P2_MODE_ADC,
	P2_MODE_PWM,
	P2_MODE_TONE,
	P2_MODE_SERVO,
	P2_MODE_SQUARE_WAVE,
	P2_MODE_SMART,
};

// These values match the Arduino pin-mode values passed by shared VM modules.
enum {
	MB_INPUT = 0,
	MB_OUTPUT = 1,
	MB_INPUT_PULLUP = 2,
	MB_INPUT_PULLDOWN = 3,
};

static uint8_t pinModeState[P2_USER_PIN_COUNT];
static uint32_t smartModeState[P2_USER_PIN_COUNT];
static uint16_t adcLow[P2_USER_PIN_COUNT];
static uint16_t adcHigh[P2_USER_PIN_COUNT];
static int tonePin = -1;
static int squareWavePin = -1;

static int validPin(int pin) {
	return (0 <= pin) && (pin < P2_USER_PIN_COUNT);
}

static void releasePin(int pin) {
	if (!validPin(pin)) return;

	if (tonePin == pin) tonePin = -1;
	if (squareWavePin == pin) squareWavePin = -1;
	_pinclear(pin);
	_pinf(pin);
	pinModeState[pin] = P2_MODE_FLOATING;
	smartModeState[pin] = 0;
}

void invalidatePinModeTracking(int pin) {
	// Platform modules that configure P2 pads directly call this so the next
	// normal I/O operation cannot reuse a stale smart-pin or GPIO mode.
	if (!validPin(pin)) return;
	if (tonePin == pin) tonePin = -1;
	if (squareWavePin == pin) squareWavePin = -1;
	pinModeState[pin] = P2_MODE_FLOATING;
	smartModeState[pin] = 0;
}

static void preparePin(int pin) {
	// Clear both the smart-pin mode and the output-enable state before giving
	// the pin a new role. Board-reserved flash, serial, and PSRAM pins are never
	// accepted by validPin().
	releasePin(pin);
}

static void configureInput(int pin, int mode) {
	if (!validPin(pin)) return;
	if (pinModeState[pin] == mode) return;

	preparePin(pin);
	if (mode == P2_MODE_PULLUP) {
		_wrpin(pin, P_HIGH_15K);
		_pinh(pin);
	} else if (mode == P2_MODE_PULLDOWN) {
		_wrpin(pin, P_LOW_15K);
		_pinl(pin);
	} else {
		_pinf(pin);
		mode = P2_MODE_INPUT;
	}
	pinModeState[pin] = mode;
}

static void setDirectOutput(int pin, int flag) {
	if (!validPin(pin)) return;

	if (pinModeState[pin] != P2_MODE_OUTPUT) preparePin(pin);
	if (flag) {
		_pinh(pin);
	} else {
		_pinl(pin);
	}
	pinModeState[pin] = P2_MODE_OUTPUT;
}

static uint32_t clockFrequency(void) {
	uint32_t result = _clockfreq();
	return result ? result : 1;
}

static uint32_t ncoStepFor(int frequency) {
	uint32_t step = _muldiv64((uint32_t) frequency, 0xFFFFFFFFU, clockFrequency());
	return step ? step : 1;
}

static int startNCO(int pin, int frequency, int mode) {
	uint32_t clock = clockFrequency();
	if (!validPin(pin) || (frequency <= 0) || ((uint32_t) frequency > (clock / 2))) {
		return false;
	}

	if (pinModeState[pin] == mode) {
		_wypin(pin, ncoStepFor(frequency));
	} else {
		preparePin(pin);
		_pinstart(pin, P_NCO_FREQ | P_OE, 1, ncoStepFor(frequency));
		pinModeState[pin] = mode;
	}
	return true;
}

static void setPWM(int pin, int value) {
	if (!validPin(pin)) return;
	if (value < 0) value = 0;
	if (value > ANALOG_MAX) value = ANALOG_MAX;

	if (pinModeState[pin] == P2_MODE_PWM) {
		_wypin(pin, (uint32_t) value);
		return;
	}

	uint32_t periodScale = PWM_FREQUENCY * ANALOG_MAX;
	uint32_t unitTicks = (clockFrequency() + (periodScale / 2)) / periodScale;
	if (unitTicks < 1) unitTicks = 1;
	if (unitTicks > 0xFFFFU) unitTicks = 0xFFFFU;
	uint32_t x = ((uint32_t) ANALOG_MAX << 16) | unitTicks;

	preparePin(pin);
	_pinstart(pin, P_PWM_SAWTOOTH | P_OE, x, (uint32_t) value);
	pinModeState[pin] = P2_MODE_PWM;
}

static void setServoPulse(int pin, int usecs) {
	if (!validPin(pin)) return;
	if (usecs <= 0) {
		if (pinModeState[pin] == P2_MODE_SERVO) releasePin(pin);
		return;
	}
	if (usecs > 5000) usecs = 5000;

	if (pinModeState[pin] == P2_MODE_SERVO) {
		_wypin(pin, (uint32_t) usecs);
		return;
	}

	uint32_t ticksPerMicrosecond = clockFrequency() / 1000000U;
	if (ticksPerMicrosecond < 1) ticksPerMicrosecond = 1;
	if (ticksPerMicrosecond > 0xFFFFU) ticksPerMicrosecond = 0xFFFFU;
	uint32_t x = (20000U << 16) | ticksPerMicrosecond;

	preparePin(pin);
	_pinstart(pin, P_PWM_SAWTOOTH | P_OE, x, (uint32_t) usecs);
	pinModeState[pin] = P2_MODE_SERVO;
}

// Pin support used directly by interpreter opcodes and shared primitive sets.

int pinCount(void) {
	return P2_USER_PIN_COUNT;
}

int mapDigitalPinNum(int userPinNum) {
	return validPin(userPinNum) ? userPinNum : -1;
}

int inputOnlyPin(int pin) {
	(void) pin;
	return false;
}

void setPinMode(int pin, int newMode) {
	if (!validPin(pin)) return;

	switch (newMode) {
	case MB_OUTPUT:
		setDirectOutput(pin, false);
		break;
	case MB_INPUT_PULLUP:
		configureInput(pin, P2_MODE_PULLUP);
		break;
	case MB_INPUT_PULLDOWN:
		configureInput(pin, P2_MODE_PULLDOWN);
		break;
	default:
		configureInput(pin, P2_MODE_INPUT);
		break;
	}
}

OBJ primAnalogPins(OBJ *args) {
	(void) args;
	return int2obj(P2_USER_PIN_COUNT);
}

OBJ primDigitalPins(OBJ *args) {
	(void) args;
	return int2obj(P2_USER_PIN_COUNT);
}

static uint32_t readADCMode(int pin, uint32_t mode, uint32_t settleCycles) {
	preparePin(pin);
	_pinstart(pin, mode | P_ADC, ANALOG_SAMPLE_BITS - 1, 0);
	_waitx(settleCycles);
	return _rdpin(pin);
}

OBJ primAnalogRead(int argCount, OBJ *args) {
	if (argCount < 1) return fail(notEnoughArguments);
	if (!isInt(args[0])) return fail(needsIntegerError);
	int pin = mapDigitalPinNum(obj2int(args[0]));
	if (pin < 0) return zeroObj;

	uint32_t raw;
	if (pinModeState[pin] != P2_MODE_ADC) {
		// Every P2 pin has its own ADC offset and gain. Measure the internal
		// ground and VIO references whenever a pin is assigned to analog input.
		adcLow[pin] = (uint16_t) readADCMode(pin, P_ADC_GIO, ANALOG_CALIBRATION_CYCLES);
		adcHigh[pin] = (uint16_t) readADCMode(pin, P_ADC_VIO, ANALOG_CALIBRATION_CYCLES);
		raw = readADCMode(pin, P_ADC_1X, ANALOG_SETTLE_CYCLES);
		pinModeState[pin] = P2_MODE_ADC;
	} else {
		raw = _rdpin(pin);
	}

	int32_t low = adcLow[pin];
	int32_t span = (int32_t) adcHigh[pin] - low;
	int32_t sample = (int32_t) raw - low;
	if ((span <= 0) || (sample <= 0)) return zeroObj;
	if (sample >= span) return int2obj(ANALOG_MAX);
	int scaled = (int) ((((int64_t) sample * ANALOG_MAX) + (span / 2)) / span);
	return int2obj(scaled);
}

void primAnalogWrite(OBJ *args) {
	if (!isInt(args[0]) || !isInt(args[1])) {
		fail(needsIntegerError);
		return;
	}
	setPWM(mapDigitalPinNum(obj2int(args[0])), obj2int(args[1]));
}

static int inputModeFor(OBJ pullArg) {
	if (objType(pullArg) == BooleanType) {
		return (pullArg == trueObj) ? P2_MODE_PULLUP : P2_MODE_INPUT;
	}
	if (objType(pullArg) == StringType) {
		char *setting = obj2str(pullArg);
		if (strcmp(setting, "up") == 0) return P2_MODE_PULLUP;
		if (strcmp(setting, "down") == 0) return P2_MODE_PULLDOWN;
	}
	return P2_MODE_INPUT;
}

OBJ primDigitalRead(int argCount, OBJ *args) {
	if (argCount < 1) return fail(notEnoughArguments);
	if (!isInt(args[0])) return fail(needsIntegerError);
	int pin = mapDigitalPinNum(obj2int(args[0]));
	if (pin < 0) return falseObj;

	int mode = (argCount > 1) ? inputModeFor(args[1]) : P2_MODE_INPUT;
	configureInput(pin, mode);
	return _pinr(pin) ? trueObj : falseObj;
}

void primDigitalSet(int pinNum, int flag) {
	int pin = mapDigitalPinNum(pinNum);
	if (pin < 0) return;

	// Match the shared VM behavior: a digital write to an active PWM pin
	// changes it to a 0% or 100% duty cycle without detaching the PWM unit.
	if (pinModeState[pin] == P2_MODE_PWM) {
		_wypin(pin, flag ? ANALOG_MAX : 0);
		return;
	}
	setDirectOutput(pin, flag);
}

void primDigitalWrite(OBJ *args) {
	if (!isInt(args[0])) {
		fail(needsIntegerError);
		return;
	}
	primDigitalSet(obj2int(args[0]), args[1] == trueObj);
}

void primSetUserLED(OBJ *args) {
	#if P2_USER_LED_ACTIVE_LOW
		// Eval Rev C LEDs are active-low.
		setDirectOutput(P2_USER_LED_PIN, args[0] != trueObj);
	#else
		// Both P2 Edge variants use a high-impedance, active-high LED buffer.
		setDirectOutput(P2_USER_LED_PIN, args[0] == trueObj);
	#endif
}

OBJ primButtonA(OBJ *args) {
	(void) args;
	return falseObj;
}

OBJ primButtonB(OBJ *args) {
	(void) args;
	return falseObj;
}

// Tone and servo support. Every P2 user pin has a smart-pin unit, so all
// exposed pins can generate PWM, NCO square waves, and servo pulses.

void stopTone(void) {
	if (validPin(tonePin)) releasePin(tonePin);
	tonePin = -1;
}

void stopServos(void) {
	for (int pin = 0; pin < P2_USER_PIN_COUNT; pin++) {
		if (pinModeState[pin] == P2_MODE_SERVO) releasePin(pin);
	}
}

void stopPWM(void) {
	for (int pin = 0; pin < P2_USER_PIN_COUNT; pin++) {
		if ((pinModeState[pin] == P2_MODE_PWM) ||
			(pinModeState[pin] == P2_MODE_SQUARE_WAVE)) {
			releasePin(pin);
		}
	}
	squareWavePin = -1;
}

void turnOffPins(void) {
	for (int pin = 0; pin < P2_USER_PIN_COUNT; pin++) {
		_pinclear(pin);
		_pinf(pin);
		pinModeState[pin] = P2_MODE_FLOATING;
	}
	tonePin = -1;
	squareWavePin = -1;
}

void beep(int frequency, int msecs) {
	// Standard P2 Eval and Edge boards do not have a built-in speaker.
	(void) frequency;
	(void) msecs;
}

static OBJ primHasTone(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return trueObj;
}

static OBJ primPlayTone(int argCount, OBJ *args) {
	if (argCount < 2) return falseObj;
	if (!isInt(args[0]) || !isInt(args[1])) return falseObj;

	int pin = mapDigitalPinNum(obj2int(args[0]));
	if (pin < 0) pin = DEFAULT_TONE_PIN;
	int frequency = obj2int(args[1]);
	if ((frequency < 16) || (frequency > 100000)) {
		stopTone();
		setDirectOutput(pin, false);
		return trueObj;
	}

	if ((tonePin >= 0) && (tonePin != pin)) stopTone();
	if (!startNCO(pin, frequency, P2_MODE_TONE)) return falseObj;
	tonePin = pin;
	return trueObj;
}

static OBJ primHasServo(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return trueObj;
}

static OBJ primSetServo(int argCount, OBJ *args) {
	if (argCount < 2) return falseObj;
	if (!isInt(args[0]) || !isInt(args[1])) return falseObj;
	int pin = mapDigitalPinNum(obj2int(args[0]));
	if (pin < 0) return falseObj;

	int usecs = obj2int(args[1]);
	if (usecs > 5000) usecs = 5000;
	setServoPulse(pin, usecs);
	return trueObj;
}

// Unsupported stream audio APIs remain present in the named primitive table
// so projects can detect them without encountering a missing primitive.

static OBJ primI2SInit(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return falseObj;
}

static OBJ primI2SWrite(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return falseObj;
}

static OBJ primDACInit(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return falseObj;
}

static OBJ primDACWrite(int argCount, OBJ *args) {
	(void) argCount;
	(void) args;
	return falseObj;
}

static OBJ primSoftwareSerialWriteByte(int argCount, OBJ *args) {
	if (argCount < 3) return fail(notEnoughArguments);
	if (!isInt(args[0]) || !isInt(args[1]) || !isInt(args[2])) {
		return fail(needsIntegerError);
	}

	int byte = obj2int(args[0]);
	int pin = mapDigitalPinNum(obj2int(args[1]));
	int baud = obj2int(args[2]);
	if ((pin < 0) || (baud <= 0)) return falseObj;

	uint32_t bitTicks = clockFrequency() / (uint32_t) baud;
	if (bitTicks < 2) bitTicks = 2;
	setDirectOutput(pin, true);

	_pinl(pin); // start bit
	_waitx(bitTicks);
	for (int bit = 0; bit < 8; bit++) {
		if (byte & (1 << bit)) {
			_pinh(pin);
		} else {
			_pinl(pin);
		}
		_waitx(bitTicks);
	}
	_pinh(pin); // stop bit and idle state
	_waitx(bitTicks);
	return falseObj;
}

static OBJ primSquareWave(int argCount, OBJ *args) {
	if (argCount < 1) return falseObj;
	OBJ pinArg = (argCount > 1) ? args[1] : zeroObj;
	if (!isInt(args[0]) || !isInt(pinArg)) return falseObj;

	int frequency = obj2int(args[0]);
	if (frequency <= 0) {
		if (validPin(squareWavePin)) releasePin(squareWavePin);
		squareWavePin = -1;
		return falseObj;
	}

	int pin = mapDigitalPinNum(obj2int(pinArg));
	if (pin < 0) return falseObj;
	if ((squareWavePin >= 0) && (squareWavePin != pin)) releasePin(squareWavePin);
	if (!startNCO(pin, frequency, P2_MODE_SQUARE_WAVE)) return falseObj;
	squareWavePin = pin;
	return trueObj;
}

// Power/reset hooks used by the VM. P2 has no FlexC deep-sleep API, so the
// sleep hooks wait for the requested interval without changing clock setup.

void systemReset(void) {
	_reboot();
}

void lightSleep(int msecs) {
	if (msecs > 0) _waitms((uint32_t) msecs);
}

void deepSleep(int secs) {
	if (secs > 0) _waitsec((uint32_t) secs);
}

// Forward named primitives to interpreter primitives that omit argCount.

static OBJ primSetUserLED2(int argCount, OBJ *args) {
	if (argCount != 1) return fail(notEnoughArguments);
	primSetUserLED(args);
	return falseObj;
}

static OBJ primAnalogWrite2(int argCount, OBJ *args) {
	(void) argCount;
	primAnalogWrite(args);
	return falseObj;
}

static OBJ primDigitalWrite2(int argCount, OBJ *args) {
	(void) argCount;
	primDigitalWrite(args);
	return falseObj;
}

// P2-specific blocks share IOPrims with the portal compiler's "p2" alias.
// Raw register values travel as hexadecimal strings to retain all 32 bits.
static int p2PinArg(int argc, OBJ *args) {
	if (argc < 1 || !isInt(args[0])) return -1;
	int pin = obj2int(args[0]);
	return validPin(pin) ? pin : -1;
}

static int p2Hex(OBJ arg, uint32_t *value) {
	if (!IS_TYPE(arg, StringType)) return false;
	const char *s = obj2str(arg);
	if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) s += 2;
	uint32_t n = 0;
	int count = 0;
	while (*s) {
		int digit = *s++;
		if (digit >= '0' && digit <= '9') digit -= '0';
		else if (digit >= 'a' && digit <= 'f') digit = digit - 'a' + 10;
		else if (digit >= 'A' && digit <= 'F') digit = digit - 'A' + 10;
		else return false;
		if (++count > 8) return false;
		n = (n << 4) | (uint32_t) digit;
	}
	if (!count) return false;
	*value = n;
	return true;
}

static OBJ p2HexString(uint32_t value) {
	char text[9];
	snprintf(text, sizeof(text), "%08lx", (unsigned long) value);
	return newStringFromBytes(text, 8);
}

static OBJ primP2Board(int argc, OBJ *args) {
	(void) argc; (void) args;
	return newStringFromBytes(P2_BOARD_NAME, strlen(P2_BOARD_NAME));
}
extern uint32_t p2FlashJEDEC(void);
static OBJ primP2FlashID(int argc, OBJ *args) {
	(void) argc; (void) args; return p2HexString(p2FlashJEDEC());
}
static OBJ primP2ClockHz(int argc, OBJ *args) {
	(void) argc; (void) args; return int2obj(clockFrequency());
}
static OBJ primP2Cog(int argc, OBJ *args) {
	(void) argc; (void) args; return int2obj(_cogid());
}
static OBJ primP2PinCount(int argc, OBJ *args) {
	(void) argc; (void) args; return int2obj(P2_USER_PIN_COUNT);
}
static OBJ primP2PinUsable(int argc, OBJ *args) {
	return (argc == 1 && p2PinArg(argc, args) >= 0) ? trueObj : falseObj;
}
static OBJ primP2Release(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 1 || pin < 0) return falseObj;
	releasePin(pin); return trueObj;
}

static OBJ primP2SmartPin(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 4 || pin < 0 || !IS_TYPE(args[1], StringType) ||
		!isInt(args[2]) || !isInt(args[3])) return falseObj;
	const char *name = obj2str(args[1]);
	int x = obj2int(args[2]), y = obj2int(args[3]);
	if (x < 0 || y < 0) return falseObj;
	if (!strcmp(name, "input")) { releasePin(pin); return trueObj; }
	if (!strcmp(name, "pull-up")) { configureInput(pin, P2_MODE_PULLUP); return trueObj; }
	if (!strcmp(name, "pull-down")) { configureInput(pin, P2_MODE_PULLDOWN); return trueObj; }
	uint32_t mode = 0;
	if (!strcmp(name, "NCO frequency")) mode = P_NCO_FREQ | P_OE;
	else if (!strcmp(name, "NCO duty")) mode = P_NCO_DUTY | P_OE;
	else if (!strcmp(name, "PWM sawtooth")) mode = P_PWM_SAWTOOTH | P_OE;
	else if (!strcmp(name, "PWM triangle")) mode = P_PWM_TRIANGLE | P_OE;
	else if (!strcmp(name, "count rises")) mode = P_COUNT_RISES;
	else if (!strcmp(name, "count highs")) mode = P_COUNT_HIGHS;
	else return falseObj;
	releasePin(pin);
	_pinstart(pin, mode, (uint32_t) x, (uint32_t) y);
	pinModeState[pin] = P2_MODE_SMART; smartModeState[pin] = mode;
	return trueObj;
}

static int p2InputAllowed(int pin, unsigned selection) {
	if (selection == 0 || selection == 4) return true; // local pad or local OUT
	int offset = (selection < 4) ? (int) selection : (int) selection - 8;
	return validPin(pin + offset);
}

static OBJ primP2SmartPinRaw(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	uint32_t mode, x, y;
	if (argc != 4 || pin < 0 || !p2Hex(args[1], &mode) ||
		!p2Hex(args[2], &x) || !p2Hex(args[3], &y)) return falseObj;
	// USB mode owns a paired pin. It is not exposed through a single-pin API.
	if (!(mode & 0x3e) || (mode & 0x3e) == P_USB_PAIR ||
		!p2InputAllowed(pin, (mode >> 28) & 7) ||
		!p2InputAllowed(pin, (mode >> 24) & 7)) return falseObj;
	releasePin(pin);
	_pinstart(pin, mode, x, y);
	pinModeState[pin] = P2_MODE_SMART; smartModeState[pin] = mode;
	return trueObj;
}

static OBJ primP2Frequency(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 2 || pin < 0 || !isInt(args[1])) return falseObj;
	int frequency = obj2int(args[1]);
	if (frequency <= 0 || (uint32_t) frequency > clockFrequency() / 2) return falseObj;
	releasePin(pin);
	startNCO(pin, frequency, P2_MODE_SMART);
	smartModeState[pin] = P_NCO_FREQ | P_OE;
	return trueObj;
}
static OBJ primP2Ready(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	return (argc == 1 && pin >= 0 && _pinr(pin)) ? trueObj : falseObj;
}
static OBJ primP2ReadHex(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	return (argc == 1 && pin >= 0) ? p2HexString(_rdpin(pin)) : falseObj;
}
static OBJ primP2Read(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 1 || pin < 0) return falseObj;
	// Explicitly sign-extend the VM's 31-bit integer payload.
	uint32_t value = _rdpin(pin);
	int32_t truncated = (int32_t) (value << 1) >> 1;
	return int2obj(truncated);
}
static OBJ primP2ModeHex(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	return (argc == 1 && pin >= 0) ? p2HexString(smartModeState[pin]) : falseObj;
}
static OBJ primP2WriteX(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t value;
	if (argc != 2 || pin < 0 || pinModeState[pin] != P2_MODE_SMART || !p2Hex(args[1], &value)) return falseObj;
	_wxpin(pin, value); return trueObj;
}
static OBJ primP2WriteY(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t value;
	if (argc != 2 || pin < 0 || pinModeState[pin] != P2_MODE_SMART || !p2Hex(args[1], &value)) return falseObj;
	_wypin(pin, value); return trueObj;
}

static PrimEntry entries[] = {
	{"p2Board", primP2Board},
	{"p2FlashID", primP2FlashID},
	{"p2ClockHz", primP2ClockHz},
	{"p2Cog", primP2Cog},
	{"p2PinCount", primP2PinCount},
	{"p2PinUsable", primP2PinUsable},
	{"p2SmartPin", primP2SmartPin},
	{"p2SmartPinRaw", primP2SmartPinRaw},
	{"p2Frequency", primP2Frequency},
	{"p2PinRelease", primP2Release},
	{"p2PinReady", primP2Ready},
	{"p2PinRead", primP2Read},
	{"p2PinReadHex", primP2ReadHex},
	{"p2PinModeHex", primP2ModeHex},
	{"p2PinWriteX", primP2WriteX},
	{"p2PinWriteY", primP2WriteY},
	{"hasTone", primHasTone},
	{"playTone", primPlayTone},
	{"hasServo", primHasServo},
	{"setServo", primSetServo},
	{"i2sInit", primI2SInit},
	{"i2sWrite", primI2SWrite},
	{"dacInit", primDACInit},
	{"dacWrite", primDACWrite},
	{"softWriteByte", primSoftwareSerialWriteByte},
	{"squareWave", primSquareWave},
	{"setUserLED", primSetUserLED2},
	{"analogRead", primAnalogRead},
	{"analogWrite", primAnalogWrite2},
	{"digitalRead", primDigitalRead},
	{"digitalWrite", primDigitalWrite2},
};

void addIOPrims(void) {
	addPrimitiveSet(IOPrims, "io", sizeof(entries) / sizeof(PrimEntry), entries);
}
