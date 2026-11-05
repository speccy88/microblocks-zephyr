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
#include "p2Capture.h"

#define DEFAULT_TONE_PIN 0

#define ANALOG_MAX 1023
#define ANALOG_SAMPLE_BITS 14
#define ANALOG_SAMPLE_CYCLES (1U << (ANALOG_SAMPLE_BITS - 1))
#define ANALOG_CALIBRATION_CYCLES (ANALOG_SAMPLE_CYCLES << 2)
/* SINC2 needs complete samples after changing the pad/reference. Two nominal
   periods can still return the reset value on the first calibrated read. */
#define ANALOG_SETTLE_CYCLES (ANALOG_SAMPLE_CYCLES << 2)
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
	P2_MODE_PAD,
	P2_MODE_DAC,
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
static uint8_t serialBits[P2_USER_PIN_COUNT], serialMSB[P2_USER_PIN_COUNT], serialQueued[P2_USER_PIN_COUNT];
static uint8_t filterState[4] = {0,37,83,118};
static uint16_t adcLow[P2_USER_PIN_COUNT];
static uint16_t adcHigh[P2_USER_PIN_COUNT];
static int tonePin = -1;
static int squareWavePin = -1;

static int validPin(int pin) {
	return (0 <= pin) && (pin < P2_USER_PIN_COUNT);
}

static void releasePin(int pin) {
	if (!validPin(pin)) return;
	extern void p2SerialReleasePin(int pin);
	p2SerialReleasePin(pin);
	extern void p2DisplayReleasePin(int pin);
	p2DisplayReleasePin(pin);
	p2CaptureReleasePin(pin);

	if (tonePin == pin) tonePin = -1;
	if (squareWavePin == pin) squareWavePin = -1;
	_pinclear(pin);
	_pinf(pin);
	pinModeState[pin] = P2_MODE_FLOATING;
	smartModeState[pin] = 0;
	serialBits[pin] = serialMSB[pin] = serialQueued[pin] = 0;
}

void invalidatePinModeTracking(int pin) {
	extern void p2SerialReleasePin(int pin);
	p2SerialReleasePin(pin);
	extern void p2DisplayReleasePin(int pin);
	p2DisplayReleasePin(pin);
	p2CaptureReleasePin(pin);
	// Platform modules that configure P2 pads directly call this so the next
	// normal I/O operation cannot reuse a stale smart-pin or GPIO mode.
	if (!validPin(pin)) return;
	if (tonePin == pin) tonePin = -1;
	if (squareWavePin == pin) squareWavePin = -1;
	pinModeState[pin] = P2_MODE_FLOATING;
	smartModeState[pin] = 0;
	serialBits[pin] = serialMSB[pin] = serialQueued[pin] = 0;
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
	extern void p2PeripheralIOReset(void);
	p2PeripheralIOReset();
	extern void p2SerialReset(void);
	p2SerialReset();
	extern void p2LEDReset(void);
	p2LEDReset();
	extern void p2DisplayReset(void);
	p2DisplayReset();
	primP2CaptureStop(0, NULL);
	for (int pin = 0; pin < P2_USER_PIN_COUNT; pin++) {
		_pinclear(pin);
		_pinf(pin);
		pinModeState[pin] = P2_MODE_FLOATING;
		smartModeState[pin] = 0;
		serialBits[pin] = serialMSB[pin] = serialQueued[pin] = 0;
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
static OBJ primP2LocalPinDIR(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 1 || pin < 0) return falseObj;
	uint32_t direction = pin < 32 ? _DIRA : _DIRB;
	return direction & (1U << (pin & 31)) ? trueObj : falseObj;
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

static void p2Start(int pin, uint32_t mode, uint32_t x, uint32_t y) {
	releasePin(pin);
	_pinstart(pin, mode, x, y);
	unsigned operation = mode & 0x3e;
	/* These registers are cleared/ignored during DIR-low reset. */
	if (operation == P_PULSE || operation == P_TRANSITION) _wypin(pin, y);
	if (operation >= P_REPOSITORY && operation <= P_DAC_DITHER_PWM &&
		(mode & 0x1c0000) != 0x140000) _wxpin(pin, x);
	pinModeState[pin] = P2_MODE_SMART;
	smartModeState[pin] = mode;
}

int p2ScopeCaptureReady(int base, unsigned mask) {
    if (base<0 || base+3>=P2_USER_PIN_COUNT) return 0;
    for (int i=0;i<4;i++) if ((mask&(1U<<i)) && (smartModeState[base+i]&0x3e)!=P_ADC_SCOPE) return 0;
    return 1;
}
int p2PrepareCapturePin(int pin, int order, int period, int external, int b, uint32_t pad) {
    if (!validPin(pin) || b < -3 || b > 3 || !validPin(pin+b)) return 0;
    uint32_t mode = (external ? P_ADC_EXT : P_ADC) | pad;
    if (external) mode |= (uint32_t)(b < 0 ? b+8 : b)<<24;
    uint32_t x = order==0 ? 53U : (order==2 ? 16U : 32U);
    p2Start(pin,mode,x,period);return 1;
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
	p2Start(pin, mode, x, y);
	return trueObj;
}

typedef struct { const char *name; uint32_t bits; } P2NamedBits;
static const P2NamedBits p2PadNames[] = {
	{"logic", P_LOGIC_A}, {"logic A feedback", P_LOGIC_A_FB}, {"logic B feedback", P_LOGIC_B_FB},
	{"Schmitt", P_SCHMITT_A}, {"Schmitt A feedback", P_SCHMITT_A_FB}, {"Schmitt B feedback", P_SCHMITT_B_FB},
	{"compare A B", P_COMPARE_AB}, {"compare A B feedback", P_COMPARE_AB_FB},
	{"ADC ground", P_ADC_GIO}, {"ADC VIO", P_ADC_VIO}, {"ADC floating", P_ADC_FLOAT},
	{"ADC 1x", P_ADC_1X}, {"ADC 3x", P_ADC_3X}, {"ADC 10x", P_ADC_10X},
	{"ADC 30x", P_ADC_30X}, {"ADC 100x", P_ADC_100X},
	{"DAC 990R 3V", P_DAC_990R_3V}, {"DAC 600R 2V", P_DAC_600R_2V},
	{"DAC 124R 3V", P_DAC_124R_3V}, {"DAC 75R 2V", P_DAC_75R_2V},
	{"level A", P_LEVEL_A}, {"level A feedback negative", P_LEVEL_A_FBN},
	{"level B feedback positive", P_LEVEL_B_FBP}, {"level B feedback negative", P_LEVEL_B_FBN},
};
static const P2NamedBits p2OperationNames[] = {
	{"repository", P_REPOSITORY}, {"DAC noise", P_DAC_NOISE},
	{"DAC random dither", P_DAC_DITHER_RND}, {"DAC PWM dither", P_DAC_DITHER_PWM},
	{"pulse", P_PULSE}, {"transition", P_TRANSITION}, {"NCO frequency", P_NCO_FREQ},
	{"NCO duty", P_NCO_DUTY}, {"PWM triangle", P_PWM_TRIANGLE}, {"PWM sawtooth", P_PWM_SAWTOOTH},
	{"PWM SMPS", P_PWM_SMPS}, {"quadrature", P_QUADRATURE}, {"register up", P_REG_UP},
	{"register up down", P_REG_UP_DOWN}, {"count rises", P_COUNT_RISES}, {"count highs", P_COUNT_HIGHS},
	{"state ticks", P_STATE_TICKS}, {"high ticks", P_HIGH_TICKS}, {"event ticks", P_EVENTS_TICKS},
	{"period ticks", P_PERIODS_TICKS}, {"period highs", P_PERIODS_HIGHS},
	{"window ticks", P_COUNTER_TICKS}, {"window highs", P_COUNTER_HIGHS}, {"window periods", P_COUNTER_PERIODS},
	{"ADC sample", P_ADC}, {"ADC external", P_ADC_EXT}, {"ADC scope", P_ADC_SCOPE},
	{"sync transmit", P_SYNC_TX}, {"sync receive", P_SYNC_RX},
	{"async transmit", P_ASYNC_TX}, {"async receive", P_ASYNC_RX},
};
static int p2Named(const P2NamedBits *table, int count, OBJ name, uint32_t *bits) {
	if (!IS_TYPE(name, StringType)) return false;
	for (int i = 0; i < count; i++) if (!strcmp(table[i].name, obj2str(name))) {
		*bits = table[i].bits; return true;
	}
	return false;
}
#define P2_NAMED(table, name, bits) p2Named(table, sizeof(table)/sizeof(table[0]), name, bits)

static void p2Pad(int pin, uint32_t pad, int drive, int high) {
	releasePin(pin);
	_wrpin(pin, pad);
	/* Normal-mode DIR enables the pad; OUT is set only when explicitly asked. */
	if (drive) _pinw(pin, high);
	pinModeState[pin] = P2_MODE_PAD; smartModeState[pin] = pad;
}
void p2FiltersInit(void) {
	static const uint8_t defaults[4]={0,37,83,118};
	for (int bank=0;bank<4;bank++) {
		filterState[bank]=defaults[bank];
		_hubset(0x40000000U|((uint32_t)bank<<7)|defaults[bank]);
	}
}
static int p2FilterUsers(int bank) {
	int users=0;
	for (int pin=0;pin<P2_USER_PIN_COUNT;pin++) if (((smartModeState[pin]>>21)&7U)==(unsigned)(4+bank)) users++;
	return users;
}
static OBJ primP2FilterConfigure(int argc, OBJ *args) {
	if (argc!=3 || !isInt(args[0]) || !isInt(args[2])) return falseObj;
	int bank=obj2int(args[0]),length=0,tap=obj2int(args[2]),code=0;
	if (isInt(args[1])) length=obj2int(args[1]);
	else if (IS_TYPE(args[1],StringType)) {
		const char *text=obj2str(args[1]);
		if (!strcmp(text,"2")) length=2;else if (!strcmp(text,"3")) length=3;
		else if (!strcmp(text,"5")) length=5;else if (!strcmp(text,"8")) length=8;
	}
	if (bank<0 || bank>3 || tap<0 || tap>31) return falseObj;
	if (length==2) code=0;else if (length==3) code=1;else if (length==5) code=2;else if (length==8) code=3;else return falseObj;
	uint32_t setting=(code<<5)|tap;
	if (setting==filterState[bank]) return trueObj;
	if (p2FilterUsers(bank)) return falseObj;
	_hubset(0x40000000U|((uint32_t)bank<<7)|setting);filterState[bank]=setting;
	return trueObj;
}
static OBJ primP2FilterInfo(int argc, OBJ *args) {
	if (argc!=2 || !isInt(args[0]) || !IS_TYPE(args[1],StringType)) return falseObj;
	int bank=obj2int(args[0]);if (bank<0 || bank>3) return falseObj;
	const char *field=obj2str(args[1]);uint32_t value=filterState[bank];
	static const int lengths[4]={2,3,5,8};
	if (!strcmp(field,"length")) return int2obj(lengths[value>>5]);
	if (!strcmp(field,"tap")) return int2obj(value&31);
	if (!strcmp(field,"users")) return int2obj(p2FilterUsers(bank));
	if (!strcmp(field,"sample clocks hex")) return p2HexString(1U<<(value&31));
	if (!strcmp(field,"configuration hex")) return p2HexString(0x40000000U|((uint32_t)bank<<7)|value);
	return falseObj;
}
static OBJ primP2FilterInput(int argc, OBJ *args) {
	int pin=p2PinArg(argc,args);
	if (argc!=6 || pin<0 || !isInt(args[1]) || !isInt(args[2]) || !isInt(args[4]) ||
		objType(args[3])!=BooleanType || objType(args[5])!=BooleanType) return falseObj;
	int bank=obj2int(args[1]),a=obj2int(args[2]),b=obj2int(args[4]);
	if (bank<0 || bank>3 || a< -3 || a>3 || b< -3 || b>3 || !validPin(pin+a) || !validPin(pin+b)) return falseObj;
	uint32_t route=((uint32_t)(a<0 ? a+8 : a)<<28)|((uint32_t)(b<0 ? b+8 : b)<<24);
	if (args[3]==trueObj) route|=P_INVERT_A;
	if (args[5]==trueObj) route|=P_INVERT_B;
	p2Pad(pin,P_SCHMITT_A|route|((uint32_t)(4+bank)<<21),0,0);return trueObj;
}
static int p2Register(OBJ arg, uint32_t *value) {
	if (isInt(arg)) {
		int n = obj2int(arg); if (n < 0) return false;
		*value = n; return true;
	}
	return p2Hex(arg, value);
}
int p2CapturePadBits(OBJ value, int external, uint32_t *pad) {
    if (!P2_NAMED(p2PadNames,value,pad)) return 0;
    return external ? (*pad==P_SCHMITT_A || *pad==P_LOGIC_A) : ((*pad&0x1c0000)==0x100000);
}
int p2PrepareDMAInput(int pin, OBJ circuit) {
    uint32_t pad;
    if (!validPin(pin) || (!p2CapturePadBits(circuit,0,&pad) && !p2CapturePadBits(circuit,1,&pad))) return 0;
    p2Pad(pin,pad,0,0);return 1;
}
int p2PrepareDMATrigger(int pin) {
    if (!validPin(pin)) return 0;
    p2Pad(pin,P_SCHMITT_A,0,0);return 1;
}
static OBJ primP2LevelInput(int argc, OBJ *args) {
    int pin=p2PinArg(argc,args);uint32_t pad;
    if (argc!=3 || pin<0 || !isInt(args[1]) || !P2_NAMED(p2PadNames,args[2],&pad) ||
        (pad!=P_LEVEL_A && pad!=P_LEVEL_A_FBN && pad!=P_LEVEL_B_FBP && pad!=P_LEVEL_B_FBN)) return falseObj;
    int level=obj2int(args[1]);if (level<0 || level>255) return falseObj;
    p2Pad(pin,pad|((uint32_t)level<<8),false,false);return trueObj;
}
static OBJ primP2PadRaw(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t pad;
	if (argc != 4 || pin < 0 || !p2Hex(args[1], &pad) || pad > 0x1fff ||
		objType(args[2]) != BooleanType || objType(args[3]) != BooleanType) return falseObj;
	p2Pad(pin, pad << 8, args[2] == trueObj, args[3] == trueObj); return trueObj;
}
static OBJ primP2PadNamed(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t pad;
	if (argc != 4 || pin < 0 || !P2_NAMED(p2PadNames, args[1], &pad) ||
		objType(args[2]) != BooleanType || objType(args[3]) != BooleanType) return falseObj;
	p2Pad(pin, pad, args[2] == trueObj, args[3] == trueObj); return trueObj;
}
static OBJ primP2Configure(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t pad, operation, x, y;
	if ((argc != 7 && argc != 8 && argc != 9) || pin < 0 || !P2_NAMED(p2OperationNames, args[1], &operation) ||
		!P2_NAMED(p2PadNames, args[2], &pad) || !p2Register(args[3], &x) || !p2Register(args[4], &y) ||
		objType(args[5]) != BooleanType || !isInt(args[6])) return falseObj;
	int a = argc >= 8 ? obj2int(args[6]) : 0;
	if (argc >= 8 && !isInt(args[7])) return falseObj;
	int b = obj2int(args[argc>=8 ? 7 : 6]);
	if (a < -3 || a > 3 || b < -3 || b > 3 || !validPin(pin+a) || !validPin(pin+b)) return falseObj;
	uint32_t route = ((uint32_t)(a < 0 ? a+8 : a)<<28) | ((uint32_t)(b < 0 ? b+8 : b)<<24);
	if (argc==9) {
		if (!isInt(args[8]) || obj2int(args[8])<0 || obj2int(args[8])>3) return falseObj;
		route|=(uint32_t)(4+obj2int(args[8]))<<21;
	}
	int dac = (pad & 0x1c0000) == 0x140000;
	const char *name = obj2str(args[1]);
	if ((!strncmp(name, "DAC ", 4) && !dac) || (!strcmp(name, "repository") && dac)) return falseObj;
	p2Start(pin, route | pad | operation | (args[5] == trueObj ? P_OE : 0), x, y);
	return trueObj;
}
static OBJ primP2Sample(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	return argc == 1 && pin >= 0 && _pinr(pin) ? trueObj : falseObj;
}
static OBJ primP2PeekHex(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	return argc == 1 && pin >= 0 ? p2HexString(_rqpin(pin)) : falseObj;
}
static OBJ primP2Ack(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 1 || pin < 0 || p2CaptureOwnsPin(pin)) return falseObj;
	_akpin(pin); return trueObj;
}
static OBJ primP2Pulse(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 4 || pin < 0 || !isInt(args[1]) || !isInt(args[2]) || !isInt(args[3])) return falseObj;
	int high = obj2int(args[1]), low = obj2int(args[2]), count = obj2int(args[3]);
	uint32_t ticks = clockFrequency()/1000000;
	if (!ticks || high <= 0 || low < 0 || count < 1 || (uint32_t)high > 65535U/ticks ||
		(uint32_t)low > 65535U/ticks || (uint32_t)(high+low)*ticks > 65535U) return falseObj;
	p2Start(pin, P_PULSE | P_OE, (((uint32_t)low*ticks)<<16) | ((uint32_t)(high+low)*ticks), count);
	return trueObj;
}
static OBJ primP2Transition(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 3 || pin < 0 || !isInt(args[1]) || !isInt(args[2])) return falseObj;
	int usecs = obj2int(args[1]), count = obj2int(args[2]); uint32_t ticks = clockFrequency()/1000000;
	if (!ticks || usecs < 1 || count < 1 || (uint32_t)usecs > 65535U/ticks) return falseObj;
	p2Start(pin, P_TRANSITION | P_OE, usecs*ticks, count); return trueObj;
}
static OBJ primP2PWM(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 4 || pin < 0 || !isInt(args[1]) || !isInt(args[2]) || objType(args[3]) != BooleanType) return falseObj;
	int hz = obj2int(args[1]), duty = obj2int(args[2]), triangle = args[3] == trueObj;
	if (hz < 1 || duty < 0 || duty > 1000 || (uint32_t)hz > clockFrequency()/4) return falseObj;
	uint32_t clocks = clockFrequency()/hz/(triangle ? 2 : 1);
	uint32_t unit = (clocks+65534)/65535, frame = clocks/unit;
	if (unit > 65535 || frame < 2) return falseObj;
	p2Start(pin, (triangle ? P_PWM_TRIANGLE : P_PWM_SAWTOOTH) | P_OE,
		(frame<<16)|unit, (frame*(uint32_t)duty+500)/1000); return trueObj;
}
/* Checked conveniences keep clocks, voltage circuits and operating modes explicit. */
static OBJ primP2Duty(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 3 || pin < 0 || !isInt(args[1]) || !isInt(args[2])) return falseObj;
	int duty = obj2int(args[1]), clocks = obj2int(args[2]);
	if (duty < 0 || duty > 1000 || clocks < 1 || clocks > 65536) return falseObj;
	uint32_t fraction = _muldiv64((uint32_t)duty, 0xffffffffU, 1000U);
	p2Start(pin, P_NCO_DUTY | P_OE, clocks & 65535, fraction);
	return trueObj;
}
static OBJ primP2FeedbackPWM(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 5 || pin < 0) return falseObj;
	for (int i = 1; i < 5; i++) if (!isInt(args[i])) return falseObj;
	int hz = obj2int(args[1]), duty = obj2int(args[2]);
	int a = obj2int(args[3]), b = obj2int(args[4]);
	if (hz < 1 || (uint32_t)hz > clockFrequency()/4 || duty < 0 || duty > 1000 ||
		a < -3 || a > 3 || b < -3 || b > 3 || !validPin(pin+a) || !validPin(pin+b)) return falseObj;
	uint32_t clocks = clockFrequency()/hz, unit = (clocks+65534)/65535, frame = clocks/unit;
	if (unit > 65535 || frame < 2) return falseObj;
	uint32_t route = ((uint32_t)(a < 0 ? a+8 : a)<<28) | ((uint32_t)(b < 0 ? b+8 : b)<<24);
	p2Start(pin, P_PWM_SMPS | P_OE | route, (frame<<16)|unit, (frame*(uint32_t)duty+500)/1000);
	return trueObj;
}
static OBJ primP2DACNoise(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t pad;
	if (argc != 3 || pin < 0 || !isInt(args[1]) || !P2_NAMED(p2PadNames, args[2], &pad) ||
		(pad & 0x1c0000) != 0x140000) return falseObj;
	int clocks = obj2int(args[1]);
	if (clocks < 1 || clocks > 65536) return falseObj;
	p2Start(pin, P_DAC_NOISE | P_OE | pad, clocks & 65535, 0); return trueObj;
}
static OBJ primP2DAC16(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t pad;
	if (argc != 5 || pin < 0 || !isInt(args[1]) || !isInt(args[2]) ||
		objType(args[3]) != BooleanType || !P2_NAMED(p2PadNames, args[4], &pad) ||
		(pad & 0x1c0000) != 0x140000) return falseObj;
	int level = obj2int(args[1]), clocks = obj2int(args[2]), pwm = args[3] == trueObj;
	if (level < 0 || level > 65535 || clocks < 1 || clocks > 65536 || (pwm && (clocks & 255))) return falseObj;
	p2Start(pin, (pwm ? P_DAC_DITHER_PWM : P_DAC_DITHER_RND) | P_OE | pad, clocks & 65535, level);
	return trueObj;
}
static OBJ primP2ADCSetup(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t pad;
	if (argc != 6 || pin < 0 || !IS_TYPE(args[1], StringType) || !isInt(args[2]) ||
		objType(args[3]) != BooleanType || !P2_NAMED(p2PadNames, args[4], &pad) || !isInt(args[5])) return falseObj;
	const char *kind = obj2str(args[1]);
	int power = obj2int(args[2]), external = args[3] == trueObj, b = obj2int(args[5]), mode = 0;
	if (!strcmp(kind, "sample")) { mode = 0; if (power < 1 || power > 13) return falseObj; }
	else if (!strcmp(kind, "SINC2 accumulator")) { mode = 1; if (power < 3 || power > 13) return falseObj; }
	else if (!strcmp(kind, "SINC3 accumulator")) { mode = 2; if (power < 4 || power > 9) return falseObj; }
	else if (!strcmp(kind, "bitstream")) { mode = 3; if (power < 0 || power > 5) return falseObj; }
	else return falseObj;
	if (b < -3 || b > 3 || !validPin(pin+b) ||
		(!external && (pad & 0x1c0000) != 0x100000) ||
		(external && pad != P_SCHMITT_A && pad != P_LOGIC_A)) return falseObj;
	uint32_t route = external ? (uint32_t)(b < 0 ? b+8 : b)<<24 : 0;
	p2Start(pin, (external ? P_ADC_EXT : P_ADC) | route | pad, (mode<<4)|power, 1U<<power);
	return trueObj;
}
static OBJ primP2Scope(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t pad;
	if (argc != 5 || pin < 0 || !isInt(args[1]) || !isInt(args[2]) || !isInt(args[3]) ||
		!P2_NAMED(p2PadNames, args[4], &pad) || (pad & 0x1c0000) != 0x100000) return falseObj;
	int filter = obj2int(args[1]), a = obj2int(args[2]), b = obj2int(args[3]);
	if (filter < 0 || filter > 2 || a < 0 || a > 63 || b < 0 || b > 63) return falseObj;
	p2Start(pin, P_ADC_SCOPE | pad, (b<<10)|(a<<2)|filter, 0); return trueObj;
}
static uint32_t p2ReverseWord(uint32_t value, int bits) {
	uint32_t result=0;
	for (int i=0;i<bits;i++) { result=(result<<1)|(value&1U);value>>=1; }
	return result;
}
static void p2SerialStart(int pin, uint32_t mode, uint32_t x, int bits, int msb, int prime, uint32_t word) {
	releasePin(pin);_wrpin(pin,mode);_wxpin(pin,x);
	if (prime) _wypin(pin,msb ? p2ReverseWord(word,bits) : word);
	if (pin<32) _DIRA|=1U<<pin;else _DIRB|=1U<<(pin-32);
	pinModeState[pin]=P2_MODE_SMART;smartModeState[pin]=mode;
	serialBits[pin]=bits;serialMSB[pin]=msb;serialQueued[pin]=0;
}
static OBJ primP2AsyncWords(int argc, OBJ *args) {
	int pin=p2PinArg(argc,args);
	if (argc!=5 || pin<0 || !isInt(args[1]) || !isInt(args[2]) ||
		objType(args[3])!=BooleanType || objType(args[4])!=BooleanType) return falseObj;
	int baud=obj2int(args[1]),bits=obj2int(args[2]),tx=args[3]==trueObj,inv=args[4]==trueObj;
	if (baud<1 || bits<1 || bits>32 || (uint32_t)baud>clockFrequency()/4) return falseObj;
	uint32_t clocks=clockFrequency()/(uint32_t)baud;
	if (clocks<4 || clocks>65535) return falseObj;
	uint32_t x=(clocks<<16)|(bits-1);
	if (clocks<1024) x|=(_muldiv64(clockFrequency(),64U,(uint32_t)baud)&63U)<<10;
	uint32_t mode=tx ? P_ASYNC_TX|P_OE : P_ASYNC_RX|P_SCHMITT_A;
	if (inv) mode|=tx ? P_INVERT_OUTPUT : P_INVERT_A;
	p2SerialStart(pin,mode,x,bits,0,0,0);return trueObj;
}
static OBJ primP2SyncTransmitWords(int argc, OBJ *args) {
	int pin=p2PinArg(argc,args);uint32_t word;
	if (argc!=7 || pin<0 || !isInt(args[1]) || !p2Hex(args[2],&word) || !isInt(args[3])) return falseObj;
	for (int i=4;i<7;i++) if (objType(args[i])!=BooleanType) return falseObj;
	int bits=obj2int(args[1]),b=obj2int(args[3]),falling=args[4]==trueObj;
	int continuous=args[5]==trueObj,msb=args[6]==trueObj;
	if (bits<1 || bits>32 || b< -3 || b>3 || !validPin(pin+b) || (bits<32 && (word>>bits))) return falseObj;
	uint32_t route=(uint32_t)(b<0 ? b+8 : b)<<24;
	if (falling) route|=P_INVERT_B;
	p2SerialStart(pin,P_SYNC_TX|P_OE|route,(continuous ? 0U : 32U)|(bits-1),bits,msb,1,word);
	return trueObj;
}
static OBJ primP2SyncReceiveWords(int argc, OBJ *args) {
	int pin=p2PinArg(argc,args);
	if (argc!=6 || pin<0 || !isInt(args[1]) || !isInt(args[2])) return falseObj;
	for (int i=3;i<6;i++) if (objType(args[i])!=BooleanType) return falseObj;
	int bits=obj2int(args[1]),b=obj2int(args[2]),falling=args[3]==trueObj;
	if (bits<1 || bits>32 || b< -3 || b>3 || !validPin(pin+b)) return falseObj;
	uint32_t route=(uint32_t)(b<0 ? b+8 : b)<<24;
	if (falling) route|=P_INVERT_B;
	p2SerialStart(pin,P_SYNC_RX|P_SCHMITT_A|route,(args[4]==trueObj ? 32U : 0U)|(bits-1),bits,args[5]==trueObj,0,0);
	return trueObj;
}
static int p2AsyncBusy(int pin) {
	uint32_t busy;__asm { rqpin busy, pin wc; muxc busy, #1; }
	return busy&1U;
}
static OBJ primP2SerialSendHex(int argc, OBJ *args) {
	int pin=p2PinArg(argc,args);uint32_t word;
	if (argc!=2 || pin<0 || !serialBits[pin] || !p2Hex(args[1],&word)) return falseObj;
	uint32_t mode=smartModeState[pin]&0x3eU;
	int bits=serialBits[pin];
	if ((mode!=P_SYNC_TX && mode!=P_ASYNC_TX) || (bits<32 && (word>>bits))) return falseObj;
	if (mode==P_ASYNC_TX) { if (!_pinr(pin) && p2AsyncBusy(pin)) return falseObj; }
	else if (serialQueued[pin] && !_pinr(pin)) return falseObj;
	_wypin(pin,serialMSB[pin] ? p2ReverseWord(word,bits) : word);serialQueued[pin]=1;
	return trueObj;
}
static OBJ primP2SerialReadHex(int argc, OBJ *args) {
	int pin=p2PinArg(argc,args);
	if (argc!=1 || pin<0 || !serialBits[pin]) return falseObj;
	uint32_t mode=smartModeState[pin]&0x3eU;
	if ((mode!=P_SYNC_RX && mode!=P_ASYNC_RX) || !_pinr(pin)) return falseObj;
	int bits=serialBits[pin];uint32_t word=((uint32_t)_rdpin(pin))>>(32-bits);
	return p2HexString(serialMSB[pin] ? p2ReverseWord(word,bits) : word);
}
static OBJ primP2SerialBusy(int argc, OBJ *args) {
	int pin=p2PinArg(argc,args);
	return argc==1 && pin>=0 && serialBits[pin] && (smartModeState[pin]&0x3eU)==P_ASYNC_TX && p2AsyncBusy(pin) ? trueObj : falseObj;
}
static OBJ primP2LogicInput(int argc, OBJ *args) {
	int pin=p2PinArg(argc,args);uint32_t logic;
	static const P2NamedBits operations[]={{"pass A",P_PASS_AB},{"A AND B",P_AND_AB},{"A OR B",P_OR_AB},{"A XOR B",P_XOR_AB}};
	if (argc!=6 || pin<0 || !P2_NAMED(operations,args[1],&logic) || !isInt(args[2]) || !isInt(args[4]) ||
		objType(args[3])!=BooleanType || objType(args[5])!=BooleanType) return falseObj;
	int a=obj2int(args[2]),b=obj2int(args[4]);
	if (a< -3 || a>3 || b< -3 || b>3 || !validPin(pin+a) || !validPin(pin+b)) return falseObj;
	uint32_t route=((uint32_t)(a<0 ? a+8 : a)<<28)|((uint32_t)(b<0 ? b+8 : b)<<24);
	if (args[3]==trueObj) route|=P_INVERT_A;
	if (args[5]==trueObj) route|=P_INVERT_B;
	p2Pad(pin,P_SCHMITT_A|logic|route,0,0);return trueObj;
}
static OBJ primP2UART(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 3 || pin < 0 || !isInt(args[1]) || objType(args[2]) != BooleanType) return falseObj;
	int baud = obj2int(args[1]);
	if (baud < 1 || (uint32_t)baud > clockFrequency()/4) return falseObj;
	uint32_t period = clockFrequency()/baud;
	if (period < 4 || period > 65535) return falseObj;
	uint32_t mode = args[2] == trueObj ? P_ASYNC_TX | P_OE : P_ASYNC_RX;
	releasePin(pin); _wrpin(pin, mode); _wxpin(pin, (period<<16)|7);
	/* Do not buffer a spurious zero byte while configuring the transmitter. */
	if (pin < 32) _DIRA |= 1U<<pin; else _DIRB |= 1U<<(pin-32);
	pinModeState[pin] = P2_MODE_SMART; smartModeState[pin] = mode; serialBits[pin]=8; return trueObj;
}
static OBJ primP2UARTWrite(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 2 || pin < 0 || !isInt(args[1]) || (serialBits[pin] && serialBits[pin]!=8) || smartModeState[pin] != (P_ASYNC_TX | P_OE)) return falseObj;
	int byte = obj2int(args[1]); if (byte < 0 || byte > 255) return falseObj;
	/* First write is allowed while IN is low; subsequent writes need buffer space.
	   Conservative frame spacing avoids needing the mode-specific C flag. */
	if (!_pinr(pin)) {
		/* An idle, newly configured transmitter has no queued word. */
		uint32_t busy; __asm { rqpin busy, pin wc; muxc busy, #1; }
		if (busy & 1) return falseObj;
	}
	_wypin(pin, byte); return trueObj;
}
static OBJ primP2UARTRead(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 1 || pin < 0 || (serialBits[pin] && serialBits[pin]!=8) || smartModeState[pin] != P_ASYNC_RX || !_pinr(pin)) return int2obj(-1);
	/* The FlexC smart-pin builtin can propagate its sign bit when shifting. */
	return int2obj((_rdpin(pin)>>24) & 255);
}
static OBJ primP2DAC8(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t pad;
	if (argc != 3 || pin < 0 || !isInt(args[1]) || !P2_NAMED(p2PadNames, args[2], &pad) ||
		(pad & 0x1c0000) != 0x140000) return falseObj;
	int level = obj2int(args[1]); if (level < 0 || level > 255) return falseObj;
	uint32_t mode = pad | ((uint32_t)level<<8);
	p2Pad(pin, mode, true, false); pinModeState[pin] = P2_MODE_DAC; return trueObj;
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
	return (argc == 1 && pin >= 0 && !p2CaptureOwnsPin(pin)) ? p2HexString(_rdpin(pin)) : falseObj;
}
static OBJ primP2Read(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args);
	if (argc != 1 || pin < 0 || p2CaptureOwnsPin(pin)) return falseObj;
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
	if (argc != 2 || pin < 0 || p2CaptureOwnsPin(pin) || pinModeState[pin] != P2_MODE_SMART || !p2Hex(args[1], &value)) return falseObj;
	_wxpin(pin, value); serialBits[pin]=0; return trueObj;
}
static OBJ primP2WriteY(int argc, OBJ *args) {
	int pin = p2PinArg(argc, args); uint32_t value;
	if (argc != 2 || pin < 0 || p2CaptureOwnsPin(pin) || pinModeState[pin] != P2_MODE_SMART || !p2Hex(args[1], &value)) return falseObj;
	_wypin(pin, value); serialQueued[pin]=1; return trueObj;
}

extern OBJ p2KeypadInit(int,OBJ*),p2KeypadScan(int,OBJ*);
static PrimEntry entries[] = {
	{"p2KeypadInit",p2KeypadInit},{"p2KeypadScan",p2KeypadScan},
	{"p2FilterConfigure",primP2FilterConfigure}, {"p2FilterInfo",primP2FilterInfo}, {"p2FilterInput",primP2FilterInput},
	{"p2AsyncWords",primP2AsyncWords}, {"p2SyncTransmitWords",primP2SyncTransmitWords},
	{"p2SyncReceiveWords",primP2SyncReceiveWords}, {"p2SerialSendHex",primP2SerialSendHex},
	{"p2SerialReadHex",primP2SerialReadHex}, {"p2SerialBusy",primP2SerialBusy}, {"p2LogicInput",primP2LogicInput},
    {"p2ScaleSample", primP2ScaleSample},
    {"p2LevelInput", primP2LevelInput},
    {"p2ScopeCapture", primP2ScopeCapture},
    {"p2DMACapture", primP2DMACapture},
    {"p2DMARecord", primP2DMARecord},
    {"p2BitDensity", primP2BitDensity},
    {"p2CaptureStart", primP2CaptureStart}, {"p2CaptureStop", primP2CaptureStop},
    {"p2CaptureInfo", primP2CaptureInfo}, {"p2StreamRead", primP2StreamRead},
    {"p2CaptureRead", primP2CaptureRead},
	{"p2Duty", primP2Duty}, {"p2FeedbackPWM", primP2FeedbackPWM},
	{"p2DACNoise", primP2DACNoise}, {"p2DAC16", primP2DAC16},
	{"p2ADCSetup", primP2ADCSetup}, {"p2Scope", primP2Scope},
	{"p2ConfigureInputs", primP2Configure},
	{"p2LocalPinDIR", primP2LocalPinDIR},
	{"p2ListAtomicAdd", primP2ListAtomicAdd},
	{"p2PadRaw", primP2PadRaw},
	{"p2PadNamed", primP2PadNamed},
	{"p2Configure", primP2Configure},
	{"p2PinSample", primP2Sample},
	{"p2PinPeekHex", primP2PeekHex},
	{"p2PinAck", primP2Ack},
	{"p2Pulse", primP2Pulse},
	{"p2Transition", primP2Transition},
	{"p2PWM", primP2PWM},
	{"p2UART", primP2UART},
	{"p2UARTWrite", primP2UARTWrite},
	{"p2UARTRead", primP2UARTRead},
	{"p2DAC8", primP2DAC8},
	{"p2Board", primP2Board},
	{"p2FlashID", primP2FlashID},
	{"p2ClockHz", primP2ClockHz},
	{"p2Cog", primP2Cog},
	{"p2CogStart", primP2CogStart},
	{"p2CogStop", primP2CogStop},
	{"p2CogRunning", primP2CogRunning},
	{"p2CogError", primP2CogError},
	{"p2CogStackOK", primP2CogStackOK},
	{"p2CogStackUsed", primP2CogStackUsed},
	{"p2SharedRead", primP2SharedRead},
	{"p2SharedWrite", primP2SharedWrite},
	{"p2SharedAdd", primP2SharedAdd},
	{"p2RuntimeRevision", primP2RuntimeRevision},
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
