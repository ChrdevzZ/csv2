include_guard(GLOBAL)

function(csv2_declare_test_domain)
  set(one_value_args ID MIN_STANDARD TIMEOUT)
  set(multi_value_args SOURCES PROFILES REQUIRES LABELS FIXTURES)
  cmake_parse_arguments(DOMAIN "" "${one_value_args}" "${multi_value_args}" ${ARGN})

  if(DOMAIN_UNPARSED_ARGUMENTS)
    message(FATAL_ERROR
      "Unknown arguments for csv2_declare_test_domain: ${DOMAIN_UNPARSED_ARGUMENTS}")
  endif()
  if(NOT DOMAIN_ID MATCHES "^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$")
    message(FATAL_ERROR "Invalid CSV2 test domain ID: ${DOMAIN_ID}")
  endif()
  if(NOT DOMAIN_SOURCES)
    message(FATAL_ERROR "CSV2 test domain ${DOMAIN_ID} has no sources")
  endif()
  if(NOT DOMAIN_MIN_STANDARD MATCHES "^(11|14|17|20|23|26)$")
    message(FATAL_ERROR
      "CSV2 test domain ${DOMAIN_ID} has an invalid minimum standard")
  endif()
  if(NOT DOMAIN_TIMEOUT)
    set(DOMAIN_TIMEOUT 20)
  endif()
  if(NOT DOMAIN_PROFILES)
    set(DOMAIN_PROFILES quick full perf)
  endif()
  foreach(profile IN LISTS DOMAIN_PROFILES)
    if(NOT profile MATCHES "^(quick|full|perf)$")
      message(FATAL_ERROR
        "CSV2 test domain ${DOMAIN_ID} has unknown profile ${profile}")
    endif()
  endforeach()
  foreach(requirement IN LISTS DOMAIN_REQUIRES)
    if(NOT requirement MATCHES "^(mmap|exceptions)$")
      message(FATAL_ERROR
        "CSV2 test domain ${DOMAIN_ID} has unknown requirement ${requirement}")
    endif()
  endforeach()

  get_property(domain_ids GLOBAL PROPERTY CSV2_TEST_DOMAIN_IDS)
  if(DOMAIN_ID IN_LIST domain_ids)
    message(FATAL_ERROR "Duplicate CSV2 test domain ID: ${DOMAIN_ID}")
  endif()

  set(resolved_sources)
  foreach(source IN LISTS DOMAIN_SOURCES)
    if(IS_ABSOLUTE "${source}")
      set(resolved_source "${source}")
    else()
      set(resolved_source "${csv2_SOURCE_DIR}/test/${source}")
    endif()
    list(APPEND resolved_sources "${resolved_source}")
  endforeach()

  string(REPLACE "." "_" domain_key "${DOMAIN_ID}")
  set_property(GLOBAL APPEND PROPERTY CSV2_TEST_DOMAIN_IDS "${DOMAIN_ID}")
  set_property(GLOBAL PROPERTY CSV2_TEST_DOMAIN_${domain_key}_SOURCES
    "${resolved_sources}")
  set_property(GLOBAL PROPERTY CSV2_TEST_DOMAIN_${domain_key}_MIN_STANDARD
    "${DOMAIN_MIN_STANDARD}")
  set_property(GLOBAL PROPERTY CSV2_TEST_DOMAIN_${domain_key}_PROFILES
    "${DOMAIN_PROFILES}")
  set_property(GLOBAL PROPERTY CSV2_TEST_DOMAIN_${domain_key}_REQUIRES
    "${DOMAIN_REQUIRES}")
  set_property(GLOBAL PROPERTY CSV2_TEST_DOMAIN_${domain_key}_LABELS
    "${DOMAIN_LABELS}")
  set_property(GLOBAL PROPERTY CSV2_TEST_DOMAIN_${domain_key}_TIMEOUT
    "${DOMAIN_TIMEOUT}")
endfunction()
