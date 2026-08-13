if(NOT DEFINED CSV2_BENCHMARK_EXECUTABLE OR NOT DEFINED CSV2_BENCHMARK_INPUT OR
   NOT DEFINED CSV2_BENCHMARK_VALUE)
  message(FATAL_ERROR "common benchmark CLI rejection check is missing an argument")
endif()

if(CSV2_BENCHMARK_VALUE STREQUAL "<leading-space>")
  set(CSV2_BENCHMARK_VALUE " 1")
elseif(CSV2_BENCHMARK_VALUE STREQUAL "<trailing-space>")
  set(CSV2_BENCHMARK_VALUE "1 ")
endif()

execute_process(
  COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
    --operation rows_cells
    --input "${CSV2_BENCHMARK_INPUT}"
    --source buffer
    --iterations "${CSV2_BENCHMARK_VALUE}"
  RESULT_VARIABLE result
  OUTPUT_VARIABLE output
  ERROR_VARIABLE error
  TIMEOUT 5)

if(result EQUAL 0)
  message(FATAL_ERROR "common benchmark accepted --iterations=${CSV2_BENCHMARK_VALUE}")
endif()
if(NOT error MATCHES "usage: csv2_common_benchmark")
  message(FATAL_ERROR
    "common benchmark did not reject --iterations=${CSV2_BENCHMARK_VALUE} during option parsing:\n${error}")
endif()
