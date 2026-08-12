cmake_minimum_required(VERSION 3.10)

if(POLICY CMP0092)
  cmake_policy(SET CMP0092 NEW)
endif()

project(csv2 VERSION 1.8.0 LANGUAGES CXX)

set(CSV2_CI_EXPECTED_COMPILER_ID "" CACHE STRING
  "Expected CMake compiler ID for CI toolchain verification")
set(CSV2_CI_EXPECTED_COMPILER_VERSION_PREFIX "" CACHE STRING
  "Expected compiler version prefix for CI toolchain verification")

if(CSV2_CI_EXPECTED_COMPILER_ID AND
   NOT CMAKE_CXX_COMPILER_ID STREQUAL CSV2_CI_EXPECTED_COMPILER_ID)
  message(FATAL_ERROR
    "CI expected compiler ID ${CSV2_CI_EXPECTED_COMPILER_ID}, but CMake "
    "detected ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
endif()

if(CSV2_CI_EXPECTED_COMPILER_VERSION_PREFIX)
  set(csv2_expected_compiler_version
    "${CSV2_CI_EXPECTED_COMPILER_VERSION_PREFIX}.")
  string(FIND "${CMAKE_CXX_COMPILER_VERSION}"
    "${csv2_expected_compiler_version}" csv2_compiler_version_position)
  if(NOT CMAKE_CXX_COMPILER_VERSION STREQUAL
       CSV2_CI_EXPECTED_COMPILER_VERSION_PREFIX AND
     NOT csv2_compiler_version_position EQUAL 0)
    message(FATAL_ERROR
      "CI expected compiler version prefix "
      "${CSV2_CI_EXPECTED_COMPILER_VERSION_PREFIX}, but CMake detected "
      "${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
  endif()
endif()

if(CSV2_CI_EXPECTED_COMPILER_ID OR
   CSV2_CI_EXPECTED_COMPILER_VERSION_PREFIX)
  message(STATUS
    "Verified CI compiler: ${CMAKE_CXX_COMPILER_ID} "
    "${CMAKE_CXX_COMPILER_VERSION}")
endif()

if(POLICY CMP0077)
  cmake_policy(SET CMP0077 NEW)
endif()

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  set(CSV2_IS_TOP_LEVEL ON)
else()
  set(CSV2_IS_TOP_LEVEL OFF)
endif()

if(EXISTS "${CMAKE_BINARY_DIR}/conanbuildinfo.cmake")
    include("${CMAKE_BINARY_DIR}/conanbuildinfo.cmake")
    conan_basic_setup()
endif()

option(CSV2_BUILD_TESTS "Build csv2 tests + enable CTest" OFF)
option(CSV2_BUILD_BENCHMARKS "Build csv2 benchmarks" OFF)
option(CSV2_BUILD_FUZZERS "Build the Clang libFuzzer target" OFF)
option(CSV2_ENABLE_SANITIZERS
  "Enable AddressSanitizer and, where supported, UndefinedBehaviorSanitizer for tests" OFF)

# Keep every optional build matrix on one compiler/CMake-supported standard
# list. CXX_STANDARD 20 and 23 were added in CMake 3.12 and 3.20 respectively.
set(csv2_supported_standards)
foreach(csv2_standard IN ITEMS 11 14 17)
  if(cxx_std_${csv2_standard} IN_LIST CMAKE_CXX_COMPILE_FEATURES)
    list(APPEND csv2_supported_standards ${csv2_standard})
  endif()
endforeach()
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.12 AND
   cxx_std_20 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  list(APPEND csv2_supported_standards 20)
endif()
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.20 AND
   cxx_std_23 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  list(APPEND csv2_supported_standards 23)
endif()

function(csv2_filter_supported_standards output)
  set(csv2_filtered_standards)
  foreach(csv2_standard IN LISTS ARGN)
    if(csv2_standard IN_LIST csv2_supported_standards)
      list(APPEND csv2_filtered_standards ${csv2_standard})
    endif()
  endforeach()
  set(${output} ${csv2_filtered_standards} PARENT_SCOPE)
endfunction()

if(CSV2_BUILD_FUZZERS AND NOT CSV2_BUILD_TESTS)
  message(FATAL_ERROR "CSV2_BUILD_FUZZERS requires CSV2_BUILD_TESTS=ON")
endif()
if(CSV2_BUILD_FUZZERS AND NOT 20 IN_LIST csv2_supported_standards)
  message(FATAL_ERROR
    "CSV2_BUILD_FUZZERS requires CMake and a compiler with C++20 support")
endif()

include(GNUInstallDirs)

add_library(csv2 INTERFACE)
add_library(csv2::csv2 ALIAS csv2)

target_compile_features(csv2 INTERFACE cxx_std_11)
target_include_directories(csv2 INTERFACE
  $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
  $<BUILD_INTERFACE:${CMAKE_CURRENT_LIST_DIR}/include>)

if(CSV2_BUILD_TESTS)
  if(CSV2_IS_TOP_LEVEL)
    enable_testing()
  endif()
  add_subdirectory(test)
endif()

if(CSV2_BUILD_BENCHMARKS)
  add_subdirectory(benchmark)
endif()

if(CSV2_IS_TOP_LEVEL)
  include(CMakePackageConfigHelpers)

  configure_package_config_file(csv2Config.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/csv2Config.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/csv2)
  write_basic_package_version_file(csv2ConfigVersion.cmake
                                   COMPATIBILITY AnyNewerVersion)

  configure_file(csv2.pc.in csv2.pc @ONLY)

  install(TARGETS csv2 EXPORT csv2Targets)
  install(EXPORT csv2Targets
          FILE csv2Targets.cmake
          NAMESPACE csv2::
          DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/csv2)
  install(FILES ${CMAKE_CURRENT_BINARY_DIR}/csv2Config.cmake
                ${CMAKE_CURRENT_BINARY_DIR}/csv2ConfigVersion.cmake
          DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/csv2)
  install(FILES ${CMAKE_CURRENT_BINARY_DIR}/csv2.pc
          DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)
  install(DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/include/csv2
          DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
          USE_SOURCE_PERMISSIONS
          PATTERN "*.hpp")
  install(FILES LICENSE LICENSE.mio
          DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/licenses/csv2)

  if(EXISTS "${PROJECT_SOURCE_DIR}/.gitignore")
    # Simple glob to regex conversion (.gitignore => CPACK_SOURCE_IGNORE_FILES)
    file(READ ".gitignore" DOT_GITIGNORE)
    string(REPLACE ";" "RANDOMSEQUENCE" DOT_GITIGNORE "${DOT_GITIGNORE}")
    string(REPLACE "\n" ";" DOT_GITIGNORE "${DOT_GITIGNORE}")
    string(REPLACE "RANDOMSEQUENCE" "\\;" DOT_GITIGNORE "${DOT_GITIGNORE}")
    foreach(IGNORE_LINE ${DOT_GITIGNORE})
      if(NOT IGNORE_LINE OR IGNORE_LINE MATCHES "^#")
        continue()
      endif()
      string(REPLACE "\\" "\\\\" IGNORE_LINE "${IGNORE_LINE}")
      string(REPLACE "." "\\\\." IGNORE_LINE "${IGNORE_LINE}")
      string(REPLACE "*" ".*" IGNORE_LINE "${IGNORE_LINE}")
      string(REPLACE "+" "\\\\+" IGNORE_LINE "${IGNORE_LINE}")
      list(APPEND CPACK_SOURCE_IGNORE_FILES "${IGNORE_LINE}")
    endforeach()
  endif()

  # extra ignored files
  list(APPEND CPACK_SOURCE_IGNORE_FILES
    .editorconfig
    .git
    .gitignore
    .travis.yml
    .appveyor.yml
  )
  set(CPACK_SOURCE_PACKAGE_FILE_NAME "${PROJECT_NAME}-${PROJECT_VERSION}")
  set(CPACK_GENERATOR "TGZ;TXZ")
  set(CPACK_SOURCE_GENERATOR "TGZ;TXZ")
  include(CPack)
endif()
