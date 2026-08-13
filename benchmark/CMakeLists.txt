cmake_minimum_required(VERSION 3.16)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Csv2BenchmarkDependencies)
csv2_load_google_benchmark()

if(NOT 20 IN_LIST csv2_supported_standards)
  message(FATAL_ERROR
    "CSV2_BUILD_BENCHMARKS requires CMake and a compiler with C++20 support")
endif()

# Resolve mmap once at configure time, then compile the benchmark executables
# and register their tests from the same value. The compile probe follows the
# header's auto-detection and also observes a global -DCSV2_HAS_MMAP=0 flag.
if(DEFINED CSV2_HAS_MMAP AND
   NOT CSV2_HAS_MMAP STREQUAL "0" AND
   NOT CSV2_HAS_MMAP STREQUAL "1")
  message(FATAL_ERROR "CSV2_HAS_MMAP must be 0 or 1 when set as a CMake variable")
endif()

if(DEFINED CSV2_HAS_MMAP AND NOT CSV2_HAS_MMAP)
  set(csv2_benchmark_has_mmap FALSE)
else()
  include(CheckCXXSourceCompiles)
  set(csv2_saved_required_definitions ${CMAKE_REQUIRED_DEFINITIONS})
  set(csv2_saved_required_includes ${CMAKE_REQUIRED_INCLUDES})
  if(DEFINED CSV2_HAS_MMAP)
    list(APPEND CMAKE_REQUIRED_DEFINITIONS -DCSV2_HAS_MMAP=1)
  endif()
  list(APPEND CMAKE_REQUIRED_INCLUDES ${csv2_SOURCE_DIR}/include)
  unset(CSV2_BENCHMARK_MMAP_PROBE CACHE)
  check_cxx_source_compiles(
    "#include <csv2/reader.hpp>
#if !CSV2_HAS_MMAP
#error mmap is unavailable
#endif
int main() { csv2::Reader<> reader; (void)reader; return 0; }"
    CSV2_BENCHMARK_MMAP_PROBE)
  set(CMAKE_REQUIRED_DEFINITIONS ${csv2_saved_required_definitions})
  set(CMAKE_REQUIRED_INCLUDES ${csv2_saved_required_includes})
  set(csv2_benchmark_has_mmap ${CSV2_BENCHMARK_MMAP_PROBE})
  if(DEFINED CSV2_HAS_MMAP AND NOT csv2_benchmark_has_mmap)
    message(FATAL_ERROR "CSV2_HAS_MMAP=1 was requested, but mmap is unavailable")
  endif()
endif()

if(csv2_benchmark_has_mmap)
  set(csv2_benchmark_mmap_value 1)
else()
  set(csv2_benchmark_mmap_value 0)
endif()

add_executable(csv2_benchmark main.cpp)
add_executable(csv2_benchmark_allocations main.cpp)
add_executable(csv2_common_benchmark common_driver.cpp)
target_link_libraries(csv2_common_benchmark PRIVATE csv2::csv2)
set(CSV2_BENCHMARK_REVISION "unstamped" CACHE STRING
  "Revision embedded in the version-neutral benchmark driver")
target_compile_definitions(csv2_common_benchmark PRIVATE
  CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}"
  CSV2_BENCHMARK_ENABLE_MODERN_WRITER_OPERATIONS=1
  CSV2_HAS_MMAP=${csv2_benchmark_mmap_value})
csv2_set_test_standard(csv2_common_benchmark 11)
csv2_enable_test_options(csv2_common_benchmark)
target_compile_definitions(csv2_benchmark_allocations PRIVATE
  CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1)
foreach(target IN ITEMS csv2_benchmark csv2_benchmark_allocations)
  target_link_libraries(${target} PRIVATE csv2::csv2)
  target_compile_definitions(${target} PRIVATE
    CSV2_BENCHMARK_REVISION="${CSV2_BENCHMARK_REVISION}"
    CSV2_HAS_MMAP=${csv2_benchmark_mmap_value})
  csv2_set_test_standard(${target} 20)
  csv2_enable_test_options(${target})
endforeach()

if(CSV2_BUILD_BENCHMARK_CHECKS)
  find_package(Python3 3.10 COMPONENTS Interpreter QUIET)
  if(Python3_Interpreter_FOUND)
    add_test(NAME csv2.benchmark.tooling_contract
      COMMAND ${Python3_EXECUTABLE}
        ${csv2_SOURCE_DIR}/benchmark/test_collect_metrics.py -v)
    set_tests_properties(csv2.benchmark.tooling_contract PROPERTIES
      LABELS benchmark-checksum)
  endif()

  set(csv2_benchmark_fixture ${csv2_SOURCE_DIR}/test/inputs/test_01.csv)
  set(csv2_benchmark_mmap_fixture
      ${CMAKE_CURRENT_BINARY_DIR}/csv2_benchmark_fixture.csv)
  set(csv2_benchmark_quote_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/quote_heavy.csv)
  set(csv2_benchmark_multiline_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/multiline.csv)
  set(csv2_benchmark_crlf_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/crlf.csv)
  set(csv2_benchmark_doubled_quotes_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/doubled_quotes.csv)
  set(csv2_benchmark_trailing_empty_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/trailing_empty.csv)
  set(csv2_benchmark_long_field_fixture
      ${CMAKE_CURRENT_SOURCE_DIR}/fixtures/long_field.csv)
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
  foreach(operation IN ITEMS
      legacy_writer_raw
      writer_raw_direct
      writer_raw_streamable
      writer_escaped_direct
      writer_escaped_streamable)
    add_test(NAME csv2.benchmark.common_${operation}
      COMMAND csv2_common_benchmark --operation ${operation}
        --input ${csv2_benchmark_fixture} --source buffer --iterations 1)
    set_tests_properties(csv2.benchmark.common_${operation} PROPERTIES
      LABELS benchmark-checksum
      PASS_REGULAR_EXPRESSION
        "protocol=csv2-common-v1.*scope=writer_only.*rows=3.*cells=9")
  endforeach()
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
  csv2_add_benchmark_checksum(writer_raw_direct buffer 9730279101474490404)
  csv2_add_benchmark_checksum(writer_raw_streamable buffer 9730279101474490404)
  csv2_add_benchmark_checksum(writer_escaped_direct buffer 9730279101474490404)
  csv2_add_benchmark_checksum(writer_escaped_streamable buffer 9730279101474490404)
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
  function(csv2_add_writer_fixture_checksums name fixture raw_checksum escaped_checksum)
    foreach(operation IN ITEMS writer_raw_direct writer_raw_streamable)
      csv2_add_fixture_checksum(${name}_${operation} ${operation}
        ${fixture} ${raw_checksum})
    endforeach()
    foreach(operation IN ITEMS writer_escaped_direct writer_escaped_streamable)
      csv2_add_fixture_checksum(${name}_${operation} ${operation}
        ${fixture} ${escaped_checksum})
    endforeach()
  endfunction()

  csv2_add_writer_fixture_checksums(quote_heavy ${csv2_benchmark_quote_fixture}
    11995933538725573646 11995933538725573646)
  csv2_add_writer_fixture_checksums(multiline ${csv2_benchmark_multiline_fixture}
    10979403492338463298 10979403492338463298)
  csv2_add_writer_fixture_checksums(crlf ${csv2_benchmark_crlf_fixture}
    10184391320815297044 10184391320815297044)
  csv2_add_writer_fixture_checksums(doubled_quotes ${csv2_benchmark_doubled_quotes_fixture}
    8420966736546147094 8420966736546147094)
  csv2_add_writer_fixture_checksums(trailing_empty ${csv2_benchmark_trailing_empty_fixture}
    1350449405305950233 1350449405305950233)
  csv2_add_writer_fixture_checksums(long_field ${csv2_benchmark_long_field_fixture}
    12182800595363329554 12182800595363329554)
  add_test(NAME csv2.benchmark.allocations.rows_cells
    COMMAND csv2_benchmark_allocations --operation rows_cells
      --input ${csv2_benchmark_fixture} --source buffer --iterations 1
      --track-allocations --expect-allocations 0)
  set_tests_properties(csv2.benchmark.allocations.rows_cells PROPERTIES
    LABELS benchmark-checksum)
  foreach(operation IN ITEMS writer_raw_direct writer_escaped_direct)
    add_test(NAME csv2.benchmark.allocations.${operation}
      COMMAND csv2_benchmark_allocations --operation ${operation}
        --input ${csv2_benchmark_quote_fixture} --source buffer --iterations 1
        --track-allocations --expect-allocations 0)
    set_tests_properties(csv2.benchmark.allocations.${operation} PROPERTIES
      LABELS benchmark-checksum)
  endforeach()
  if(csv2_benchmark_has_mmap)
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
  else()
    add_test(NAME csv2.benchmark.reject.mmap_disabled
      COMMAND csv2_benchmark --operation map_only
        --input ${csv2_benchmark_mmap_fixture} --source mmap --iterations 1)
    set_tests_properties(csv2.benchmark.reject.mmap_disabled PROPERTIES
      LABELS benchmark-checksum
      WILL_FAIL TRUE)
  endif()
endif()
