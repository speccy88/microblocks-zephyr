# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.28.0)
list(APPEND BOARD_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../zephyr")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(xrp_production_non_actuating LANGUAGES C ASM)
execute_process(COMMAND git -C ${ZEPHYR_BASE} rev-parse HEAD
  OUTPUT_VARIABLE xrp_zephyr_commit OUTPUT_STRIP_TRAILING_WHITESPACE
  COMMAND_ERROR_IS_FATAL ANY)
if(NOT xrp_zephyr_commit STREQUAL "a915b2f12675b48b16d56653ea145dcd8f20cbbf")
  message(FATAL_ERROR "Use the XRP target's pinned Zephyr revision")
endif()
if(NOT CONFIG_BOARD_SPARKFUN_XRP_RP2350B_M33_0)
  message(FATAL_ERROR "This app is restricted to sparkfun_xrp/rp2350b/m33_0, not beta or another RP2350")
endif()
if(CONFIG_WIFI OR CONFIG_BT OR CONFIG_FLASH OR CONFIG_PWM)
  message(FATAL_ERROR "This non-actuating baseline does not enable radio, flash writes or PWM")
endif()
target_sources(app PRIVATE src/main.c)
