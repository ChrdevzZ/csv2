cmake_minimum_required(VERSION 3.16)

project(csv2_verification_superproject LANGUAGES CXX)

if(NOT DEFINED CSV2_SOURCE_DIR OR NOT IS_DIRECTORY "${CSV2_SOURCE_DIR}")
  message(FATAL_ERROR "CSV2_SOURCE_DIR must identify the csv2 source tree")
endif()
if(NOT DEFINED CSV2_SUPERPROJECT_MODE)
  set(CSV2_SUPERPROJECT_MODE normal)
endif()

if(CSV2_SUPERPROJECT_MODE STREQUAL "catch_collision")
  add_library(Catch2::Catch2WithMain INTERFACE IMPORTED)
  set(CSV2_BUILD_TESTS ON CACHE BOOL "" FORCE)
  set(CSV2_BUILD_BENCHMARKS OFF CACHE BOOL "" FORCE)
  add_subdirectory("${CSV2_SOURCE_DIR}" csv2)
  message(FATAL_ERROR "Catch2 target collision was not rejected")
elseif(CSV2_SUPERPROJECT_MODE STREQUAL "benchmark_collision")
  add_library(benchmark::benchmark INTERFACE IMPORTED)
  set(CSV2_BUILD_TESTS OFF CACHE BOOL "" FORCE)
  set(CSV2_BUILD_BENCHMARKS ON CACHE BOOL "" FORCE)
  add_subdirectory("${CSV2_SOURCE_DIR}" csv2)
  message(FATAL_ERROR "Google Benchmark target collision was not rejected")
elseif(NOT CSV2_SUPERPROJECT_MODE STREQUAL "normal")
  message(FATAL_ERROR "Unknown CSV2_SUPERPROJECT_MODE=${CSV2_SUPERPROJECT_MODE}")
endif()

set(CMAKE_COMPILE_WARNING_AS_ERROR ON)
set(CSV2_BUILD_TESTS ON CACHE BOOL "" FORCE)
set(CSV2_BUILD_BENCHMARKS ON CACHE BOOL "" FORCE)
set(CSV2_BUILD_BENCHMARK_CHECKS OFF CACHE BOOL "" FORCE)
set(CSV2_ENABLE_SANITIZERS ON CACHE BOOL "" FORCE)
set(CSV2_VERIFICATION_PROFILE quick CACHE STRING "" FORCE)

function(csv2_define_parent_cache name value help)
  set("${name}" "${value}" CACHE STRING "${help}" FORCE)
  set_property(CACHE "${name}" PROPERTY ADVANCED TRUE)
  set_property(CACHE "${name}" PROPERTY STRINGS
    "${value}" "${value}-alternative")
endfunction()

csv2_define_parent_cache(CATCH_BUILD_TESTING parent-catch
  "parent Catch2 sentinel")
csv2_define_parent_cache(BENCHMARK_ENABLE_TESTING parent-benchmark
  "parent Google Benchmark sentinel")
csv2_define_parent_cache(HAVE_STD_REGEX parent-have
  "parent feature-probe sentinel")

get_cmake_property(csv2_parent_cache_before CACHE_VARIABLES)
add_subdirectory("${CSV2_SOURCE_DIR}" csv2)

function(csv2_assert_parent_cache name value help)
  get_property(actual_value CACHE "${name}" PROPERTY VALUE)
  get_property(actual_type CACHE "${name}" PROPERTY TYPE)
  get_property(actual_help CACHE "${name}" PROPERTY HELPSTRING)
  get_property(actual_advanced CACHE "${name}" PROPERTY ADVANCED)
  get_property(actual_strings CACHE "${name}" PROPERTY STRINGS)
  if(NOT actual_value STREQUAL value OR NOT actual_type STREQUAL "STRING" OR
     NOT actual_help STREQUAL help OR NOT actual_advanced OR
     NOT actual_strings STREQUAL "${value};${value}-alternative")
    message(FATAL_ERROR
      "Vendored dependency changed parent Cache metadata for ${name}")
  endif()
endfunction()

csv2_assert_parent_cache(CATCH_BUILD_TESTING parent-catch
  "parent Catch2 sentinel")
csv2_assert_parent_cache(BENCHMARK_ENABLE_TESTING parent-benchmark
  "parent Google Benchmark sentinel")
csv2_assert_parent_cache(HAVE_STD_REGEX parent-have
  "parent feature-probe sentinel")

get_cmake_property(csv2_parent_cache_after CACHE_VARIABLES)
foreach(cache_name IN LISTS csv2_parent_cache_after)
  if(cache_name MATCHES
       "^(CATCH_|BENCHMARK_|HAVE_|CSV2_BENCHMARK_PFM_|STD_REGEX$|STEADY_CLOCK$|PTHREAD_AFFINITY$|CMAKE_HAVE_LIBC_PTHREAD$|THREADS_PTHREAD_ARG$)")
    list(FIND csv2_parent_cache_before "${cache_name}" original_index)
    if(original_index EQUAL -1)
      message(FATAL_ERROR
        "Vendored dependency leaked Cache entry ${cache_name}")
    endif()
  endif()
endforeach()

foreach(target IN ITEMS Catch2 Catch2WithMain benchmark benchmark_main)
  if(NOT TARGET "${target}")
    message(FATAL_ERROR "Vendored verification target ${target} is missing")
  endif()
  get_target_property(werror "${target}" COMPILE_WARNING_AS_ERROR)
  if(werror)
    message(FATAL_ERROR
      "Vendored verification target ${target} inherited Werror")
  endif()
  get_target_property(compile_options "${target}" COMPILE_OPTIONS)
  if(compile_options MATCHES "sanitize")
    message(FATAL_ERROR
      "Vendored verification target ${target} inherited sanitizers")
  endif()
endforeach()
