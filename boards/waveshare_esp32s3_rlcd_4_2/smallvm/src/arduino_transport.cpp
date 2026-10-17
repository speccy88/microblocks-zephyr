// SPDX-License-Identifier: MPL-2.0
#include <Arduino.h>
#include <Wire.h>
#include "vm/interp.h"
#if defined(SMALLVM_WEBSOCKET)
extern "C" int mb_transport_recv(unsigned char *, int);
extern "C" int mb_transport_send(unsigned char *, int, int);
#endif

extern "C" void hardwareInit(void)
{
    initTasks();
#if !defined(SMALLVM_WEBSOCKET)
    Serial.begin(115200);
#endif
    Wire.begin();
}

extern "C" uint32 microsecs(void) { return micros(); }
extern "C" uint32 millisecs(void) { return millis(); }
extern "C" uint64 totalMicrosecs(void) { return k_ticks_to_us_floor64(k_uptime_ticks()); }
extern "C" uint32 seconds(void) { return millis() / 1000; }
extern "C" void handleMicosecondClockWrap(void) {}
extern "C" void smallvmDelay(unsigned long ms) { delay(ms); }
extern "C" void lightSleep(int ms) { if (ms > 0) delay(ms); }
extern "C" void deepSleep(int seconds) { (void)seconds; fail(primitiveNotImplemented); }

extern "C" int recvBytes(uint8 *dst, int count)
{
#if defined(SMALLVM_WEBSOCKET)
    return mb_transport_recv(dst, count);
#else
    int received = 0;
    while (received < count && Serial.available() > 0) {
        dst[received++] = Serial.read();
    }
    return received;
#endif
}

extern "C" int sendBytes(uint8 *data, int start, int end)
{
    if (start < 0 || end < start) return 0;
#if defined(SMALLVM_WEBSOCKET)
    return mb_transport_send(data, start, end);
#else
    return Serial.write(data + start, end - start);
#endif
}

extern "C" int pinCount(void) { return 3; }
extern "C" OBJ primDigitalPins(OBJ *) { return int2obj(3); }
extern "C" OBJ primAnalogPins(OBJ *) { return int2obj(0); }
extern "C" OBJ primDigitalRead(int count, OBJ *args)
{
    if (count < 1) return fail(notEnoughArguments);
    if (!isInt(args[0])) return fail(needsIntegerError);
    int pin = obj2int(args[0]);
    if (pin < 0 || pin >= 3) return fail(indexOutOfRangeError);
    pinMode(pin, INPUT);
    return digitalRead(pin) ? trueObj : falseObj;
}
extern "C" void primDigitalSet(int pin, int state)
{
    if (pin < 0 || pin >= 3) { fail(indexOutOfRangeError); return; }
    pinMode(pin, OUTPUT);
    digitalWrite(pin, state ? HIGH : LOW);
}
extern "C" void primDigitalWrite(OBJ *args)
{
    if (!isInt(args[0])) { fail(needsIntegerError); return; }
    primDigitalSet(obj2int(args[0]), args[1] != falseObj);
}
extern "C" void turnOffPins(void)
{
    for (int pin = 0; pin < 3; ++pin) pinMode(pin, INPUT);
}
