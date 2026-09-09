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

foreach(field IN ITEMS ROWS CELLS ROW_BYTES)
  if(NOT DEFINED CSV2_EXPECTED_${field})
    if(field STREQUAL "ROWS")
      set(CSV2_EXPECTED_${field} 2)
    elseif(field STREQUAL "CELLS")
      set(CSV2_EXPECTED_${field} 6)
    else()
      set(CSV2_EXPECTED_${field} 36)
    endif()
  endif()
endforeach()

set(CSV2_EXPECTED_PROTOCOL csv2-common-v5)
set(CSV2_EXPECTED_INSTRUMENTATION none)
set(CSV2_EXPECTED_CAPABILITIES legacy-reader,legacy-writer,modern-writer)
set(CSV2_EXPECTED_OPERATION "${CSV2_BENCHMARK_OPERATION}")
set(CSV2_EXPECTED_SCOPE writer_only)
set(CSV2_EXPECTED_SOURCE buffer)
set(CSV2_EXPECTED_ITERATIONS 2)
set(CSV2_EXPECTED_TIMED_READER_STEPS 0)
set(CSV2_EXPECTED_TIMED_CHECKSUM_MIX_CALLS 0)

set(CSV2_BENCHMARK_WIRE "${csv2_wire}")
include("${CMAKE_CURRENT_LIST_DIR}/verify_wire.cmake")
