# SPDX-License-Identifier: MPL-2.0
cmake_minimum_required(VERSION 3.28)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(p4_microblocks LANGUAGES C)
get_filename_component(repo "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
execute_process(COMMAND ${Python3_EXECUTABLE} "${repo}/tools/apply_p4_zephyr_patches.py"
  --zephyr "${ZEPHYR_BASE}" --require-applied COMMAND_ERROR_IS_FATAL ANY)
if(NOT SMALLVM_SOURCE_DIR)
  set(SMALLVM_SOURCE_DIR "${repo}/build-artifacts/p4-sources/smallvm")
endif()
set(vm_root "${CMAKE_CURRENT_BINARY_DIR}/smallvm")
execute_process(COMMAND ${Python3_EXECUTABLE} "${repo}/tools/prepare_p4_zephyr_runtime.py"
  "${SMALLVM_SOURCE_DIR}" "${vm_root}" COMMAND_ERROR_IS_FATAL ANY)
target_include_directories(app PRIVATE "${vm_root}" "${vm_root}/vm" "${repo}/common/image" "${repo}/common/audio" src "${ZEPHYR_BASE}/drivers/video")
target_compile_definitions(app PRIVATE SMALLVM_ZEPHYR=1 HAS_BOARD_HOOKS=1 IMAGE_ALLOC_EXTERNAL=1 AUDIO_ALLOC_EXTERNAL=1)
target_sources(app PRIVATE src/main.c src/platform.c src/image_primitives.c src/camera_backend.c
  src/p4_sensors.c src/p4_csi.c src/audio_backend.c
  "${repo}/common/image/image_store.c"
  "${repo}/common/audio/audio_store.c"
  ${vm_root}/vm/interp.c ${vm_root}/vm/runtime.c ${vm_root}/vm/mem.c
  ${vm_root}/vm/persist.c ${vm_root}/vm/dataPrims.c ${vm_root}/vm/varPrims.c
  ${vm_root}/vm/tinyJSON.c ${vm_root}/vm/mbFont.c ${vm_root}/vm/boardHooks.c)
# Native HAL only: no esp_driver_cam/ISP FreeRTOS drivers are linked.
target_sources(app PRIVATE
  ${ZEPHYR_HAL_ESPRESSIF_MODULE_DIR}/components/esp_hal_cam/mipi_csi_hal.c
  ${ZEPHYR_HAL_ESPRESSIF_MODULE_DIR}/components/esp_hal_cam/esp32p4/mipi_csi_periph.c
  ${ZEPHYR_HAL_ESPRESSIF_MODULE_DIR}/components/esp_hal_dma/dw_gdma_hal.c)
