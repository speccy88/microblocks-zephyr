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
if(CONFIG_I2S_ESP32 AND CONFIG_DMA_ESP32_MAX_DESCRIPTOR_NUM EQUAL 1)
  set(patched_i2s ${CMAKE_CURRENT_BINARY_DIR}/drivers/i2s_esp32.c)
  execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/prepare_i2s.py
    ${ZEPHYR_BASE}/drivers/i2s/i2s_esp32.c ${patched_i2s}
    COMMAND_ERROR_IS_FATAL ANY)
  get_target_property(i2s_sources drivers__i2s SOURCES)
  list(LENGTH i2s_sources i2s_source_count)
  list(FILTER i2s_sources EXCLUDE REGEX "i2s_esp32\\.c$")
  list(LENGTH i2s_sources i2s_other_count)
  math(EXPR replaced_count "${i2s_source_count} - ${i2s_other_count}")
  if(NOT replaced_count EQUAL 1)
    message(FATAL_ERROR "Expected exactly one pinned ESP32 I2S driver")
  endif()
  set_property(TARGET drivers__i2s PROPERTY SOURCES ${i2s_sources} ${patched_i2s})
endif()
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/prepare_smallvm.py
  ${SMALLVM_SOURCE_DIR} ${vm_root} COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/package_ide.py
  ${IDE_SOURCE_DIR} ${web_root} COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/generate_device_secrets.py
  ${CMAKE_CURRENT_BINARY_DIR}/private COMMAND_ERROR_IS_FATAL ANY)
target_include_directories(app PRIVATE ${vm_root} ${vm_root}/vm
  ../bringup/src ../smallvm/src src ${CMAKE_CURRENT_BINARY_DIR}/private)
target_compile_definitions(app PRIVATE SMALLVM_ZEPHYR=1 SMALLVM_WEBSOCKET=1)
target_sources(app PRIVATE src/main.cpp src/network.c src/server.c src/transport.c src/program_store.c src/wifi_settings.c
  ../smallvm/src/platform.c ../smallvm/src/arduino_transport.cpp
  ../smallvm/src/generic_primitives.c ../smallvm/src/generic_io.cpp
  ../bringup/src/rlcd_board.c ../bringup/src/rlcd_audio.c ../integration/rlcd_smallvm_primitives.c
  ${vm_root}/vm/interp.c ${vm_root}/vm/runtime.c ${vm_root}/vm/mem.c
  ${vm_root}/vm/persist.c ${vm_root}/vm/dataPrims.c ${vm_root}/vm/varPrims.c
  ${vm_root}/vm/tinyJSON.c ${vm_root}/vm/mbFont.c ${vm_root}/vm/boardHooks.c
  ${web_root}/assets.c ${web_root}/assets.S)
zephyr_linker_sources(SECTIONS sections-rom.ld)
zephyr_linker_section(NAME http_resource_desc_mb_http KVMA RAM_REGION GROUP RODATA_REGION)
