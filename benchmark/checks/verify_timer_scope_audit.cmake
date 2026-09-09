foreach(required IN ITEMS CSV2_BENCHMARK_EXECUTABLE CSV2_BENCHMARK_INPUT)
  if(NOT DEFINED ${required})
    message(FATAL_ERROR "Missing ${required}")
  endif()
endforeach()

function(csv2_read_wire_field wire name output)
  string(REGEX MATCH "(^|[ \r\n])${name}=([^ \r\n]+)($|[ \r\n])" match "${wire}")
  if(NOT match)
    message(FATAL_ERROR "Missing ${name} in benchmark wire: ${wire}")
  endif()
  set(${output} "${CMAKE_MATCH_2}" PARENT_SCOPE)
endfunction()

function(csv2_run_audit operation expect_traversal_steps)
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --operation "${operation}"
      --input "${CSV2_BENCHMARK_INPUT}"
      --source buffer
      --iterations 1
    RESULT_VARIABLE result
    OUTPUT_VARIABLE wire
    ERROR_VARIABLE error
    TIMEOUT 10)
  if(NOT result EQUAL 0)
    message(FATAL_ERROR "Timer audit failed for ${operation} (${result}): ${error}")
  endif()

  foreach(field IN ITEMS
      protocol instrumentation rows cells timed_reader_steps timed_checksum_mix_calls)
    csv2_read_wire_field("${wire}" "${field}" ${field})
  endforeach()
  if(NOT protocol STREQUAL "csv2-common-v5")
    message(FATAL_ERROR "Unexpected audit protocol: ${protocol}")
  endif()
  if(NOT instrumentation STREQUAL "timer_scope_audit")
    message(FATAL_ERROR "Unexpected audit instrumentation: ${instrumentation}")
  endif()
  if(expect_traversal_steps)
    math(EXPR expected_steps "${rows} + ${cells}")
  else()
    set(expected_steps 0)
  endif()
  if(NOT timed_reader_steps STREQUAL "${expected_steps}")
    message(FATAL_ERROR
      "${operation} Reader-step audit mismatch: expected ${expected_steps}, got ${timed_reader_steps}")
  endif()
  if(NOT timed_checksum_mix_calls STREQUAL "0")
    message(FATAL_ERROR
      "${operation} mixed checksums inside the timer: ${timed_checksum_mix_calls}")
  endif()
endfunction()

csv2_run_audit(rows_cells TRUE)
foreach(writer_operation IN ITEMS
    legacy_writer_raw
    writer_raw_direct
    writer_raw_streamable
    writer_escaped_direct
    writer_escaped_streamable)
  csv2_run_audit(${writer_operation} FALSE)
endforeach()
