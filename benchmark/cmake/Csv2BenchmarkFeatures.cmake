include_guard(GLOBAL)

function(csv2_detect_benchmark_features)
  if(DEFINED CSV2_HAS_MMAP AND
     NOT CSV2_HAS_MMAP STREQUAL "0" AND
     NOT CSV2_HAS_MMAP STREQUAL "1")
    message(FATAL_ERROR "CSV2_HAS_MMAP must be 0 or 1 when set as a CMake variable")
  endif()

  if(DEFINED CSV2_HAS_MMAP AND NOT CSV2_HAS_MMAP)
    set(csv2_has_mmap FALSE)
  else()
    include(CheckCXXSourceCompiles)
    set(csv2_saved_required_definitions ${CMAKE_REQUIRED_DEFINITIONS})
    set(csv2_saved_required_includes ${CMAKE_REQUIRED_INCLUDES})
    if(DEFINED CSV2_HAS_MMAP)
      list(APPEND CMAKE_REQUIRED_DEFINITIONS -DCSV2_HAS_MMAP=1)
    endif()
    list(APPEND CMAKE_REQUIRED_INCLUDES "${csv2_SOURCE_DIR}/include")
    unset(CSV2_BENCHMARK_MMAP_PROBE CACHE)
    check_cxx_source_compiles(
      "#include <csv2/reader.hpp>\n#if !CSV2_HAS_MMAP\n#error mmap unavailable\n#endif\nint main() { csv2::Reader<> r; (void)r; }"
      CSV2_BENCHMARK_MMAP_PROBE)
    set(CMAKE_REQUIRED_DEFINITIONS ${csv2_saved_required_definitions})
    set(CMAKE_REQUIRED_INCLUDES ${csv2_saved_required_includes})
    set(csv2_has_mmap ${CSV2_BENCHMARK_MMAP_PROBE})
  endif()

  if(DEFINED CSV2_HAS_MMAP AND CSV2_HAS_MMAP AND NOT csv2_has_mmap)
    message(FATAL_ERROR "CSV2_HAS_MMAP=1 was requested, but mmap is unavailable")
  endif()
  if(csv2_has_mmap)
    set(csv2_mmap_value 1)
  else()
    set(csv2_mmap_value 0)
  endif()
  set(csv2_benchmark_has_mmap ${csv2_has_mmap} PARENT_SCOPE)
  set(csv2_benchmark_mmap_value ${csv2_mmap_value} PARENT_SCOPE)
endfunction()
