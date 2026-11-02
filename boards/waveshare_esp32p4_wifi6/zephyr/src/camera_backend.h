/* SPDX-License-Identifier: MIT */
#pragma once
#include "image_store.h"
int camera_request(void);
int camera_available(void);
int camera_busy(void);
int camera_result(void);
enum { CAMERA_OWNER_VM=0,CAMERA_OWNER_POSE=1,CAMERA_OWNER_TUNER=2 };
int camera_request_owned(int owner);
int camera_result_owned(int owner);
void camera_discard_owned(int owner);
uint64_t camera_ready_time_owned(int owner);
void camera_discard(void);
const char *camera_status(void);
int p4_sensor_ids(unsigned *imx,unsigned *ov);
int p4_video_capture(image_view *out);
