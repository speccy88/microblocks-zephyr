/* SPDX-License-Identifier: MPL-2.0 */
#ifndef P2_CAPTURE_H
#define P2_CAPTURE_H
int p2CaptureOwnsPin(int pin);
void p2CaptureReleasePin(int pin);
int p2PrepareCapturePin(int pin, int order, int period, int external, int b, uint32_t pad);
int p2CapturePadBits(OBJ value, int external, uint32_t *pad);
int p2PrepareDMAInput(int pin, OBJ circuit);
int p2PrepareDMATrigger(int pin);
int p2ScopeCaptureReady(int base, unsigned mask);
OBJ primP2ScopeCapture(int argc, OBJ *args);
OBJ primP2ScaleSample(int argc, OBJ *args);
OBJ primP2CaptureStart(int argc, OBJ *args);
OBJ primP2CaptureStop(int argc, OBJ *args);
OBJ primP2CaptureInfo(int argc, OBJ *args);
OBJ primP2StreamRead(int argc, OBJ *args);
OBJ primP2CaptureRead(int argc, OBJ *args);
OBJ primP2DMACapture(int argc, OBJ *args);
OBJ primP2DMARecord(int argc, OBJ *args);
OBJ primP2BitDensity(int argc, OBJ *args);
#endif
