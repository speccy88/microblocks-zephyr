# Generic MicroBlocks I/O on Waveshare

## Specification before implementation

Keep existing logical pins D0=GPIO1, D1=GPIO2, D2=GPIO17. Do not expose other
SoC pin numbers. These pins appear on the official 2x8 header and do not share
the display, audio, flash/PSRAM, USB or recovery UART. GPIO3 is a strapping pin
and stays excluded. The battery is ADC1 channel 3, which maps to GPIO4 on S3;
the previous text calling it GPIO3 confused ADC channel and GPIO numbering.
The existing battery driver/channel remains unchanged.

| Operation | Mapping and contract |
|---|---|
| I2C register read/write | Existing shared I2C0, SDA13/SCL14, 100 kHz; 7-bit address 0..127, register/value 0..255. Read uses one atomic write/read with repeated start. Driver errors become VM error 35. |
| SPI send/receive | Separate SPI3, clock GPIO1/D0, MOSI GPIO2/D1, MISO GPIO17/D2. Default 1 MHz, mode 0, MSB first. Send integer byte or up to 256 bytes; receive clocks a zero byte. No automatic CS: external circuitry must hold/select the peripheral. SPI2 remains exclusively LCD-owned. |
| Analog input | A0/D0=GPIO1/ADC1 channel0, A1/D1=GPIO2/ADC1 channel1. Real ArduinoCore-Zephyr `analogRead`, scaled to MicroBlocks 0..1023. Optional input/pull-up/pull-down mode follows the VM contract. No calibrated-voltage claim. |
| Analog output | D2/GPIO17 only: Zephyr LEDC PWM at 1 kHz, duty 0..1023, clamped like upstream. This is a 3.3 V digital pulse train, not a true DAC/DC voltage. ESP32-S3 has no general-purpose DAC output; ES8311 remains speaker-only. |

SPI and PWM devices are initialized lazily, so boot and validation do not drive
the extension pins. SPI/PWM share D2: starting SPI stops PWM, applies SPI pins
for that transfer, then releases all three pins as inputs. GPIO/analog actions
restore their requested modes. PWM setup touches only GPIO17. Global Stop
stops PWM and returns extension pins to inputs. No new sound is emitted.

The six native VM opcode contracts must check argument counts before accessing
the VM stack. Keep upstream integer/type and I2C range errors. Invalid pin use
reports error 57. A zero-length SPI byte array is a no-op without device/pin
initialization. The named `sensors.spiSetup(hz, mode=0, channel=0, order="MSB")`
accepts 10 kHz..8 MHz, modes 0..3, channel 0 and `MSB`/`LSB`. It only records
configuration; the next nonempty transfer applies it. `sensors.spiExchange`
exchanges a byte array in place (maximum 256 bytes). Other named sensor helpers,
including I2C bulk transactions, remain unsupported. The native I2C register
blocks use the shared driver directly; generic register writes can alter onboard
peripherals and should target only deliberate user wiring/registers.

## Acceptance and limits

Use meaningful software/mocked checks for writes, SPI transfer and PWM because
there is no confirmed external test wiring. On COM4, only perform safe onboard
register reads (ES8311 immutable chip IDs), read-only RTC/sensor/battery checks,
argument rejection, capabilities and empty-transfer no-op checks. Do not test
generic register writes against the onboard codecs/RTC or transmit on external
SPI/PWM pins just to obtain a PASS.

Record the pinned build and app-only COM4 flash hash; preserve Wi-Fi, direct
no-code access, RTC/audio and all original program CRCs. Run one bounded
50-result transport/IDE/reconnect/persistence regression. Physical external
ADC accuracy, PWM waveform/duty, external SPI loopback/peripherals and external
I2C writes remain unverified until the owner supplies a deliberate test setup.

Reproduce the real-interpreter and backend simulations (WASI SDK plus Python
`wasmtime` required):

```sh
python tools/test_vm_runtime.py --source /path/to/verified-smallvm-v417 \
  --wasi-sdk /path/to/wasi-sdk --evidence /tmp/generic-io-simulation.json
```

The runner compiles the actual adapter with the real 32-bit interpreter and the
actual C++ backend with driver doubles. It checks argument errors, byte-array
bounds, no-op/deferred initialization, SPI configuration cache refresh, error
cleanup, ADC mapping and PWM duty/Stop. These tests do not measure physical pins.

Sources: the verified v417 `sensorPrims.cpp`/`ioPrims.cpp` contracts, pinned
ArduinoCore-Zephyr, and [official Waveshare resources/schematic](https://docs.waveshare.com/ESP32-S3-RLCD-4.2/Resources-And-Documents).
