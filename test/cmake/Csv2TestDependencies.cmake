include_guard(GLOBAL)

function(csv2_load_catch2)
  if(TARGET Catch2::Catch2WithMain)
    return()
  endif()

  set(CATCH_INSTALL_DOCS OFF CACHE BOOL "" FORCE)
  set(CATCH_INSTALL_EXTRAS OFF CACHE BOOL "" FORCE)
  set(CATCH_DEVELOPMENT_BUILD OFF CACHE BOOL "" FORCE)
  set(CATCH_BUILD_TESTING OFF CACHE BOOL "" FORCE)
  set(CATCH_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(CATCH_BUILD_EXTRA_TESTS OFF CACHE BOOL "" FORCE)
  set(CATCH_BUILD_FUZZERS OFF CACHE BOOL "" FORCE)
  set(CATCH_BUILD_BENCHMARKS OFF CACHE BOOL "" FORCE)
  set(CATCH_ENABLE_WERROR OFF CACHE BOOL "" FORCE)

  add_subdirectory(
    "${csv2_SOURCE_DIR}/third_party/verification/catch2"
    "${CMAKE_CURRENT_BINARY_DIR}/third_party/catch2"
    EXCLUDE_FROM_ALL)

  set_target_properties(Catch2 Catch2WithMain PROPERTIES
    FOLDER "third_party/verification"
    COMPILE_WARNING_AS_ERROR OFF)
  if(MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
    target_compile_options(Catch2 PRIVATE /EHsc)
    target_compile_options(Catch2WithMain PRIVATE /EHsc)
  endif()
endfunction()
