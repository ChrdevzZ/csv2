# CPack's source traversal interprets directory names as glob expressions.
# Keep binary CPack, but build source archives with literal-path CMake copying.
set(CPACK_GENERATOR "TGZ;TXZ")
include(CPack)
file(REMOVE "${CMAKE_CURRENT_BINARY_DIR}/CPackSourceConfig.cmake")

set(CSV2_SOURCE_PACKAGE_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}" CACHE PATH
  "Directory for the TGZ and TXZ source archives")
# Select a literal delimiter absent from all configured path values.
set(CSV2_SOURCE_PACKAGE_QUOTE "=")
set(csv2_package_paths
  "${CMAKE_CURRENT_SOURCE_DIR}${CMAKE_CURRENT_BINARY_DIR}${CSV2_SOURCE_PACKAGE_OUTPUT_DIRECTORY}")
string(FIND "${csv2_package_paths}" "]${CSV2_SOURCE_PACKAGE_QUOTE}]" csv2_quote_at)
while(NOT csv2_quote_at EQUAL -1)
  string(APPEND CSV2_SOURCE_PACKAGE_QUOTE "=")
  string(FIND "${csv2_package_paths}" "]${CSV2_SOURCE_PACKAGE_QUOTE}]" csv2_quote_at)
endwhile()
configure_file("${CMAKE_CURRENT_LIST_DIR}/csv2-package-source.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/csv2-package-source.cmake" @ONLY)
cmake_policy(PUSH)
if(CMAKE_VERSION VERSION_LESS 3.11)
  # CMake <=3.10 reserves package_source even without its generated config.
  cmake_policy(SET CMP0037 OLD)
endif()
add_custom_target(package_source
  COMMAND "${CMAKE_COMMAND}" -P
    "${CMAKE_CURRENT_BINARY_DIR}/csv2-package-source.cmake"
  COMMENT "Creating TGZ and TXZ source archives"
  VERBATIM)
cmake_policy(POP)
