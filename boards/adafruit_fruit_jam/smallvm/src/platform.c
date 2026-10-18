/* SPDX-License-Identifier: MPL-2.0 */
/* Minimal Zephyr platform; unsupported hardware reports an explicit VM error.
 * Interface pattern follows the existing speccy88/uno-q-microblocks port. */
#include "vm/interp.h"
#include "fruit_jam.h"
#include "generic_io.h"
#include <stdlib.h>
#include <string.h>

int useTFT, mbDisplayColor, resetDoubleTap, wifiActive, isCodingBox, isSpringbotGold;
int BLE_allowShutdown, BLE_connected_to_IDE, bleRunning;
int fj_sht4x_read(int *milli_c, int *milli_percent);
int fj_sht4x_status(char *dst, unsigned size);
int fj_pixels_set(unsigned index, unsigned red, unsigned green, unsigned blue);
int fj_pixels_off(void);
char BLE_ThreeLetterID[4] = "---";
const char *boardType(void) { return "Fruit Jam RP2350B Zephyr (experimental)"; }
void consolePrint(const char *s) { (void)s; }
void consoleReportNum(const char *s, int n) { (void)s; (void)n; }
void processFileMessage(int t, int n, char *p) { (void)t; (void)n; (void)p; }
void stopPWM(void) { fj_io_pwm_stop(); }
void stopServos(void) {}
void stopTone(void) {}
void resetRadio(void) {}
void turnOffInternalNeoPixels(void) { fj_pixels_off(); }
void tftClear(void) {}
void tftInit(void) {}
void updateMicrobitDisplay(void) {}
void restartSerial(void) {}
void BLE_start(void) {}
void BLE_stop(void) {}
void BLE_setEnabled(int n) { (void)n; }
int BLE_isEnabled(void) { return 0; }
int displayIsActive(void) { return 0; }
void getMACAddress(uint8 *p) { memset(p, 0, 6); }
OBJ primHexToInt(int n, OBJ *a) {
    if (n < 1) return fail(notEnoughArguments);
    if (!IS_TYPE(a[0], StringType)) return fail(needsStringError);
    return int2obj(strtol(obj2str(a[0]), 0, 16));
}
OBJ primButtonA(OBJ *a) {
    (void)a; int value = fj_button(1);
    return value < 0 ? fail(primitiveNotImplemented) : value ? trueObj : falseObj;
}
OBJ primButtonB(OBJ *a) {
    (void)a; int value = fj_button(2);
    return value < 0 ? fail(primitiveNotImplemented) : value ? trueObj : falseObj;
}
#define DISABLED_A(name) OBJ name(OBJ *a) { (void)a; return fail(primitiveNotImplemented); }
#define DISABLED_N(name) OBJ name(int n, OBJ *a) { (void)n; (void)a; return fail(primitiveNotImplemented); }
#define DISABLED_V(name) void name(OBJ *a) { (void)a; fail(primitiveNotImplemented); }
DISABLED_N(primMBDisplay) DISABLED_N(primMBEnableDisplay)
DISABLED_N(primMBPlot) DISABLED_N(primMBUnplot) DISABLED_N(primMBDrawShape) DISABLED_N(primMBShapeForLetter)
DISABLED_N(primMBTiltX) DISABLED_N(primMBTiltY) DISABLED_N(primMBTiltZ) DISABLED_N(primMBTemp)
OBJ primMBDisplayOff(int n, OBJ *a) { (void)n; (void)a; return falseObj; }
void primSetUserLED(OBJ *a) { if (a && a[0] != falseObj) fail(primitiveNotImplemented); }
#define OMIT(name) void name(void) {}
OMIT(addDisplayPrims) OMIT(addFilePrims) OMIT(addMiscPrims)
OMIT(addNetPrims) OMIT(addBLEPrims) OMIT(addRadioPrims)
OMIT(addSerialPrims) OMIT(addTFTPrims) OMIT(addHIDPrims) OMIT(addOneWirePrims)
OMIT(addCameraPrims) OMIT(addEncoderPrims) OMIT(addSDCardPrims) OMIT(addElecfreaksPrims)
OMIT(addElecfreaksSensorPrims) OMIT(addSoundPrims)

static OBJ button_pressed(int argc, OBJ *args) {
    if (argc != 1) return fail(notEnoughArguments);
    if (!isInt(args[0])) return fail(needsIntegerError);
    int button = obj2int(args[0]);
    if (button < 1 || button > 3) return fail(indexOutOfRangeError);
    int value = fj_button(button - 1);
    return value < 0 ? fail(primitiveNotImplemented) : value ? trueObj : falseObj;
}
static OBJ io_info(int argc, OBJ *args) {
    (void)args;
    if (argc != 0) return fail(notEnoughArguments);
    char text[384];
    if (fj_io_info(text, sizeof(text))) return fail(primitiveNotImplemented);
    return newStringFromBytes(text, strlen(text));
}
static OBJ temperature_read(int argc, OBJ *args) {
    (void)args;
    if (argc) return fail(notEnoughArguments);
    int t, h;
    return fj_sht4x_read(&t, &h) ? fail(i2cTransferFailed) : int2obj(t);
}
static OBJ humidity_read(int argc, OBJ *args) {
    (void)args;
    if (argc) return fail(notEnoughArguments);
    int t, h;
    return fj_sht4x_read(&t, &h) ? fail(i2cTransferFailed) : int2obj(h);
}
static OBJ sht4x_info(int argc, OBJ *args) {
    (void)args;
    if (argc) return fail(notEnoughArguments);
    char text[384];
    fj_sht4x_status(text, sizeof(text));
    return newStringFromBytes(text, strlen(text));
}
static OBJ pixel_set(int argc, OBJ *args) {
    if (argc != 4) return fail(notEnoughArguments);
    for (unsigned i = 0; i < 4; ++i)
        if (!isInt(args[i])) return fail(needsIntegerError);
    int index = obj2int(args[0]);
    if (index < 1 || index > 5) return fail(indexOutOfRangeError);
    for (unsigned i = 1; i < 4; ++i)
        if (obj2int(args[i]) < 0 || obj2int(args[i]) > 255) return fail(indexOutOfRangeError);
    return fj_pixels_set(index - 1, obj2int(args[1]), obj2int(args[2]), obj2int(args[3])) ?
        fail(primitiveNotImplemented) : falseObj;
}
static OBJ pixels_off(int argc, OBJ *args) {
    (void)args;
    if (argc) return fail(notEnoughArguments);
    return fj_pixels_off() ? fail(primitiveNotImplemented) : falseObj;
}
static PrimEntry fruit_jam_entries[] = {
    {"buttonPressed", button_pressed}, {"ioCapabilities", io_info},
    {"temperatureMilliC", temperature_read}, {"humidityMilliPct", humidity_read},
    {"sht4xStatus", sht4x_info}, {"pixel", pixel_set}, {"pixelsOff", pixels_off}
};
void addIOPrims(void) {
    addPrimitiveSet(IOPrims, "fruitJam", sizeof(fruit_jam_entries) / sizeof(fruit_jam_entries[0]), fruit_jam_entries);
}
