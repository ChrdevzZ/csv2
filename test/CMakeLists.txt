cmake_minimum_required(VERSION 3.16)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(Csv2TestDependencies)
include(Csv2TestManifest)
include(Csv2TestMatrix)
include(Csv2TestRegistration)

if(CSV2_BUILD_TESTS AND 14 IN_LIST csv2_supported_standards)
  csv2_load_catch2()
endif()

if(CSV2_BUILD_TESTS)
  find_package(Python3 3.10 COMPONENTS Interpreter QUIET)
  if(Python3_Interpreter_FOUND)
    add_test(NAME csv2.vendor.integrity
      COMMAND ${Python3_EXECUTABLE}
        ${csv2_SOURCE_DIR}/tools/vendor/update_verification_dependencies.py
        check)
    set_tests_properties(csv2.vendor.integrity PROPERTIES
      LABELS "vendor-integrity;verification")
    add_test(NAME csv2.vendor.tooling_contract
      COMMAND ${Python3_EXECUTABLE}
        ${csv2_SOURCE_DIR}/tools/vendor/test_update_verification_dependencies.py
        -v)
    set_tests_properties(csv2.vendor.tooling_contract PROPERTIES
      LABELS "vendor-integrity;verification")
  endif()
endif()

# Fuzzer targets are independently selectable. Keep this narrow early-return
# path until the dedicated fuzz subdirectory owns them later in the migration.
if(NOT CSV2_BUILD_TESTS)
  if(CSV2_BUILD_FUZZERS)
    if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang" OR
       CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
      message(FATAL_ERROR
        "CSV2_BUILD_FUZZERS requires Clang with the GNU frontend")
    endif()
    add_executable(csv2_fuzz fuzz_reader.cpp)
    target_link_libraries(csv2_fuzz PRIVATE csv2::csv2)
    target_compile_definitions(csv2_fuzz PRIVATE CSV2_HAS_MMAP=0)
    target_compile_options(csv2_fuzz PRIVATE
      -fsanitize=fuzzer,address,undefined
      -fno-omit-frame-pointer
      -fno-sanitize-recover=all)
    set_property(TARGET csv2_fuzz APPEND_STRING PROPERTY LINK_FLAGS
      " -fsanitize=fuzzer,address,undefined")
    csv2_set_test_standard(csv2_fuzz 20)
    csv2_enable_test_options(csv2_fuzz)
  endif()
  return()
endif()

add_subdirectory(support)
add_subdirectory(runtime)
csv2_add_runtime_matrix()

function(csv2_register_runtime_test target test_name)
  add_test(NAME ${test_name} COMMAND ${target})
  set_tests_properties(${test_name} PROPERTIES
    LABELS sanitizer-runtime
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endfunction()

function(csv2_add_test_variant target test_name standard single_header)
  add_executable(${target} main.cpp)
  target_compile_definitions(${target} PRIVATE
    DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
    CSV2_TEST_WRITER_OUTPUT="${target}-writer-output.csv")
  if(single_header)
    target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
    target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
  else()
    target_link_libraries(${target} PRIVATE csv2::csv2)
  endif()
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target} DOCTEST)
  csv2_register_runtime_test(${target} ${test_name})
endfunction()

set(csv2_runtime_standards ${csv2_supported_standards})
foreach(standard IN LISTS csv2_runtime_standards)
  set(suffix "_cxx${standard}")
  if(standard EQUAL 11)
    set(suffix "")
  endif()

  csv2_add_test_variant(csv2_test${suffix}
    csv2.module.cxx${standard} ${standard} FALSE)
  csv2_add_test_variant(csv2_single_header_test${suffix}
    csv2.single_header.cxx${standard} ${standard} TRUE)
endforeach()

option(CSV2_REQUIRE_MODERN_STANDARD_TESTS
  "Fail configuration unless the C++20 and C++23 CTest variants are registered" OFF)
if(CSV2_REQUIRE_MODERN_STANDARD_TESTS)
  set(csv2_required_modern_tests
    csv2.module.cxx20
    csv2.single_header.cxx20
    csv2.module.cxx23
    csv2.single_header.cxx23)
  foreach(required_test IN LISTS csv2_required_modern_tests)
    if(NOT TEST ${required_test})
      message(FATAL_ERROR
        "Required modern-standard CTest test is not registered: ${required_test}")
    endif()
  endforeach()
endif()

option(CSV2_REQUIRE_CXX26_TESTS
  "Fail configuration unless the C++26 compile-only targets are registered" OFF)

if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.30 AND
   cxx_std_26 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_standard_contract_single_cxx26)
    else()
      set(target csv2_standard_contract_module_cxx26)
    endif()
    add_library(${target} OBJECT standard_cxx26.cpp)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${target} 26)
    csv2_enable_test_options(${target})
  endforeach()
endif()

if(CSV2_REQUIRE_CXX26_TESTS)
  set(csv2_required_cxx26_targets
    csv2_standard_contract_module_cxx26
    csv2_standard_contract_single_cxx26)
  foreach(required_target IN LISTS csv2_required_cxx26_targets)
    if(NOT TARGET ${required_target})
      message(FATAL_ERROR
        "Required C++26 compile-only target is not registered: ${required_target}")
    endif()
  endforeach()
endif()

csv2_filter_supported_standards(csv2_no_mmap_standards 11 17 20 23)
foreach(standard IN LISTS csv2_no_mmap_standards)
  set(suffix "_cxx${standard}")
  if(standard EQUAL 11)
    set(suffix "")
  endif()
  csv2_add_test_variant(csv2_test_without_mmap${suffix}
    csv2.module.no_mmap.cxx${standard} ${standard} FALSE)
  target_compile_definitions(csv2_test_without_mmap${suffix} PRIVATE
    CSV2_HAS_MMAP=0 CSV2_TEST_NO_MMAP)
  csv2_add_test_variant(csv2_single_header_test_without_mmap${suffix}
    csv2.single_header.no_mmap.cxx${standard} ${standard} TRUE)
  target_compile_definitions(csv2_single_header_test_without_mmap${suffix} PRIVATE
    CSV2_HAS_MMAP=0 CSV2_TEST_NO_MMAP)
endforeach()

function(csv2_add_header_self_containment target header_definition include_directory standard)
  add_library(${target} OBJECT main.cpp)
  target_compile_definitions(${target} PRIVATE
    CSV2_TEST_HEADER_ONLY
    ${header_definition})
  target_include_directories(${target} PRIVATE ${include_directory})
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

function(csv2_add_config_contract target standard)
  add_library(${target} OBJECT config.cpp)
  target_link_libraries(${target} PRIVATE csv2::csv2)
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

function(csv2_add_config_fallback_contract target standard single_header)
  add_library(${target} OBJECT config_fallback.cpp)
  if(single_header)
    target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
    target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
  else()
    target_link_libraries(${target} PRIVATE csv2::csv2)
  endif()
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

csv2_filter_supported_standards(csv2_config_standards 11 20 23)
foreach(standard IN LISTS csv2_config_standards)
  csv2_add_config_contract(csv2_config_contract_cxx${standard} ${standard})
endforeach()

csv2_filter_supported_standards(csv2_config_fallback_standards 17 20 23)
foreach(standard IN LISTS csv2_config_fallback_standards)
  csv2_add_config_fallback_contract(
    csv2_config_fallback_module_cxx${standard} ${standard} FALSE)
  csv2_add_config_fallback_contract(
    csv2_config_fallback_single_cxx${standard} ${standard} TRUE)
endforeach()

csv2_filter_supported_standards(csv2_mmap_path_standards 11 17 20 23)
foreach(standard IN LISTS csv2_mmap_path_standards)
  add_library(csv2_mmap_path_contract_cxx${standard} OBJECT mmap_path.cpp)
  target_link_libraries(csv2_mmap_path_contract_cxx${standard} PRIVATE csv2::csv2)
  csv2_set_test_standard(csv2_mmap_path_contract_cxx${standard} ${standard})
  csv2_enable_test_options(csv2_mmap_path_contract_cxx${standard})

  add_library(csv2_mmap_path_contract_single_cxx${standard} OBJECT mmap_path.cpp)
  target_compile_definitions(csv2_mmap_path_contract_single_cxx${standard} PRIVATE
    CSV2_TEST_SINGLE_HEADER)
  target_include_directories(csv2_mmap_path_contract_single_cxx${standard} PRIVATE
    ${csv2_SOURCE_DIR}/single_include)
  csv2_set_test_standard(csv2_mmap_path_contract_single_cxx${standard} ${standard})
  csv2_enable_test_options(csv2_mmap_path_contract_single_cxx${standard})

  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_mmap_path_contract_no_mmap_single_cxx${standard})
    else()
      set(target csv2_mmap_path_contract_no_mmap_module_cxx${standard})
    endif()
    add_library(${target} OBJECT mmap_path.cpp)
    target_compile_definitions(${target} PRIVATE CSV2_HAS_MMAP=0)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${target} ${standard})
    csv2_enable_test_options(${target})
  endforeach()
endforeach()

csv2_filter_supported_standards(csv2_header_standards 11 17 20 23)
foreach(standard IN LISTS csv2_header_standards)
  set(suffix "_cxx${standard}")
  if(standard EQUAL 11)
    set(suffix "")
  endif()

  csv2_add_header_self_containment(csv2_header_mio${suffix}
    CSV2_TEST_HEADER_MIO ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_parameters${suffix}
    CSV2_TEST_HEADER_PARAMETERS ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_errors${suffix}
    CSV2_TEST_HEADER_ERRORS ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_reader${suffix}
    CSV2_TEST_HEADER_READER ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_writer${suffix}
    CSV2_TEST_HEADER_WRITER ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_single${suffix}
    CSV2_TEST_SINGLE_HEADER ${csv2_SOURCE_DIR}/single_include ${standard})
endforeach()

foreach(standard IN LISTS csv2_header_standards)
  set(suffix "_cxx${standard}")
  if(standard EQUAL 11)
    set(suffix "")
  endif()

  csv2_add_header_self_containment(csv2_header_single_without_mmap${suffix}
    CSV2_TEST_SINGLE_HEADER ${csv2_SOURCE_DIR}/single_include ${standard})
  target_compile_definitions(csv2_header_single_without_mmap${suffix} PRIVATE
    CSV2_HAS_MMAP=0 CSV2_EXPECT_NO_MIO)

  csv2_add_header_self_containment(csv2_header_reader_without_mmap${suffix}
    CSV2_TEST_HEADER_READER ${csv2_SOURCE_DIR}/include ${standard})
  target_compile_definitions(csv2_header_reader_without_mmap${suffix} PRIVATE
    CSV2_HAS_MMAP=0 CSV2_EXPECT_NO_MIO)

  csv2_add_header_self_containment(csv2_header_mio_without_mmap${suffix}
    CSV2_TEST_HEADER_MIO ${csv2_SOURCE_DIR}/include ${standard})
  target_compile_definitions(csv2_header_mio_without_mmap${suffix} PRIVATE
    CSV2_HAS_MMAP=0 CSV2_EXPECT_NO_MIO)
endforeach()

function(csv2_add_degraded_standard_contract standard)
  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_standard_contract_degraded_single_cxx${standard})
    else()
      set(target csv2_standard_contract_degraded_module_cxx${standard})
    endif()
    add_library(${target} OBJECT standard_cxx${standard}.cpp)
    target_compile_definitions(${target} PRIVATE
      CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES
      CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${target} ${standard})
    csv2_enable_test_options(${target})

    if(single_header)
      set(mmap_target csv2_mmap_path_contract_degraded_single_cxx${standard})
    else()
      set(mmap_target csv2_mmap_path_contract_degraded_module_cxx${standard})
    endif()
    add_library(${mmap_target} OBJECT mmap_path.cpp)
    target_compile_definitions(${mmap_target} PRIVATE
      CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES
      CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
    if(single_header)
      target_compile_definitions(${mmap_target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${mmap_target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${mmap_target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${mmap_target} ${standard})
    csv2_enable_test_options(${mmap_target})
  endforeach()
endfunction()

set(csv2_degraded_headers_directory
  "${CMAKE_CURRENT_BINARY_DIR}/degraded_standard_library")
file(MAKE_DIRECTORY "${csv2_degraded_headers_directory}")
file(WRITE "${csv2_degraded_headers_directory}/version"
  "/* Deliberately empty partial <version> fixture. */\n")
file(WRITE "${csv2_degraded_headers_directory}/string_view"
  "#pragma GCC system_header\n#include_next <string_view>\n"
  "#ifndef __cpp_lib_string_view\n"
  "#define __cpp_lib_string_view 201606L\n#endif\n")
file(WRITE "${csv2_degraded_headers_directory}/filesystem"
  "#pragma GCC system_header\n#include_next <filesystem>\n"
  "#ifndef __cpp_lib_filesystem\n"
  "#define __cpp_lib_filesystem 201703L\n#endif\n")
file(WRITE "${csv2_degraded_headers_directory}/span"
  "#pragma GCC system_header\n#include_next <span>\n"
  "#ifndef __cpp_lib_span\n#define __cpp_lib_span 202002L\n#endif\n")
file(WRITE "${csv2_degraded_headers_directory}/ranges"
  "#pragma GCC system_header\n#include_next <ranges>\n"
  "#ifndef __cpp_lib_ranges\n#define __cpp_lib_ranges 201911L\n#endif\n")

set(csv2_empty_headers_directory
  "${CMAKE_CURRENT_BINARY_DIR}/empty_standard_library")
file(MAKE_DIRECTORY "${csv2_empty_headers_directory}")
foreach(header IN ITEMS
    version string_view filesystem charconv memory_resource span ranges expected)
  file(WRITE "${csv2_empty_headers_directory}/${header}"
    "#pragma once\n#pragma GCC system_header\n#pragma GCC diagnostic push\n"
    "#pragma GCC diagnostic ignored \"-Wpedantic\"\n"
    "#include_next <${header}>\n#pragma GCC diagnostic pop\n")
endforeach()
file(APPEND "${csv2_empty_headers_directory}/version"
  "#undef __cpp_lib_string_view\n#undef __cpp_lib_filesystem\n"
  "#undef __cpp_lib_to_chars\n#undef __cpp_lib_memory_resource\n"
  "#undef __cpp_lib_span\n#undef __cpp_lib_ranges\n"
  "#undef __cpp_lib_ranges_to_container\n#undef __cpp_lib_expected\n")
file(APPEND "${csv2_empty_headers_directory}/string_view"
  "#undef __cpp_lib_string_view\n")
file(APPEND "${csv2_empty_headers_directory}/filesystem"
  "#undef __cpp_lib_filesystem\n")
file(APPEND "${csv2_empty_headers_directory}/charconv"
  "#undef __cpp_lib_to_chars\n")
file(APPEND "${csv2_empty_headers_directory}/memory_resource"
  "#undef __cpp_lib_memory_resource\n")
file(APPEND "${csv2_empty_headers_directory}/span"
  "#undef __cpp_lib_span\n")
file(APPEND "${csv2_empty_headers_directory}/ranges"
  "#undef __cpp_lib_ranges\n#undef __cpp_lib_ranges_to_container\n")
file(APPEND "${csv2_empty_headers_directory}/expected"
  "#undef __cpp_lib_expected\n")

csv2_filter_supported_standards(csv2_degraded_standards 17 20 23)
foreach(standard IN LISTS csv2_degraded_standards)
  csv2_add_degraded_standard_contract(${standard})

  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_standard_contract_partial_headers_single_cxx${standard})
    else()
      set(target csv2_standard_contract_partial_headers_module_cxx${standard})
    endif()
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang" AND
       NOT CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
      add_library(${target} OBJECT standard_cxx${standard}.cpp)
      target_include_directories(${target} BEFORE PRIVATE
        ${csv2_degraded_headers_directory})
      if(single_header)
        target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
        target_include_directories(${target} PRIVATE
          ${csv2_SOURCE_DIR}/single_include)
      else()
        target_link_libraries(${target} PRIVATE csv2::csv2)
      endif()
      csv2_set_test_standard(${target} ${standard})
      csv2_enable_test_options(${target})

      if(single_header)
        set(degraded_target
          csv2_standard_contract_empty_headers_single_cxx${standard})
      else()
        set(degraded_target
          csv2_standard_contract_empty_headers_module_cxx${standard})
      endif()
      add_library(${degraded_target} OBJECT standard_cxx${standard}.cpp)
      target_compile_definitions(${degraded_target} PRIVATE
        CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
      target_include_directories(${degraded_target} BEFORE PRIVATE
        ${csv2_empty_headers_directory})
      if(single_header)
        target_compile_definitions(${degraded_target} PRIVATE CSV2_TEST_SINGLE_HEADER)
        target_include_directories(${degraded_target} PRIVATE
          ${csv2_SOURCE_DIR}/single_include)
      else()
        target_link_libraries(${degraded_target} PRIVATE csv2::csv2)
      endif()
      csv2_set_test_standard(${degraded_target} ${standard})
      csv2_enable_test_options(${degraded_target})
    endif()
  endforeach()
endforeach()

function(csv2_add_version_guard_contract standard single_header)
  if(single_header)
    set(target csv2_version_guard_single_cxx${standard})
  else()
    set(target csv2_version_guard_module_cxx${standard})
  endif()
  add_library(${target} OBJECT config.cpp)
  if(single_header)
    target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
    target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
  else()
    target_link_libraries(${target} PRIVATE csv2::csv2)
  endif()
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

csv2_filter_supported_standards(csv2_pre_cxx20_standards 11 14 17)
foreach(standard IN LISTS csv2_pre_cxx20_standards)
  csv2_add_version_guard_contract(${standard} FALSE)
  csv2_add_version_guard_contract(${standard} TRUE)
endforeach()

function(csv2_add_no_exceptions_test target test_name standard single_header)
  if(NOT (MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC" OR
          CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang"))
    return()
  endif()

  add_executable(${target} main.cpp)
  target_compile_definitions(${target} PRIVATE
    DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
    DOCTEST_CONFIG_NO_EXCEPTIONS_BUT_WITH_ALL_ASSERTS
    CSV2_TEST_NO_EXCEPTIONS
    CSV2_TEST_WRITER_OUTPUT="${target}-writer-output.csv")
  if(single_header)
    target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
    target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
  else()
    target_link_libraries(${target} PRIVATE csv2::csv2)
  endif()
  if(MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
    target_compile_definitions(${target} PRIVATE _HAS_EXCEPTIONS=0)
  endif()
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target} DOCTEST NO_EXCEPTIONS)
  csv2_register_runtime_test(${target} ${test_name})
endfunction()

csv2_filter_supported_standards(csv2_no_exceptions_standards 11 20 23)
foreach(standard IN LISTS csv2_no_exceptions_standards)
  set(suffix "_cxx${standard}")
  if(standard EQUAL 11)
    set(suffix "")
  endif()
  csv2_add_no_exceptions_test(csv2_no_exceptions${suffix}
    csv2.module.no_exceptions.cxx${standard} ${standard} FALSE)
  csv2_add_no_exceptions_test(csv2_single_header_no_exceptions${suffix}
    csv2.single_header.no_exceptions.cxx${standard} ${standard} TRUE)
endforeach()

function(csv2_add_standard_contract standard)
  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_standard_contract_single_cxx${standard})
    else()
      set(target csv2_standard_contract_module_cxx${standard})
    endif()
    add_library(${target} OBJECT standard_cxx${standard}.cpp)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${target} ${standard})
    csv2_enable_test_options(${target})
  endforeach()
endfunction()

foreach(standard IN LISTS csv2_supported_standards)
  csv2_add_standard_contract(${standard})
endforeach()

add_executable(csv2_fuzz_smoke fuzz_reader.cpp)
target_link_libraries(csv2_fuzz_smoke PRIVATE csv2::csv2)
target_compile_definitions(csv2_fuzz_smoke PRIVATE CSV2_FUZZ_STANDALONE CSV2_HAS_MMAP=0)
csv2_set_test_standard(csv2_fuzz_smoke 11)
csv2_enable_test_options(csv2_fuzz_smoke)
csv2_register_runtime_test(csv2_fuzz_smoke csv2.fuzz.smoke.cxx11)
set_tests_properties(csv2.fuzz.smoke.cxx11 PROPERTIES LABELS "fuzz-smoke;sanitizer-runtime")

if(CSV2_BUILD_FUZZERS)
  if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang" OR
     CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
    message(FATAL_ERROR "CSV2_BUILD_FUZZERS requires Clang with the GNU frontend")
  endif()
  add_executable(csv2_fuzz fuzz_reader.cpp)
  target_link_libraries(csv2_fuzz PRIVATE csv2::csv2)
  target_compile_definitions(csv2_fuzz PRIVATE CSV2_HAS_MMAP=0)
  target_compile_options(csv2_fuzz PRIVATE
    -fsanitize=fuzzer,address,undefined
    -fno-omit-frame-pointer
    -fno-sanitize-recover=all)
  set_property(TARGET csv2_fuzz APPEND_STRING PROPERTY LINK_FLAGS
    " -fsanitize=fuzzer,address,undefined")
  csv2_set_test_standard(csv2_fuzz 20)
  csv2_enable_test_options(csv2_fuzz)
endif()

add_executable(csv2_benchmark_without_mmap ../benchmark/main.cpp)
target_link_libraries(csv2_benchmark_without_mmap PRIVATE csv2::csv2)
target_compile_definitions(csv2_benchmark_without_mmap PRIVATE CSV2_HAS_MMAP=0)
csv2_set_test_standard(csv2_benchmark_without_mmap 11)
csv2_enable_test_options(csv2_benchmark_without_mmap)
add_test(NAME csv2.benchmark.no_mmap
  COMMAND csv2_benchmark_without_mmap --operation map_only
    --input inputs/test_01.csv --source mmap --iterations 1)
set_tests_properties(csv2.benchmark.no_mmap PROPERTIES
  WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
  WILL_FAIL TRUE)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  set(csv2_windows_shim_directory "${CMAKE_CURRENT_BINARY_DIR}/winapi_shim")
  file(MAKE_DIRECTORY "${csv2_windows_shim_directory}")
  file(WRITE "${csv2_windows_shim_directory}/windows.h" "")

  function(csv2_add_windows_api_test target test_name single_header)
    add_executable(${target} main.cpp)
    target_compile_definitions(${target} PRIVATE CSV2_TEST_WINDOWS_API)
    target_include_directories(${target} PRIVATE ${csv2_windows_shim_directory})
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/include)
    endif()
    csv2_set_test_standard(${target} 11)
    csv2_enable_test_options(${target})
    csv2_register_runtime_test(${target} ${test_name})
  endfunction()

  csv2_add_windows_api_test(csv2_mio_windows_api
    csv2.mio.winapi_injection.module.cxx11 FALSE)
  csv2_add_windows_api_test(csv2_single_header_mio_windows_api
    csv2.mio.winapi_injection.single_header.cxx11 TRUE)
endif()

file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/inputs
     DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
