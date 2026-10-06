# Copyright (c) 2026 Paulo Santos (@wkhadgar)
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(zview_bench LANGUAGES C)

target_include_directories(app PRIVATE src)
target_sources(app PRIVATE
  src/main.c
  src/instrument.c
)

# Each mode builds only its own workload.
target_sources_ifdef(CONFIG_ZVIEW_BENCH_MODE_STEADY app PRIVATE src/steady.c)
target_sources_ifdef(CONFIG_ZVIEW_BENCH_MODE_DYNAMIC app PRIVATE
  src/dynamic/stack.c
  src/dynamic/heap.c
  src/dynamic/load.c
  src/dynamic/mutex.c
  src/dynamic/sem.c
  src/dynamic/msgq.c
  src/dynamic/slab.c
  src/dynamic/timers.c
)

# Locate the git index for this repository and add it as a dependency of the
# application VERSION file, so a new commit regenerates the version even when
# no build inputs changed. Silently skipped for freestanding (non-git) trees.
find_package(Git QUIET)
if(GIT_FOUND)
  execute_process(
    COMMAND ${GIT_EXECUTABLE} rev-parse --absolute-git-dir
    WORKING_DIRECTORY .
    OUTPUT_VARIABLE application_git_dir
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_STRIP_TRAILING_WHITESPACE
    ERROR_VARIABLE stderr
    RESULT_VARIABLE return_code
  )
  if(NOT return_code)
    if(NOT "${stderr}" STREQUAL "")
      message(WARNING "Application build version git rev-parse warned: ${stderr}")
    endif()
    set_property(TARGET app_version_h PROPERTY APP_VERSION_DEPENDS ${application_git_dir}/index)
  endif()
endif()
