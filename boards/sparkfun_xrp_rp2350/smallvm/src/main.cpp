// SPDX-License-Identifier: MPL-2.0
#include <Arduino.h>
#include "vm/interp.h"
#include "vm/persist.h"
#include "xrp.h"
#include "provisioning.h"
volatile int xrp_status;
int main(void)
{
    hardwareInit();memInit();primsInit();
    xrp_status=mb_store_load();restoreScripts();startAll();
    int e=xrp_transport_init();if(e){xrp_status=e;return e;}
    xrp_provision_start();
    for(;;){xrp_transport_poll();vmSlice(16);mb_store_poll();k_sleep(K_MSEC(1));}
}
