/* SPDX-License-Identifier: MPL-2.0 */
/* Minimal Zephyr platform; unsupported hardware reports an explicit VM error.
 * Interface pattern follows the existing speccy88/uno-q-microblocks port. */
#include "vm/interp.h"



#include <stdlib.h>
#include <string.h>

int useTFT, mbDisplayColor, resetDoubleTap, wifiActive, isCodingBox, isSpringbotGold;
int BLE_allowShutdown, BLE_connected_to_IDE, bleRunning;
char BLE_ThreeLetterID[4] = "---";
const char *boardType(void) { return "Waveshare ESP32-P4 WIFI6 Zephyr"; }
void consolePrint(const char *s) { (void)s; }
void consoleReportNum(const char *s, int n) { (void)s; (void)n; }
extern void p4_image_message(int,int,char *);
void processFileMessage(int t, int n, char *p) { p4_image_message(t,n,p); }
void stopPWM(void) {  }
void stopServos(void) {}
void stopTone(void) {  }
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
OBJ primButtonA(OBJ *a) { (void)a; return fail(primitiveNotImplemented); }
OBJ primButtonB(OBJ *a) { (void)a; return fail(primitiveNotImplemented); }
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
OMIT(addSensorPrims) OMIT(addCameraPrims) OMIT(addEncoderPrims) OMIT(addSDCardPrims) OMIT(addElecfreaksPrims)
OMIT(addElecfreaksSensorPrims) OMIT(addSoundPrims)


#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/ring_buffer.h>
#include "image_store.h"
#include "camera_backend.h"
static const struct device *const serial=DEVICE_DT_GET(DT_NODELABEL(uart0));
RING_BUF_DECLARE(input,8192);
static void rx_isr(const struct device *dev,void *arg){
    (void)arg;
    uart_irq_update(dev);
    while(uart_irq_is_pending(dev)) {
        if(!uart_irq_rx_ready(dev))break;
        unsigned char data[64];int n=uart_fifo_read(dev,data,sizeof(data));
        if(n>0)ring_buf_put(&input,data,n);else break;
    }
}
void hardwareInit(void){
    initTasks();
    if(device_is_ready(serial)){uart_irq_callback_user_data_set(serial,rx_isr,NULL);uart_irq_rx_enable(serial);}
}
uint32 microsecs(void){return (uint32)k_ticks_to_us_floor64(k_uptime_ticks());}
uint32 millisecs(void){return (uint32)k_uptime_get();}
uint64 totalMicrosecs(void){return k_ticks_to_us_floor64(k_uptime_ticks());}
uint32 seconds(void){return (uint32)(k_uptime_get()/1000);}
void handleMicosecondClockWrap(void){}
void smallvmDelay(unsigned long ms){k_sleep(K_MSEC(ms));}
void lightSleep(int ms){if(ms>0)smallvmDelay(ms);}
void deepSleep(int secs){(void)secs;fail(primitiveNotImplemented);}
int recvBytes(uint8 *dst,int n){return n>0?ring_buf_get(&input,dst,n):0;}
int sendBytes(uint8 *src,int start,int end){if(start<0||end<start)return 0;for(int i=start;i<end;i++)uart_poll_out(serial,src[i]);return end-start;}
int pinCount(void){return 0;}
OBJ primDigitalPins(OBJ *a){(void)a;return zeroObj;}
OBJ primAnalogPins(OBJ *a){(void)a;return zeroObj;}
OBJ primDigitalRead(int n,OBJ *a){(void)n;(void)a;return fail(primitiveNotImplemented);}
void primDigitalSet(int pin,int state){(void)pin;(void)state;fail(primitiveNotImplemented);}
void primDigitalWrite(OBJ *a){(void)a;fail(primitiveNotImplemented);}
void turnOffPins(void){}
OBJ primI2cGet(OBJ *a){(void)a;return fail(primitiveNotImplemented);}
OBJ primI2cSet(OBJ *a){(void)a;return fail(primitiveNotImplemented);}
OBJ primSPISend(OBJ *a){(void)a;return fail(primitiveNotImplemented);}
OBJ primSPIRecv(OBJ *a){(void)a;return fail(primitiveNotImplemented);}
OBJ primAnalogRead(int n,OBJ *a){(void)n;(void)a;return fail(primitiveNotImplemented);}
void primAnalogWrite(OBJ *a){(void)a;fail(primitiveNotImplemented);}
void boardInit(void){}
void boardAddPrims(void){}
void boardPoll(void){}
void boardStopAll(void){camera_discard();image_release_all();}
void boardIDEConnectionChanged(int connected){(void)connected;}
int boardStartAtBoot(void){return true;}
