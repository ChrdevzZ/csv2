cmake_minimum_required(VERSION 3.16)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Csv2TestDependencies)
include(Csv2TestManifest)
include(Csv2TestMatrix)
include(Csv2TestRegistration)

if(CSV2_BUILD_TESTS)
  csv2_configure_python_audits("vendor maintenance safety")
endif()

if(CSV2_BUILD_TESTS AND
   CSV2_TEST_ASSERTION_BACKEND STREQUAL "auto" AND
   14 IN_LIST csv2_supported_standards)
  csv2_load_catch2()
endif()

if(NOT CSV2_BUILD_TESTS)
  if(CSV2_BUILD_FUZZERS)
    add_subdirectory(fuzz)
  endif()
  return()
endif()

if(CSV2_PYTHON_AUDITS_AVAILABLE)
  add_test(NAME csv2.vendor.tool_safety
    COMMAND ${CSV2_PYTHON_EXECUTABLE} -B
      ${csv2_SOURCE_DIR}/tools/vendor/test_update_verification_dependencies.py -v)
  set_tests_properties(csv2.vendor.tool_safety PROPERTIES
    LABELS "vendor-safety;verification"
    TIMEOUT 30)
endif()

add_subdirectory(fixtures)
add_subdirectory(support)
add_subdirectory(runtime)
add_subdirectory(contracts)
add_subdirectory(platform)
add_subdirectory(fuzz)

csv2_add_runtime_matrix()

set(csv2_sanitizer_smoke_runtime_targets
  csv2_runtime_modular_cxx20_normal
  csv2_runtime_single_cxx23_normal
  csv2_runtime_modular_cxx11_no_mmap
  csv2_runtime_single_cxx11_no_exceptions)
set(csv2_sanitizer_smoke_dependencies
  csv2_minitest_registry_capacity
  csv2_minitest_registry_duplicate
  csv2_fuzz_smoke
  csv2_fuzz_writer_smoke)
set(csv2_sanitizer_smoke_missing_runtime_targets)
foreach(target IN LISTS csv2_sanitizer_smoke_runtime_targets)
  if(TARGET ${target})
    list(APPEND csv2_sanitizer_smoke_dependencies ${target})
  else()
    list(APPEND csv2_sanitizer_smoke_missing_runtime_targets ${target})
  endif()
endforeach()

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  list(APPEND csv2_sanitizer_smoke_dependencies
    csv2_mio_windows_api
    csv2_single_header_mio_windows_api)
endif()

if(NOT CSV2_TEST_ASSERTION_BACKEND STREQUAL "minitest")
  add_custom_target(csv2_sanitizer_smoke
    COMMAND ${CMAKE_COMMAND} -E echo
      "csv2_sanitizer_smoke requires CSV2_TEST_ASSERTION_BACKEND=minitest"
    COMMAND ${CMAKE_COMMAND} -E false)
elseif(csv2_sanitizer_smoke_missing_runtime_targets)
  string(JOIN ", " csv2_sanitizer_smoke_missing_message
    ${csv2_sanitizer_smoke_missing_runtime_targets})
  add_custom_target(csv2_sanitizer_smoke
    COMMAND ${CMAKE_COMMAND} -E echo
      "csv2_sanitizer_smoke requires unavailable runtime target(s): ${csv2_sanitizer_smoke_missing_message}"
    COMMAND ${CMAKE_COMMAND} -E false)
else()
  add_custom_target(csv2_sanitizer_smoke
    DEPENDS ${csv2_sanitizer_smoke_dependencies})
endif()

# Preserve the two historical build target names used by downstream CI while
# the executable and CTest identities follow the new matrix naming contract.
if(TARGET csv2_runtime_modular_cxx11_normal)
  add_custom_target(csv2_test DEPENDS csv2_runtime_modular_cxx11_normal)
endif()
if(TARGET csv2_runtime_single_cxx11_normal)
  add_custom_target(csv2_single_header_test
    DEPENDS csv2_runtime_single_cxx11_normal)
endif()
