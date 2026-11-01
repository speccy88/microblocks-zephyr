/* SPDX-License-Identifier: MPL-2.0 */
/* Honest headless capabilities. Hardware is unsupported, never simulated. */
#include "vm/interp.h"
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

int useTFT,mbDisplayColor,resetDoubleTap,wifiActive,isCodingBox,isSpringbotGold;
int BLE_allowShutdown,BLE_connected_to_IDE,bleRunning;
char BLE_ThreeLetterID[4]="---";
const char *boardType(void){return "Linux ARM64";}
void consolePrint(const char *s){(void)s;}
void consoleReportNum(const char *s,int n){(void)s;(void)n;}
void processFileMessage(int t,int n,char *p){(void)t;(void)n;(void)p;}
int pinCount(void){return 0;}
int hasI2CPullups(void){return 0;}
OBJ primDigitalPins(OBJ *a){(void)a;return zeroObj;}
OBJ primAnalogPins(OBJ *a){(void)a;return zeroObj;}
#define UNSUPPORTED_N(name) OBJ name(int n,OBJ *a){(void)n;(void)a;return fail(primitiveNotImplemented);}
#define UNSUPPORTED_A(name) OBJ name(OBJ *a){(void)a;return fail(primitiveNotImplemented);}
#define UNSUPPORTED_V(name) void name(OBJ *a){(void)a;fail(primitiveNotImplemented);}
UNSUPPORTED_N(primAnalogRead) UNSUPPORTED_N(primDigitalRead)
UNSUPPORTED_V(primAnalogWrite) UNSUPPORTED_V(primDigitalWrite)
UNSUPPORTED_A(primButtonA) UNSUPPORTED_A(primButtonB)
UNSUPPORTED_A(primI2cGet) UNSUPPORTED_A(primI2cSet) UNSUPPORTED_A(primSPISend) UNSUPPORTED_A(primSPIRecv)
UNSUPPORTED_N(primMBDisplay) UNSUPPORTED_N(primMBDisplayOff) UNSUPPORTED_N(primMBEnableDisplay)
UNSUPPORTED_N(primMBPlot) UNSUPPORTED_N(primMBUnplot) UNSUPPORTED_N(primMBDrawShape) UNSUPPORTED_N(primMBShapeForLetter)
UNSUPPORTED_N(primMBTiltX) UNSUPPORTED_N(primMBTiltY) UNSUPPORTED_N(primMBTiltZ) UNSUPPORTED_N(primMBTemp)
void primDigitalSet(int pin,int state){(void)pin;(void)state;fail(primitiveNotImplemented);}
void primSetUserLED(OBJ *a){if(a&&a[0]!=falseObj)fail(primitiveNotImplemented);}
OBJ primHexToInt(int n,OBJ *a){
 if(n<1)return fail(notEnoughArguments);
 if(!IS_TYPE(a[0],StringType))return fail(needsStringError);
 errno=0;char *end;long value=strtol(obj2str(a[0]),&end,16);
 if(errno||end==obj2str(a[0])||*end||value<-(1L<<30)||value>((1L<<30)-1))return fail(indexOutOfRangeError);
 return int2obj(value);
}
#define OMIT(name) void name(void){}
OMIT(turnOffPins) OMIT(stopPWM) OMIT(stopServos) OMIT(stopTone) OMIT(resetRadio)
OMIT(turnOffInternalNeoPixels) OMIT(tftClear) OMIT(tftInit) OMIT(updateMicrobitDisplay)
OMIT(BLE_start) OMIT(BLE_stop) OMIT(BLE_initThreeLetterID) OMIT(BLE_pauseAdvertising) OMIT(BLE_resumeAdvertising)
/* IDE preference messages arrive outside a VM task. This headless port keeps
 * BLE disabled; setting a task error here would poison the next real script. */
void BLE_setEnabled(int n){(void)n;}
int BLE_isEnabled(void){return 0;}
int displayIsActive(void){return 0;}
void getMACAddress(uint8 *p){memset(p,0,6);}
OMIT(addIOPrims) OMIT(addDisplayPrims) OMIT(addFilePrims) OMIT(addMiscPrims)
OMIT(addNetPrims) OMIT(addBLEPrims) OMIT(addRadioPrims) OMIT(addSensorPrims)
OMIT(addSerialPrims) OMIT(addTFTPrims) OMIT(addHIDPrims) OMIT(addOneWirePrims)
OMIT(addCameraPrims) OMIT(addEncoderPrims) OMIT(addSDCardPrims) OMIT(addElecfreaksPrims)
OMIT(addElecfreaksSensorPrims) OMIT(addSoundPrims)
