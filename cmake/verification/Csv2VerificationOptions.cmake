include_guard(GLOBAL)

option(CSV2_BUILD_TESTS "Build csv2 tests and enable their CTest entries" OFF)
option(CSV2_BUILD_BENCHMARKS "Build csv2 benchmarks" OFF)
option(CSV2_BUILD_FUZZERS "Build the Clang libFuzzer targets" OFF)
option(CSV2_BUILD_BENCHMARK_CHECKS
  "Register deterministic benchmark protocol and checksum CTest entries" OFF)
option(CSV2_ENABLE_SANITIZERS
  "Enable sanitizers for first-party verification targets" OFF)

set(CSV2_VERIFICATION_PROFILE "quick" CACHE STRING
  "Verification depth: quick, full, or perf")
set_property(CACHE CSV2_VERIFICATION_PROFILE PROPERTY STRINGS quick full perf)

set(csv2_verification_profiles quick full perf)
list(FIND csv2_verification_profiles "${CSV2_VERIFICATION_PROFILE}"
  csv2_verification_profile_index)
if(csv2_verification_profile_index EQUAL -1)
  message(FATAL_ERROR
    "CSV2_VERIFICATION_PROFILE must be quick, full, or perf; got "
    "'${CSV2_VERIFICATION_PROFILE}'")
endif()

if(CSV2_BUILD_BENCHMARK_CHECKS AND NOT CSV2_BUILD_BENCHMARKS)
  message(FATAL_ERROR
    "CSV2_BUILD_BENCHMARK_CHECKS requires CSV2_BUILD_BENCHMARKS=ON")
endif()

set(csv2_verification_enabled OFF)
if(CSV2_BUILD_TESTS OR CSV2_BUILD_BENCHMARKS OR CSV2_BUILD_FUZZERS)
  set(csv2_verification_enabled ON)
endif()
