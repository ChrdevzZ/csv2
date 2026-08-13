add_executable(csv2_common_benchmark common_driver.cpp)
target_link_libraries(csv2_common_benchmark PRIVATE csv2::csv2)
target_compile_definitions(csv2_common_benchmark PRIVATE
  CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}"
  CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1
  CSV2_HAS_MMAP=${csv2_benchmark_mmap_value})
csv2_set_test_standard(csv2_common_benchmark 11)
csv2_enable_test_options(csv2_common_benchmark)
