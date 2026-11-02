#!/usr/bin/env bash
# Build only. No serial ports, flash, reset, credential or network operations.
set -euo pipefail
P4_REPO="$(cd "$(dirname "$0")/../.." && pwd)"
P4_WORKSPACE="${P4_WORKSPACE:-$HOME/microblocks-zephyr-work}"
export ZEPHYR_BASE="${ZEPHYR_BASE:-$P4_WORKSPACE/zephyr-robot-eyes}"
export ZEPHYR_SDK_INSTALL_DIR="${ZEPHYR_SDK_INSTALL_DIR:-$P4_WORKSPACE/tools/zephyr-sdk-1.0.1}"
source "$P4_WORKSPACE/.venv/bin/activate"
cd "$P4_WORKSPACE"
configs=profiles/neural.conf
extra_args=(-DP4_WHISTLE_MODEL= -DEXTRA_DTC_OVERLAY_FILE=)
if [[ -n "${P4_WHISTLE_MODEL:-}" ]]; then
  configs='profiles/whistle.conf;profiles/neural.conf'
  extra_args=(-DP4_WHISTLE_MODEL="$P4_WHISTLE_MODEL"
    -DP4_WHISTLE_SOURCES="${P4_WHISTLE_SOURCES:-$P4_REPO/build-artifacts/whistle-sources}"
    -DEXTRA_DTC_OVERLAY_FILE=profiles/whistle.overlay)
fi
west build -b esp32p4_wifi6/esp32p4/hpcore \
  -s "$P4_REPO/boards/waveshare_esp32p4_wifi6/zephyr" \
  -d "${P4_BUILD_DIR:-$P4_WORKSPACE/build-p4-bilingual-kws}" -- \
  -DEXTRA_CONF_FILE="$configs" \
  -DP4_TFLM_SOURCE="$P4_WORKSPACE/optional/modules/lib/tflite-micro" \
  -DZEPHYR_EXTRA_MODULES="$P4_WORKSPACE/optional/modules/lib/tflite-micro" \
  -DP4_KWS_MODEL="$P4_REPO/build-artifacts/p4-kws/okay_nabu.tflite" \
  -DP4_VOICE_MODEL="${P4_VOICE_MODEL:-$P4_REPO/bilingual-kws/models/voice_commands_int8.tflite}" \
  "${extra_args[@]}"
