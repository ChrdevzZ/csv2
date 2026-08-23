set(csv2_required_inputs
  CSV2_BENCHMARK_EXECUTABLE
  CSV2_BENCHMARK_INPUT
  CSV2_BENCHMARK_SOURCE
  CSV2_BENCHMARK_OPERATION
  CSV2_EXPECTED_STATUS)
set(csv2_missing_inputs)
foreach(csv2_required_input IN LISTS csv2_required_inputs)
  if(NOT DEFINED ${csv2_required_input} OR
     "${${csv2_required_input}}" STREQUAL "")
    list(APPEND csv2_missing_inputs "${csv2_required_input}")
  endif()
endforeach()
if(csv2_missing_inputs)
  string(REPLACE ";" ", " csv2_missing_inputs_text
    "${csv2_missing_inputs}")
  message(FATAL_ERROR
    "current failure check is missing required inputs: ${csv2_missing_inputs_text}")
endif()

set(csv2_command
  "${CSV2_BENCHMARK_EXECUTABLE}"
  --csv2-input "${CSV2_BENCHMARK_INPUT}"
  --csv2-source "${CSV2_BENCHMARK_SOURCE}"
  --csv2-operation "${CSV2_BENCHMARK_OPERATION}")
if(DEFINED CSV2_BENCHMARK_MODE AND CSV2_BENCHMARK_MODE STREQUAL "timing")
  list(APPEND csv2_command
    --benchmark_min_time=0.001s
    --benchmark_repetitions=1)
else()
  list(APPEND csv2_command --csv2-verify)
endif()
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
if(NOT csv2_result EQUAL 4)
  message(FATAL_ERROR
    "failing kernel returned ${csv2_result}, expected 4: "
    "${csv2_stdout}${csv2_stderr}")
endif()
if(csv2_stdout MATCHES "protocol=csv2-current-v3")
  message(FATAL_ERROR "failing kernel emitted a success wire: ${csv2_stdout}")
endif()
set(csv2_failure_output "${csv2_stdout}\n${csv2_stderr}")
if(NOT csv2_failure_output MATCHES "${CSV2_EXPECTED_STATUS}")
  message(FATAL_ERROR
    "expected status ${CSV2_EXPECTED_STATUS}, got: ${csv2_failure_output}")
endif()
