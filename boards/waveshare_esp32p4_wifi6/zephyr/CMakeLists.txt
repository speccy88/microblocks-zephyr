# SPDX-License-Identifier: MPL-2.0
cmake_minimum_required(VERSION 3.28)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
if(CONFIG_P4_NEURAL)
  project(p4_microblocks LANGUAGES C CXX)
else()
  project(p4_microblocks LANGUAGES C)
endif()
get_filename_component(repo "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
execute_process(COMMAND ${Python3_EXECUTABLE} "${repo}/tools/apply_p4_zephyr_patches.py"
  --zephyr "${ZEPHYR_BASE}" --require-applied COMMAND_ERROR_IS_FATAL ANY)
if(NOT SMALLVM_SOURCE_DIR)
  set(SMALLVM_SOURCE_DIR "${repo}/build-artifacts/p4-sources/smallvm")
endif()
set(vm_root "${CMAKE_CURRENT_BINARY_DIR}/smallvm")
execute_process(COMMAND ${Python3_EXECUTABLE} "${repo}/tools/prepare_p4_zephyr_runtime.py"
  "${SMALLVM_SOURCE_DIR}" "${vm_root}" COMMAND_ERROR_IS_FATAL ANY)
target_include_directories(app PRIVATE "${vm_root}" "${vm_root}/vm" "${repo}/common/image" "${repo}/common/audio" "${repo}/common/media" src "${ZEPHYR_BASE}/drivers/video")
target_include_directories(app PRIVATE "${repo}/common/nn" "${repo}/common/i2c")
target_compile_definitions(app PRIVATE SMALLVM_ZEPHYR=1 HAS_BOARD_HOOKS=1 IMAGE_ALLOC_EXTERNAL=1 AUDIO_ALLOC_EXTERNAL=1 MEDIA_ALLOC_EXTERNAL=1)
if(CONFIG_ESP_HOSTED_MCU)
  target_include_directories(app PRIVATE "${ZEPHYR_BASE}/drivers/misc/esp_hosted_mcu")
endif()
target_sources(app PRIVATE src/main.c src/platform.c src/image_primitives.c src/camera_backend.c
  src/p4_sensors.c src/p4_csi.c src/audio_backend.c src/whistle_backend.c src/media_protocol.c src/c6_trace.c
  "${repo}/common/image/image_store.c"
  "${repo}/common/audio/audio_store.c"
  "${repo}/common/media/result_store.c"
  ${vm_root}/vm/interp.c ${vm_root}/vm/runtime.c ${vm_root}/vm/mem.c
  ${vm_root}/vm/persist.c ${vm_root}/vm/dataPrims.c ${vm_root}/vm/varPrims.c
  ${vm_root}/vm/tinyJSON.c ${vm_root}/vm/mbFont.c ${vm_root}/vm/boardHooks.c)
target_sources(app PRIVATE src/neural_primitives.c "${repo}/common/nn/nn_contract.c")
target_sources(app PRIVATE src/discovery_backend.c src/discovery_primitives.c "${repo}/common/i2c/discovery.c")
target_sources(app PRIVATE src/ppa_backend.c)
if(CONFIG_P4_NEURAL)
  if(NOT P4_TFLM_SOURCE)
    message(FATAL_ERROR "Pass P4_TFLM_SOURCE for the pinned TFLM module and ZEPHYR_EXTRA_MODULES")
  endif()
  set(nn_generated "${CMAKE_CURRENT_BINARY_DIR}/neural")
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${repo}/tools/prepare_p4_neural.py")
  execute_process(COMMAND ${Python3_EXECUTABLE} "${repo}/tools/prepare_p4_neural.py"
    --source "${ZEPHYR_BASE}/samples/modules/tflite-micro/hello_world/src/model.cpp"
    --tflm "${P4_TFLM_SOURCE}" --output "${nn_generated}" COMMAND_ERROR_IS_FATAL ANY)
  # Error strings must never corrupt the binary SmallVM transport on UART0.
  zephyr_compile_definitions(TF_LITE_STRIP_ERROR_STRINGS)
  target_include_directories(app PRIVATE "${nn_generated}")
  target_sources(app PRIVATE src/neural_backend.cpp "${nn_generated}/neural_builtin.S")
else()
  target_sources(app PRIVATE src/neural_stub.c)
endif()
# Native HAL only: no esp_driver_cam/ISP FreeRTOS drivers are linked.
if(CONFIG_P4_HOSTED)
  zephyr_linker_section(NAME http_resource_desc_p4_http KVMA RAM_REGION GROUP RODATA_REGION)
  zephyr_linker_sources(SECTIONS sections-rom.ld)
  if(NOT P4_HOSTED_ASSETS_DIR)
    set(P4_HOSTED_ASSETS_DIR "${repo}/build-artifacts/p4-hosted-assets")
  endif()
  if(NOT EXISTS "${P4_HOSTED_ASSETS_DIR}/assets.c")
    message(FATAL_ERROR "Run tools/package_p4_hosted.py before building hosted profile")
  endif()
  target_sources(app PRIVATE src/hosted_transport.c src/hosted_server.c src/network_backend.c "${P4_HOSTED_ASSETS_DIR}/assets.c")
  set(hosted_layout_args --elf "${CMAKE_BINARY_DIR}/zephyr/zephyr.elf" --image "${CMAKE_BINARY_DIR}/zephyr/zephyr.bin" --assets "${P4_HOSTED_ASSETS_DIR}/assets.bin" --dts "${CMAKE_BINARY_DIR}/zephyr/zephyr.dts")
  if(NOT P4_WHISTLE_MODEL)
    list(APPEND hosted_layout_args --allow-no-model)
  endif()
  add_custom_target(p4_hosted_layout ALL DEPENDS zephyr_final
    COMMAND ${Python3_EXECUTABLE} "${repo}/tools/check_p4_hosted_layout.py" ${hosted_layout_args})
endif()
target_sources(app PRIVATE
  ${ZEPHYR_HAL_ESPRESSIF_MODULE_DIR}/components/esp_hal_cam/mipi_csi_hal.c
  ${ZEPHYR_HAL_ESPRESSIF_MODULE_DIR}/components/esp_hal_cam/esp32p4/mipi_csi_periph.c
  ${ZEPHYR_HAL_ESPRESSIF_MODULE_DIR}/components/esp_hal_dma/dw_gdma_hal.c)

if(P4_WHISTLE_MODEL)
  if(NOT P4_WHISTLE_SOURCES)
    set(P4_WHISTLE_SOURCES "${repo}/build-artifacts/whistle-sources")
  endif()
  set(whistle_generated "${CMAKE_CURRENT_BINARY_DIR}/whistle")
  set(whistle_args --sources "${P4_WHISTLE_SOURCES}" --model "${P4_WHISTLE_MODEL}" --output "${whistle_generated}")
  if(P4_WHISTLE_FIXTURE)
    list(APPEND whistle_args --fixture "${P4_WHISTLE_FIXTURE}")
    target_compile_definitions(app PRIVATE P4_WHISTLE_FIXTURE=1)
  endif()
  execute_process(COMMAND ${Python3_EXECUTABLE} "${repo}/tools/prepare_p4_whistle.py" ${whistle_args}
    COMMAND_ERROR_IS_FATAL ANY)
  target_compile_definitions(app PRIVATE P4_WHISTLE=1)
  target_include_directories(app PRIVATE "${P4_WHISTLE_SOURCES}/engine/include")
  target_sources(app PRIVATE "${whistle_generated}/whistle_assets.S")
  foreach(source nd_cact nd_quant nd_tokenizer nd_ledcmd nd_whistle)
    target_sources(app PRIVATE "${whistle_generated}/${source}_zephyr.c")
  endforeach()
  add_custom_target(p4_whistle_validate ALL DEPENDS zephyr_final
    COMMAND ${Python3_EXECUTABLE} "${repo}/tools/check_p4_whistle_image.py"
      --elf "${CMAKE_BINARY_DIR}/zephyr/zephyr.elf"
      --bin "${CMAKE_BINARY_DIR}/zephyr/zephyr.bin")
endif()
