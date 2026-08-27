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

set(csv2_sanitizer_smoke_manifest ${csv2_sanitizer_smoke_targets})
list(LENGTH csv2_sanitizer_smoke_manifest csv2_sanitizer_smoke_manifest_count)
list(REMOVE_DUPLICATES csv2_sanitizer_smoke_manifest)
list(LENGTH csv2_sanitizer_smoke_manifest
  csv2_sanitizer_smoke_unique_manifest_count)
if(NOT csv2_sanitizer_smoke_manifest_count EQUAL
   csv2_sanitizer_smoke_unique_manifest_count)
  message(FATAL_ERROR "csv2_sanitizer_smoke_targets contains duplicates")
endif()
string(REPLACE ";" "\n" csv2_sanitizer_smoke_manifest_text
  "${csv2_sanitizer_smoke_manifest}")
file(GENERATE
  OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/sanitizer-smoke-targets.txt"
  CONTENT "${csv2_sanitizer_smoke_manifest_text}\n")

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

set(csv2_sanitizer_smoke_dependencies)
set(csv2_sanitizer_smoke_missing_targets)
foreach(target IN LISTS csv2_sanitizer_smoke_targets)
  if(TARGET ${target})
    list(APPEND csv2_sanitizer_smoke_dependencies ${target})
  else()
    list(APPEND csv2_sanitizer_smoke_missing_targets ${target})
  endif()
endforeach()

if(NOT CSV2_TEST_ASSERTION_BACKEND STREQUAL "minitest")
  add_custom_target(csv2_sanitizer_smoke
    COMMAND ${CMAKE_COMMAND} -E echo
      "csv2_sanitizer_smoke requires CSV2_TEST_ASSERTION_BACKEND=minitest"
    COMMAND ${CMAKE_COMMAND} -E false)
elseif(csv2_sanitizer_smoke_missing_targets)
  string(JOIN ", " csv2_sanitizer_smoke_missing_message
    ${csv2_sanitizer_smoke_missing_targets})
  add_custom_target(csv2_sanitizer_smoke
    COMMAND ${CMAKE_COMMAND} -E echo
      "csv2_sanitizer_smoke requires unavailable target(s): ${csv2_sanitizer_smoke_missing_message}"
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
