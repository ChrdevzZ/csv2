include_guard(GLOBAL)

function(csv2_add_benchmark_check name)
  set(options)
  set(one_value_args TIMEOUT PASS_REGEX TIER)
  set(multi_value_args COMMAND)
  cmake_parse_arguments(CSV2_CHECK "${options}" "${one_value_args}"
    "${multi_value_args}" ${ARGN})
  if(NOT CSV2_CHECK_COMMAND)
    message(FATAL_ERROR "Benchmark check ${name} has no COMMAND")
  endif()
  if(NOT CSV2_CHECK_TIER)
    set(CSV2_CHECK_TIER exhaustive)
  endif()
  if(NOT CSV2_CHECK_TIER STREQUAL "portability" AND
     NOT CSV2_CHECK_TIER STREQUAL "exhaustive")
    message(FATAL_ERROR
      "Benchmark check ${name} has invalid tier ${CSV2_CHECK_TIER}")
  endif()
  add_test(NAME ${name} COMMAND ${CSV2_CHECK_COMMAND})
  set_tests_properties(${name} PROPERTIES
    LABELS "benchmark-checksum;benchmark-${CSV2_CHECK_TIER};quick")
  if(CSV2_CHECK_TIMEOUT)
    set_tests_properties(${name} PROPERTIES TIMEOUT ${CSV2_CHECK_TIMEOUT})
  endif()
  if(CSV2_CHECK_PASS_REGEX)
    set_tests_properties(${name} PROPERTIES
      PASS_REGULAR_EXPRESSION "${CSV2_CHECK_PASS_REGEX}")
  endif()
endfunction()
