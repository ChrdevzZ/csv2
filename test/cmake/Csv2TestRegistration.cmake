include_guard(GLOBAL)

# Keep the focused sanitizer build closure and CTest label driven by one manifest.
set(csv2_sanitizer_smoke_targets
  csv2_runtime_modular_cxx20_normal
  csv2_runtime_single_cxx23_normal
  csv2_runtime_modular_cxx11_no_mmap
  csv2_runtime_single_cxx11_no_exceptions
  csv2_minitest_registry_capacity
  csv2_minitest_registry_duplicate
  csv2_fuzz_smoke
  csv2_fuzz_writer_smoke)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  list(APPEND csv2_sanitizer_smoke_targets
    csv2_mio_windows_api
    csv2_single_header_mio_windows_api)
endif()

function(csv2_append_sanitizer_smoke_label target labels_variable)
  set(labels ${${labels_variable}})
  if(target IN_LIST csv2_sanitizer_smoke_targets)
    list(APPEND labels sanitizer-smoke)
  endif()
  set(${labels_variable} ${labels} PARENT_SCOPE)
endfunction()

function(csv2_register_runtime_test target test_name)
  add_test(NAME ${test_name} COMMAND ${target})
  set(labels sanitizer-runtime)
  csv2_append_sanitizer_smoke_label(${target} labels)
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
  csv2_append_sanitizer_smoke_label(${target} labels)
  set_tests_properties(${test_name} PROPERTIES
    LABELS "${labels}"
    TIMEOUT ${timeout}
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endfunction()
