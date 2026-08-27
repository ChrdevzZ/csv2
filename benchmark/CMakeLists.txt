cmake_minimum_required(VERSION 3.16)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Csv2BenchmarkFeatures)
include(Csv2BenchmarkProfile)
include(Csv2BenchmarkRegistration)

csv2_configure_python_audits(
  "benchmark checksum, corpus, tooling, and evidence-protocol")

csv2_detect_benchmark_features()
csv2_configure_benchmark_profile()

set(CSV2_BENCHMARK_REVISION "unstamped" CACHE STRING
  "Revision embedded in CSV2 benchmark executables")

add_subdirectory(datasets)
add_subdirectory(current)
add_subdirectory(compare)

if(CSV2_BUILD_BENCHMARK_CHECKS)
  add_subdirectory(checks)
  add_subdirectory(tools)
endif()
