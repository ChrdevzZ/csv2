include(Csv2BenchmarkDependencies)
csv2_load_google_benchmark()

set(csv2_current_core_sources
  context.cpp
  registry.cpp
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

add_library(csv2_benchmark_core OBJECT ${csv2_current_core_sources})
target_link_libraries(csv2_benchmark_core PRIVATE csv2::csv2 benchmark::benchmark)
target_include_directories(csv2_benchmark_core PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_definitions(csv2_benchmark_core PRIVATE
  CSV2_HAS_MMAP=${csv2_benchmark_mmap_value}
  $<$<PLATFORM_ID:Windows>:NOMINMAX>)
csv2_set_test_standard(csv2_benchmark_core ${csv2_current_benchmark_standard})
csv2_enable_test_options(csv2_benchmark_core)

add_library(csv2_benchmark_build_config OBJECT build_config.cpp)
target_include_directories(csv2_benchmark_build_config PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_definitions(csv2_benchmark_build_config PRIVATE
  CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}"
  CSV2_BENCHMARK_DEFAULT_INPUT="${csv2_benchmark_default_fixture}")
csv2_set_test_standard(csv2_benchmark_build_config
  ${csv2_current_benchmark_standard})
csv2_enable_test_options(csv2_benchmark_build_config)

function(csv2_add_current_frontend target)
  add_executable(${target} main.cpp support/allocation.cpp)
  target_link_libraries(${target} PRIVATE
    csv2_benchmark_core
    csv2_benchmark_build_config
    csv2::csv2
    benchmark::benchmark)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_compile_definitions(${target} PRIVATE
    CSV2_HAS_MMAP=${csv2_benchmark_mmap_value}
    $<$<PLATFORM_ID:Windows>:NOMINMAX>)
  csv2_set_test_standard(${target} ${csv2_current_benchmark_standard})
  csv2_enable_test_options(${target})
endfunction()

csv2_add_current_frontend(csv2_benchmark)
csv2_add_current_frontend(csv2_benchmark_allocations)
target_compile_definitions(csv2_benchmark_allocations PRIVATE
  CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1)

# Observer-audit macros affect inline kernel code, and Release IPO must see the
# complete target, so this executable intentionally remains independently built.
add_executable(csv2_benchmark_observer_audit
  main.cpp
  build_config.cpp
  support/allocation.cpp
  ${csv2_current_core_sources})
target_link_libraries(csv2_benchmark_observer_audit PRIVATE
  csv2::csv2 benchmark::benchmark)
target_include_directories(csv2_benchmark_observer_audit PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_definitions(csv2_benchmark_observer_audit PRIVATE
  CSV2_BENCHMARK_OBSERVER_AUDIT=1
  CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}"
  CSV2_BENCHMARK_DEFAULT_INPUT="${csv2_benchmark_default_fixture}"
  CSV2_HAS_MMAP=${csv2_benchmark_mmap_value}
  $<$<PLATFORM_ID:Windows>:NOMINMAX>)
csv2_set_test_standard(csv2_benchmark_observer_audit
  ${csv2_current_benchmark_standard})
csv2_enable_test_options(csv2_benchmark_observer_audit)

include(CheckIPOSupported)
check_ipo_supported(RESULT csv2_benchmark_ipo_supported
  OUTPUT csv2_benchmark_ipo_error LANGUAGES CXX)
if(csv2_benchmark_ipo_supported)
  set_property(TARGET csv2_benchmark_observer_audit PROPERTY
    INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
else()
  message(STATUS "CSV2 observer audit IPO unavailable: ${csv2_benchmark_ipo_error}")
endif()
