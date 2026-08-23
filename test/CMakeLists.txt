cmake_minimum_required(VERSION 3.16)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Csv2TestDependencies)
include(Csv2TestManifest)
include(Csv2TestMatrix)
include(Csv2TestRegistration)

if(CSV2_BUILD_TESTS)
  csv2_configure_python_audits("vendor maintenance safety")
endif()

if(CSV2_BUILD_TESTS AND 14 IN_LIST csv2_supported_standards)
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

# Preserve the two historical build target names used by downstream CI while
# the executable and CTest identities follow the new matrix naming contract.
if(TARGET csv2_runtime_modular_cxx11_normal)
  add_custom_target(csv2_test DEPENDS csv2_runtime_modular_cxx11_normal)
endif()
if(TARGET csv2_runtime_single_cxx11_normal)
  add_custom_target(csv2_single_header_test
    DEPENDS csv2_runtime_single_cxx11_normal)
endif()
