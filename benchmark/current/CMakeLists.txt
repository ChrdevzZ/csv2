include(Csv2BenchmarkDependencies)
csv2_load_google_benchmark()

set(csv2_current_sources
  main.cpp
  context.cpp
  registry.cpp
  support/allocation.cpp
  support/output_buffer.cpp
  support/result.cpp
  kernels/source.cpp
  kernels/traversal.cpp
  kernels/extraction.cpp
  kernels/validation.cpp
  kernels/conversion.cpp
  kernels/ranges.cpp
  kernels/index.cpp
  kernels/writer.cpp)

foreach(csv2_target IN ITEMS
    csv2_benchmark
    csv2_benchmark_allocations
    csv2_benchmark_observer_audit)
  add_executable(${csv2_target} ${csv2_current_sources})
  target_link_libraries(${csv2_target} PRIVATE csv2::csv2 benchmark::benchmark)
  target_include_directories(${csv2_target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_compile_definitions(${csv2_target} PRIVATE
    CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}"
    CSV2_BENCHMARK_DEFAULT_INPUT="${csv2_benchmark_default_fixture}"
    CSV2_HAS_MMAP=${csv2_benchmark_mmap_value}
    $<$<PLATFORM_ID:Windows>:NOMINMAX>)
  csv2_set_test_standard(${csv2_target} ${csv2_current_benchmark_standard})
  csv2_enable_test_options(${csv2_target})
endforeach()

target_compile_definitions(csv2_benchmark_allocations PRIVATE
  CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1)
target_compile_definitions(csv2_benchmark_observer_audit PRIVATE
  CSV2_BENCHMARK_OBSERVER_AUDIT=1)

include(CheckIPOSupported)
check_ipo_supported(RESULT csv2_benchmark_ipo_supported
  OUTPUT csv2_benchmark_ipo_error LANGUAGES CXX)
if(csv2_benchmark_ipo_supported)
  set_property(TARGET csv2_benchmark_observer_audit PROPERTY
    INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
else()
  message(STATUS "CSV2 observer audit IPO unavailable: ${csv2_benchmark_ipo_error}")
endif()
