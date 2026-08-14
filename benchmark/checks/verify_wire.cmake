if(DEFINED CSV2_BENCHMARK_WIRE)
  set(csv2_wire "${CSV2_BENCHMARK_WIRE}")
else()
  foreach(required IN ITEMS
      CSV2_BENCHMARK_EXECUTABLE
      CSV2_BENCHMARK_INPUT
      CSV2_BENCHMARK_SOURCE
      CSV2_BENCHMARK_OPERATION)
    if(NOT DEFINED ${required})
      message(FATAL_ERROR "Missing ${required}")
    endif()
  endforeach()
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --csv2-input "${CSV2_BENCHMARK_INPUT}"
      --csv2-source "${CSV2_BENCHMARK_SOURCE}"
      --csv2-operation "${CSV2_BENCHMARK_OPERATION}"
      --csv2-verify
    RESULT_VARIABLE csv2_result
    OUTPUT_VARIABLE csv2_wire
    ERROR_VARIABLE csv2_error)
  if(NOT csv2_result EQUAL 0)
    message(FATAL_ERROR
      "Benchmark verification failed (${csv2_result}): ${csv2_error}")
  endif()
endif()

foreach(field IN ITEMS PROTOCOL CHECKSUM ROWS CELLS ALLOCATIONS)
  set(expected_variable "CSV2_EXPECTED_${field}")
  if(DEFINED ${expected_variable})
    string(TOLOWER "${field}" field_name)
    string(REGEX MATCH
      "(^|[ \r\n])${field_name}=([^ \r\n]+)($|[ \r\n])"
      field_match "${csv2_wire}")
    if(NOT field_match)
      message(FATAL_ERROR "Benchmark wire has no exact ${field_name} field: ${csv2_wire}")
    endif()
    if(NOT CMAKE_MATCH_2 STREQUAL "${${expected_variable}}")
      message(FATAL_ERROR
        "Benchmark ${field_name} mismatch: expected ${${expected_variable}}, "
        "got ${CMAKE_MATCH_2}")
    endif()
  endif()
endforeach()
