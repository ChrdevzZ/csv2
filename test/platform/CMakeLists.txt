if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  function(csv2_add_windows_api_test target test_name single_header)
    add_executable(${target} windows_mio_shim.cpp)
    target_include_directories(${target} PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/winapi_stub)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/include)
    endif()
    csv2_set_test_standard(${target} 11)
    csv2_enable_test_options(${target})
    csv2_register_runtime_test(${target} ${test_name})
  endfunction()

  csv2_add_windows_api_test(csv2_mio_windows_api
    csv2.mio.winapi_injection.module.cxx11 FALSE)
  csv2_add_windows_api_test(csv2_single_header_mio_windows_api
    csv2.mio.winapi_injection.single_header.cxx11 TRUE)
endif()
