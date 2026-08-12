if(NOT 20 IN_LIST csv2_supported_standards)
  message(FATAL_ERROR
    "CSV2_BUILD_BENCHMARKS requires CMake and a compiler with C++20 support")
endif()

add_executable(csv2_benchmark main.cpp)
add_executable(csv2_benchmark_allocations main.cpp)
add_executable(csv2_common_benchmark common_driver.cpp)
target_link_libraries(csv2_common_benchmark PRIVATE csv2::csv2)
set(CSV2_BENCHMARK_REVISION "unstamped" CACHE STRING
  "Revision embedded in the version-neutral benchmark driver")
target_compile_definitions(csv2_common_benchmark PRIVATE
  CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}")
set_target_properties(csv2_common_benchmark PROPERTIES
  CXX_STANDARD 11
  CXX_STANDARD_REQUIRED ON
  CXX_EXTENSIONS OFF)
target_compile_definitions(csv2_benchmark_allocations PRIVATE
  CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1)
foreach(target IN ITEMS csv2_benchmark csv2_benchmark_allocations)
  target_link_libraries(${target} PRIVATE csv2::csv2)
  target_compile_definitions(${target} PRIVATE
    CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}")
  set_target_properties(${target} PROPERTIES
    CXX_STANDARD 20
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF)
endforeach()

if(CSV2_BUILD_TESTS)
  set(csv2_benchmark_fixture ${csv2_SOURCE_DIR}/test/inputs/test_01.csv)
  set(csv2_benchmark_mmap_fixture
      ${CMAKE_CURRENT_BINARY_DIR}/csv2_benchmark_fixture.csv)
  set(csv2_benchmark_quote_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/quote_heavy.csv)
  set(csv2_benchmark_multiline_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/multiline.csv)
  set(csv2_benchmark_crlf_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/crlf.csv)
  # The newline-sensitive source fixtures are excluded from text normalization;
  # keep this no-newline mmap fixture byte-for-byte stable as well.
  file(WRITE ${csv2_benchmark_mmap_fixture} "a,b,c")
  add_test(NAME csv2.benchmark.common_protocol
    COMMAND csv2_common_benchmark --describe)
  set_tests_properties(csv2.benchmark.common_protocol PROPERTIES
    LABELS benchmark-checksum
    PASS_REGULAR_EXPRESSION "protocol=csv2-common-v1")
  add_test(NAME csv2.benchmark.common_rows_cells
    COMMAND csv2_common_benchmark --operation rows_cells
      --input ${csv2_benchmark_fixture} --source buffer --iterations 1)
  set_tests_properties(csv2.benchmark.common_rows_cells PROPERTIES
    LABELS benchmark-checksum
    PASS_REGULAR_EXPRESSION "protocol=csv2-common-v1.*rows=3.*cells=9")
  function(csv2_add_common_benchmark_rejection name value)
    add_test(NAME csv2.benchmark.common_reject.${name}
      COMMAND ${CMAKE_COMMAND}
        -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_common_benchmark>
        -DCSV2_BENCHMARK_INPUT=${csv2_benchmark_fixture}
        -DCSV2_BENCHMARK_VALUE=${value}
        -P ${CMAKE_CURRENT_SOURCE_DIR}/check_common_cli_rejection.cmake)
    set_tests_properties(csv2.benchmark.common_reject.${name} PROPERTIES
      LABELS benchmark-checksum
      TIMEOUT 5)
  endfunction()

  csv2_add_common_benchmark_rejection(iterations_negative -1)
  csv2_add_common_benchmark_rejection(iterations_positive_sign +1)
  csv2_add_common_benchmark_rejection(iterations_zero 0)
  csv2_add_common_benchmark_rejection(iterations_nondigit 1x)
  csv2_add_common_benchmark_rejection(iterations_leading_space <leading-space>)
  csv2_add_common_benchmark_rejection(iterations_trailing_space <trailing-space>)
  csv2_add_common_benchmark_rejection(iterations_overflow 18446744073709551616)
  function(csv2_add_benchmark_checksum operation source checksum)
    add_test(NAME csv2.benchmark.checksum.${operation}
      COMMAND csv2_benchmark --operation ${operation}
        --input ${csv2_benchmark_fixture} --source ${source} --iterations 1
        --expect-checksum ${checksum})
    set_tests_properties(csv2.benchmark.checksum.${operation} PROPERTIES
      LABELS benchmark-checksum)
  endfunction()

  csv2_add_benchmark_checksum(rows_only buffer 8674000034234459039)
  csv2_add_benchmark_checksum(rows_cells buffer 6437334155717714538)
  csv2_add_benchmark_checksum(raw_to_string buffer 4405620607395608627)
  csv2_add_benchmark_checksum(decoded_to_string buffer 4405620607395608627)
  csv2_add_benchmark_checksum(decoded_to_vector buffer 4405620607395608627)
  csv2_add_benchmark_checksum(ranges_pipeline buffer 6437334155717714538)
  csv2_add_benchmark_checksum(integer_conversion buffer 6437334155733299317)
  csv2_add_benchmark_checksum(writer_raw buffer 9730279101474490404)
  csv2_add_benchmark_checksum(writer_escaped buffer 9730279101474490404)
  function(csv2_add_fixture_checksum name operation fixture checksum)
    add_test(NAME csv2.benchmark.fixture.${name}
      COMMAND csv2_benchmark --operation ${operation}
        --input ${fixture} --source buffer --iterations 1
        --expect-checksum ${checksum})
    set_tests_properties(csv2.benchmark.fixture.${name} PROPERTIES
      LABELS benchmark-checksum)
  endfunction()

  function(csv2_add_benchmark_rejection name argument value)
    add_test(NAME csv2.benchmark.reject.${name}
      COMMAND ${CMAKE_COMMAND}
        -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_benchmark>
        -DCSV2_BENCHMARK_INPUT=${csv2_benchmark_fixture}
        -DCSV2_BENCHMARK_ARGUMENT=${argument}
        -DCSV2_BENCHMARK_VALUE=${value}
        -P ${CMAKE_CURRENT_SOURCE_DIR}/check_cli_rejection.cmake)
    set_tests_properties(csv2.benchmark.reject.${name} PROPERTIES
      LABELS benchmark-checksum
      TIMEOUT 5)
  endfunction()

  csv2_add_benchmark_rejection(iterations_negative --iterations -1)
  csv2_add_benchmark_rejection(iterations_positive_sign --iterations +1)
  csv2_add_benchmark_rejection(iterations_zero --iterations 0)
  csv2_add_benchmark_rejection(iterations_nondigit --iterations 1x)
  csv2_add_benchmark_rejection(iterations_leading_space --iterations <leading-space>)
  csv2_add_benchmark_rejection(iterations_trailing_space --iterations <trailing-space>)
  csv2_add_benchmark_rejection(iterations_overflow --iterations 18446744073709551616)
  csv2_add_benchmark_rejection(checksum_negative --expect-checksum -1)
  csv2_add_benchmark_rejection(checksum_positive_sign --expect-checksum +1)
  csv2_add_benchmark_rejection(allocations_negative --expect-allocations -1)
  csv2_add_fixture_checksum(quote_heavy_rows rows_cells
    ${csv2_benchmark_quote_fixture} 8674000034234459038)
  csv2_add_fixture_checksum(multiline_rows rows_cells
    ${csv2_benchmark_multiline_fixture} 8674000034234398225)
  csv2_add_fixture_checksum(crlf_rows rows_cells
    ${csv2_benchmark_crlf_fixture} 12411622248167102744)
  csv2_add_fixture_checksum(quote_heavy_writer writer_escaped
    ${csv2_benchmark_quote_fixture} 11995933538725573646)
  csv2_add_fixture_checksum(multiline_writer writer_escaped
    ${csv2_benchmark_multiline_fixture} 10979403492338463298)
  csv2_add_fixture_checksum(crlf_writer writer_escaped
    ${csv2_benchmark_crlf_fixture} 10184391320815297044)
  add_test(NAME csv2.benchmark.allocations.rows_cells
    COMMAND csv2_benchmark_allocations --operation rows_cells
      --input ${csv2_benchmark_fixture} --source buffer --iterations 1
      --track-allocations --expect-allocations 0)
  set_tests_properties(csv2.benchmark.allocations.rows_cells PROPERTIES
    LABELS benchmark-checksum)
  if(CSV2_HAS_MMAP OR NOT DEFINED CSV2_HAS_MMAP)
    add_test(NAME csv2.benchmark.checksum.map_only
      COMMAND csv2_benchmark --operation map_only
        --input ${csv2_benchmark_mmap_fixture} --source mmap --iterations 1
        --expect-checksum 8674000034234391210)
    set_tests_properties(csv2.benchmark.checksum.map_only PROPERTIES
      LABELS benchmark-checksum)
    add_test(NAME csv2.benchmark.checksum.rows_cells_mmap
      COMMAND csv2_benchmark --operation rows_cells
        --input ${csv2_benchmark_mmap_fixture} --source mmap --iterations 1
        --expect-checksum 8674000034234409885)
    set_tests_properties(csv2.benchmark.checksum.rows_cells_mmap PROPERTIES
      LABELS benchmark-checksum)
  endif()
endif()
