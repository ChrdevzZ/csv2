function(csv2_set_test_standard target standard)
  set_target_properties(${target} PROPERTIES
    CXX_STANDARD ${standard}
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF)
endfunction()

function(csv2_enable_test_options target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4 /wd5285)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
  endif()

  if(CSV2_ENABLE_SANITIZERS)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
      target_compile_options(${target} PRIVATE
        -fsanitize=address,undefined
        -fno-omit-frame-pointer
        -fno-sanitize-recover=all)
      get_target_property(target_type ${target} TYPE)
      if(NOT target_type STREQUAL "OBJECT_LIBRARY")
        target_link_libraries(${target} PRIVATE -fsanitize=address,undefined)
      endif()
    else()
      message(FATAL_ERROR
        "CSV2_ENABLE_SANITIZERS requires GCC, Clang, or AppleClang")
    endif()
  endif()
endfunction()

function(csv2_add_test_variant target test_name standard single_header)
  add_executable(${target} main.cpp)
  target_compile_definitions(${target} PRIVATE
    DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
    CSV2_TEST_WRITER_OUTPUT="${target}-writer-output.csv")
  if(single_header)
    target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
    target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
  else()
    target_link_libraries(${target} PRIVATE csv2::csv2)
  endif()
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
  add_test(NAME ${test_name} COMMAND ${target})
  set_tests_properties(${test_name} PROPERTIES
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endfunction()

csv2_add_test_variant(csv2_test csv2.module.cxx11 11 FALSE)
csv2_add_test_variant(csv2_single_header_test csv2.single_header.cxx11 11 TRUE)
csv2_add_test_variant(csv2_test_cxx17 csv2.module.cxx17 17 FALSE)
csv2_add_test_variant(csv2_single_header_test_cxx17 csv2.single_header.cxx17 17 TRUE)

csv2_add_test_variant(csv2_test_without_mmap csv2.module.no_mmap.cxx11 11 FALSE)
target_compile_definitions(csv2_test_without_mmap PRIVATE CSV2_HAS_MMAP=0)
csv2_add_test_variant(csv2_single_header_test_without_mmap
  csv2.single_header.no_mmap.cxx11 11 TRUE)
target_compile_definitions(csv2_single_header_test_without_mmap PRIVATE CSV2_HAS_MMAP=0)

function(csv2_add_header_self_containment target source include_directory standard)
  add_library(${target} OBJECT ${source})
  target_include_directories(${target} PRIVATE ${include_directory})
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

csv2_add_header_self_containment(csv2_header_mio
  header_self_containment/mio.cpp ${csv2_SOURCE_DIR}/include 11)
csv2_add_header_self_containment(csv2_header_parameters
  header_self_containment/parameters.cpp ${csv2_SOURCE_DIR}/include 11)
csv2_add_header_self_containment(csv2_header_reader
  header_self_containment/reader.cpp ${csv2_SOURCE_DIR}/include 11)
csv2_add_header_self_containment(csv2_header_writer
  header_self_containment/writer.cpp ${csv2_SOURCE_DIR}/include 11)
csv2_add_header_self_containment(csv2_header_single
  header_self_containment/single_header.cpp ${csv2_SOURCE_DIR}/single_include 11)

csv2_add_header_self_containment(csv2_header_mio_cxx17
  header_self_containment/mio.cpp ${csv2_SOURCE_DIR}/include 17)
csv2_add_header_self_containment(csv2_header_parameters_cxx17
  header_self_containment/parameters.cpp ${csv2_SOURCE_DIR}/include 17)
csv2_add_header_self_containment(csv2_header_reader_cxx17
  header_self_containment/reader.cpp ${csv2_SOURCE_DIR}/include 17)
csv2_add_header_self_containment(csv2_header_writer_cxx17
  header_self_containment/writer.cpp ${csv2_SOURCE_DIR}/include 17)
csv2_add_header_self_containment(csv2_header_single_cxx17
  header_self_containment/single_header.cpp ${csv2_SOURCE_DIR}/single_include 17)

csv2_add_header_self_containment(csv2_header_single_without_mmap
  header_self_containment/single_header.cpp ${csv2_SOURCE_DIR}/single_include 11)
target_compile_definitions(csv2_header_single_without_mmap PRIVATE
  CSV2_HAS_MMAP=0 CSV2_EXPECT_NO_MIO)

csv2_add_header_self_containment(csv2_header_reader_without_mmap
  header_self_containment/reader.cpp ${csv2_SOURCE_DIR}/include 11)
target_compile_definitions(csv2_header_reader_without_mmap PRIVATE CSV2_HAS_MMAP=0)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  function(csv2_add_no_exceptions_test target test_name single_header)
    add_executable(${target} no_exceptions.cpp)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${target} PRIVATE csv2::csv2)
    endif()
    target_compile_options(${target} PRIVATE -fno-exceptions)
    csv2_set_test_standard(${target} 11)
    csv2_enable_test_options(${target})
    add_test(NAME ${test_name} COMMAND ${target} inputs/empty.csv)
    set_tests_properties(${test_name} PROPERTIES
      WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
  endfunction()

  csv2_add_no_exceptions_test(csv2_no_exceptions csv2.no_exceptions.module FALSE)
  csv2_add_no_exceptions_test(csv2_single_header_no_exceptions
    csv2.no_exceptions.single_header TRUE)
endif()

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  function(csv2_add_windows_api_test target test_name single_header)
    add_executable(${target} mio_windows_api_test.cpp)
    target_compile_definitions(${target} PRIVATE _WIN32)
    target_include_directories(${target} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/winapi_shim)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/include)
    endif()
    csv2_set_test_standard(${target} 11)
    csv2_enable_test_options(${target})
    add_test(NAME ${test_name} COMMAND ${target})
  endfunction()

  csv2_add_windows_api_test(csv2_mio_windows_api csv2.mio.windows_api.module FALSE)
  csv2_add_windows_api_test(csv2_single_header_mio_windows_api
    csv2.mio.windows_api.single_header TRUE)
endif()

file(COPY ${CMAKE_CURRENT_SOURCE_DIR}/inputs
     DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
