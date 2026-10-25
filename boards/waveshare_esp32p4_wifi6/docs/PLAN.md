# Native implementation plan

1. Preserve IDF proof locally; retain portable layers on main.
2. Build native exact-board SmallVM/UART/PSRAM target and verify COM5.
3. Bind IMX219 and OV5647 control to Zephyr video sensor interfaces.
4. Implement P4 CSI/ISP video endpoint with native DMA/interrupt/cache control.
5. Run real scene, buffer, GC, error and browser pipeline acceptance.
6. Establish C6 protocol/version, then separately approve and test networking.
7. Validate ArduinoCore-Zephyr variant/build compatibility explicitly before
   claiming it; preserve unsupported errors where no native backend exists.
8. Publish only source and evidence that accurately meet the chosen target.

9. Native bounded PCM then Whistle: reuse the prior pinned C99 engine,
   flash-resident model, independent native input and bounded PSRAM arena;
   measure actual call-stack high water, cancellation, pressure/recovery and
   real GP block execution. Publish this as experimental recognition with
   observed accuracy/latency, not a generic inference runtime.
10. Add per-block copied image/audio results with bounded native/browser
    lifetimes, explicit collapse/expand and click-only playback. Implement
    actual GP layout/compiler mapping and test both transport profiles.
11. Diagnose C6 frame/version protocol without radio changes; the exact
    MicroBlocks-P4 WPA2 AP is approved. Preserve USB and implement actual
    onboard assets/HTTP/WebSocket. Companion firmware replacement still
    needs separate authority if the protocol diagnosis establishes a need.
12. Add independent local keyword spotting and event hats, listener off by
    default, then measured compatible P4 NN/DSP/PPA acceleration and staged
    codec interfaces. Do not infer unsupported operators or board support.
