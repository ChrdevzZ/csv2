function(csv2_configure_fuzz_target target source standalone)
  add_executable(${target} ${source})
  target_link_libraries(${target} PRIVATE csv2::csv2)
  target_compile_definitions(${target} PRIVATE CSV2_HAS_MMAP=0)
  if(standalone)
    target_compile_definitions(${target} PRIVATE CSV2_FUZZ_STANDALONE)
    csv2_set_test_standard(${target} 11)
    csv2_enable_test_options(${target})
  else()
    target_compile_options(${target} PRIVATE
      -fsanitize=fuzzer,address,undefined
      -fno-omit-frame-pointer
      -fno-sanitize-recover=all)
    set_property(TARGET ${target} APPEND_STRING PROPERTY LINK_FLAGS
      " -fsanitize=fuzzer,address,undefined")
    csv2_set_test_standard(${target} 20)
    csv2_enable_test_options(${target})
  endif()
endfunction()

if(CSV2_BUILD_TESTS)
  csv2_configure_fuzz_target(csv2_fuzz_smoke reader.cpp TRUE)
  add_test(NAME csv2.fuzz.reader.smoke.cxx11 COMMAND csv2_fuzz_smoke)
  set_tests_properties(csv2.fuzz.reader.smoke.cxx11 PROPERTIES
    LABELS "fuzz-smoke;reader;sanitizer-runtime;sanitizer-smoke" TIMEOUT 30
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})

  csv2_configure_fuzz_target(csv2_fuzz_writer_smoke writer_roundtrip.cpp TRUE)
  add_test(NAME csv2.fuzz.writer.smoke.cxx11 COMMAND csv2_fuzz_writer_smoke)
  set_tests_properties(csv2.fuzz.writer.smoke.cxx11 PROPERTIES
    LABELS "fuzz-smoke;writer;sanitizer-runtime;sanitizer-smoke" TIMEOUT 30
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endif()

if(CSV2_BUILD_FUZZERS)
  if(WIN32 OR NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang" OR
     CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
    message(FATAL_ERROR
      "CSV2_BUILD_FUZZERS requires Clang with the GNU frontend on a "
      "non-Windows platform")
  endif()
  csv2_configure_fuzz_target(csv2_fuzz reader.cpp FALSE)
  csv2_configure_fuzz_target(csv2_fuzz_writer writer_roundtrip.cpp FALSE)
endif()
