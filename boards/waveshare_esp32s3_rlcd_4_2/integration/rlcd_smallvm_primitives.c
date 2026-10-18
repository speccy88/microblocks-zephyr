// SPDX-License-Identifier: MPL-2.0
// Linked into the SmallVM and standalone targets; excluded from diagnostics.
// Adapted from the named-primitive mechanism in speccy88/uno-q-microblocks.
// Wire this into the fully ported SmallVM and load the .ubl in the editor.
#include "vm/interp.h"
#include "rlcd_board.h"
#include "rlcd_audio.h"
#include <errno.h>
#include <string.h>

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

static OBJ display_text(int argc, OBJ *argv)
{
    if (argc != 1) return fail(notEnoughArguments);
    if (!IS_TYPE(argv[0], StringType)) return fail(needsStringError);
    return rlcd_display_text(obj2str(argv[0])) == 0 ? falseObj : fail(primitiveNotImplemented);
}

static OBJ display_clear(int argc, OBJ *argv)
{
    if (argc != 1) return fail(notEnoughArguments);
    return rlcd_display_clear(argv[0] != falseObj) == 0 ? falseObj : fail(primitiveNotImplemented);
}

static OBJ rtc_text(int argc, OBJ *argv)
{
    (void)argv;
    if (argc != 0) return fail(notEnoughArguments);
    char text[32];
    return rlcd_rtc_read(text, sizeof(text)) == 0 ? newStringFromBytes(text, strlen(text)) : newStringFromBytes("RTC unset or unavailable", 24);
}

static OBJ rtc_set_utc(int argc, OBJ *argv)
{
    if (argc != 6) return fail(notEnoughArguments);
    for (int i = 0; i < 6; ++i)
        if (!isInt(argv[i])) return fail(needsIntegerError);
    int err = rlcd_rtc_set_utc(obj2int(argv[0]), obj2int(argv[1]), obj2int(argv[2]),
        obj2int(argv[3]), obj2int(argv[4]), obj2int(argv[5]));
    if (err == -EINVAL) return fail(indexOutOfRangeError);
    return err == 0 ? falseObj : fail(primitiveNotImplemented);
}

static OBJ audio_tone(int argc, OBJ *argv)
{
    if (argc != 3) return fail(notEnoughArguments);
    for (int i = 0; i < 3; ++i)
        if (!isInt(argv[i])) return fail(needsIntegerError);
    int err = rlcd_audio_play(obj2int(argv[0]), obj2int(argv[1]), obj2int(argv[2]));
    if (err == -EINVAL) return fail(indexOutOfRangeError);
    return err == 0 ? falseObj : fail(primitiveNotImplemented);
}

static OBJ audio_busy(int argc, OBJ *argv)
{
    (void)argv;
    if (argc != 0) return fail(notEnoughArguments);
    return rlcd_audio_busy() ? trueObj : falseObj;
}

static OBJ audio_stop(int argc, OBJ *argv)
{
    (void)argv;
    if (argc != 0) return fail(notEnoughArguments);
    rlcd_audio_stop();
    return falseObj;
}

static OBJ audio_status(int argc, OBJ *argv)
{
    (void)argv;
    if (argc != 0) return fail(notEnoughArguments);
    char status[384];
    return rlcd_audio_status(status, sizeof(status)) == 0 ? newStringFromBytes(status, strlen(status)) : fail(primitiveNotImplemented);
}

static PrimEntry rlcd_entries[] = {
    {"temperatureMilliC", temperature_milli_c},
    {"humidityMilliPct", humidity_milli_pct},
    {"batteryRaw", battery_raw},
    {"buttonPressed", button_pressed},
    {"displayChecker", display_test},
    {"displayText", display_text},
    {"displayClear", display_clear},
    {"rtcText", rtc_text},
    {"rtcSetUTC", rtc_set_utc},
    {"audioTone", audio_tone},
    {"audioBusy", audio_busy},
    {"audioStop", audio_stop},
    {"audioStatus", audio_status}
};

// Existing UNO Q port implements this callback for the VM's IOPrims slot.
// Before linking, ensure no other object defines addIOPrims.
void addIOPrims(void)
{
    addPrimitiveSet(IOPrims, "rlcd", sizeof(rlcd_entries) / sizeof(rlcd_entries[0]), rlcd_entries);
}
