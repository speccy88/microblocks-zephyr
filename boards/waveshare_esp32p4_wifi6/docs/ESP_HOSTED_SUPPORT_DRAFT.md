# Ready-to-post ESP-Hosted support question

Submission attempted once through the authenticated GitHub connector on 2026-10-26. GitHub returned HTTP 403, `Resource not accessible by integration`; no issue was created. No new access grants were requested. This is a draft, not a sent message.

Title: Native Zephyr ESP32-P4/C6 SDIO: WifiSetConfig (284) has no reply after STA start

### Question

I am bringing up an ESP32-P4 host using native Zephyr and the factory ESP32-C6 companion on a Waveshare ESP32-P4-WIFI6. I need guidance on the minimum compatible station configuration and on identifying the installed companion protocol/version without replacing its firmware.

### Host and transport

- ESP32-P4 silicon revision 1.3; ESP32-C6 connected by SDIO.
- Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`; hal_espressif `b16851b3c20e6fad3d2da42ec24a3e82d0b8b444`; Zephyr SDK 1.0.1.
- SDIO 4-bit, 20 MHz: D0-D3 GPIO14-17, CLK18, CMD19; C6 reset GPIO54.
- Station only, 2.4 GHz WPA2-PSK. Coprocessor Wi-Fi NVS and disconnected-station power management are disabled in WifiInit. No AP, radio streaming, camera capture or microphone recording is active during the test.
- The companion firmware is unchanged and its version is unknown. The boot private event contains tags 0x11-0x14 but no version tag 0x17. Firmware-version RPC 350 receives no reply. I cannot honestly claim a test against the latest companion release.

### Reproduction and sanitized observations

After core initialization, the stock Zephyr pre-init interface-MAC request was not compatible with this companion. An opt-in host adaptation initializes Wi-Fi first, then uses legacy GetMACAddress 257. This succeeds.

An explicit station connection then produces:

1. WifiInit succeeds, with valid initialization magic.
2. Legacy GetMACAddress (257) succeeds.
3. SetWifiMode (260), station mode, succeeds (response 516).
4. WifiStart (280) succeeds (response 536), followed by station-start event 773.
5. WifiSetConfig (284), with `iface=STA` and the station configuration variant, receives no response 540 and times out.
6. Subsequent SDIO operations report Zephyr `-ETIMEDOUT` (-116). The P4 USB application remains responsive in the baseline build. No association/DHCP address is obtained.

This happens with the same explicit start/config sequence and with independently verified host-side credential storage. No credentials, addresses, payloads or raw logs are included here.

Public host adaptation and reproduction context:
https://github.com/speccy88/microblocks-zephyr/tree/9d34a516312ef850cf4aa4031a80a2ecdbbbb58a/boards/waveshare_esp32p4_wifi6

I compared the release/v2.x host serializer and current v2 protobuf schema. Request numbers and nested station tags match. The official host includes threshold/PMF submessages and a fixed empty SAE-H2E identifier, whereas Zephyr omits these for WPA2; current companion handlers appear to guard absent pointers. A local experiment adding those fields has not passed host boot acceptance, so I am not presenting it as a protocol result.

I checked existing reports including #219 (DMA alignment) and #244 (connect-time crash after configuration); neither matches the observed no-reply at request 284. Following the SDIO bring-up guidance, a separate test reduced the configured host maximum to 5 MHz with the original serializer. It built, passed flash/model/layout checks, booted with responsive USB, and produced the same request-284/no-response-540 and subsequent -116 result. The physical clock was not instrumented. No other radio/security setting changed.

### Questions

- Are threshold/PMF/SAE identifier fields or other station defaults mandatory on any supported older companion revisions despite the current null guards?
- Is setting station configuration after WifiStart supported across those revisions, or is configuration-before-start required for some protocol/firmware combinations?
- What non-destructive query or boot metadata reliably identifies this factory companion's protocol/version when RPC 350 is unanswered?
- Which minimal host/companion version pairing and safe SDIO diagnostic would you recommend for native Zephyr before considering a companion update?

Happy to provide additional bounded, sanitized metadata. Please do not require credentials or full raw logs.
