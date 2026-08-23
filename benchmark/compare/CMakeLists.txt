function(csv2_add_common_benchmark target instrumentation modern_writer)
  add_executable(${target} common_driver.cpp)
  target_link_libraries(${target} PRIVATE csv2::csv2)
  target_compile_definitions(${target} PRIVATE
    CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}"
    CSV2_BENCHMARK_TIMER_SCOPE_AUDIT=${instrumentation}
    CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=${modern_writer}
    CSV2_HAS_MMAP=${csv2_benchmark_mmap_value})
  csv2_set_test_standard(${target} 11)
  csv2_enable_test_options(${target})
endfunction()

csv2_add_common_benchmark(csv2_common_benchmark 0 1)
csv2_add_common_benchmark(csv2_common_benchmark_timer_audit 1 1)
