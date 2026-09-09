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
  set(csv2_expected_result 2)
elseif(CSV2_BENCHMARK_KIND STREQUAL "common-zero-iterations")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --operation rows_cells --input "${CSV2_BENCHMARK_INPUT}"
      --source buffer --iterations 0
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
  set(csv2_expected_result 1)
elseif(CSV2_BENCHMARK_KIND STREQUAL "current-timing-no-operation")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --csv2-input "${CSV2_BENCHMARK_INPUT}"
      --csv2-source buffer
      --benchmark_dry_run
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
  set(csv2_expected_result 2)
elseif(CSV2_BENCHMARK_KIND STREQUAL "current-timing-all-sources")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --csv2-input "${CSV2_BENCHMARK_INPUT}"
      --csv2-operation traversal/rows-cells
      --csv2-source all
      --benchmark_dry_run
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
  set(csv2_expected_result 2)
elseif(CSV2_BENCHMARK_KIND STREQUAL "current-unsupported-list")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --csv2-list --csv2-source file
      --csv2-operation writer/raw-direct
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
  set(csv2_expected_result 2)
elseif(CSV2_BENCHMARK_KIND STREQUAL "current-unsupported-timing")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --csv2-input "${CSV2_BENCHMARK_INPUT}"
      --csv2-source file --csv2-operation writer/raw-direct
      --benchmark_dry_run
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
  set(csv2_expected_result 2)
elseif(CSV2_BENCHMARK_KIND STREQUAL "current-validation-valid_as_invalid")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --csv2-input "${CSV2_BENCHMARK_INPUT}"
      --csv2-source buffer --csv2-operation validation/invalid-early
      --csv2-verify
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
  set(csv2_expected_result 2)
elseif(CSV2_BENCHMARK_KIND STREQUAL "current-validation-invalid_as_valid")
  execute_process(
    COMMAND "${CSV2_BENCHMARK_EXECUTABLE}"
      --csv2-input "${CSV2_BENCHMARK_INPUT}"
      --csv2-source buffer --csv2-operation validation/valid
      --csv2-verify
    RESULT_VARIABLE csv2_result
    TIMEOUT 5)
  set(csv2_expected_result 2)
else()
  message(FATAL_ERROR "unknown rejection contract: ${CSV2_BENCHMARK_KIND}")
endif()

if(NOT csv2_result MATCHES "^[0-9]+$" OR
   NOT csv2_result EQUAL csv2_expected_result)
  message(FATAL_ERROR
    "benchmark rejection returned ${csv2_result}; expected ${csv2_expected_result}")
endif()
