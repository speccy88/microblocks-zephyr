/* SPDX-License-Identifier: MPL-2.0 */
/* Minimal Zephyr platform; unsupported hardware reports an explicit VM error.
 * Interface pattern follows the existing speccy88/uno-q-microblocks port. */
#include "vm/interp.h"
#include "rlcd_board.h"
#include <stdlib.h>
#include <string.h>

int useTFT, mbDisplayColor, resetDoubleTap, wifiActive, isCodingBox, isSpringbotGold;
int BLE_allowShutdown, BLE_connected_to_IDE, bleRunning;
char BLE_ThreeLetterID[4] = "---";
const char *boardType(void) { return "Waveshare RLCD 4.2 Zephyr"; }
void consolePrint(const char *s) { (void)s; }
void consoleReportNum(const char *s, int n) { (void)s; (void)n; }
void processFileMessage(int t, int n, char *p) { (void)t; (void)n; (void)p; }
void stopPWM(void) {}
void stopServos(void) {}
void stopTone(void) {}
void resetRadio(void) {}
void turnOffInternalNeoPixels(void) {}
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
OBJ primButtonA(OBJ *a) { (void)a; return rlcd_button_pressed(0) ? trueObj : falseObj; }
OBJ primButtonB(OBJ *a) { (void)a; return rlcd_button_pressed(1) ? trueObj : falseObj; }
#define DISABLED_A(name) OBJ name(OBJ *a) { (void)a; return fail(primitiveNotImplemented); }
#define DISABLED_N(name) OBJ name(int n, OBJ *a) { (void)n; (void)a; return fail(primitiveNotImplemented); }
#define DISABLED_V(name) void name(OBJ *a) { (void)a; fail(primitiveNotImplemented); }
DISABLED_A(primI2cGet) DISABLED_A(primI2cSet) DISABLED_A(primSPISend) DISABLED_A(primSPIRecv)
DISABLED_N(primAnalogRead)
DISABLED_N(primMBDisplay) DISABLED_N(primMBEnableDisplay)
DISABLED_N(primMBPlot) DISABLED_N(primMBUnplot) DISABLED_N(primMBDrawShape) DISABLED_N(primMBShapeForLetter)
DISABLED_N(primMBTiltX) DISABLED_N(primMBTiltY) DISABLED_N(primMBTiltZ) DISABLED_N(primMBTemp)
DISABLED_V(primAnalogWrite)
OBJ primMBDisplayOff(int n, OBJ *a) { (void)n; (void)a; return falseObj; }
void primSetUserLED(OBJ *a) { if (a && a[0] != falseObj) fail(primitiveNotImplemented); }
#define OMIT(name) void name(void) {}
OMIT(addDisplayPrims) OMIT(addFilePrims) OMIT(addMiscPrims)
OMIT(addNetPrims) OMIT(addBLEPrims) OMIT(addRadioPrims) OMIT(addSensorPrims)
OMIT(addSerialPrims) OMIT(addTFTPrims) OMIT(addHIDPrims) OMIT(addOneWirePrims)
OMIT(addCameraPrims) OMIT(addEncoderPrims) OMIT(addSDCardPrims) OMIT(addElecfreaksPrims)
OMIT(addElecfreaksSensorPrims) OMIT(addSoundPrims)
