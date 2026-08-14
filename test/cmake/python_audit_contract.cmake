if(NOT DEFINED CSV2_TEST_CONTRACT_ROOT OR
   NOT DEFINED CSV2_TEST_CONTRACT_CSV2_SOURCE OR
   NOT DEFINED CSV2_TEST_CONTRACT_GENERATOR OR
   NOT DEFINED CSV2_TEST_CONTRACT_MODE)
  message(FATAL_ERROR "The Python audit contract is missing required inputs")
endif()

file(REMOVE_RECURSE "${CSV2_TEST_CONTRACT_ROOT}")
set(profile quick)
set(require_python OFF)
if(CSV2_TEST_CONTRACT_MODE STREQUAL "full_required")
  set(profile full)
elseif(CSV2_TEST_CONTRACT_MODE STREQUAL "explicit_required")
  set(require_python ON)
elseif(NOT CSV2_TEST_CONTRACT_MODE STREQUAL "quick_warning")
  message(FATAL_ERROR "Unknown Python audit contract mode")
endif()

set(configure_command
  "${CMAKE_COMMAND}"
  -S "${CSV2_TEST_CONTRACT_CSV2_SOURCE}"
  -B "${CSV2_TEST_CONTRACT_ROOT}"
  -G "${CSV2_TEST_CONTRACT_GENERATOR}"
  -DCSV2_BUILD_TESTS=ON
  -DCSV2_BUILD_BENCHMARKS=OFF
  "-DCSV2_VERIFICATION_PROFILE=${profile}"
  "-DCSV2_REQUIRE_PYTHON_AUDITS=${require_python}"
  -DCMAKE_DISABLE_FIND_PACKAGE_Python3=ON)
if(DEFINED CSV2_TEST_CONTRACT_GENERATOR_PLATFORM AND
   NOT CSV2_TEST_CONTRACT_GENERATOR_PLATFORM STREQUAL "")
  list(APPEND configure_command -A "${CSV2_TEST_CONTRACT_GENERATOR_PLATFORM}")
endif()
if(DEFINED CSV2_TEST_CONTRACT_GENERATOR_TOOLSET AND
   NOT CSV2_TEST_CONTRACT_GENERATOR_TOOLSET STREQUAL "")
  list(APPEND configure_command -T "${CSV2_TEST_CONTRACT_GENERATOR_TOOLSET}")
endif()
foreach(tool IN ITEMS CXX_COMPILER RC_COMPILER MT)
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

if(CSV2_TEST_CONTRACT_MODE STREQUAL "quick_warning")
  if(NOT configure_result EQUAL 0 OR
     NOT configure_log MATCHES "quick verification is incomplete" OR
     NOT configure_log MATCHES "vendor integrity/tooling" OR
     NOT configure_log MATCHES "legacy test parity audits")
    message(FATAL_ERROR
      "Missing-Python quick contract failed:\n${configure_log}")
  endif()
elseif(configure_result EQUAL 0 OR
       NOT configure_log MATCHES "Python 3.10\\+ is required" OR
       NOT configure_log MATCHES "full/perf")
  message(FATAL_ERROR
    "Missing-Python required contract did not fail closed:\n${configure_log}")
endif()
