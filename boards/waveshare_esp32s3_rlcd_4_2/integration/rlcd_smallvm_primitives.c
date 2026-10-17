// SPDX-License-Identifier: MPL-2.0
// PORTING SOURCE ONLY: not compiled into bringup/CMakeLists.txt.
// Adapted from the named-primitive mechanism in speccy88/uno-q-microblocks.
// Wire this into the fully ported SmallVM and load the .ubl in the editor.
#include "vm/interp.h"
#include "rlcd_board.h"

static OBJ temperature_milli_c(int argc, OBJ *argv)
{
    (void)argv;
    if (argc != 0) { return fail(notEnoughArguments); }
    struct rlcd_environment env;
    if (rlcd_environment_read(&env) != 0) { return fail(primitiveNotImplemented); }
    return int2obj(env.temp_milli_c);
}

static OBJ humidity_milli_pct(int argc, OBJ *argv)
{
    (void)argv;
    if (argc != 0) { return fail(notEnoughArguments); }
    struct rlcd_environment env;
    if (rlcd_environment_read(&env) != 0) { return fail(primitiveNotImplemented); }
    return int2obj(env.humidity_milli_pct);
}

static OBJ battery_raw(int argc, OBJ *argv)
{
    (void)argv;
    if (argc != 0) { return fail(notEnoughArguments); }
    int32_t raw;
    if (rlcd_battery_read(&raw, NULL) != 0) { return fail(primitiveNotImplemented); }
    return int2obj(raw);
}

static OBJ button_pressed(int argc, OBJ *argv)
{
    if (argc != 1) { return fail(notEnoughArguments); }
    if (!isInt(argv[0])) { return fail(needsIntegerError); }
    int n = obj2int(argv[0]);
    if (n != 0 && n != 1) { return fail(indexOutOfRangeError); }
    return rlcd_button_pressed((unsigned)n) ? trueObj : falseObj;
}

static OBJ display_test(int argc, OBJ *argv)
{
    (void)argv;
    if (argc != 0) { return fail(notEnoughArguments); }
    return rlcd_display_checkerboard() == 0 ? falseObj : fail(primitiveNotImplemented);
}

static PrimEntry rlcd_entries[] = {
    {"temperatureMilliC", temperature_milli_c},
    {"humidityMilliPct", humidity_milli_pct},
    {"batteryRaw", battery_raw},
    {"buttonPressed", button_pressed},
    {"displayChecker", display_test}
};

// Existing UNO Q port implements this callback for the VM's IOPrims slot.
// Before linking, ensure no other object defines addIOPrims.
void addIOPrims(void)
{
    addPrimitiveSet(IOPrims, "rlcd", sizeof(rlcd_entries) / sizeof(rlcd_entries[0]), rlcd_entries);
}
