/* SPDX-License-Identifier: MIT */
#pragma once
#include "image_store.h"
int camera_request(void);
int camera_available(void);
int camera_busy(void);
int camera_result(void);
void camera_discard(void);
const char *camera_status(void);
int p4_sensor_ids(unsigned *imx,unsigned *ov);
int p4_video_capture(image_view *out);
