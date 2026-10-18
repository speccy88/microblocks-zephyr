#!/usr/bin/env bash
set -euo pipefail
cd /home/fred/microblocks-zephyr-work
export PATH="$PWD/.venv/bin:$PWD/tools/host/usr/bin:$PATH"
export ZEPHYR_BASE="$PWD/zephyr"
export ZEPHYR_SDK_INSTALL_DIR="$PWD/tools/zephyr-sdk-1.0.1"
export CMAKE_BUILD_PARALLEL_LEVEL=4
task=/mnt/c/Users/fred_/Documents/Codex/2026-10-17/task-5
repo="$task/microblocks-zephyr"
test "$(git -C zephyr rev-parse HEAD)" = a915b2f12675b48b16d56653ea145dcd8f20cbbf
west build -b adafruit_fruit_jam/rp2350b/m33_0 -d build/fruit-jam \
  "$repo/boards/adafruit_fruit_jam/smallvm" -- \
  -DZEPHYR_EXTRA_MODULES="$PWD/build/arduino-fruit-jam-cbridge" \
  -DFRUIT_JAM_ARDUINO_DIR="$PWD/build/arduino-fruit-jam-cbridge" \
  -DSMALLVM_SOURCE_DIR="$task/upstream-smallvm-v417-snapshot"
