# SPDX-License-Identifier: MPL-2.0
cmake_minimum_required(VERSION 3.28)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(p4_sd_readonly LANGUAGES C)
get_filename_component(repo "${CMAKE_CURRENT_SOURCE_DIR}/../../../.." ABSOLUTE)
execute_process(COMMAND ${Python3_EXECUTABLE} "${repo}/tools/apply_p4_zephyr_patches.py"
  --zephyr "${ZEPHYR_BASE}" --require-applied COMMAND_ERROR_IS_FATAL ANY)
target_sources(app PRIVATE src/main.c src/probe.c)
