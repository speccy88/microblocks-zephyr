/* SPDX-License-Identifier: MPL-2.0 */
#include <zephyr/kernel.h>
#include "vm/interp.h"
#include "vm/persist.h"
#include "media_protocol.h"
#if defined(CONFIG_P4_HOSTED)
#include "hosted_server.h"
#endif
int main(void) {
    hardwareInit();memInit();primsInit();restoreScripts();startAll();
    for(;;){
#if defined(CONFIG_P4_HOSTED)
        p4_transport_poll();
#endif
        vmSlice(32);p4_media_poll();k_sleep(K_MSEC(1));}
}
