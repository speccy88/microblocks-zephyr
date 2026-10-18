// SPDX-License-Identifier: MPL-2.0
#include <Arduino.h>
#include "vm/interp.h"
#include "vm/persist.h"
#include "fruit_jam.h"

volatile int fruit_jam_status;

int main(void)
{
    hardwareInit();
    memInit();
    primsInit();
    fruit_jam_status = mb_store_load();
    restoreScripts();
    startAll();
    int err = fj_transport_init();
    if (err) { fruit_jam_status = err; return err; }
    for (;;) {
        fj_transport_poll();
        vmSlice(16);
        mb_store_poll();
        k_sleep(K_MSEC(1));
    }
}
