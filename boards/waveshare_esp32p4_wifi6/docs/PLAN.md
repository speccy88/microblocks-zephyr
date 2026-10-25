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
