# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.28.0)
set(CONF_FILE ../smallvm/prj.conf prj.conf)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(waveshare_standalone LANGUAGES C CXX ASM)
if(NOT SMALLVM_SOURCE_DIR OR NOT IDE_SOURCE_DIR)
  message(FATAL_ERROR "Set SMALLVM_SOURCE_DIR and IDE_SOURCE_DIR to verified source snapshots")
endif()
set(repo ${CMAKE_CURRENT_SOURCE_DIR}/../../..)
set(vm_root ${CMAKE_CURRENT_BINARY_DIR}/smallvm)
set(web_root ${CMAKE_CURRENT_BINARY_DIR}/web)
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/prepare_smallvm.py
  ${SMALLVM_SOURCE_DIR} ${vm_root} COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/package_ide.py
  ${IDE_SOURCE_DIR} ${web_root} COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/generate_device_secrets.py
  ${CMAKE_CURRENT_BINARY_DIR}/private COMMAND_ERROR_IS_FATAL ANY)
target_include_directories(app PRIVATE ${vm_root} ${vm_root}/vm
  ../bringup/src src ${CMAKE_CURRENT_BINARY_DIR}/private)
target_compile_definitions(app PRIVATE SMALLVM_ZEPHYR=1 SMALLVM_WEBSOCKET=1)
target_sources(app PRIVATE src/main.cpp src/network.c src/server.c src/transport.c src/program_store.c src/wifi_settings.c
  ../smallvm/src/platform.c ../smallvm/src/arduino_transport.cpp
  ../bringup/src/rlcd_board.c ../integration/rlcd_smallvm_primitives.c
  ${vm_root}/vm/interp.c ${vm_root}/vm/runtime.c ${vm_root}/vm/mem.c
  ${vm_root}/vm/persist.c ${vm_root}/vm/dataPrims.c ${vm_root}/vm/varPrims.c
  ${vm_root}/vm/tinyJSON.c ${vm_root}/vm/mbFont.c ${vm_root}/vm/boardHooks.c
  ${web_root}/assets.c ${web_root}/assets.S)
zephyr_linker_sources(SECTIONS sections-rom.ld)
zephyr_linker_section(NAME http_resource_desc_mb_http KVMA RAM_REGION GROUP RODATA_REGION)
