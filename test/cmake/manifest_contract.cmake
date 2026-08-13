if(NOT DEFINED CSV2_TEST_CONTRACT_MODE OR NOT DEFINED CSV2_TEST_CONTRACT_ROOT)
  message(FATAL_ERROR "Manifest contract mode and root are required")
endif()

include("${CMAKE_CURRENT_LIST_DIR}/Csv2TestManifest.cmake")
file(REMOVE_RECURSE "${CSV2_TEST_CONTRACT_ROOT}")
file(MAKE_DIRECTORY "${CSV2_TEST_CONTRACT_ROOT}")

set(domains
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

foreach(domain IN LISTS domains)
  string(REPLACE "." "_" key "${domain}")
  set(source "${CSV2_TEST_CONTRACT_ROOT}/${key}.cpp")
  set(declaration "CSV2_TEST_CASE(\"${domain}.case\", \"${domain}\") {}\n")
  if(domain STREQUAL "reader.scan")
    if(CSV2_TEST_CONTRACT_MODE STREQUAL "duplicate")
      string(APPEND declaration
        "CSV2_TEST_CASE(\"reader.scan.case\", \"reader.scan\") {}\n")
    elseif(CSV2_TEST_CONTRACT_MODE STREQUAL "wrong_domain")
      set(declaration
        "CSV2_TEST_CASE(\"reader.iterate.case-two\", \"reader.iterate\") {}\n")
    elseif(CSV2_TEST_CONTRACT_MODE STREQUAL "wrong_prefix")
      set(declaration
        "CSV2_TEST_CASE(\"writer.raw.case-two\", \"reader.scan\") {}\n")
    elseif(CSV2_TEST_CONTRACT_MODE STREQUAL "missing")
      set(declaration "int no_stable_case_id;\n")
    elseif(CSV2_TEST_CONTRACT_MODE STREQUAL "malformed")
      string(APPEND declaration
        "CSV2_TEST_CASE(\"Reader Scan Case\", \"reader.scan\") {}\n")
    else()
      message(FATAL_ERROR "Unknown manifest contract mode")
    endif()
  endif()
  file(WRITE "${source}" "${declaration}")
  csv2_declare_test_domain(
    ID ${domain}
    SOURCES "${source}"
    MIN_STANDARD 11)
endforeach()

csv2_validate_test_manifest()
