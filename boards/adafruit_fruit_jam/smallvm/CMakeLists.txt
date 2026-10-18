# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.28.0)
list(APPEND BOARD_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../zephyr")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(fruit_jam_smallvm LANGUAGES C CXX)
if(NOT CONFIG_BOARD_ADAFRUIT_FRUIT_JAM_RP2350B_M33_0)
  message(FATAL_ERROR "This app is restricted to adafruit_fruit_jam/rp2350b/m33_0")
endif()
if(NOT SMALLVM_SOURCE_DIR OR NOT EXISTS "${SMALLVM_SOURCE_DIR}/provenance.json")
  message(FATAL_ERROR "Set SMALLVM_SOURCE_DIR to the verified v417 snapshot")
endif()
if(NOT FRUIT_JAM_ARDUINO_DIR OR NOT EXISTS "${FRUIT_JAM_ARDUINO_DIR}/fruitjam-provenance.json")
  message(FATAL_ERROR "Prepare the isolated Arduino module with tools/prepare_fruit_jam_arduino.py")
endif()
set(vm_root "${CMAKE_CURRENT_BINARY_DIR}/smallvm")
execute_process(COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/../../../tools/prepare_smallvm.py
  ${SMALLVM_SOURCE_DIR} ${vm_root} --strict-digital-arity
  COMMAND_ERROR_IS_FATAL ANY)
target_include_directories(app PRIVATE ${vm_root} ${vm_root}/vm src)
target_compile_definitions(app PRIVATE SMALLVM_ZEPHYR=1)
target_sources(app PRIVATE src/main.cpp src/platform.c src/transport.c
  src/io.cpp src/generic_primitives.c src/program_store.c
  ${vm_root}/vm/interp.c ${vm_root}/vm/runtime.c ${vm_root}/vm/mem.c
  ${vm_root}/vm/persist.c ${vm_root}/vm/dataPrims.c ${vm_root}/vm/varPrims.c
  ${vm_root}/vm/tinyJSON.c ${vm_root}/vm/mbFont.c ${vm_root}/vm/boardHooks.c)
