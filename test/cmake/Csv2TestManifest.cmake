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
    if(NOT EXISTS "${resolved_source}")
      message(FATAL_ERROR
        "CSV2 test domain ${DOMAIN_ID} source does not exist: ${resolved_source}")
    endif()
    list(APPEND resolved_sources "${resolved_source}")
  endforeach()
  foreach(fixture IN LISTS DOMAIN_FIXTURES)
    if(NOT EXISTS "${csv2_SOURCE_DIR}/test/fixtures/${fixture}")
      message(FATAL_ERROR
        "CSV2 test domain ${DOMAIN_ID} fixture does not exist: ${fixture}")
    endif()
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

function(csv2_validate_test_manifest)
  set(csv2_stable_case_ids)
  set(expected_domains
    reader.scan
    reader.iterate
    reader.extract
    reader.source
    reader.validate
    reader.convert
    reader.ranges
    reader.index
    writer.raw
    writer.escape
    writer.stream
    mio.mapping
    property.roundtrip)
  get_property(actual_domains GLOBAL PROPERTY CSV2_TEST_DOMAIN_IDS)
  list(SORT expected_domains)
  list(SORT actual_domains)
  if(NOT actual_domains STREQUAL expected_domains)
    message(FATAL_ERROR
      "CSV2 runtime domain manifest mismatch. Expected ${expected_domains}; "
      "declared ${actual_domains}")
  endif()

  foreach(domain IN LISTS actual_domains)
    string(REPLACE "." "_" domain_key "${domain}")
    get_property(requirements GLOBAL
      PROPERTY CSV2_TEST_DOMAIN_${domain_key}_REQUIRES)
    foreach(requirement IN LISTS requirements)
      if(NOT requirement MATCHES "^(mmap|exceptions)$")
        message(FATAL_ERROR
          "CSV2 test domain ${domain} has unknown requirement ${requirement}")
      endif()
    endforeach()

    get_property(domain_sources GLOBAL
      PROPERTY CSV2_TEST_DOMAIN_${domain_key}_SOURCES)
    foreach(source IN LISTS domain_sources)
      file(READ "${source}" source_contents)
      string(REGEX MATCHALL
        "CSV2_TEST_CASE[ \t\r\n]*\\("
        source_case_openings "${source_contents}")
      string(REGEX MATCHALL
        "CSV2_TEST_CASE\\([ \t\r\n]*\"[a-z0-9_.-]+\"[ \t\r\n]*,[ \t\r\n]*\"[a-z0-9_.]+\"[ \t\r\n]*\\)"
        source_cases "${source_contents}")
      list(LENGTH source_case_openings source_case_opening_count)
      list(LENGTH source_cases source_case_count)
      if(source_case_opening_count EQUAL 0)
        message(FATAL_ERROR
          "CSV2 test manifest source has no stable case ID: ${source}")
      endif()
      if(NOT source_case_count EQUAL source_case_opening_count)
        message(FATAL_ERROR
          "Malformed CSV2 stable case declaration in ${source}")
      endif()
      foreach(source_case IN LISTS source_cases)
        string(REGEX MATCHALL "\"[a-z0-9_.-]+\"" case_tokens "${source_case}")
        list(LENGTH case_tokens case_token_count)
        if(NOT case_token_count EQUAL 2)
          message(FATAL_ERROR
            "Malformed CSV2 stable case declaration in ${source}: ${source_case}")
        endif()
        list(GET case_tokens 0 case_id)
        list(GET case_tokens 1 case_domain)
        string(REGEX REPLACE "^\"|\"$" "" case_id "${case_id}")
        string(REGEX REPLACE "^\"|\"$" "" case_domain "${case_domain}")
        if(NOT case_domain STREQUAL domain)
          message(FATAL_ERROR
            "CSV2 stable case ${case_id} declares domain ${case_domain}, but "
            "${source} belongs to ${domain}")
        endif()
        string(FIND "${case_id}" "${case_domain}." case_domain_prefix)
        if(NOT case_domain_prefix EQUAL 0)
          message(FATAL_ERROR
            "CSV2 stable case ${case_id} is outside domain ${case_domain}")
        endif()
        if(case_id IN_LIST csv2_stable_case_ids)
          message(FATAL_ERROR "Duplicate CSV2 stable case ID: ${case_id}")
        endif()
        list(APPEND csv2_stable_case_ids "${case_id}")
      endforeach()
    endforeach()
  endforeach()
endfunction()
