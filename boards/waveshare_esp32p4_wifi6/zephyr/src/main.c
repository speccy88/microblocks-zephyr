/* SPDX-License-Identifier: MPL-2.0 */
#include <zephyr/kernel.h>
#include "vm/interp.h"
#include "vm/persist.h"
int main(void) {
    hardwareInit();memInit();primsInit();restoreScripts();startAll();
    for(;;){vmSlice(32);k_sleep(K_MSEC(1));}
}
