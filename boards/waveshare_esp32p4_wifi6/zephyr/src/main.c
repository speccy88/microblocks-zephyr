/* SPDX-License-Identifier: MPL-2.0 */
#include <zephyr/kernel.h>
#include "vm/interp.h"
#include "vm/persist.h"
#include "media_protocol.h"
#include "neural_backend.h"
#include "kws_primitives.h"
#include "primitives.h"
#include "storage_primitives.h"
#include "storage_protocol.h"
#include "eyes_backend.h"
#include "pose_camera.h"
#include "camera_tuning.h"
#include "serial_speed.h"
#if defined(CONFIG_P4_HOSTED)
#include "hosted_server.h"
#endif
int main(void) {
    hardwareInit();memInit();primsInit();restoreScripts();startAll();
    for(;;){
#if defined(CONFIG_P4_HOSTED)
        p4_transport_poll();
#endif
        vmSlice(32);p4_serial_speed_poll();p4_media_poll();p4_nn_poll();p4_kws_poll();mb_automation_poll();mb_storage_poll();
        mb_storage_protocol_poll(k_uptime_get(),ideConnected());p4_pose_camera_poll();p4_camera_tuning_poll();p4_eyes_poll();k_sleep(K_MSEC(1));}
}
