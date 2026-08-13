cmake_minimum_required(VERSION 3.16)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Csv2BenchmarkFeatures)
include(Csv2BenchmarkProfile)
include(Csv2BenchmarkRegistration)

csv2_detect_benchmark_features()
csv2_configure_benchmark_profile()

set(CSV2_BENCHMARK_REVISION "unstamped" CACHE STRING
  "Revision embedded in CSV2 benchmark executables")

add_subdirectory(datasets)
add_subdirectory(current)

# Keep the existing C++11 comparison driver available until its protocol and
# tooling move together in the next atomic commit.
add_executable(csv2_common_benchmark common_driver.cpp)
target_link_libraries(csv2_common_benchmark PRIVATE csv2::csv2)
target_compile_definitions(csv2_common_benchmark PRIVATE
  CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}"
  CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1
  CSV2_HAS_MMAP=${csv2_benchmark_mmap_value})
csv2_set_test_standard(csv2_common_benchmark 11)
csv2_enable_test_options(csv2_common_benchmark)

if(CSV2_BUILD_BENCHMARK_CHECKS)
  add_subdirectory(checks)
endif()
