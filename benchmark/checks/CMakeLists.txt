set(csv2_check_fixture
  "${csv2_SOURCE_DIR}/test/fixtures/upstream/test_01.csv")
set(csv2_quote_fixture
  "${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/quote_heavy.csv")

csv2_add_benchmark_check(csv2.benchmark.current.protocol
  COMMAND csv2_benchmark --csv2-input ${csv2_check_fixture}
    --csv2-source buffer --csv2-operation traversal/rows-cells --csv2-verify
  PASS_REGEX "protocol=csv2-current-v2.*rows=3.*cells=9")

function(csv2_add_exact_current_check name input operation checksum)
  csv2_add_benchmark_check(${name}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_benchmark>
      -DCSV2_BENCHMARK_INPUT=${input}
      -DCSV2_BENCHMARK_SOURCE=buffer
      -DCSV2_BENCHMARK_OPERATION=${operation}
      -DCSV2_EXPECTED_PROTOCOL=csv2-current-v2
      -DCSV2_EXPECTED_CHECKSUM=${checksum}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake)
endfunction()

csv2_add_exact_current_check(csv2.benchmark.current.checksum.rows_cells
  ${csv2_check_fixture} traversal/rows-cells 638386005512892526)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.writer_raw
  ${csv2_quote_fixture} writer/raw-direct 12859166230996484343)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.writer_escaped
  ${csv2_quote_fixture} writer/escaped-direct 3103906658680031245)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.integer_conversion
  ${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/numeric.csv
  conversion/integer-bool-error 8166090483508935075)

add_test(NAME csv2.benchmark.reject.checksum-prefix
  COMMAND ${CMAKE_COMMAND}
    "-DCSV2_BENCHMARK_WIRE=protocol=csv2-current-v2 checksum=1239 bytes=1"
    -DCSV2_EXPECTED_PROTOCOL=csv2-current-v2
    -DCSV2_EXPECTED_CHECKSUM=123
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake)
set_tests_properties(csv2.benchmark.reject.checksum-prefix PROPERTIES
  LABELS "benchmark-checksum;quick" WILL_FAIL TRUE TIMEOUT 5)

csv2_add_benchmark_check(csv2.benchmark.current.dry_run
  COMMAND csv2_benchmark --csv2-input ${csv2_check_fixture}
    --csv2-source buffer --csv2-operation traversal/rows-cells
    --benchmark_min_time=0.001s --benchmark_repetitions=1)

foreach(csv2_unsupported_mode IN ITEMS list timing)
  if(csv2_unsupported_mode STREQUAL "list")
    set(csv2_unsupported_command
      csv2_benchmark --csv2-list --csv2-source file
      --csv2-operation writer/raw-direct)
  else()
    set(csv2_unsupported_command
      csv2_benchmark --csv2-input ${csv2_check_fixture}
      --csv2-source file --csv2-operation writer/raw-direct
      --benchmark_min_time=0.001s --benchmark_repetitions=1)
  endif()
  csv2_add_benchmark_check(
    csv2.benchmark.reject.unsupported_${csv2_unsupported_mode}
    COMMAND ${csv2_unsupported_command})
  set_tests_properties(
    csv2.benchmark.reject.unsupported_${csv2_unsupported_mode}
    PROPERTIES WILL_FAIL TRUE)
endforeach()

foreach(csv2_failure IN ITEMS overflow stream)
  set(csv2_failure_extra_definitions)
  if(csv2_failure STREQUAL "overflow")
    set(csv2_failure_argument --csv2-test-output-capacity)
    set(csv2_failure_value 1)
    set(csv2_failure_status output_overflow)
  else()
    set(csv2_failure_argument --csv2-test-output-stream-failure)
    unset(csv2_failure_value)
    set(csv2_failure_status output_stream_failed)
  endif()
  if(DEFINED csv2_failure_value)
    list(APPEND csv2_failure_extra_definitions
      -DCSV2_EXTRA_VALUE=${csv2_failure_value})
  endif()
  csv2_add_benchmark_check(csv2.benchmark.reject.writer_${csv2_failure}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_benchmark>
      -DCSV2_BENCHMARK_INPUT=${csv2_quote_fixture}
      -DCSV2_BENCHMARK_SOURCE=buffer
      -DCSV2_BENCHMARK_OPERATION=writer/escaped-direct
      -DCSV2_EXPECTED_STATUS=${csv2_failure_status}
      -DCSV2_EXTRA_ARGUMENT=${csv2_failure_argument}
      ${csv2_failure_extra_definitions}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_current_failure.cmake)
endforeach()

set(csv2_missing_input
  "${CMAKE_CURRENT_BINARY_DIR}/does-not-exist.csv")
set(csv2_io_failures open read changed)
if(csv2_benchmark_has_mmap)
  list(APPEND csv2_io_failures mmap)
endif()
foreach(csv2_io_failure IN LISTS csv2_io_failures)
  if(csv2_io_failure STREQUAL "open")
    set(csv2_io_operation source/file-read)
    set(csv2_io_source file)
    set(csv2_io_status input_open_failed)
    set(csv2_io_argument --csv2-test-input-path-after-load)
    set(csv2_io_value ${csv2_missing_input})
  elseif(csv2_io_failure STREQUAL "read")
    set(csv2_io_operation source/file-read)
    set(csv2_io_source file)
    set(csv2_io_status input_read_failed)
    set(csv2_io_argument --csv2-test-input-read-failure)
    unset(csv2_io_value)
  elseif(csv2_io_failure STREQUAL "mmap")
    set(csv2_io_operation source/mmap-open)
    set(csv2_io_source mmap)
    set(csv2_io_status mmap_failed)
    set(csv2_io_argument --csv2-test-input-path-after-load)
    set(csv2_io_value ${csv2_missing_input})
  else()
    set(csv2_io_operation source/file-read)
    set(csv2_io_source file)
    set(csv2_io_status input_changed)
    set(csv2_io_argument --csv2-test-input-path-after-load)
    set(csv2_io_value ${csv2_quote_fixture})
  endif()
  set(csv2_io_extra_definitions)
  if(DEFINED csv2_io_value)
    list(APPEND csv2_io_extra_definitions -DCSV2_EXTRA_VALUE=${csv2_io_value})
  endif()
  csv2_add_benchmark_check(csv2.benchmark.reject.io_${csv2_io_failure}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_benchmark>
      -DCSV2_BENCHMARK_INPUT=${csv2_check_fixture}
      -DCSV2_BENCHMARK_SOURCE=${csv2_io_source}
      -DCSV2_BENCHMARK_OPERATION=${csv2_io_operation}
      -DCSV2_EXPECTED_STATUS=${csv2_io_status}
      -DCSV2_EXTRA_ARGUMENT=${csv2_io_argument}
      ${csv2_io_extra_definitions}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_current_failure.cmake)
endforeach()

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.validation
  COMMAND csv2_benchmark_observer_audit --csv2-input ${csv2_check_fixture}
    --csv2-source buffer --csv2-operation validation/strict
    --csv2-observer-audit
  PASS_REGEX "value_observations=[1-9][0-9]*")

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.parse
  COMMAND csv2_benchmark_observer_audit --csv2-input ${csv2_check_fixture}
    --csv2-source buffer --csv2-operation source/parse-borrowed
    --csv2-observer-audit
  PASS_REGEX "value_observations=[1-9][0-9]*")

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.extraction
  COMMAND csv2_benchmark_observer_audit --csv2-input ${csv2_quote_fixture}
    --csv2-source buffer --csv2-operation extraction/cell-content/reused-string
    --csv2-observer-audit
  PASS_REGEX "memory_observations=[1-9][0-9]*")

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.file_read
  COMMAND csv2_benchmark_observer_audit --csv2-input ${csv2_check_fixture}
    --csv2-source file --csv2-operation source/file-read
    --csv2-observer-audit
  PASS_REGEX "memory_observations=[1-9][0-9]*")

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.writer
  COMMAND csv2_benchmark_observer_audit --csv2-input ${csv2_quote_fixture}
    --csv2-source buffer --csv2-operation writer/escaped-direct
    --csv2-observer-audit
  PASS_REGEX
    "value_observations=[1-9][0-9]* memory_observations=[1-9][0-9]*")

csv2_add_benchmark_check(csv2.benchmark.current.preparation.file_read
  COMMAND csv2_benchmark --csv2-input ${csv2_check_fixture}
    --csv2-source file --csv2-operation source/file-read
    --csv2-preparation-audit
  PASS_REGEX "prepared=metadata-only decoded_rows=0 streamable_rows=0 output_capacity=0")

csv2_add_benchmark_check(csv2.benchmark.current.preparation.traversal
  COMMAND csv2_benchmark --csv2-input ${csv2_check_fixture}
    --csv2-source buffer --csv2-operation traversal/rows-cells
    --csv2-preparation-audit
  PASS_REGEX "prepared=data,buffer-reader decoded_rows=0 streamable_rows=0 output_capacity=0")

csv2_add_benchmark_check(csv2.benchmark.current.preparation.writer
  COMMAND csv2_benchmark --csv2-input ${csv2_quote_fixture}
    --csv2-source buffer --csv2-operation writer/raw-streamable
    --csv2-preparation-audit
  PASS_REGEX
    "prepared=data,buffer-reader,decoded-rows,streamable-rows,output decoded_rows=[1-9][0-9]* streamable_rows=[1-9][0-9]* output_capacity=[1-9][0-9]*")

set(csv2_group_checks
  "source/parse-borrowed|buffer|${csv2_check_fixture}"
  "traversal/rows-cells|buffer|${csv2_check_fixture}"
  "extraction/cell-content/reused-string|buffer|${csv2_quote_fixture}"
  "validation/strict|buffer|${csv2_check_fixture}"
  "conversion/integer-bool-error|buffer|${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/numeric.csv"
  "ranges/pipeline|buffer|${csv2_check_fixture}"
  "index/random-lookup|buffer|${csv2_check_fixture}"
  "writer/escaped-direct|buffer|${csv2_quote_fixture}")
foreach(csv2_group_check IN LISTS csv2_group_checks)
  string(REPLACE "|" ";" csv2_group_values "${csv2_group_check}")
  list(GET csv2_group_values 0 csv2_group_operation)
  list(GET csv2_group_values 1 csv2_group_source)
  list(GET csv2_group_values 2 csv2_group_fixture)
  string(REPLACE "/" "." csv2_group_name "${csv2_group_operation}")
  csv2_add_benchmark_check(csv2.benchmark.group.${csv2_group_name}.verify
    COMMAND csv2_benchmark --csv2-input ${csv2_group_fixture}
      --csv2-source ${csv2_group_source}
      --csv2-operation ${csv2_group_operation} --csv2-verify)
  csv2_add_benchmark_check(csv2.benchmark.group.${csv2_group_name}.dry_run
    COMMAND csv2_benchmark --csv2-input ${csv2_group_fixture}
      --csv2-source ${csv2_group_source}
      --csv2-operation ${csv2_group_operation}
      --benchmark_min_time=0.001s --benchmark_repetitions=1)
endforeach()

foreach(csv2_index_operation IN ITEMS sequential-lookup random-lookup)
  csv2_add_benchmark_check(
    csv2.benchmark.current.allocations.index.${csv2_index_operation}
    COMMAND csv2_benchmark_allocations --csv2-input ${csv2_check_fixture}
      --csv2-source buffer --csv2-operation index/${csv2_index_operation}
      --csv2-verify
    PASS_REGEX "allocations=0")
endforeach()

csv2_add_benchmark_check(csv2.benchmark.current.preparation.index.sequential
  COMMAND csv2_benchmark --csv2-input ${csv2_check_fixture}
    --csv2-source buffer --csv2-operation index/sequential-lookup
    --csv2-preparation-audit
  PASS_REGEX "prepared=data,buffer-reader,buffer-index")

csv2_add_benchmark_check(csv2.benchmark.current.preparation.index.random
  COMMAND csv2_benchmark --csv2-input ${csv2_check_fixture}
    --csv2-source buffer --csv2-operation index/random-lookup
    --csv2-preparation-audit
  PASS_REGEX "prepared=data,buffer-reader,buffer-index,random-positions")

foreach(csv2_writer_operation IN ITEMS raw-direct escaped-direct always-direct)
  csv2_add_benchmark_check(csv2.benchmark.current.allocations.${csv2_writer_operation}
    COMMAND csv2_benchmark_allocations --csv2-input ${csv2_quote_fixture}
      --csv2-source buffer --csv2-operation writer/${csv2_writer_operation}
      --csv2-verify
    PASS_REGEX "allocations=0")
endforeach()

foreach(csv2_extraction_operation IN ITEMS
    row-raw/reused-string
    cell-raw/reused-string
    cell-decoded/reused-string
    cell-decoded/reused-vector
    cell-content/reused-string)
  string(REPLACE "/" "." csv2_extraction_name "${csv2_extraction_operation}")
  csv2_add_benchmark_check(
    csv2.benchmark.current.allocations.extraction.${csv2_extraction_name}
    COMMAND csv2_benchmark_allocations --csv2-input ${csv2_quote_fixture}
      --csv2-source buffer
      --csv2-operation extraction/${csv2_extraction_operation}
      --csv2-verify
    PASS_REGEX "allocations=0")
endforeach()

set(csv2_zero_allocation_checks
  "source/parse-borrowed|buffer|${csv2_check_fixture}"
  "traversal/rows|buffer|${csv2_check_fixture}"
  "traversal/rows-cells|buffer|${csv2_check_fixture}"
  "validation/strict|buffer|${csv2_check_fixture}"
  "conversion/integer-bool-error|buffer|${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/numeric.csv"
  "ranges/pipeline|buffer|${csv2_check_fixture}")
if(csv2_benchmark_has_mmap)
  list(APPEND csv2_zero_allocation_checks
    "traversal/rows|mmap|${csv2_check_fixture}"
    "traversal/rows-cells|mmap|${csv2_check_fixture}")
endif()
foreach(csv2_zero_check IN LISTS csv2_zero_allocation_checks)
  string(REPLACE "|" ";" csv2_zero_values "${csv2_zero_check}")
  list(GET csv2_zero_values 0 csv2_zero_operation)
  list(GET csv2_zero_values 1 csv2_zero_source)
  list(GET csv2_zero_values 2 csv2_zero_fixture)
  string(REPLACE "/" "." csv2_zero_name "${csv2_zero_operation}")
  csv2_add_benchmark_check(
    csv2.benchmark.current.allocations.${csv2_zero_name}.${csv2_zero_source}
    COMMAND csv2_benchmark_allocations --csv2-input ${csv2_zero_fixture}
      --csv2-source ${csv2_zero_source}
      --csv2-operation ${csv2_zero_operation}
      --csv2-verify
    PASS_REGEX "allocations=0")
endforeach()

csv2_add_benchmark_check(csv2.benchmark.common.protocol
  COMMAND csv2_common_benchmark --describe
  PASS_REGEX "protocol=csv2-common-v3.*operation_contracts=rows_cells:traversal_only:")
csv2_add_benchmark_check(csv2.benchmark.common.rows_cells
  COMMAND csv2_common_benchmark --operation rows_cells
    --input ${csv2_check_fixture} --source buffer --iterations 1
  PASS_REGEX "protocol=csv2-common-v3.*rows=3.*cells=9.*timed_reader_steps=[1-9][0-9]*")

foreach(csv2_common_writer_operation IN ITEMS
    legacy_writer_raw
    writer_raw_direct
    writer_raw_streamable
    writer_escaped_direct
    writer_escaped_streamable)
  csv2_add_benchmark_check(
    csv2.benchmark.common.${csv2_common_writer_operation}.checksum
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_common_benchmark>
      -DCSV2_BENCHMARK_INPUT=${csv2_quote_fixture}
      -DCSV2_BENCHMARK_OPERATION=${csv2_common_writer_operation}
      -DCSV2_EXPECTED_CHECKSUM=11995933538725573646
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_common_wire.cmake)
endforeach()

if(csv2_benchmark_has_mmap)
  csv2_add_benchmark_check(csv2.benchmark.current.mmap
    COMMAND csv2_benchmark --csv2-input ${csv2_check_fixture}
      --csv2-source mmap --csv2-operation traversal/rows-cells --csv2-verify
    PASS_REGEX "protocol=csv2-current-v2.*source=mmap")
endif()

foreach(csv2_contract IN ITEMS
    current-legacy-option
    current-timing-no-operation
    current-timing-all-sources
    common-zero-iterations)
  if(csv2_contract MATCHES "^current-")
    set(csv2_contract_target csv2_benchmark)
  else()
    set(csv2_contract_target csv2_common_benchmark)
  endif()
  csv2_add_benchmark_check(csv2.benchmark.reject.${csv2_contract}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:${csv2_contract_target}>
      -DCSV2_BENCHMARK_KIND=${csv2_contract}
      -DCSV2_BENCHMARK_INPUT=${csv2_check_fixture}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/cli_contract.cmake
    TIMEOUT 5)
endforeach()

if(CSV2_PYTHON_AUDITS_AVAILABLE)
  csv2_add_benchmark_check(csv2.benchmark.current.checksum.manifest
    COMMAND ${CSV2_PYTHON_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/verify_expected_checksums.py
      --executable $<TARGET_FILE:csv2_benchmark>
      --source-root ${csv2_SOURCE_DIR}
      --manifest ${CMAKE_CURRENT_SOURCE_DIR}/expected_checksums.json)
  csv2_add_benchmark_check(csv2.benchmark.corpus.reproducible
    COMMAND ${CSV2_PYTHON_EXECUTABLE}
      ${csv2_SOURCE_DIR}/benchmark/datasets/generate.py --check)
endif()
