# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.28.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(waveshare_arduino_smoke LANGUAGES C CXX)
target_sources(app PRIVATE src/main.cpp)
