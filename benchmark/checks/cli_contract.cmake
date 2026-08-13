if(NOT DEFINED CSV2_BENCHMARK_EXECUTABLE OR
   NOT DEFINED CSV2_BENCHMARK_KIND OR
   NOT DEFINED CSV2_BENCHMARK_INPUT)
  message(FATAL_ERROR "benchmark rejection contract is missing arguments")
endif()

if(CSV2_BENCHMARK_KIND STREQUAL "current-legacy-option")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --csv2-input "${CSV2_BENCHMARK_INPUT}"
      --operation rows_cells
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
elseif(CSV2_BENCHMARK_KIND STREQUAL "common-zero-iterations")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --operation rows_cells --input "${CSV2_BENCHMARK_INPUT}"
      --source buffer --iterations 0
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
else()
  message(FATAL_ERROR "unknown rejection contract: ${CSV2_BENCHMARK_KIND}")
endif()

if(csv2_result EQUAL 0)
  message(FATAL_ERROR "benchmark unexpectedly accepted invalid arguments")
endif()
