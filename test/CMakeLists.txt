cmake_minimum_required(VERSION 3.16)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Csv2TestDependencies)
include(Csv2TestManifest)
include(Csv2TestMatrix)
include(Csv2TestRegistration)

if(CSV2_BUILD_TESTS AND 14 IN_LIST csv2_supported_standards)
  csv2_load_catch2()
endif()

if(NOT CSV2_BUILD_TESTS)
  if(CSV2_BUILD_FUZZERS)
    add_subdirectory(fuzz)
  endif()
  return()
endif()

find_package(Python3 3.10 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
  add_test(NAME csv2.vendor.integrity
    COMMAND ${Python3_EXECUTABLE}
      ${csv2_SOURCE_DIR}/tools/vendor/update_verification_dependencies.py check)
  set_tests_properties(csv2.vendor.integrity PROPERTIES
    LABELS "vendor-integrity;verification")

  add_test(NAME csv2.vendor.tooling_contract
    COMMAND ${Python3_EXECUTABLE}
      ${csv2_SOURCE_DIR}/tools/vendor/test_update_verification_dependencies.py -v)
  set_tests_properties(csv2.vendor.tooling_contract PROPERTIES
    LABELS "vendor-integrity;verification")

  add_test(NAME csv2.test.legacy_parity
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/migration/check_legacy_case_map.py)
  set_tests_properties(csv2.test.legacy_parity PROPERTIES
    LABELS "test-manifest;verification")
endif()

add_subdirectory(fixtures)
add_subdirectory(support)
add_subdirectory(runtime)
add_subdirectory(contracts)
add_subdirectory(platform)
add_subdirectory(fuzz)

csv2_validate_test_manifest()
csv2_add_runtime_matrix()

foreach(csv2_manifest_contract IN ITEMS
    duplicate wrong_domain wrong_prefix missing malformed)
  add_test(NAME csv2.test.manifest.reject.${csv2_manifest_contract}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_TEST_CONTRACT_MODE=${csv2_manifest_contract}
      -DCSV2_TEST_CONTRACT_ROOT=${CMAKE_CURRENT_BINARY_DIR}/manifest-contract/${csv2_manifest_contract}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/manifest_contract.cmake)
  set_tests_properties(csv2.test.manifest.reject.${csv2_manifest_contract}
    PROPERTIES LABELS "test-manifest;verification" WILL_FAIL TRUE TIMEOUT 5)
endforeach()

# Preserve the two historical build target names used by downstream CI while
# the executable and CTest identities follow the new matrix naming contract.
if(TARGET csv2_runtime_modular_cxx11_normal)
  add_custom_target(csv2_test DEPENDS csv2_runtime_modular_cxx11_normal)
endif()
if(TARGET csv2_runtime_single_cxx11_normal)
  add_custom_target(csv2_single_header_test
    DEPENDS csv2_runtime_single_cxx11_normal)
endif()

option(CSV2_REQUIRE_MODERN_STANDARD_TESTS
  "Fail configuration unless the C++20 and C++23 CTest variants are registered" OFF)
if(CSV2_REQUIRE_MODERN_STANDARD_TESTS)
  foreach(required_test IN ITEMS
      csv2.runtime.reader.scan.modular.cxx20.normal
      csv2.runtime.reader.scan.single.cxx20.normal
      csv2.runtime.reader.scan.modular.cxx23.normal
      csv2.runtime.reader.scan.single.cxx23.normal)
    if(NOT TEST ${required_test})
      message(FATAL_ERROR
        "Required modern-standard CTest test is not registered: ${required_test}")
    endif()
  endforeach()
endif()
