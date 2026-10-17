// SPDX-License-Identifier: MPL-2.0
#include <Arduino.h>
#include "vm/interp.h"
#include "vm/persist.h"

int main(void)
{
    hardwareInit();
    memInit();
    primsInit();
    restoreScripts();
    startAll();
    for (;;) {
        vmSlice(16);
        delay(1);
    }
}
