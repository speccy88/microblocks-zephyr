# Zephyr's Metro RP2350 runner composition, Pete Johanson 2025.
# SPDX-License-Identifier: Apache-2.0
if("${RPI_PICO_DEBUG_ADAPTER}" STREQUAL "")
  set(RPI_PICO_DEBUG_ADAPTER "cmsis-dap")
endif()
board_runner_args(openocd --cmd-pre-init "source [find interface/${RPI_PICO_DEBUG_ADAPTER}.cfg]")
board_runner_args(openocd --cmd-pre-init "source [find target/rp2350.cfg]")
board_runner_args(openocd --cmd-pre-init "set_adapter_speed_if_not_set 1000")
board_runner_args(uf2 "--board-id=RP2350")
include(${ZEPHYR_BASE}/boards/common/uf2.board.cmake)
include(${ZEPHYR_BASE}/boards/common/openocd.board.cmake)
