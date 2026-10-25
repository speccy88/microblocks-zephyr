/* SPDX-License-Identifier: MPL-2.0 */
#include <zephyr/kernel.h>
#include "vm/interp.h"
#include "vm/persist.h"
#include "media_protocol.h"
int main(void) {
    hardwareInit();memInit();primsInit();restoreScripts();startAll();
    for(;;){vmSlice(32);p4_media_poll();k_sleep(K_MSEC(1));}
}
