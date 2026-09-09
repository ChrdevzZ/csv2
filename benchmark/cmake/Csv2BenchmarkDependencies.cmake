include_guard(GLOBAL)

function(csv2_load_google_benchmark)
  csv2_vendor_assert_targets_absent(google_benchmark
    benchmark benchmark_main benchmark::benchmark benchmark::benchmark_main)
  csv2_vendor_cache_snapshot(csv2_benchmark_cache)

  set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_USE_BUNDLED_GTEST OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_DOWNLOAD_DEPENDENCIES OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_DOXYGEN OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_INSTALL_DOCS OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_INSTALL_TOOLS OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_WERROR OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_FORCE_WERROR OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_ASSEMBLY_TESTS OFF CACHE BOOL "" FORCE)
  if(CSV2_VERIFICATION_PROFILE STREQUAL "perf" AND UNIX AND NOT APPLE)
    find_library(CSV2_BENCHMARK_PFM_LIBRARY pfm)
    find_path(CSV2_BENCHMARK_PFM_INCLUDE_DIR perfmon/pfmlib.h)
    if(CSV2_BENCHMARK_PFM_LIBRARY AND CSV2_BENCHMARK_PFM_INCLUDE_DIR)
      set(BENCHMARK_ENABLE_LIBPFM ON CACHE BOOL "" FORCE)
    else()
      set(BENCHMARK_ENABLE_LIBPFM OFF CACHE BOOL "" FORCE)
    endif()
  else()
    set(BENCHMARK_ENABLE_LIBPFM OFF CACHE BOOL "" FORCE)
  endif()

  add_subdirectory(
    "${csv2_SOURCE_DIR}/third_party/verification/google_benchmark"
    "${CMAKE_CURRENT_BINARY_DIR}/third_party/google_benchmark"
    EXCLUDE_FROM_ALL)

  csv2_vendor_cache_restore(csv2_benchmark_cache)

  if(NOT TARGET benchmark OR NOT TARGET benchmark_main OR
     NOT TARGET benchmark::benchmark OR NOT TARGET benchmark::benchmark_main)
    message(FATAL_ERROR "The vendored Google Benchmark targets were not created")
  endif()
  set_target_properties(benchmark benchmark_main PROPERTIES
    FOLDER "third_party/verification"
    COMPILE_WARNING_AS_ERROR OFF)
  if(MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
    # The root verification layer deliberately removes a global /EHsc and
    # adds it only to targets that need exceptions. Google Benchmark is an
    # isolated third-party target, so restore its own required unwind mode.
    target_compile_options(benchmark PRIVATE /EHsc)
    target_compile_options(benchmark_main PRIVATE /EHsc)
  endif()
endfunction()
