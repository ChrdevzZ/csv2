function(csv2_enable_test_warnings target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra)
  endif()
endfunction()

if(MSVC)
  string(REGEX REPLACE "/W[0-4]" "" CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}")
endif()

add_executable(csv2_test main.cpp)
target_compile_definitions(csv2_test PRIVATE DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN)
target_compile_features(csv2_test PRIVATE cxx_std_11)
target_link_libraries(csv2_test PRIVATE csv2::csv2)
csv2_enable_test_warnings(csv2_test)

add_executable(csv2_single_header_test main.cpp)
target_compile_definitions(csv2_single_header_test PRIVATE
  CSV2_TEST_SINGLE_HEADER
  DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN)
target_compile_features(csv2_single_header_test PRIVATE cxx_std_11)
target_include_directories(csv2_single_header_test PRIVATE
  ${csv2_SOURCE_DIR}/single_include)
csv2_enable_test_warnings(csv2_single_header_test)

if(MSVC)
  target_compile_options(csv2_test PRIVATE /wd5285)
  target_compile_options(csv2_single_header_test PRIVATE /wd5285)
endif()

file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/inputs
     DESTINATION ${CMAKE_CURRENT_BINARY_DIR})

add_test(NAME csv2.module COMMAND csv2_test)
add_test(NAME csv2.single_header COMMAND csv2_single_header_test)
set_tests_properties(csv2.module csv2.single_header PROPERTIES
  WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
