# Waveshare UTC clock

The board library now provides **RLCD set clock UTC year/month/day/hour/minute/
second**, alongside **RLCD clock (text)**. Supply six integers. Supported dates
are 2000-01-01 through 2099-12-31, with ordinary Gregorian leap years and hours
0..23, minutes/seconds 0..59. Leap seconds are not accepted. The RTC stores UTC
by this API's convention; no time-zone or automatic network synchronization is
stored on the chip.

The setter validates all fields before touching I2C. Invalid calendar/range
values raise VM error 18, noninteger arguments error 13 and the wrong argument
count error 28. A driver/device failure raises primitive-not-implemented error 27.
Valid writes use the existing Zephyr PCF85063A driver at address 0x51.

The physical test passed a year 2000 leap-day write/readback, fifteen invalid
inputs without a clock jump, the 2024-02-29 to March 1 rollover, year 2099 readback,
current host-UTC comparison, ticking and retention across a powered COM4 reset.
The test leaves the board clock at current UTC and preserves the original VM
program. It does not validate RTC battery retention, power removal or long-term
oscillator accuracy. Physical LCD appearance and button presses remain pending.

Reproduce the board test only when authorized to set its clock:

```sh
python3 tools/test_rtc.py --host <board-ip> \
  --private /outside-repo/private/device-private.json \
  --evidence evidence/rtc-physical.json --reboot-port <recovery-port>
```

The complete C calendar helper is also cross-checked against Python datetime
over 36,525 valid dates plus invalid boundaries (36,978 cases total):

```sh
python3 tools/test_calendar.py
# With an existing WASI SDK/runtime instead of a native C compiler:
python3 tools/test_calendar.py --compiler /path/to/wasi-sdk/bin/clang --wasi
```

Calendar tests exercise the exact C helper; they make no physical RTC claim.
The actual readings are in `evidence/2026-10-18/rtc-physical.json`.
