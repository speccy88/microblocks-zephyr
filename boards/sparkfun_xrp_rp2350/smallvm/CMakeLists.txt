# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.28.0)
list(APPEND BOARD_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../zephyr")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(xrp_production_smallvm LANGUAGES C CXX ASM)
execute_process(COMMAND git -C ${ZEPHYR_BASE} rev-parse HEAD
  OUTPUT_VARIABLE zephyr_commit OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
if(NOT zephyr_commit STREQUAL "a915b2f12675b48b16d56653ea145dcd8f20cbbf")
  message(FATAL_ERROR "Use the XRP pinned Zephyr revision")
endif()
if(NOT CONFIG_BOARD_SPARKFUN_XRP_RP2350B_M33_0 OR CONFIG_BT)
  message(FATAL_ERROR "Production XRP RP2350B only; Bluetooth unsupported")
endif()
if(NOT SMALLVM_SOURCE_DIR OR NOT EXISTS "${SMALLVM_SOURCE_DIR}/provenance.json")
  message(FATAL_ERROR "Set SMALLVM_SOURCE_DIR to the verified v417 snapshot")
endif()
if(NOT XRP_ARDUINO_DIR OR NOT EXISTS "${XRP_ARDUINO_DIR}/xrp-provenance.json")
  message(FATAL_ERROR "Use tools/prepare_xrp_arduino.py to prepare the isolated Arduino API")
endif()
if(NOT IDE_SOURCE_DIR)
  message(FATAL_ERROR "Set IDE_SOURCE_DIR to the verified GP 2.5.8 assets")
endif()
set(repo ${CMAKE_CURRENT_SOURCE_DIR}/../../..)
set(vm_root ${CMAKE_CURRENT_BINARY_DIR}/smallvm)
set(web_root ${CMAKE_CURRENT_BINARY_DIR}/web-xrp)
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/prepare_smallvm.py
  ${SMALLVM_SOURCE_DIR} ${vm_root} --strict-digital-arity COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/prepare_xrp_runtime.py
  ${vm_root} COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND ${Python3_EXECUTABLE} ${repo}/tools/package_xrp_ide.py
  ${IDE_SOURCE_DIR} ${web_root} COMMAND_ERROR_IS_FATAL ANY)
target_include_directories(app PRIVATE ${vm_root} ${vm_root}/vm src ${repo}/common)
target_compile_definitions(app PRIVATE SMALLVM_ZEPHYR=1)
target_sources(app PRIVATE src/main.cpp src/platform.c src/transport.c src/io.cpp
  src/generic_primitives.c src/program_store.c src/safety.c src/provisioning.c
  src/server.c src/websocket.c src/capture.c
  ${repo}/common/network_setup.c ${repo}/common/network_setup_store.c
  ${repo}/common/zephyr_network_store.c
  ${web_root}/assets.c ${web_root}/assets.S
  ${vm_root}/vm/encoderPrims.cpp
  ${vm_root}/vm/interp.c ${vm_root}/vm/runtime.c ${vm_root}/vm/mem.c
  ${vm_root}/vm/persist.c ${vm_root}/vm/dataPrims.c ${vm_root}/vm/varPrims.c
  ${vm_root}/vm/tinyJSON.c ${vm_root}/vm/mbFont.c ${vm_root}/vm/boardHooks.c)
zephyr_linker_sources(SECTIONS sections-rom.ld)
zephyr_linker_section(NAME http_resource_desc_mb_http KVMA RAM_REGION GROUP RODATA_REGION)
