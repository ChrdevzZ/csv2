set(csv2_check_fixture
  "${csv2_SOURCE_DIR}/test/fixtures/upstream/test_01.csv")
set(csv2_quote_fixture
  "${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/quote_heavy.csv")

add_executable(csv2_benchmark_writer_allocations
  writer_allocations.cpp ../current/support/allocation.cpp)
target_link_libraries(csv2_benchmark_writer_allocations PRIVATE
  csv2_benchmark_core csv2_benchmark_build_config csv2::csv2 benchmark::benchmark)
target_compile_definitions(csv2_benchmark_writer_allocations PRIVATE
  CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1
  CSV2_HAS_MMAP=${csv2_benchmark_mmap_value}
  $<$<PLATFORM_ID:Windows>:NOMINMAX>)
csv2_set_test_standard(csv2_benchmark_writer_allocations
  ${csv2_current_benchmark_standard})
csv2_enable_test_options(csv2_benchmark_writer_allocations)
csv2_add_benchmark_check(csv2.benchmark.current.allocations.writer_single_execution
  COMMAND csv2_benchmark_writer_allocations
    ${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/long_field.csv)

csv2_add_benchmark_check(csv2.benchmark.current.default_input
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PROTOCOL=csv2-current-v4
    -DCSV2_EXPECTED_DATASET=short_unquoted.csv
    -DCSV2_EXPECTED_ROWS=128
    -DCSV2_EXPECTED_CELLS=1024
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark>
    --csv2-source buffer
    --csv2-operation traversal/rows-cells --csv2-verify
  TIER portability)

function(csv2_add_exact_current_check name input operation checksum)
  csv2_add_benchmark_check(${name}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_EXPECTED_PROTOCOL=csv2-current-v4
      -DCSV2_EXPECTED_CHECKSUM=${checksum}
      ${ARGN}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark>
      --csv2-input ${input}
      --csv2-source buffer
      --csv2-operation ${operation} --csv2-verify
    TIER portability)
endfunction()

csv2_add_exact_current_check(csv2.benchmark.current.checksum.rows_cells
  ${csv2_check_fixture} traversal/rows-cells 638386005512892526
  -DCSV2_EXPECTED_ROWS=3 -DCSV2_EXPECTED_CELLS=9)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.writer_raw
  ${csv2_quote_fixture} writer/raw-direct 12859166230996484343)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.writer_escaped
  ${csv2_quote_fixture} writer/escaped-direct 3103906658680031245)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.integer_conversion
  ${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/numeric.csv
  conversion/integer-bool-error 8166090483508935075)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.validation_valid
  ${csv2_check_fixture} validation/valid 8448068682874244928)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.validation_invalid_early
  ${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/invalid_early.csv
  validation/invalid-early 8448068682924013388)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.validation_invalid_middle
  ${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/invalid_middle.csv
  validation/invalid-middle 8448068682913353024)
csv2_add_exact_current_check(csv2.benchmark.current.checksum.validation_invalid_late
  ${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/invalid_late.csv
  validation/invalid-late 8448068682914525194)

csv2_add_benchmark_check(csv2.benchmark.current.dry_run
  COMMAND csv2_benchmark --csv2-input ${csv2_check_fixture}
    --csv2-source buffer --csv2-operation traversal/rows-cells
    --benchmark_dry_run
  TIER portability)

foreach(csv2_unsupported_mode IN ITEMS list timing)
  csv2_add_benchmark_check(csv2.benchmark.reject.unsupported_${csv2_unsupported_mode}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_benchmark>
      -DCSV2_BENCHMARK_KIND=current-unsupported-${csv2_unsupported_mode}
      -DCSV2_BENCHMARK_INPUT=${csv2_check_fixture}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/cli_contract.cmake
    TIMEOUT 5)
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
  csv2_add_benchmark_check(csv2.benchmark.reject.writer_${csv2_failure}.timing
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_benchmark>
      -DCSV2_BENCHMARK_INPUT=${csv2_quote_fixture}
      -DCSV2_BENCHMARK_SOURCE=buffer
      -DCSV2_BENCHMARK_OPERATION=writer/escaped-direct
      -DCSV2_BENCHMARK_MODE=timing
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
    set(csv2_io_operation source/file-read-cached)
    set(csv2_io_source file)
    set(csv2_io_status input_open_failed)
    set(csv2_io_argument --csv2-test-input-path-after-load)
    set(csv2_io_value ${csv2_missing_input})
  elseif(csv2_io_failure STREQUAL "read")
    set(csv2_io_operation source/file-read-cached)
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
    set(csv2_io_operation source/file-read-cached)
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
  COMMAND ${CMAKE_COMMAND}
    "-DCSV2_POSITIVE_FIELDS=value_observations"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark_observer_audit>
    --csv2-input ${csv2_check_fixture}
    --csv2-source buffer
    --csv2-operation validation/valid
    --csv2-observer-audit)

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.parse
  COMMAND ${CMAKE_COMMAND}
    "-DCSV2_POSITIVE_FIELDS=value_observations"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark_observer_audit>
    --csv2-input ${csv2_check_fixture}
    --csv2-source buffer
    --csv2-operation source/parse-borrowed
    --csv2-observer-audit)

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.extraction
  COMMAND ${CMAKE_COMMAND}
    "-DCSV2_POSITIVE_FIELDS=memory_observations"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark_observer_audit>
    --csv2-input ${csv2_quote_fixture}
    --csv2-source buffer
    --csv2-operation extraction/cell-content/reused-string
    --csv2-observer-audit)

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.file_read
  COMMAND ${CMAKE_COMMAND}
    "-DCSV2_POSITIVE_FIELDS=memory_observations"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark_observer_audit>
    --csv2-input ${csv2_check_fixture}
    --csv2-source file
    --csv2-operation source/file-read-cached
    --csv2-observer-audit)

csv2_add_benchmark_check(csv2.benchmark.current.observer_audit.writer
  COMMAND ${CMAKE_COMMAND}
    "-DCSV2_POSITIVE_FIELDS=value_observations,memory_observations"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark_observer_audit>
    --csv2-input ${csv2_quote_fixture}
    --csv2-source buffer
    --csv2-operation writer/escaped-direct
    --csv2-observer-audit)

csv2_add_benchmark_check(csv2.benchmark.current.preparation.file_read
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PREPARED=metadata-only
    -DCSV2_EXPECTED_DECODED_ROWS=0
    -DCSV2_EXPECTED_STREAMABLE_ROWS=0
    -DCSV2_EXPECTED_OUTPUT_CAPACITY=0
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark>
    --csv2-input ${csv2_check_fixture}
    --csv2-source file
    --csv2-operation source/file-read-cached
    --csv2-preparation-audit)

csv2_add_benchmark_check(csv2.benchmark.current.preparation.traversal
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PREPARED=data,buffer-reader
    -DCSV2_EXPECTED_DECODED_ROWS=0
    -DCSV2_EXPECTED_STREAMABLE_ROWS=0
    -DCSV2_EXPECTED_OUTPUT_CAPACITY=0
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark>
    --csv2-input ${csv2_check_fixture}
    --csv2-source buffer
    --csv2-operation traversal/rows-cells
    --csv2-preparation-audit)

csv2_add_benchmark_check(csv2.benchmark.current.preparation.writer
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PREPARED=data,buffer-reader,decoded-rows,streamable-rows,output
    "-DCSV2_POSITIVE_FIELDS=decoded_rows,streamable_rows,output_capacity"
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark>
    --csv2-input ${csv2_quote_fixture}
    --csv2-source buffer
    --csv2-operation writer/raw-streamable
    --csv2-preparation-audit)

set(csv2_group_checks
  "source/parse-borrowed|buffer|${csv2_check_fixture}"
  "extraction/cell-content/reused-string|buffer|${csv2_quote_fixture}"
  "ranges/pipeline|buffer|${csv2_check_fixture}"
  "index/random-lookup|buffer|${csv2_check_fixture}")
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
endforeach()
set(csv2_group_dry_runs ${csv2_group_checks}
  "conversion/integer-bool-error|buffer|${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/numeric.csv"
  "writer/escaped-direct|buffer|${csv2_quote_fixture}")
foreach(csv2_group_check IN LISTS csv2_group_dry_runs)
  string(REPLACE "|" ";" csv2_group_values "${csv2_group_check}")
  list(GET csv2_group_values 0 csv2_group_operation)
  list(GET csv2_group_values 1 csv2_group_source)
  list(GET csv2_group_values 2 csv2_group_fixture)
  string(REPLACE "/" "." csv2_group_name "${csv2_group_operation}")
  csv2_add_benchmark_check(csv2.benchmark.group.${csv2_group_name}.dry_run
    COMMAND csv2_benchmark --csv2-input ${csv2_group_fixture}
      --csv2-source ${csv2_group_source}
      --csv2-operation ${csv2_group_operation}
      --benchmark_dry_run)
endforeach()

set(csv2_validation_cases
  "valid|${csv2_check_fixture}"
  "invalid-early|${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/invalid_early.csv"
  "invalid-middle|${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/invalid_middle.csv"
  "invalid-late|${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/invalid_late.csv")
foreach(csv2_validation_case IN LISTS csv2_validation_cases)
  string(REPLACE "|" ";" csv2_validation_values "${csv2_validation_case}")
  list(GET csv2_validation_values 0 csv2_validation_scenario)
  list(GET csv2_validation_values 1 csv2_validation_fixture)
  csv2_add_benchmark_check(
    csv2.benchmark.validation.${csv2_validation_scenario}.dry_run
    COMMAND csv2_benchmark --csv2-input ${csv2_validation_fixture}
      --csv2-source buffer
      --csv2-operation validation/${csv2_validation_scenario}
      --benchmark_dry_run)
endforeach()

foreach(csv2_validation_mismatch IN ITEMS valid_as_invalid invalid_as_valid)
  if(csv2_validation_mismatch STREQUAL "valid_as_invalid")
    set(csv2_validation_fixture ${csv2_check_fixture})
    set(csv2_validation_operation validation/invalid-early)
  else()
    set(csv2_validation_fixture
      ${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/invalid_early.csv)
    set(csv2_validation_operation validation/valid)
  endif()
  csv2_add_benchmark_check(csv2.benchmark.reject.validation.${csv2_validation_mismatch}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_benchmark>
      -DCSV2_BENCHMARK_KIND=current-validation-${csv2_validation_mismatch}
      -DCSV2_BENCHMARK_INPUT=${csv2_validation_fixture}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/cli_contract.cmake
    TIMEOUT 5)
endforeach()

foreach(csv2_index_operation IN ITEMS sequential-lookup random-lookup)
  csv2_add_benchmark_check(
    csv2.benchmark.current.allocations.index.${csv2_index_operation}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_EXPECTED_ALLOCATIONS=0
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark_allocations>
      --csv2-input ${csv2_check_fixture}
      --csv2-source buffer
      --csv2-operation index/${csv2_index_operation} --csv2-verify
    TIER portability)
endforeach()

csv2_add_benchmark_check(csv2.benchmark.current.preparation.index.sequential
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PREPARED=data,buffer-reader,buffer-index
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark>
    --csv2-input ${csv2_check_fixture}
    --csv2-source buffer
    --csv2-operation index/sequential-lookup
    --csv2-preparation-audit)

csv2_add_benchmark_check(csv2.benchmark.current.preparation.index.random
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PREPARED=data,buffer-reader,buffer-index,random-positions
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_benchmark>
    --csv2-input ${csv2_check_fixture}
    --csv2-source buffer
    --csv2-operation index/random-lookup
    --csv2-preparation-audit)

foreach(csv2_writer_operation IN ITEMS raw-direct escaped-direct always-direct)
  csv2_add_benchmark_check(csv2.benchmark.current.allocations.${csv2_writer_operation}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_EXPECTED_ALLOCATIONS=0
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark_allocations>
      --csv2-input ${csv2_quote_fixture}
      --csv2-source buffer
      --csv2-operation writer/${csv2_writer_operation} --csv2-verify
    TIER portability)
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
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_EXPECTED_ALLOCATIONS=0
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark_allocations>
      --csv2-input ${csv2_quote_fixture}
      --csv2-source buffer
      --csv2-operation extraction/${csv2_extraction_operation} --csv2-verify)
endforeach()

foreach(csv2_allocating_extraction IN ITEMS
    cell-raw/fresh-string
    cell-decoded/fresh-vector)
  string(REPLACE "/" "." csv2_allocating_extraction_name
    "${csv2_allocating_extraction}")
  csv2_add_benchmark_check(
    csv2.benchmark.current.allocations.positive.${csv2_allocating_extraction_name}
    COMMAND ${CMAKE_COMMAND}
      "-DCSV2_POSITIVE_FIELDS=allocations,allocated_bytes"
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark_allocations>
      --csv2-input ${csv2_SOURCE_DIR}/benchmark/datasets/fixtures/long_field.csv
      --csv2-source buffer
      --csv2-operation extraction/${csv2_allocating_extraction} --csv2-verify
    TIER portability)
endforeach()

set(csv2_zero_allocation_checks
  "source/parse-borrowed|buffer|${csv2_check_fixture}"
  "traversal/rows|buffer|${csv2_check_fixture}"
  "traversal/rows-cells|buffer|${csv2_check_fixture}"
  "validation/valid|buffer|${csv2_check_fixture}"
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
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_EXPECTED_ALLOCATIONS=0
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark_allocations>
      --csv2-input ${csv2_zero_fixture}
      --csv2-source ${csv2_zero_source}
      --csv2-operation ${csv2_zero_operation} --csv2-verify)
endforeach()

set(csv2_common_sources buffer)
if(csv2_benchmark_has_mmap)
  set(csv2_common_sources buffer+mmap)
endif()
csv2_add_benchmark_check(csv2.benchmark.common.protocol
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PROTOCOL=csv2-common-v5
    -DCSV2_EXPECTED_INSTRUMENTATION=none
    -DCSV2_EXPECTED_CAPABILITIES=legacy-reader,legacy-writer,modern-writer
    -DCSV2_REQUIRED_OPERATION_CONTRACT=rows_cells:traversal_only:${csv2_common_sources}:csv2.traversal.rows-cells.v1:input_corpus
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_common_benchmark> --describe
  TIER portability)
csv2_add_benchmark_check(csv2.benchmark.common.rows_cells
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PROTOCOL=csv2-common-v5
    -DCSV2_EXPECTED_INSTRUMENTATION=none
    -DCSV2_EXPECTED_SEMANTIC_CASE_ID=csv2.traversal.rows-cells.v1
    -DCSV2_EXPECTED_ROWS=3
    -DCSV2_EXPECTED_CELLS=9
    -DCSV2_EXPECTED_TIMED_READER_STEPS=0
    -DCSV2_EXPECTED_TIMED_CHECKSUM_MIX_CALLS=0
    -DCSV2_EXPECTED_OPERATION=rows_cells
    -DCSV2_EXPECTED_SCOPE=traversal_only
    -DCSV2_EXPECTED_SOURCE=buffer
    -DCSV2_EXPECTED_ITERATIONS=1
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_common_benchmark> --operation rows_cells --input ${csv2_check_fixture} --source buffer --iterations 1
  TIER portability)
set(csv2_timer_audit_operations
  "rows_cells,legacy_writer_raw,writer_raw_direct,writer_raw_streamable,writer_escaped_direct,writer_escaped_streamable")
if(csv2_benchmark_has_mmap)
  string(APPEND csv2_timer_audit_operations ",legacy_mmap_rows_cells")
endif()
csv2_add_benchmark_check(csv2.benchmark.common.timer_scope_audit.protocol
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_EXPECTED_PROTOCOL=csv2-common-v5
    -DCSV2_EXPECTED_INSTRUMENTATION=timer_scope_audit
    -DCSV2_EXPECTED_CAPABILITIES=legacy-reader,legacy-writer,modern-writer
    -DCSV2_EXPECTED_OPERATIONS=${csv2_timer_audit_operations}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
    -- $<TARGET_FILE:csv2_common_benchmark_timer_audit> --describe)
csv2_add_benchmark_check(csv2.benchmark.common.timer_scope_audit.behavior
  COMMAND ${CMAKE_COMMAND}
    -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_common_benchmark_timer_audit>
    -DCSV2_BENCHMARK_INPUT=${csv2_check_fixture}
    -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_timer_scope_audit.cmake)

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
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_common_wire.cmake
    TIER portability)
endforeach()

# Raw-field and decoded-content writers intentionally produce different bytes.
# These expectations describe literal fixture/output bytes, not another driver.
set(csv2_representation_fixture
  "${csv2_SOURCE_DIR}/benchmark/checks/fixtures/writer_representation.csv")
foreach(csv2_writer_form IN ITEMS direct streamable)
  csv2_add_benchmark_check(csv2.benchmark.current.writer_representation.${csv2_writer_form}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_EXPECTED_SEMANTIC_CASE_ID=csv2.writer.raw-${csv2_writer_form}.decoded-content.v1
      -DCSV2_EXPECTED_SCOPE=writer_only
      -DCSV2_EXPECTED_BYTE_BASIS=input_corpus
      -DCSV2_EXPECTED_CHECKSUM=6787285681050815190
      -DCSV2_EXPECTED_BYTES=8
      -DCSV2_EXPECTED_ROWS=2
      -DCSV2_EXPECTED_CELLS=2
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark>
      --csv2-input ${csv2_representation_fixture}
      --csv2-source buffer
      --csv2-operation writer/raw-${csv2_writer_form} --csv2-verify
    TIER portability)
  csv2_add_benchmark_check(csv2.benchmark.common.writer_representation.${csv2_writer_form}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_BENCHMARK_EXECUTABLE=$<TARGET_FILE:csv2_common_benchmark>
      -DCSV2_BENCHMARK_INPUT=${csv2_representation_fixture}
      -DCSV2_BENCHMARK_OPERATION=writer_raw_${csv2_writer_form}
      -DCSV2_EXPECTED_SEMANTIC_CASE_ID=csv2.writer.raw-${csv2_writer_form}.raw-fields.v1
      -DCSV2_EXPECTED_CHECKSUM=10850464182905031630
      -DCSV2_EXPECTED_BYTES=13
      -DCSV2_EXPECTED_ROWS=4
      -DCSV2_EXPECTED_CELLS=4
      -DCSV2_EXPECTED_ROW_BYTES=22
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_common_wire.cmake
    TIER portability)
endforeach()

if(csv2_benchmark_has_mmap)
  csv2_add_benchmark_check(csv2.benchmark.current.mmap
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_EXPECTED_PROTOCOL=csv2-current-v4
      -DCSV2_EXPECTED_SOURCE=mmap
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark>
      --csv2-input ${csv2_check_fixture}
      --csv2-source mmap
      --csv2-operation traversal/rows-cells --csv2-verify
    TIER portability)
  csv2_add_benchmark_check(csv2.benchmark.current.preparation.mmap_pretouched
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_EXPECTED_PREPARED=mapping,pretouched-mapping
      -DCSV2_EXPECTED_DECODED_ROWS=0
      -DCSV2_EXPECTED_STREAMABLE_ROWS=0
      -DCSV2_EXPECTED_OUTPUT_CAPACITY=0
      -P ${CMAKE_CURRENT_SOURCE_DIR}/verify_wire.cmake
      -- $<TARGET_FILE:csv2_benchmark>
      --csv2-input ${csv2_check_fixture}
      --csv2-source mmap
      --csv2-operation source/mmap-touch-pretouched
      --csv2-preparation-audit)
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
  csv2_add_benchmark_check(csv2.benchmark.current.external_collector
    COMMAND ${CSV2_PYTHON_EXECUTABLE} -B
      ${csv2_SOURCE_DIR}/benchmark/collect_metrics.py
      --external-artifacts
      --executable $<TARGET_FILE:csv2_benchmark>
      --allocation-executable $<TARGET_FILE:csv2_benchmark_allocations>
      --revision ${CSV2_BENCHMARK_REVISION}
      --compiler-executable ${CMAKE_CXX_COMPILER}
      --input ${csv2_check_fixture}
      --operation traversal/rows-cells --source buffer
      --runs 1 --minimum-time 0.001s --warmup-seconds 0
      --skip-pmu --skip-rss --skip-size
      --output ${CMAKE_CURRENT_BINARY_DIR}/external-metrics-$<CONFIG>.json
    TIER portability)
  csv2_add_benchmark_check(csv2.benchmark.current.case_manifest.registry
    COMMAND ${CSV2_PYTHON_EXECUTABLE} -B
      ${CMAKE_CURRENT_SOURCE_DIR}/verify_case_manifest.py
      --executable $<TARGET_FILE:csv2_benchmark>
      --source-root ${csv2_SOURCE_DIR}
      --manifest ${CMAKE_CURRENT_SOURCE_DIR}/case_manifest.json
      --registry-only
    TIER portability)
  csv2_add_benchmark_check(csv2.benchmark.current.case_manifest.execute
    COMMAND ${CSV2_PYTHON_EXECUTABLE} -B
      ${CMAKE_CURRENT_SOURCE_DIR}/verify_case_manifest.py
      --executable $<TARGET_FILE:csv2_benchmark>
      --source-root ${csv2_SOURCE_DIR}
      --manifest ${CMAKE_CURRENT_SOURCE_DIR}/case_manifest.json
    TIMEOUT 120)
  csv2_add_benchmark_check(csv2.benchmark.current.checksum.manifest
    COMMAND ${CSV2_PYTHON_EXECUTABLE} -B
      ${CMAKE_CURRENT_SOURCE_DIR}/verify_expected_checksums.py
      --executable $<TARGET_FILE:csv2_benchmark>
      --source-root ${csv2_SOURCE_DIR}
      --manifest ${CMAKE_CURRENT_SOURCE_DIR}/expected_checksums.json
      --revision ${CSV2_BENCHMARK_REVISION})
endif()
