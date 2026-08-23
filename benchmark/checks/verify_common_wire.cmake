foreach(required IN ITEMS
    CSV2_BENCHMARK_EXECUTABLE
    CSV2_BENCHMARK_INPUT
    CSV2_BENCHMARK_OPERATION
    CSV2_EXPECTED_CHECKSUM)
  if(NOT DEFINED ${required})
    message(FATAL_ERROR "Missing ${required}")
  endif()
endforeach()

execute_process(
  COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
    --operation "${CSV2_BENCHMARK_OPERATION}"
    --input "${CSV2_BENCHMARK_INPUT}"
    --source buffer
    --iterations 2
  RESULT_VARIABLE csv2_result
  OUTPUT_VARIABLE csv2_wire
  ERROR_VARIABLE csv2_error
  TIMEOUT 10)
if(NOT csv2_result EQUAL 0)
  message(FATAL_ERROR
    "Common benchmark verification failed (${csv2_result}): ${csv2_error}")
endif()

set(csv2_expected_fields
  "protocol=csv2-common-v5"
  "instrumentation=none"
  "capabilities=legacy-reader,legacy-writer,modern-writer"
  "operation=${CSV2_BENCHMARK_OPERATION}"
  "scope=writer_only"
  "source=buffer"
  "iterations=2"
  "rows=2"
  "cells=6"
  "row_bytes=36"
  "timed_reader_steps=0"
  "timed_checksum_mix_calls=0"
  "checksum=${CSV2_EXPECTED_CHECKSUM}")
foreach(expected_field IN LISTS csv2_expected_fields)
  string(REPLACE "=" ";" field_parts "${expected_field}")
  list(GET field_parts 0 field_name)
  list(GET field_parts 1 field_value)
  string(REGEX MATCH
    "(^|[ \r\n])${field_name}=([^ \r\n]+)($|[ \r\n])"
    field_match "${csv2_wire}")
  if(NOT field_match OR NOT CMAKE_MATCH_2 STREQUAL field_value)
    message(FATAL_ERROR
      "Common benchmark ${field_name} mismatch: expected ${field_value}, "
      "got '${CMAKE_MATCH_2}' in ${csv2_wire}")
  endif()
endforeach()
