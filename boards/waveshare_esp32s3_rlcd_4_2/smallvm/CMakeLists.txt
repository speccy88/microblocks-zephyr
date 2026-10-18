# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.28.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(waveshare_smallvm LANGUAGES C CXX)
if(NOT SMALLVM_SOURCE_DIR OR NOT EXISTS "${SMALLVM_SOURCE_DIR}/provenance.json")
  message(FATAL_ERROR "Set SMALLVM_SOURCE_DIR to the verified v417 snapshot")
endif()
set(vm_root "${CMAKE_CURRENT_BINARY_DIR}/smallvm")
execute_process(COMMAND ${Python3_EXECUTABLE}
  ${CMAKE_CURRENT_SOURCE_DIR}/../../../tools/prepare_smallvm.py
  ${SMALLVM_SOURCE_DIR} ${vm_root}
  COMMAND_ERROR_IS_FATAL ANY)
target_include_directories(app PRIVATE ${vm_root} ${vm_root}/vm ../bringup/src)
target_compile_definitions(app PRIVATE SMALLVM_ZEPHYR=1)
target_sources(app PRIVATE src/main.cpp src/platform.c src/arduino_transport.cpp
  ../bringup/src/rlcd_board.c ../bringup/src/rlcd_audio.c ../integration/rlcd_smallvm_primitives.c
  ${vm_root}/vm/interp.c ${vm_root}/vm/runtime.c ${vm_root}/vm/mem.c
  ${vm_root}/vm/persist.c ${vm_root}/vm/dataPrims.c ${vm_root}/vm/varPrims.c
  ${vm_root}/vm/tinyJSON.c ${vm_root}/vm/mbFont.c ${vm_root}/vm/boardHooks.c)
