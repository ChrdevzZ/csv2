if(NOT DEFINED CSV2_FAILURE_CHECK_SCRIPT)
  message(FATAL_ERROR "failure-check contract is missing its script path")
endif()

execute_process(
  COMMAND "${CMAKE_COMMAND}"
    -DCSV2_BENCHMARK_EXECUTABLE=not-run
    -DCSV2_BENCHMARK_INPUT=not-run.csv
    -DCSV2_BENCHMARK_OPERATION=source/file-read-cached
    -DCSV2_EXPECTED_STATUS=input_open_failed
    -P "${CSV2_FAILURE_CHECK_SCRIPT}"
  RESULT_VARIABLE csv2_result
  OUTPUT_VARIABLE csv2_stdout
  ERROR_VARIABLE csv2_stderr
  TIMEOUT 5)

if(csv2_result EQUAL 0)
  message(FATAL_ERROR "failure check accepted a missing source")
endif()
if(NOT csv2_stderr MATCHES
   "missing required inputs: CSV2_BENCHMARK_SOURCE([ \r\n]|$)")
  message(FATAL_ERROR
    "failure check did not diagnose its missing source: ${csv2_stdout}${csv2_stderr}")
endif()
