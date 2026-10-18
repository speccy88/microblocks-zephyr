# SPDX-License-Identifier: MIT
# Optional project() hook for minimal hosts without a native C++ compiler.
if(NOT TARGET pioasm)
  if(NOT EXISTS "${PICO_PREBUILT_PIOASM}")
    message(FATAL_ERROR "PICO_PREBUILT_PIOASM must name the reviewed host binary")
  endif()
  add_executable(pioasm IMPORTED GLOBAL)
  set_property(TARGET pioasm PROPERTY IMPORTED_LOCATION "${PICO_PREBUILT_PIOASM}")
endif()
