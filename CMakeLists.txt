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

include(${CMAKE_CURRENT_LIST_DIR}/cmake/verification/Csv2VerificationOptions.cmake)

if(csv2_verification_enabled)
  include(${CMAKE_CURRENT_LIST_DIR}/cmake/verification/Csv2VerificationStandards.cmake)
  include(${CMAKE_CURRENT_LIST_DIR}/cmake/verification/Csv2VerificationTargetOptions.cmake)
  include(${CMAKE_CURRENT_LIST_DIR}/cmake/verification/Csv2VerificationVendor.cmake)
  include(${CMAKE_CURRENT_LIST_DIR}/cmake/verification/Csv2VerificationPython.cmake)
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

if(CSV2_BUILD_TESTS OR CSV2_BUILD_FUZZERS OR CSV2_BUILD_BENCHMARK_CHECKS)
  if(CSV2_IS_TOP_LEVEL)
    enable_testing()
  endif()
endif()

if(CSV2_BUILD_TESTS OR CSV2_BUILD_FUZZERS)
  add_subdirectory(test)
endif()

if(CSV2_BUILD_BENCHMARKS)
  if(CSV2_BENCHMARKS_EXCLUDE_FROM_ALL)
    add_subdirectory(benchmark EXCLUDE_FROM_ALL)
  else()
    add_subdirectory(benchmark)
  endif()

  # Keep one root-level entry point for the cross-platform portability owner.
  # Visual Studio does not expose excluded subdirectory projects as direct
  # root-solution targets, while this aggregate remains outside the default
  # ALL build and follows its dependencies on every generator.
  add_custom_target(csv2_benchmark_portability)
  add_dependencies(csv2_benchmark_portability
    csv2_benchmark
    csv2_benchmark_allocations
    csv2_common_benchmark)
endif()

if(CSV2_IS_TOP_LEVEL)
  include(CMakePackageConfigHelpers)

  file(RELATIVE_PATH CSV2_PC_INCLUDEDIR_FROM_PCDIR
    "${CMAKE_INSTALL_FULL_LIBDIR}/pkgconfig"
    "${CMAKE_INSTALL_FULL_INCLUDEDIR}")

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

  # CPack consumes regular expressions, not gitignore globs. Keep packaging
  # policy explicit so editor preferences cannot silently change artifacts.
  # Use [.] for literal dots because CPack serializes these expressions through
  # a generated CMake configuration before evaluating them.
  set(CPACK_SOURCE_IGNORE_FILES
    "/[.]git[^/]*($|/)"
    "/[.](codex_tmp|idea|temp|tmp|vs|vscode)($|/)"
    "/(analysis-cppcheck-build-dir|build|coverage|out|test-output|test-results)($|/)"
    "/(build-|cmake-build-|coverage-)[^/]*/"
    "/(__pycache__|CMakeFiles|Testing|_deps)($|/)"
    "/(CMakeCache[.]txt|CTestTestfile[.]cmake|cmake_install[.]cmake|install_manifest[.]txt)$"
    "/(build[.]ninja|rules[.]ninja|[.]ninja_deps|[.]ninja_log)$"
    "/[^/]+[.](a|dll|docstates|dylib|exe|iml|lib|nupkg|o|obj|pdb|so|suo|user|userosscache)$"
    "/[^/]+[.]py[cod]$"
    "/(Debug|Release|x64|x86|artifacts)($|/)"
    "/[^/]+[.](gcda|gcno|profraw|tmp|log)$"
    "/[^/]+-writer-output[.]csv$"
    "/[^/]+~$"
    "/(desktop[.]ini|[.]DS_Store)$"
  )
  set(CPACK_SOURCE_PACKAGE_FILE_NAME "${PROJECT_NAME}-${PROJECT_VERSION}")
  set(CPACK_GENERATOR "TGZ;TXZ")
  set(CPACK_SOURCE_GENERATOR "TGZ;TXZ")
  include(CPack)
endif()
