# Matrice cartes × fonctionnalités

Index audité au 2026-11-04. Famille d’exécution, architecture CPU et capacités sont trois axes distincts.
Les manifestes matériels par cible restent canoniques. Ce tableau résume leurs preuves et les limites du dépôt ; il ne configure aucun matériel.
Un bloc commun peut utiliser différents backends. Une dépendance installée, un même CPU ou une API amont ne valent pas prise en charge validée.

« Testé matériel » désigne la cible et le périmètre cités ; « Testé / limites » conserve un résultat partiel ou une restriction.
« Logiciel testé » ne valide aucun capteur. Les tests hôte CI et les simulations sont distincts des essais sur la carte.
« Indisponible » signifie absent/non fourni dans ce port, sans conclure à une impossibilité matérielle. « Non évalué » n’est jamais « disponible ».

| Cible | Famille | CPU | NN | Voix / Whistle | Capteurs | OLED I²C | MQTT | SQLite | Capture caméra | Traitement image |
|---|---|---|---|---|---|---|---|---|---|---|
| Propeller 2 / Edge32 | bare_metal | propeller2_32 | Non évalué | Non évalué | Impl. / non testé | Non évalué | Non évalué | Indisponible | Non évalué | Non évalué |
| Waveshare ESP32-S3 RLCD | zephyr | xtensa_32 | Non évalué | Non évalué | Testé matériel | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué |
| Waveshare ESP32-P4 WIFI6 | zephyr | riscv_32 | Testé matériel | Testé / limites | Testé / limites | Testé / limites | Non évalué | Non évalué | Testé / limites | Testé / limites |
| Adafruit Fruit Jam RP2350B | zephyr | arm_32 | Non évalué | Non évalué | Impl. / non testé | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué |
| SparkFun XRP RP2350B production | zephyr | arm_32 | Non évalué | Non évalué | Testé / limites | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué |
| UNO Q — MCU | zephyr | arm_32 | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué |
| UNO Q — MPU | linux | arm_64 | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué |
| Raspberry Pi 5 | linux | arm_64 | Testé / limites | Prévu | Logiciel testé | Prévu | Impl. / simulé | Testé matériel | Indisponible | Prévu |
| MicroDuck RK3566 | linux | arm_64 | Partiel | Non évalué | Impl. / simulé | Prévu | Impl. / simulé | Testé hôte CI | Partiel / simulé | Prévu |
| Linux x86-64 — hôte CI | linux | x86_64 | Testé hôte CI | Non évalué | Non évalué | Non évalué | Impl. / simulé | Testé hôte CI | Non évalué | Non évalué |
| Linux ARM32 — cible souhaitée | linux | arm_32 | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué | Non évalué |

## Prérequis et contrat commun

Les identifiants ci-dessous sont des catégories de catalogue, pas la promesse de primitives/blocs déjà implémentés sur toutes les cartes.

- **Réseaux de neurones** (`neural`) : Modèle, opérateurs, formes/dtypes, mémoire et backend compatibles; aucune action moteur implicite.
- **Reconnaissance vocale / Whistle** (`speech`) : Backend STT, modèle/langue, frontend PCM et microphone validés; Whistle et wake-word restent distincts.
- **Capteurs** (`sensors`) : Pilote, modèle, bus/interface, adresse, unités, permissions et câblage validés par matériel.
- **OLED I²C** (`oled_i2c`) : Contrôleur et dimensions exacts, pilote graphique, bus/adresse et broches validés; un bus I²C ne prouve pas un écran.
- **MQTT** (`mqtt`) : Backend client, réseau, broker, protocole/QoS et éventuels TLS/identifiants configurés; broker réel à tester.
- **SQLite** (`sqlite`) : Backend SQL, stockage et transactions; bibliothèque Python sqlite3 pour le backend Linux actuel.
- **Caméras / capture** (`camera_capture`) : Capteur ou source autorisée, pilote, format, résolution, buffers et accès matériel; recevoir une piste ne prouve pas une capture.
- **Traitement d’image** (`image_processing`) : Formats/pas mémoire, dimensions, opérateurs et ressources du backend; rotation affichée et décodage ne prouvent pas un traitement de pixels.

## Périmètre par matériel

### Propeller 2 / Edge32

- Famille : `bare_metal` ; CPU : `propeller2_32` ; état du port : `physical_target`.
- VM : native FlexC v405 ; Arduino core : `not_linked`.
- Tests : P2-EC32MB / USB, calculs, persistance et Smart Pin entrée; capteurs externes non testés. JavaScript Edge USB: arithmetic/live edit, local UBP save, reset CRC persistence and connected project readback verified on EC32MB; file import blocked by automation. Real scalar worker cogs 2/3 with main cog 0, 15000 exact shared increments, GC, reconnect and lifecycle checks PASS; Revision 3 adds rooted worker heap values and audited object/pin services on the main cog: eight GCs, exact atomic list total 3000, foreach, timers, deferred returns, error recovery and ten rapid reset cycles PASS after flash boot. Worker DIR remains unchanged; unaudited operations remain refused. Current extension browser execution is pending. Revision 2 wired-pair GPIO, finite counts, NCO/PWM timing, quadrature, sync/UART serial and DAC8-to-ADC1x transfer PASS after flash boot; other Smart Pin/pad behaviors configuration-only, USB unsupported. Revision 4 checked modes PASS after flash boot: NCO duty, digital SMPS feedback, gated/differential counting, timing/timeout, DAC dither/noise mean, typed internal/synthetic external ADC and scope triggers, 1-32-bit sync serial and worker main-DIR ownership. Revision 5 adds RAM and flash-boot native SINC2/SINC3 streaming, GC-safe static rings and worker consumption/scaling, exact synthetic external counts, contiguous finite bit bursts (including 16384-bit pattern continuity), multi-channel GETSCP triggered/continuous recording, overflow/timeout/cancellation. Four DAC pads, five ADC gain responses and four input-only threshold circuits plus analog PWM feedback gating tested. At revision 5, USB and continuous internal bits/streamer DMA were unsupported; actual converter hardware and analog performance remain unvalidated. Revision 6 flash-boot: 1-32-bit asynchronous word/polarity tests and independent fractional bit timing; synchronous clock/sample/bit-order and reset-primed multiword transfers; 64 Boolean routing truth cases, metadata/buffer guards and worker main-owned serial/logic services PASS. Every operating value is mapped in the mode audit; USB remains unavailable and external analog/protocol performance is not inferred. Revision 7 RAM and flash-boot: all four owned global filter banks, routed/inverted input, debounce and filtered rises; shared/raw retiming refusal and worker/IDE transport checks PASS. Continuous external raw ring verifies 45312 pattern bits through wrap/five GCs at 20 kbit/s, exact worker consumption, and 32736 contiguous retained bits on 1 MHz overflow. All nine physical suites PASS on final image; at revision 7, internal continuous capture/DMA, external converter hardware and browser execution remained unverified. Revision 8 RAM and flash-boot: native streamer/WRFAST input pages, full-clock finite/overflow patterns, divided continuous ring through five GCs and concurrent worker consumption/density PASS. Page-granular high/low pretrigger retains chronological history/post pages after many wraps, with timeout/partial history and lifecycle cancellation. ADC raw ground/VIO and four DAC1x response points pass; all ten suites repeated on final image. Sample-accurate edge timing, external-clock/multi-pin DMA, sustained full-clock host export, external devices/analog performance and guarded browser execution remain unvalidated. Library 0.10 usability: unchanged extension-8 firmware; PWM percent, servo signal/endpoints, bounded ready/read, pulse/period/frequency/duty units, ms count windows and timed normal release PASS on paired inputs. Worker-safe services through five GCs pass; 79 functions compile. No new DMA, USB Smart Pin or external-clock exercise; owner stopped further work on those areas. Servo motion/sound and calibrated time/voltage remain unverified.
- Sources : [boards/propeller2/hardware.json](../boards/propeller2/hardware.json), [boards/propeller2/README.md](../boards/propeller2/README.md), [evidence/2026-11-03/propeller2/js-acceptance.json](../evidence/2026-11-03/propeller2/js-acceptance.json), [evidence/2026-11-03/propeller2/cogs-acceptance-ram.json](../evidence/2026-11-03/propeller2/cogs-acceptance-ram.json), [evidence/2026-11-03/propeller2/cogs-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/cogs-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/smart-pins-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/smart-pins-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/cogs-revision3-flash-boot.json](../evidence/2026-11-03/propeller2/cogs-revision3-flash-boot.json), [evidence/2026-11-03/propeller2/objects-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/objects-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/smart-pins-revision3-flash-boot.json](../evidence/2026-11-03/propeller2/smart-pins-revision3-flash-boot.json), [evidence/2026-11-03/propeller2/modes-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/modes-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/objects-revision4-flash-boot.json](../evidence/2026-11-03/propeller2/objects-revision4-flash-boot.json), [evidence/2026-11-03/propeller2/cogs-revision4-flash-boot.json](../evidence/2026-11-03/propeller2/cogs-revision4-flash-boot.json), [evidence/2026-11-03/propeller2/smart-pins-revision4-flash-boot.json](../evidence/2026-11-03/propeller2/smart-pins-revision4-flash-boot.json), [evidence/2026-11-03/propeller2/capture-usb-flash-boot.json](../evidence/2026-11-03/propeller2/capture-usb-flash-boot.json), [evidence/2026-11-03/propeller2/capture-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/capture-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/converters-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/converters-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/modes-revision5-flash-boot.json](../evidence/2026-11-03/propeller2/modes-revision5-flash-boot.json), [evidence/2026-11-03/propeller2/objects-revision5-flash-boot.json](../evidence/2026-11-03/propeller2/objects-revision5-flash-boot.json), [evidence/2026-11-03/propeller2/cogs-revision5-flash-boot.json](../evidence/2026-11-03/propeller2/cogs-revision5-flash-boot.json), [evidence/2026-11-03/propeller2/smart-pins-revision5-flash-boot.json](../evidence/2026-11-03/propeller2/smart-pins-revision5-flash-boot.json), [evidence/2026-11-03/propeller2/capture-native-builds.json](../evidence/2026-11-03/propeller2/capture-native-builds.json), [evidence/2026-11-03/propeller2/serial-options-usb-flash-boot.json](../evidence/2026-11-03/propeller2/serial-options-usb-flash-boot.json), [evidence/2026-11-03/propeller2/serial-options-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/serial-options-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/capture-revision6-flash-boot.json](../evidence/2026-11-03/propeller2/capture-revision6-flash-boot.json), [evidence/2026-11-03/propeller2/objects-revision6-flash-boot.json](../evidence/2026-11-03/propeller2/objects-revision6-flash-boot.json), [evidence/2026-11-03/propeller2/cogs-revision6-flash-boot.json](../evidence/2026-11-03/propeller2/cogs-revision6-flash-boot.json), [evidence/2026-11-03/propeller2/modes-revision6-flash-boot.json](../evidence/2026-11-03/propeller2/modes-revision6-flash-boot.json), [evidence/2026-11-03/propeller2/converters-revision6-flash-boot.json](../evidence/2026-11-03/propeller2/converters-revision6-flash-boot.json), [evidence/2026-11-03/propeller2/smart-pins-revision6-flash-boot.json](../evidence/2026-11-03/propeller2/smart-pins-revision6-flash-boot.json), [docs/PROPELLER2_MODE_COVERAGE.md](../docs/PROPELLER2_MODE_COVERAGE.md), [evidence/2026-11-03/propeller2/filters-usb-flash-boot.json](../evidence/2026-11-03/propeller2/filters-usb-flash-boot.json), [evidence/2026-11-03/propeller2/filters-capture-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/filters-capture-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/serial-options-revision7-flash-boot.json](../evidence/2026-11-03/propeller2/serial-options-revision7-flash-boot.json), [evidence/2026-11-03/propeller2/capture-revision7-flash-boot.json](../evidence/2026-11-03/propeller2/capture-revision7-flash-boot.json), [evidence/2026-11-03/propeller2/objects-revision7-flash-boot.json](../evidence/2026-11-03/propeller2/objects-revision7-flash-boot.json), [evidence/2026-11-03/propeller2/cogs-revision7-flash-boot.json](../evidence/2026-11-03/propeller2/cogs-revision7-flash-boot.json), [evidence/2026-11-03/propeller2/modes-revision7-flash-boot.json](../evidence/2026-11-03/propeller2/modes-revision7-flash-boot.json), [evidence/2026-11-03/propeller2/converters-revision7-flash-boot.json](../evidence/2026-11-03/propeller2/converters-revision7-flash-boot.json), [evidence/2026-11-03/propeller2/smart-pins-revision7-flash-boot.json](../evidence/2026-11-03/propeller2/smart-pins-revision7-flash-boot.json), [evidence/2026-11-03/propeller2/filters-native-builds.json](../evidence/2026-11-03/propeller2/filters-native-builds.json), [evidence/2026-11-03/propeller2/filters-capture-acceptance-ram.json](../evidence/2026-11-03/propeller2/filters-capture-acceptance-ram.json), [evidence/2026-11-03/propeller2/dma-usb-flash-boot.json](../evidence/2026-11-03/propeller2/dma-usb-flash-boot.json), [evidence/2026-11-03/propeller2/dma-acceptance-flash-boot.json](../evidence/2026-11-03/propeller2/dma-acceptance-flash-boot.json), [evidence/2026-11-03/propeller2/filters-capture-revision8-flash-boot.json](../evidence/2026-11-03/propeller2/filters-capture-revision8-flash-boot.json), [evidence/2026-11-03/propeller2/serial-options-revision8-flash-boot.json](../evidence/2026-11-03/propeller2/serial-options-revision8-flash-boot.json), [evidence/2026-11-03/propeller2/capture-revision8-flash-boot.json](../evidence/2026-11-03/propeller2/capture-revision8-flash-boot.json), [evidence/2026-11-03/propeller2/objects-revision8-flash-boot.json](../evidence/2026-11-03/propeller2/objects-revision8-flash-boot.json), [evidence/2026-11-03/propeller2/cogs-revision8-flash-boot.json](../evidence/2026-11-03/propeller2/cogs-revision8-flash-boot.json), [evidence/2026-11-03/propeller2/modes-revision8-flash-boot.json](../evidence/2026-11-03/propeller2/modes-revision8-flash-boot.json), [evidence/2026-11-03/propeller2/converters-revision8-flash-boot.json](../evidence/2026-11-03/propeller2/converters-revision8-flash-boot.json), [evidence/2026-11-03/propeller2/smart-pins-revision8-flash-boot.json](../evidence/2026-11-03/propeller2/smart-pins-revision8-flash-boot.json), [evidence/2026-11-03/propeller2/dma-native-builds.json](../evidence/2026-11-03/propeller2/dma-native-builds.json), [evidence/2026-11-03/propeller2/dma-acceptance-ram.json](../evidence/2026-11-03/propeller2/dma-acceptance-ram.json), [evidence/2026-11-03/propeller2/filters-capture-revision8-ram.json](../evidence/2026-11-03/propeller2/filters-capture-revision8-ram.json), [evidence/2026-11-03/propeller2/capture-revision8-ram.json](../evidence/2026-11-03/propeller2/capture-revision8-ram.json), [evidence/2026-11-04/propeller2/usability-acceptance-installed-firmware.json](../evidence/2026-11-04/propeller2/usability-acceptance-installed-firmware.json), [evidence/2026-11-04/propeller2/usability-editor-check.json](../evidence/2026-11-04/propeller2/usability-editor-check.json).

- **Capteurs — Impl. / non testé** : Primitives natives FlexC I²C/SPI/GPIO ; Implémentations récupérées; périphériques externes non validés. État déclaré : `not_reported`. Preuves : [boards/propeller2/hardware.json](../boards/propeller2/hardware.json).
- **SQLite — Indisponible** : Aucune intégration SQLite fournie pour ce port natif; ce n’est pas une impossibilité matérielle. État déclaré : `not_reported`. Preuves : [boards/propeller2/hardware.json](../boards/propeller2/hardware.json), [linux/extensions/README.md](../linux/extensions/README.md).

### Waveshare ESP32-S3 RLCD

- Famille : `zephyr` ; CPU : `xtensa_32` ; état du port : `physical_target`.
- VM : v417 ; Arduino core : `linked`.
- Tests : Carte ESP32-S3 RLCD; SHTC3 et E/S documentées. Le RLCD SPI ne valide pas un OLED I²C.
- Sources : [boards/waveshare_esp32s3_rlcd_4_2/hardware.json](../boards/waveshare_esp32s3_rlcd_4_2/hardware.json), [boards/waveshare_esp32s3_rlcd_4_2/README.md](../boards/waveshare_esp32s3_rlcd_4_2/README.md).

- **Capteurs — Testé matériel** : Zephyr + Arduino API; SHTC3 I²C ; Température/humidité et lectures physiques; validation limitée aux périphériques cités. État déclaré : `not_reported`. Preuves : [boards/waveshare_esp32s3_rlcd_4_2/hardware.json](../boards/waveshare_esp32s3_rlcd_4_2/hardware.json), [evidence/2026-10-18/generic-io-checkpoint.json](../evidence/2026-10-18/generic-io-checkpoint.json).

### Waveshare ESP32-P4 WIFI6

- Famille : `zephyr` ; CPU : `riscv_32` ; état du port : `physical_target`.
- VM : v417 ; Arduino core : `planned_not_linked`.
- Tests : P4 révision silicium 1.3 / IMX219 / ES8311; détails et limites dans le manifeste.
- Sources : [boards/waveshare_esp32p4_wifi6/hardware.json](../boards/waveshare_esp32p4_wifi6/hardware.json), [boards/waveshare_esp32p4_wifi6/docs/NEURAL_NETWORKS.md](../boards/waveshare_esp32p4_wifi6/docs/NEURAL_NETWORKS.md).

- **Réseaux de neurones — Testé matériel** : Zephyr TFLM référence CPU, sous-ensemble dense float32/int8 ; Modèles intégrés/personnalisés bornés; ORT direct et accélération non disponibles. État déclaré : `profile_dependent`. Preuves : [boards/waveshare_esp32p4_wifi6/hardware.json](../boards/waveshare_esp32p4_wifi6/hardware.json), [evidence/2026-10-25/p4-neural-native.json](../evidence/2026-10-25/p4-neural-native.json), [evidence/2026-10-25/p4-neural-browser.json](../evidence/2026-10-25/p4-neural-browser.json).
- **Reconnaissance vocale / Whistle — Testé / limites** : Whistle C99 int8, modèle épinglé, frontend PCM ; Transcription même PCM microphone et exécution GP testées; qualité variable. Wake-word séparé. Commandes bilingues INT8: entrainement/fixtures hote seulement; aucune precision acoustique P4 etablie. État déclaré : `profile_dependent`. Preuves : [boards/waveshare_esp32p4_wifi6/hardware.json](../boards/waveshare_esp32p4_wifi6/hardware.json), [evidence/2026-10-25/p4-whistle-same-pcm.json](../evidence/2026-10-25/p4-whistle-same-pcm.json), [bilingual-kws/reports/results.md](../bilingual-kws/reports/results.md).
- **Capteurs — Testé / limites** : Zephyr I²C0, sondes d’identification explicites ; IMX219/ES8311 identifiés; TMP117 seulement en fixtures; pas un catalogue universel. État déclaré : `not_reported`. Preuves : [boards/waveshare_esp32p4_wifi6/hardware.json](../boards/waveshare_esp32p4_wifi6/hardware.json).
- **OLED I²C — Testé / limites** : RoboEyes GPL-3.0-or-later, framebuffer et pilote OLED natifs Zephyr ; SSD1306 0x3C: alignement confirme par operateur et etats USB testes. Chaque expression, SH1106 et suivi visuel reel restent a valider. Aucun moteur. État déclaré : `explicit_initialization`. Preuves : [boards/waveshare_esp32p4_wifi6/docs/ROBOT_EYES_POSE.md](../boards/waveshare_esp32p4_wifi6/docs/ROBOT_EYES_POSE.md), [evidence/2026-10-29/robot-eyes-alignment-native.json](../evidence/2026-10-29/robot-eyes-alignment-native.json).
- **Caméras / capture — Testé / limites** : IMX219 CSI/ISP natif Zephyr ; Capture testée; qualité actuelle insuffisante: quatre niveaux gris, scène éclairée à reprendre. OV5647 seulement compilé. État déclaré : `not_reported`. Preuves : [boards/waveshare_esp32p4_wifi6/hardware.json](../boards/waveshare_esp32p4_wifi6/hardware.json), [evidence/2026-10-25/p4-zephyr-camera.json](../evidence/2026-10-25/p4-zephyr-camera.json).
- **Traitement d’image — Testé / limites** : CPU + PPA/2D DMA P4 ; Resize/gris/RGB888 et transformations PPA testés; JPEG/H264 non implémentés; aucun gain de vitesse inféré. État déclaré : `not_reported`. Preuves : [boards/waveshare_esp32p4_wifi6/hardware.json](../boards/waveshare_esp32p4_wifi6/hardware.json), [evidence/2026-10-25/p4-ppa-whistle-regression.json](../evidence/2026-10-25/p4-ppa-whistle-regression.json).

Caméra :

- Capture native : True ; réception seulement : False.
- Pilote : CSI/ISP Zephyr natif; IMX219 attaché; OV5647 compilé non attaché.
- Formats capteur : IMX219 RAW10, OV5647 RAW8 (non testé matériel).
- Formats de sortie : RGB565, RGB888 (transformation).
- Résolutions de capture : [{"width": 1280, "height": 720, "sensor": "IMX219", "validation": "physical_limited"}, {"width": 800, "height": 640, "sensor": "OV5647", "validation": "source_only"}].
- Résolutions de prévisualisation : [{"width": 160, "height": 90, "validation": "physical_target"}].
- Codecs : {"JPEG": "unavailable", "H264": "unavailable"} ; qualité : `strict_scene_content_failed_pending_lit_scene_retest`.

### Adafruit Fruit Jam RP2350B

- Famille : `zephyr` ; CPU : `arm_32` ; état du port : `physical_target`.
- VM : v417 ; Arduino core : `linked`.
- Tests : Fruit Jam: USB/VM, Wi-Fi, boutons et NeoPixels testés; I²C externe non validé.
- Sources : [boards/adafruit_fruit_jam/hardware.json](../boards/adafruit_fruit_jam/hardware.json), [boards/adafruit_fruit_jam/README.md](../boards/adafruit_fruit_jam/README.md).

- **Capteurs — Impl. / non testé** : Pilote Zephyr I²C0 + primitives ; Compilé mais aucune transaction physique réussie; investigation SHT4x annulée, aucun nouvel accès autorisé. État déclaré : `not_reported`. Preuves : [boards/adafruit_fruit_jam/hardware.json](../boards/adafruit_fruit_jam/hardware.json).

### SparkFun XRP RP2350B production

- Famille : `zephyr` ; CPU : `arm_32` ; état du port : `physical_target`.
- VM : v417 ; Arduino core : `linked`.
- Tests : XRP ROB-26619 production; IMU identité/ADC. Moteurs et servos restent verrouillés.
- Sources : [boards/sparkfun_xrp_rp2350/hardware.json](../boards/sparkfun_xrp_rp2350/hardware.json), [boards/sparkfun_xrp_rp2350/README.md](../boards/sparkfun_xrp_rp2350/README.md).

- **Capteurs — Testé / limites** : Zephyr + Arduino Wire / ADC ; IMU WHO_AM_I 0x6c et ADC lus; accélération, gyro/calibration et périphérique Qwiic externe non validés. État déclaré : `not_reported`. Preuves : [boards/sparkfun_xrp_rp2350/hardware.json](../boards/sparkfun_xrp_rp2350/hardware.json), [evidence/xrp-inputs-02-2026-10-19.json](../evidence/xrp-inputs-02-2026-10-19.json).

### UNO Q — MCU

- Famille : `zephyr` ; CPU : `arm_32` ; état du port : `external_reference`.
- VM : référence externe, pas validée dans ce dépôt ; Arduino core : `external_reference`.
- Tests : STM32U585 Cortex-M33 selon Arduino; tests du projet de référence non transférés à cette matrice.
- Sources : [README.md](../README.md), [https://docs.arduino.cc/hardware/uno-q/](https://docs.arduino.cc/hardware/uno-q/).


### UNO Q — MPU

- Famille : `linux` ; CPU : `arm_64` ; état du port : `external_reference`.
- VM : aucune installation SmallVM de ce dépôt validée sur ce MPU ; Arduino core : `not_applicable`.
- Tests : QRB2210 Cortex-A53/Linux selon Arduino; capacité matérielle ne prouve aucun backend MicroBlocks.
- Sources : [README.md](../README.md), [https://docs.arduino.cc/hardware/uno-q/](https://docs.arduino.cc/hardware/uno-q/).


### Raspberry Pi 5

- Famille : `linux` ; CPU : `arm_64` ; état du port : `physical_target`.
- VM : v417 LP64 ; Arduino core : `not_applicable`.
- Tests : Pi5 Debian13.4 AArch64; programme/SQLite/HTTP/WS et Blinka logiciel. Aucun capteur ni caméra testé.
- Sources : [linux/arm64/hardware.json](../linux/arm64/hardware.json), [linux/extensions/README.md](../linux/extensions/README.md), [evidence/2026-11-02/pi5-installer/README.md](../evidence/2026-11-02/pi5-installer/README.md).

- **Réseaux de neurones — Testé / limites** : Extension Python commune, LiteRT 2.3.0 / ONNX Runtime 1.31.1 CPU ; Pi5 physique: 15 tests sans ignore, deux moteurs CPU reels, modele PyTorch exporte et blocs compiles dans SmallVM 417 avec heartbeat. Environnement prive de test, non active dans le service courant; profils desactives par defaut. Un tenseur float32 fixe en entree/sortie et echelles explicites; formats .tflite/.onnx distincts. Aucune acceleration NPU/GPU ni charge representative validee. État déclaré : `disabled_by_default`. Preuves : [linux/extensions/inference/README.md](../linux/extensions/inference/README.md), [docs/LINUX_INFERENCE_SPEC.md](../docs/LINUX_INFERENCE_SPEC.md), [evidence/2026-11-02/linux-inference/host-arm64-ci.json](../evidence/2026-11-02/linux-inference/host-arm64-ci.json), [evidence/2026-11-02/linux-inference/pi5-cpu.json](../evidence/2026-11-02/linux-inference/pi5-cpu.json), [evidence/2026-11-02/linux-inference/README.md](../evidence/2026-11-02/linux-inference/README.md).
- **Reconnaissance vocale / Whistle — Prévu** : Port/backend STT Linux demandé; aucune intégration Whistle validée sur le Pi. État déclaré : `not_reported`. Preuves : [boards/waveshare_esp32p4_wifi6/docs/NEURAL_NETWORKS.md](../boards/waveshare_esp32p4_wifi6/docs/NEURAL_NETWORKS.md).
- **Capteurs — Logiciel testé** : Service Python partagé + exemple Blinka/SHT4x ; Blinka10.1.0 et détection Pi5 validés; capteur, driver SHT4x et bus I²C non activés/testés. État déclaré : `disabled`. Preuves : [linux/extensions/README.md](../linux/extensions/README.md), [evidence/2026-11-02/pi5-installer/existing-service-blinka.json](../evidence/2026-11-02/pi5-installer/existing-service-blinka.json).
- **OLED I²C — Prévu** : Aucun pilote/bloc OLED intégré validé; contrôleur, taille, adresse et bus à choisir. État déclaré : `not_reported`. Preuves : [linux/extensions/README.md](../linux/extensions/README.md).
- **MQTT — Impl. / simulé** : Plugin Python Paho 2.x ; Fixtures API seulement; broker réel, TLS et matériel non testés. Plugin désactivé. État déclaré : `disabled`. Preuves : [linux/extensions/README.md](../linux/extensions/README.md), [tests/test_python_mqtt.py](../tests/test_python_mqtt.py).
- **SQLite — Testé matériel** : Python sqlite3 via service/VM et blocs partagés ; Éditeur réel, paramètres liés, persistance et sélection Blinka du worker testés sur Pi5. État déclaré : `enabled`. Preuves : [linux/extensions/README.md](../linux/extensions/README.md), [evidence/2026-11-02/pi5-installer/existing-service-e2e.json](../evidence/2026-11-02/pi5-installer/existing-service-e2e.json).
- **Caméras / capture — Indisponible** : Le port SmallVM Linux ne fournit pas la capture caméra; aucun pilote caméra n’a été commissionné. État déclaré : `not_reported`. Preuves : [linux/arm64/hardware.json](../linux/arm64/hardware.json).
- **Traitement d’image — Prévu** : API/backends image Linux à intégrer; aucun traitement validé sur le Pi par cette installation. État déclaré : `not_reported`. Preuves : [linux/arm64/hardware.json](../linux/arm64/hardware.json).

Caméra :

- Capture native : False ; réception seulement : False.
- Pilote : non validé/non fourni.
- Formats capteur : non validés.
- Formats de sortie : non validés.
- Résolutions de capture : non validées.
- Résolutions de prévisualisation : non validées.
- Codecs : non validés ; qualité : `not_tested`.

### MicroDuck RK3566

- Famille : `linux` ; CPU : `arm_64` ; état du port : `adapter_simulation`.
- VM : adaptateur LP64; déploiement matériel robot non validé ; Arduino core : `not_applicable`.
- Tests : Tests de services simulés exécutés sur Pi, distincts du MicroDuck. Réservation UART2 rapportée par le test opérateur.
- Sources : [docs/PI5_MICRODUCK_STATUS.md](../docs/PI5_MICRODUCK_STATUS.md), [docs/MICRODUCK_SERVICE_CAPABILITIES.md](../docs/MICRODUCK_SERVICE_CAPABILITIES.md), [evidence/2026-11-02/microduck-uart2-constraint.md](../evidence/2026-11-02/microduck-uart2-constraint.md).

- **Réseaux de neurones — Partiel** : Extension Python commune, LiteRT 2.3.0 / ONNX Runtime 1.31.1 CPU ; Un tenseur float32 fixe en entree/sortie, listes et echelles explicites; formats distincts .tflite/.onnx, dependances optionnelles; aucune acceleration validee. Contrat et adaptateur Linux CPU partages; Python/libc/ABI/recettes Yocto et inference sur le robot non valides. Aucun backend NPU, controle moteur ni mapping Blinka Radxa ajoute. État déclaré : `disabled_by_default`. Preuves : [linux/extensions/inference/README.md](../linux/extensions/inference/README.md), [docs/LINUX_INFERENCE_SPEC.md](../docs/LINUX_INFERENCE_SPEC.md).
- **Capteurs — Impl. / simulé** : Interfaces robotd/tofd/padd et adaptateurs Unix typés ; Tests avec services simulés sur Pi; pas un test capteur MicroDuck. Aucun mapping Blinka Radxa forcé: UART2 sert aux moteurs. État déclaré : `commissioning_required`. Preuves : [docs/MICRODUCK_SERVICE_CAPABILITIES.md](../docs/MICRODUCK_SERVICE_CAPABILITIES.md), [evidence/2026-11-02/microduck-uart2-constraint.md](../evidence/2026-11-02/microduck-uart2-constraint.md).
- **OLED I²C — Prévu** : Pas de pilote OLED MicroDuck validé; utiliser une interface périphérique robot appropriée, jamais un mapping GPIO Radxa deviné. État déclaré : `not_reported`. Preuves : [evidence/2026-11-02/microduck-uart2-constraint.md](../evidence/2026-11-02/microduck-uart2-constraint.md).
- **MQTT — Impl. / simulé** : Plugin Python partagé; installation robot non validée ; Tests API génériques seulement; pas de broker réel ni de déploiement robot. État déclaré : `disabled`. Preuves : [linux/extensions/README.md](../linux/extensions/README.md), [tests/test_python_mqtt.py](../tests/test_python_mqtt.py).
- **SQLite — Testé hôte CI** : Plugin Python partagé; installation robot non validée ; Code/service testé sur Linux et Pi; persistance sur le MicroDuck physique non validée. État déclaré : `not_reported`. Preuves : [linux/extensions/README.md](../linux/extensions/README.md), [tests/test_python_extensions.py](../tests/test_python_extensions.py).
- **Caméras / capture — Partiel / simulé** : Observateur navigateur receive-only, protocole mediad/WebRTC ; Signalisation/pistes/callbacks simulés uniquement; aucune capture native, vraie vidéo, résolution ou décodage caméra validé. État déclaré : `commissioning_required`. Preuves : [linux/microduck/CAMERA.md](../linux/microduck/CAMERA.md), [linux/microduck/CAMERA_VIEWER.md](../linux/microduck/CAMERA_VIEWER.md).
- **Traitement d’image — Prévu** : Orientation/métadonnées du viewer ne constituent pas un traitement d’image; pixels/format/résolution non validés. État déclaré : `not_reported`. Preuves : [linux/microduck/CAMERA_VIEWER.md](../linux/microduck/CAMERA_VIEWER.md).

Caméra :

- Capture native : False ; réception seulement : True.
- Pilote : mediad/GStreamer amont; adaptateur navigateur de réception simulé.
- Formats capteur : non validés.
- Formats de sortie : non validés.
- Résolutions de capture : non validées.
- Résolutions de prévisualisation : non validées.
- Codecs : non validés ; qualité : `physical_video_and_decode_not_tested`.

### Linux x86-64 — hôte CI

- Famille : `linux` ; CPU : `x86_64` ; état du port : `host_ci`.
- VM : v417 LP64 natif en CI ; Arduino core : `not_applicable`.
- Tests : Hôte GitHub x86-64; tests logiciels natifs, aucune validation GPIO/Blinka/caméra. Installateur Pi5 non applicable.
- Sources : [.github/workflows/linux-arm64.yml](../.github/workflows/linux-arm64.yml), [.github/workflows/python-extensions.yml](../.github/workflows/python-extensions.yml), [evidence/2026-11-02/pi5-installer/ci-9612848-complete.json](../evidence/2026-11-02/pi5-installer/ci-9612848-complete.json).

- **Réseaux de neurones — Testé hôte CI** : Extension Python commune, LiteRT 2.3.0 / ONNX Runtime 1.31.1 CPU ; Un tenseur float32 fixe en entree/sortie, listes et echelles explicites; formats distincts .tflite/.onnx, dependances optionnelles; aucune acceleration validee. Modele PyTorch reel exporte vers les deux moteurs et execute depuis les blocs compiles dans SmallVM 417 sur WSL x86_64; aucun peripherique physique teste. État déclaré : `disabled_by_default`. Preuves : [linux/extensions/inference/README.md](../linux/extensions/inference/README.md), [docs/LINUX_INFERENCE_SPEC.md](../docs/LINUX_INFERENCE_SPEC.md), [evidence/2026-11-02/linux-inference/README.md](../evidence/2026-11-02/linux-inference/README.md), [evidence/2026-11-02/linux-inference/host-x86_64.json](../evidence/2026-11-02/linux-inference/host-x86_64.json), [evidence/2026-11-02/linux-inference/native-host-litert.json](../evidence/2026-11-02/linux-inference/native-host-litert.json), [evidence/2026-11-02/linux-inference/native-host-onnx.json](../evidence/2026-11-02/linux-inference/native-host-onnx.json), [https://github.com/speccy88/microblocks-zephyr/actions/runs/41491581084](https://github.com/speccy88/microblocks-zephyr/actions/runs/41491581084).
- **MQTT — Impl. / simulé** : Plugin Python partagé Paho ; API testée avec fakes; aucun broker réel ni installateur dédié. État déclaré : `not_reported`. Preuves : [linux/extensions/README.md](../linux/extensions/README.md), [tests/test_python_mqtt.py](../tests/test_python_mqtt.py).
- **SQLite — Testé hôte CI** : Python sqlite3 + VM native x86-64 en CI ; Vrai bytecode et SQLite testés sur hôte CI; aucune carte/périphérique x86 physique validé. État déclaré : `not_reported`. Preuves : [.github/workflows/python-extensions.yml](../.github/workflows/python-extensions.yml).

### Linux ARM32 — cible souhaitée

- Famille : `linux` ; CPU : `arm_32` ; état du port : `planned_target`.
- VM : port/intégration ARM32 non validés dans ce dépôt ; Arduino core : `not_applicable`.
- Tests : Aucun build/release/installateur ou test matériel ARM32 de ce port. LP64 ARM64 ne vaut pas validation ARM32.
- Sources : [docs/LINUX_ARM64_SMALLVM_PORT.md](../docs/LINUX_ARM64_SMALLVM_PORT.md), [linux/arm64/SPEC.md](../linux/arm64/SPEC.md).


## Utilisation future par l’éditeur

La source lisible par machine est [capabilities/matrix.json](../capabilities/matrix.json). Les sources matérielles revues sont liées par empreinte ; si elles changent, réauditer la synthèse plutôt que conserver une copie divergente.
L’éditeur doit combiner le contrat commun, le manifeste de la cible, les capacités réellement rapportées, la configuration et la disponibilité des ressources. Ce catalogue documentaire seul ne doit ni activer un bloc ni autoriser un accès matériel.
Une cible sans rapport fiable reste inconnue. Préserver les définitions des blocs des projets existants et expliquer les fonctions non disponibles. Le filtrage de la palette Python reste à implémenter dans une interface commune ; le runtime refuse déjà les extensions désactivées.
MicroDuck : ne jamais forcer le profil Blinka Radxa. UART2 est réservé aux moteurs selon le test opérateur rapporté ; utiliser les interfaces robot appropriées, sans transfert de validation depuis le Pi5.

Régénération : `python tools/capability_matrix.py` ; vérification sans écriture : `python tools/capability_matrix.py --check`.
