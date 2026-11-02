/* SPDX-License-Identifier: Apache-2.0 */
#pragma once
#include <zephyr/drivers/video.h>
/* DEVICE_DECLARE is a static forward declaration within one translation
 * unit, not an extern. Export getters so each driver has one device object. */
const struct device *p4_sensor_device(void);
const struct device *p4_csi_device(void);
int p4_sensor_ids(unsigned *imx, unsigned *ov);
unsigned p4_sensor_bits(void);
bool p4_capture_cancelled(void);
const char *p4_video_diagnostic(void);
typedef struct {unsigned exposure,analog,digital;} p4_camera_settings;
bool p4_sensor_settings(p4_camera_settings *out);
int p4_sensor_settings_set(const p4_camera_settings *settings);
void p4_sensor_settings_reset(void);
