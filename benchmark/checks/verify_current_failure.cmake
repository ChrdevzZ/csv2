if(NOT DEFINED CSV2_BENCHMARK_EXECUTABLE OR
   NOT DEFINED CSV2_BENCHMARK_INPUT OR
   NOT DEFINED CSV2_BENCHMARK_OPERATION OR
   NOT DEFINED CSV2_EXPECTED_STATUS)
  message(FATAL_ERROR "current failure check is missing required inputs")
endif()

set(csv2_command
  "${CSV2_BENCHMARK_EXECUTABLE}"
  --csv2-input "${CSV2_BENCHMARK_INPUT}"
  --csv2-source "${CSV2_BENCHMARK_SOURCE}"
  --csv2-operation "${CSV2_BENCHMARK_OPERATION}"
  --csv2-verify)
if(DEFINED CSV2_EXTRA_ARGUMENT)
  list(APPEND csv2_command "${CSV2_EXTRA_ARGUMENT}")
endif()
if(DEFINED CSV2_EXTRA_VALUE)
  list(APPEND csv2_command "${CSV2_EXTRA_VALUE}")
endif()
if(DEFINED CSV2_EXTRA_ARGUMENT_2)
  list(APPEND csv2_command "${CSV2_EXTRA_ARGUMENT_2}")
endif()
if(DEFINED CSV2_EXTRA_VALUE_2)
  list(APPEND csv2_command "${CSV2_EXTRA_VALUE_2}")
endif()

execute_process(
  COMMAND ${csv2_command}
  RESULT_VARIABLE csv2_result
  OUTPUT_VARIABLE csv2_stdout
  ERROR_VARIABLE csv2_stderr
  TIMEOUT 5)
if(csv2_result EQUAL 0)
  message(FATAL_ERROR "failing kernel returned success: ${csv2_stdout}")
endif()
if(csv2_stdout MATCHES "protocol=csv2-current-v2")
  message(FATAL_ERROR "failing kernel emitted a success wire: ${csv2_stdout}")
endif()
if(NOT csv2_stderr MATCHES "kernel_status=${CSV2_EXPECTED_STATUS}([ \r\n]|$)")
  message(FATAL_ERROR
    "expected kernel_status=${CSV2_EXPECTED_STATUS}, got: ${csv2_stderr}")
endif()
