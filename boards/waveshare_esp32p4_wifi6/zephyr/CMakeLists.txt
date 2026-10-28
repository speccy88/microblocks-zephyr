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
if(CONFIG_ESP_SPIRAM)
 add_custom_target(p4_vm_memory_validate ALL DEPENDS zephyr_final
   COMMAND ${Python3_EXECUTABLE} "${repo}/tools/check_p4_vm_memory.py"
     --elf "${CMAKE_BINARY_DIR}/zephyr/zephyr.elf")
endif()
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

# Portable JSON service; append its primitive set without changing p4:* indices.
target_include_directories(app PRIVATE "${repo}/common/json" "${repo}/third_party/yyjson")
target_sources(app PRIVATE "${repo}/common/json/json_service.c" "${repo}/common/json/json_primitives.c" "${repo}/third_party/yyjson/yyjson.c")
set_source_files_properties("${repo}/third_party/yyjson/yyjson.c" PROPERTIES COMPILE_OPTIONS "-include;${repo}/common/json/json_config.h")

target_include_directories(app PRIVATE "${repo}/common/automation")
target_sources(app PRIVATE "${repo}/common/automation/clock.c" "${repo}/common/automation/steps.c" "${repo}/common/automation/primitives.c")
target_include_directories(app PRIVATE "${repo}/common/storage")
target_sources(app PRIVATE "${repo}/common/storage/storage.c" "${repo}/common/storage/storage_primitives.c" "${repo}/common/storage/sd_file.c"
  "${repo}/common/storage/dispatcher.c" "${repo}/common/storage/wire.c"
  "${repo}/common/storage/controller.c" "${repo}/common/storage/storage_protocol.c")
if(CONFIG_P4_SD_READONLY OR CONFIG_P4_SD_FILES)
  target_include_directories(app PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/../diagnostics/sd_readonly/src")
  target_sources(app PRIVATE src/sd_backend.c "${CMAKE_CURRENT_SOURCE_DIR}/../diagnostics/sd_readonly/src/probe.c")
  if(CONFIG_P4_SD_FILES)
    target_sources(app PRIVATE src/sd_file_io.c "${repo}/common/storage/sd_wire.c")
  endif()
else()
  target_sources(app PRIVATE "${repo}/common/storage/sd_service_stub.c")
endif()
target_sources(app PRIVATE src/kws_primitives.c)
if(P4_KWS_MODEL)
  if(NOT CONFIG_P4_NEURAL OR NOT P4_TFLM_SOURCE)
    message(FATAL_ERROR "KWS requires the pinned TFLM neural profile")
  endif()
  set(kws_generated "${CMAKE_CURRENT_BINARY_DIR}/kws")
  set(kws_args --tflm "${P4_TFLM_SOURCE}" --model "${P4_KWS_MODEL}" --output "${kws_generated}")
  if(P4_KWS_POSITIVE AND P4_KWS_NEGATIVE)
    list(APPEND kws_args --positive "${P4_KWS_POSITIVE}" --negative "${P4_KWS_NEGATIVE}")
  endif()
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${repo}/tools/prepare_p4_kws.py" "${repo}/tools/prepare_p4_kws_frontend.py" "${P4_KWS_MODEL}")
  execute_process(COMMAND ${Python3_EXECUTABLE} "${repo}/tools/prepare_p4_kws.py" ${kws_args} COMMAND_ERROR_IS_FATAL ANY)
  set(kws_frontend "${P4_TFLM_SOURCE}/tensorflow/lite/experimental/microfrontend/lib")
  set(kws_external "${kws_generated}/filterbank_util_checked.c")
  foreach(source filterbank frontend frontend_util log_lut log_scale log_scale_util noise_reduction noise_reduction_util pcan_gain_control pcan_gain_control_util window window_util)
    list(APPEND kws_external "${kws_frontend}/${source}.c")
  endforeach()
  foreach(source fft fft_util kiss_fft_int16)
    list(APPEND kws_external "${kws_frontend}/${source}.cc")
  endforeach()
  # Redirect only frontend allocations; never alter the TFLM/custom NN allocator.
  set_source_files_properties(${kws_external} PROPERTIES COMPILE_OPTIONS "-include;${repo}/common/kws/alloc_redirect.h")
  target_include_directories(app PRIVATE "${repo}/common/kws" "${kws_generated}" "${P4_TFLM_SOURCE}/third_party_static/kissfft")
  target_sources(app PRIVATE src/kws_backend.cpp "${repo}/common/kws/features.c" "${kws_generated}/kws_assets.S" ${kws_external})
else()
  target_sources(app PRIVATE src/kws_stub.c)
endif()
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
if(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
 target_sources(app PRIVATE src/http_diagnostics.c)
endif()
if(CONFIG_P4_HOSTED)
  if(NOT TARGET modules__nanopb OR NOT CONFIG_ESP_SPIRAM)
    message(FATAL_ERROR "Hosted RPC isolation requires pinned nanopb and initialized PSRAM")
  endif()
  target_compile_options(modules__nanopb PRIVATE "SHELL:-include ${CMAKE_CURRENT_SOURCE_DIR}/src/rpc_allocator.h")
  target_sources(app PRIVATE src/rpc_allocator.c src/rpc_decode.c)
  add_custom_target(p4_rpc_memory_validate ALL DEPENDS zephyr_final
    COMMAND ${Python3_EXECUTABLE} "${repo}/tools/check_p4_rpc_memory.py"
      --elf "${CMAKE_BINARY_DIR}/zephyr/zephyr.elf" --objdump "${CMAKE_OBJDUMP}")
  if(NOT CONFIG_COMMON_LIBC_MALLOC OR NOT CONFIG_COMMON_LIBC_MALLOC_ARENA_SIZE EQUAL -1)
    message(FATAL_ERROR "Hosted memory guard requires the audited automatic libc arena")
  endif()
  if(CONFIG_HTTP_SERVER_VERSION_2 OR CONFIG_NET_SOCKETS_OFFLOAD)
    message(FATAL_ERROR "Re-audit asset buffer ownership before enabling HTTP/2 or socket offload")
  endif()
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
