// SPDX-License-Identifier: MPL-2.0
#include <Arduino.h>
#include "vm/interp.h"
#include "vm/persist.h"
extern "C" {
#include "server.h"
}

int main(void)
{
    hardwareInit();
    memInit();
    primsInit();
    printk("MicroBlocks program load: %d\n", mb_store_load());
    restoreScripts();
    startAll();
    int err = mb_network_start();
    printk("MicroBlocks network initialization: %d\n", err);
    if (err == 0) printk("MicroBlocks HTTP initialization: %d\n", mb_server_start());
    for (;;) {
        mb_transport_poll();
        vmSlice(16);
        mb_store_poll();
        delay(1);
    }
}
