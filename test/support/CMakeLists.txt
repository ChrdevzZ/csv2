add_library(csv2_test_support STATIC runtime_values.cpp)
target_include_directories(csv2_test_support PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(csv2_test_support PUBLIC csv2_test_fixtures)
csv2_set_test_standard(csv2_test_support 11)
csv2_enable_test_options(csv2_test_support)

add_library(csv2_minitest STATIC minitest.cpp)
target_link_libraries(csv2_minitest PUBLIC csv2_test_support)
csv2_set_test_standard(csv2_minitest 11)
csv2_enable_test_options(csv2_minitest)

set(csv2_minitest_capacity_source
  "${CMAKE_CURRENT_BINARY_DIR}/minitest_registry_capacity.cpp")
file(WRITE "${csv2_minitest_capacity_source}"
  "#include <csv2_test/case_registry.hpp>\n\n"
  "namespace {\nint executed = 0;\n")
foreach(case_index RANGE 0 599)
  file(APPEND "${csv2_minitest_capacity_source}"
    "void case_${case_index}() { ++executed; }\n"
    "csv2_test::registrar registrar_${case_index}(\"registry.capacity.${case_index}\", \"registry.capacity\", &case_${case_index});\n")
endforeach()
file(APPEND "${csv2_minitest_capacity_source}"
  "} // namespace\n\n"
  "int main() {\n"
  "  const int result = csv2_test::run_registered_tests(\"registry.capacity\");\n"
  "  return result == 0 && executed == 600 ? 0 : 1;\n"
  "}\n")

add_executable(csv2_minitest_registry_capacity
  "${csv2_minitest_capacity_source}")
target_link_libraries(csv2_minitest_registry_capacity PRIVATE csv2_minitest)
csv2_set_test_standard(csv2_minitest_registry_capacity 11)
csv2_enable_test_options(csv2_minitest_registry_capacity)
add_test(NAME csv2.minitest.registry_capacity
  COMMAND csv2_minitest_registry_capacity)
set(csv2_minitest_capacity_labels
  minitest sanitizer-runtime verification)
csv2_append_sanitizer_smoke_label(csv2_minitest_registry_capacity
  csv2_minitest_capacity_labels)
set_tests_properties(csv2.minitest.registry_capacity PROPERTIES
  LABELS "${csv2_minitest_capacity_labels}" TIMEOUT 10)

set(csv2_minitest_duplicate_source
  "${CMAKE_CURRENT_BINARY_DIR}/minitest_registry_duplicate.cpp")
file(WRITE "${csv2_minitest_duplicate_source}"
  "#include <csv2_test/case_registry.hpp>\n\n"
  "namespace {\n"
  "void first() {}\n"
  "void second() {}\n"
  "csv2_test::registrar first_registration(\"registry.duplicate\", \"registry\", &first);\n"
  "csv2_test::registrar second_registration(\"registry.duplicate\", \"registry\", &second);\n"
  "} // namespace\n\n"
  "int main() {\n"
  "  return csv2_test::run_registered_tests(\"registry\") == 2 ? 0 : 1;\n"
  "}\n")

add_executable(csv2_minitest_registry_duplicate
  "${csv2_minitest_duplicate_source}")
target_link_libraries(csv2_minitest_registry_duplicate PRIVATE csv2_minitest)
csv2_set_test_standard(csv2_minitest_registry_duplicate 11)
csv2_enable_test_options(csv2_minitest_registry_duplicate)
add_test(NAME csv2.minitest.registry_duplicate
  COMMAND csv2_minitest_registry_duplicate)
set(csv2_minitest_duplicate_labels
  minitest sanitizer-runtime verification)
csv2_append_sanitizer_smoke_label(csv2_minitest_registry_duplicate
  csv2_minitest_duplicate_labels)
set_tests_properties(csv2.minitest.registry_duplicate PROPERTIES
  LABELS "${csv2_minitest_duplicate_labels}" TIMEOUT 10)
