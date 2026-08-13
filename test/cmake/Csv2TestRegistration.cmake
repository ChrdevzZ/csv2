include_guard(GLOBAL)

function(csv2_register_domain_test target domain header_mode standard variant backend)
  string(REPLACE "." "_" domain_key "${domain}")
  get_property(timeout GLOBAL PROPERTY CSV2_TEST_DOMAIN_${domain_key}_TIMEOUT)
  get_property(labels GLOBAL PROPERTY CSV2_TEST_DOMAIN_${domain_key}_LABELS)
  set(test_name
    "csv2.runtime.${domain}.${header_mode}.cxx${standard}.${variant}")
  if(backend STREQUAL "catch2")
    add_test(NAME ${test_name}
      COMMAND ${target} "[${domain}]" --reporter compact)
  else()
    add_test(NAME ${test_name}
      COMMAND ${target} --domain ${domain})
  endif()
  set_tests_properties(${test_name} PROPERTIES
    LABELS "runtime;sanitizer-runtime;${domain};${labels};${variant};${header_mode};cxx${standard}"
    TIMEOUT ${timeout}
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endfunction()
