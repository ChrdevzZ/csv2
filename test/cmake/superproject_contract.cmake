if(NOT DEFINED CSV2_TEST_CONTRACT_ROOT OR
   NOT DEFINED CSV2_TEST_CONTRACT_SOURCE OR
   NOT DEFINED CSV2_TEST_CONTRACT_CSV2_SOURCE OR
   NOT DEFINED CSV2_TEST_CONTRACT_GENERATOR OR
   NOT DEFINED CSV2_TEST_CONTRACT_MODE)
  message(FATAL_ERROR "The superproject contract is missing required inputs")
endif()

file(REMOVE_RECURSE "${CSV2_TEST_CONTRACT_ROOT}")
set(configure_command
  "${CMAKE_COMMAND}"
  -S "${CSV2_TEST_CONTRACT_SOURCE}"
  -B "${CSV2_TEST_CONTRACT_ROOT}"
  -G "${CSV2_TEST_CONTRACT_GENERATOR}"
  "-DCSV2_SOURCE_DIR=${CSV2_TEST_CONTRACT_CSV2_SOURCE}"
  "-DCSV2_SUPERPROJECT_MODE=${CSV2_TEST_CONTRACT_MODE}")
if(DEFINED CSV2_TEST_CONTRACT_GENERATOR_PLATFORM AND
   NOT CSV2_TEST_CONTRACT_GENERATOR_PLATFORM STREQUAL "")
  list(APPEND configure_command -A "${CSV2_TEST_CONTRACT_GENERATOR_PLATFORM}")
endif()
if(DEFINED CSV2_TEST_CONTRACT_GENERATOR_TOOLSET AND
   NOT CSV2_TEST_CONTRACT_GENERATOR_TOOLSET STREQUAL "")
  list(APPEND configure_command -T "${CSV2_TEST_CONTRACT_GENERATOR_TOOLSET}")
endif()
if(DEFINED CSV2_TEST_CONTRACT_CXX_COMPILER AND
   NOT CSV2_TEST_CONTRACT_CXX_COMPILER STREQUAL "")
  list(APPEND configure_command
    "-DCMAKE_CXX_COMPILER=${CSV2_TEST_CONTRACT_CXX_COMPILER}")
endif()
foreach(tool IN ITEMS RC_COMPILER MT)
  if(DEFINED CSV2_TEST_CONTRACT_CMAKE_${tool} AND
     NOT CSV2_TEST_CONTRACT_CMAKE_${tool} STREQUAL "")
    list(APPEND configure_command
      "-DCMAKE_${tool}=${CSV2_TEST_CONTRACT_CMAKE_${tool}}")
  endif()
endforeach()

execute_process(
  COMMAND ${configure_command}
  RESULT_VARIABLE configure_result
  OUTPUT_VARIABLE configure_stdout
  ERROR_VARIABLE configure_stderr)
set(configure_log "${configure_stdout}\n${configure_stderr}")

if(CSV2_TEST_CONTRACT_MODE STREQUAL "normal")
  if(NOT configure_result STREQUAL "0")
    message(FATAL_ERROR
      "Superproject isolation configuration failed:\n${configure_log}")
  endif()
elseif(CSV2_TEST_CONTRACT_MODE STREQUAL "catch_collision" OR
       CSV2_TEST_CONTRACT_MODE STREQUAL "benchmark_collision")
  if(CSV2_TEST_CONTRACT_MODE STREQUAL "catch_collision")
    set(expected_dependency catch2)
    set(expected_target "Catch2::Catch2WithMain")
  else()
    set(expected_dependency google_benchmark)
    set(expected_target "benchmark::benchmark")
  endif()
  if(configure_result STREQUAL "0")
    message(FATAL_ERROR
      "${expected_dependency} collision contract did not fail closed:\n${configure_log}")
  endif()
  set(expected_diagnostic
    "Cannot load vendored ${expected_dependency}:[ \t\r\n]+target[ \t\r\n]+${expected_target}[ \t\r\n]+already[ \t\r\n]+exists")
  if(NOT configure_log MATCHES "${expected_diagnostic}")
    message(FATAL_ERROR
      "Collision configuration failed for an unrelated reason:\n${configure_log}")
  endif()
else()
  message(FATAL_ERROR "Unknown contract mode ${CSV2_TEST_CONTRACT_MODE}")
endif()
