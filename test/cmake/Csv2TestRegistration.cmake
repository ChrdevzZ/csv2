include_guard(GLOBAL)

function(csv2_register_runtime_test target test_name)
  add_test(NAME ${test_name} COMMAND ${target})
  set(labels sanitizer-runtime)
  if(target STREQUAL "csv2_mio_windows_api" OR
     target STREQUAL "csv2_single_header_mio_windows_api")
    list(APPEND labels sanitizer-smoke)
  endif()
  set_tests_properties(${test_name} PROPERTIES
    LABELS "${labels}"
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endfunction()

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
  set(labels runtime sanitizer-runtime ${domain} ${labels} ${variant}
    ${header_mode} cxx${standard})
  if(target STREQUAL "csv2_runtime_modular_cxx20_normal" OR
     target STREQUAL "csv2_runtime_single_cxx23_normal" OR
     target STREQUAL "csv2_runtime_modular_cxx11_no_mmap" OR
     target STREQUAL "csv2_runtime_single_cxx11_no_exceptions")
    list(APPEND labels sanitizer-smoke)
  endif()
  set_tests_properties(${test_name} PROPERTIES
    LABELS "${labels}"
    TIMEOUT ${timeout}
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endfunction()
