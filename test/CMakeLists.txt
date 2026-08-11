include(CheckCXXCompilerFlag)

if(MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
  string(REGEX REPLACE "(^| )[/-]EHsc( |$)" " "
    CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}")
endif()

if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|AppleClang" AND
   NOT CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
  check_cxx_compiler_flag("-Wno-c2y-extensions"
    CSV2_HAS_NO_C2Y_EXTENSIONS_WARNING)
endif()

if(CSV2_ENABLE_SANITIZERS AND
   CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND
   CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
  if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR
     (CMAKE_CXX_COMPILER_ARCHITECTURE_ID AND
      NOT CMAKE_CXX_COMPILER_ARCHITECTURE_ID STREQUAL "x64"))
    message(FATAL_ERROR
      "CSV2 Clang-CL sanitizers currently require an x64 target")
  endif()

  execute_process(
    COMMAND "${CMAKE_CXX_COMPILER}" --print-resource-dir
    RESULT_VARIABLE csv2_clang_resource_result
    OUTPUT_VARIABLE csv2_clang_resource_directory
    OUTPUT_STRIP_TRAILING_WHITESPACE)
  if(NOT csv2_clang_resource_result EQUAL 0 OR
     NOT IS_DIRECTORY "${csv2_clang_resource_directory}/lib/windows")
    message(FATAL_ERROR
      "Unable to locate the Clang-CL compiler-rt directory")
  endif()

  set(csv2_clang_runtime_directory
    "${csv2_clang_resource_directory}/lib/windows")
  set(csv2_clang_asan_library
    "${csv2_clang_runtime_directory}/clang_rt.asan_dynamic-x86_64.lib")
  set(csv2_clang_asan_thunk_library
    "${csv2_clang_runtime_directory}/clang_rt.asan_dynamic_runtime_thunk-x86_64.lib")
  set(csv2_clang_ubsan_libraries
    "${csv2_clang_runtime_directory}/clang_rt.ubsan_standalone-x86_64.lib"
    "${csv2_clang_runtime_directory}/clang_rt.ubsan_standalone_cxx-x86_64.lib")
  set(csv2_clang_required_runtime_files
    "${csv2_clang_asan_library}"
    "${csv2_clang_asan_thunk_library}"
    ${csv2_clang_ubsan_libraries}
    "${csv2_clang_runtime_directory}/clang_rt.asan_dynamic-x86_64.dll")
  foreach(csv2_runtime_file IN LISTS csv2_clang_required_runtime_files)
    if(NOT EXISTS "${csv2_runtime_file}")
      message(FATAL_ERROR
        "Required Clang-CL runtime is missing: ${csv2_runtime_file}")
    endif()
  endforeach()
endif()

function(csv2_set_test_standard target standard)
  set_target_properties(${target} PROPERTIES
    CXX_STANDARD ${standard}
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF)
endfunction()

function(csv2_register_runtime_test target test_name)
  add_test(NAME ${test_name} COMMAND ${target})
  set_tests_properties(${test_name} PROPERTIES
    LABELS sanitizer-runtime
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endfunction()

function(csv2_enable_test_options target)
  set(csv2_uses_doctest FALSE)
  set(csv2_disables_exceptions FALSE)
  foreach(option IN LISTS ARGN)
    if(option STREQUAL "DOCTEST")
      set(csv2_uses_doctest TRUE)
    elseif(option STREQUAL "NO_EXCEPTIONS")
      set(csv2_disables_exceptions TRUE)
    else()
      message(FATAL_ERROR "Unknown csv2 test option: ${option}")
    endif()
  endforeach()

  if(MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
    target_compile_options(${target} PRIVATE /W4)
    if(CMAKE_CXX_COMPILER_ID STREQUAL "MSVC" AND csv2_uses_doctest)
      target_compile_options(${target} PRIVATE /wd5285)
    endif()
    if(csv2_disables_exceptions)
      target_compile_options(${target} PRIVATE /EHs-c-)
    else()
      target_compile_options(${target} PRIVATE /EHsc)
    endif()
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    if(csv2_uses_doctest AND CSV2_HAS_NO_C2Y_EXTENSIONS_WARNING)
      target_compile_options(${target} PRIVATE -Wno-c2y-extensions)
    endif()
    if(csv2_disables_exceptions)
      target_compile_options(${target} PRIVATE -fno-exceptions)
    endif()
  endif()

  if(CSV2_ENABLE_SANITIZERS)
    if(CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
      target_compile_options(${target} PRIVATE /fsanitize=address /Zi)
      get_target_property(target_type ${target} TYPE)
      if(NOT target_type STREQUAL "OBJECT_LIBRARY")
        set_property(TARGET ${target} APPEND_STRING PROPERTY LINK_FLAGS " /DEBUG")
      endif()
    elseif(CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND
           CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
      target_compile_options(${target} PRIVATE
        -fsanitize=address,undefined
        -fno-sanitize=object-size
        -fno-sanitize-recover=all
        /Oy-
        /Zi)
      get_target_property(target_type ${target} TYPE)
      if(NOT target_type STREQUAL "OBJECT_LIBRARY")
        target_link_libraries(${target} PRIVATE
          "${csv2_clang_asan_library}"
          ${csv2_clang_ubsan_libraries})
        set_property(TARGET ${target} APPEND_STRING PROPERTY LINK_FLAGS
          " /WHOLEARCHIVE:\"${csv2_clang_asan_thunk_library}\" /DEBUG")
      endif()
    elseif(CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
      message(FATAL_ERROR
        "CSV2_ENABLE_SANITIZERS does not support "
        "${CMAKE_CXX_COMPILER_ID} with the MSVC frontend")
    elseif(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
      target_compile_options(${target} PRIVATE
        -fsanitize=address,undefined
        -fno-omit-frame-pointer
        -fno-sanitize-recover=all)
      get_target_property(target_type ${target} TYPE)
      if(NOT target_type STREQUAL "OBJECT_LIBRARY")
        target_link_libraries(${target} PRIVATE -fsanitize=address,undefined)
      endif()
    else()
      message(FATAL_ERROR
        "CSV2_ENABLE_SANITIZERS requires MSVC, GCC, Clang, or AppleClang")
    endif()
  endif()
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

set(csv2_runtime_standards 11 14 17)
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.12 AND
   cxx_std_20 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  list(APPEND csv2_runtime_standards 20)
endif()
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.20 AND
   cxx_std_23 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  list(APPEND csv2_runtime_standards 23)
endif()
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.30 AND
   cxx_std_26 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  list(APPEND csv2_runtime_standards 26)
endif()

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
  "Fail configuration unless the C++26 CTest variants are registered" OFF)
if(CSV2_REQUIRE_CXX26_TESTS)
  set(csv2_required_cxx26_tests
    csv2.module.cxx26
    csv2.single_header.cxx26)
  foreach(required_test IN LISTS csv2_required_cxx26_tests)
    if(NOT TEST ${required_test})
      message(FATAL_ERROR
        "Required C++26 CTest test is not registered: ${required_test}")
    endif()
  endforeach()
endif()

csv2_add_test_variant(csv2_test_without_mmap csv2.module.no_mmap.cxx11 11 FALSE)
target_compile_definitions(csv2_test_without_mmap PRIVATE CSV2_HAS_MMAP=0 CSV2_TEST_NO_MMAP)
csv2_add_test_variant(csv2_single_header_test_without_mmap
  csv2.single_header.no_mmap.cxx11 11 TRUE)
target_compile_definitions(csv2_single_header_test_without_mmap PRIVATE
  CSV2_HAS_MMAP=0 CSV2_TEST_NO_MMAP)
csv2_add_test_variant(csv2_test_without_mmap_cxx17
  csv2.module.no_mmap.cxx17 17 FALSE)
target_compile_definitions(csv2_test_without_mmap_cxx17 PRIVATE
  CSV2_HAS_MMAP=0 CSV2_TEST_NO_MMAP)
csv2_add_test_variant(csv2_single_header_test_without_mmap_cxx17
  csv2.single_header.no_mmap.cxx17 17 TRUE)
target_compile_definitions(csv2_single_header_test_without_mmap_cxx17 PRIVATE
  CSV2_HAS_MMAP=0 CSV2_TEST_NO_MMAP)

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

foreach(standard IN ITEMS 11 20 23)
  csv2_add_config_contract(csv2_config_contract_cxx${standard} ${standard})
endforeach()

foreach(standard IN ITEMS 11 17)
  add_library(csv2_mmap_path_contract_cxx${standard} OBJECT mmap_path.cpp)
  target_link_libraries(csv2_mmap_path_contract_cxx${standard} PRIVATE csv2::csv2)
  csv2_set_test_standard(csv2_mmap_path_contract_cxx${standard} ${standard})
  csv2_enable_test_options(csv2_mmap_path_contract_cxx${standard})
endforeach()

foreach(standard IN ITEMS 11 17 20 23)
  set(suffix "_cxx${standard}")
  if(standard EQUAL 11)
    set(suffix "")
  endif()

  csv2_add_header_self_containment(csv2_header_mio${suffix}
    CSV2_TEST_HEADER_MIO ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_parameters${suffix}
    CSV2_TEST_HEADER_PARAMETERS ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_reader${suffix}
    CSV2_TEST_HEADER_READER ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_writer${suffix}
    CSV2_TEST_HEADER_WRITER ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_single${suffix}
    CSV2_TEST_SINGLE_HEADER ${csv2_SOURCE_DIR}/single_include ${standard})
endforeach()

foreach(standard IN ITEMS 11 17 20 23)
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
endforeach()

function(csv2_add_no_exceptions_test target test_name single_header)
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
  csv2_set_test_standard(${target} 11)
  csv2_enable_test_options(${target} DOCTEST NO_EXCEPTIONS)
  csv2_register_runtime_test(${target} ${test_name})
endfunction()

csv2_add_no_exceptions_test(csv2_no_exceptions csv2.module.no_exceptions.cxx11 FALSE)
csv2_add_no_exceptions_test(csv2_single_header_no_exceptions
  csv2.single_header.no_exceptions.cxx11 TRUE)

add_executable(csv2_benchmark_without_mmap ../benchmark/main.cpp)
target_link_libraries(csv2_benchmark_without_mmap PRIVATE csv2::csv2)
target_compile_definitions(csv2_benchmark_without_mmap PRIVATE CSV2_HAS_MMAP=0)
csv2_set_test_standard(csv2_benchmark_without_mmap 11)
csv2_enable_test_options(csv2_benchmark_without_mmap)
add_test(NAME csv2.benchmark.no_mmap
  COMMAND csv2_benchmark_without_mmap inputs/test_01.csv)
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
