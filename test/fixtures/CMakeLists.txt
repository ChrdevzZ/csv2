add_library(csv2_test_fixtures INTERFACE)
target_compile_definitions(csv2_test_fixtures INTERFACE
  CSV2_TEST_FIXTURE_ROOT="${CMAKE_CURRENT_SOURCE_DIR}/upstream")
