if(NOT 20 IN_LIST csv2_supported_standards)
  message(FATAL_ERROR
    "CSV2_BUILD_BENCHMARKS requires CMake and a compiler with C++20 support")
endif()

add_executable(csv2_benchmark main.cpp)
add_executable(csv2_benchmark_allocations main.cpp)
target_compile_definitions(csv2_benchmark_allocations PRIVATE
  CSV2_BENCHMARK_ENABLE_ALLOCATION_TRACKING=1)
foreach(target IN ITEMS csv2_benchmark csv2_benchmark_allocations)
  target_link_libraries(${target} PRIVATE csv2::csv2)
  set_target_properties(${target} PROPERTIES
    CXX_STANDARD 20
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF)
endforeach()

if(CSV2_BUILD_TESTS)
  set(csv2_python_executable)
  if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.12)
    find_package(Python3 3.10 COMPONENTS Interpreter QUIET)
    if(Python3_Interpreter_FOUND)
      set(csv2_python_executable ${Python3_EXECUTABLE})
    endif()
  else()
    find_package(PythonInterp 3.10 QUIET)
    if(PYTHONINTERP_FOUND)
      set(csv2_python_executable ${PYTHON_EXECUTABLE})
    endif()
  endif()
  if(csv2_python_executable)
    add_test(NAME csv2.benchmark.metrics_contract
      COMMAND ${csv2_python_executable}
        ${CMAKE_CURRENT_SOURCE_DIR}/test_collect_metrics.py -v)
    set_tests_properties(csv2.benchmark.metrics_contract PROPERTIES
      LABELS benchmark-checksum)
  endif()

  set(csv2_benchmark_fixture ${csv2_SOURCE_DIR}/test/inputs/test_01.csv)
  set(csv2_benchmark_mmap_fixture
      ${CMAKE_CURRENT_BINARY_DIR}/csv2_benchmark_fixture.csv)
  # Generate a byte-for-byte stable mmap fixture. Source-tree checkouts can
  # retain historical CRLF contents even though .gitattributes now requests LF.
  file(WRITE ${csv2_benchmark_mmap_fixture} "a,b,c")
  function(csv2_add_benchmark_checksum operation source checksum)
    add_test(NAME csv2.benchmark.checksum.${operation}
      COMMAND csv2_benchmark --operation ${operation}
        --input ${csv2_benchmark_fixture} --source ${source} --iterations 1
        --expect-checksum ${checksum})
    set_tests_properties(csv2.benchmark.checksum.${operation} PROPERTIES
      LABELS benchmark-checksum)
  endfunction()

  csv2_add_benchmark_checksum(rows_only buffer 8674000034234459039)
  csv2_add_benchmark_checksum(rows_cells buffer 6437334155717714538)
  csv2_add_benchmark_checksum(raw_to_string buffer 4405620607395608627)
  csv2_add_benchmark_checksum(decoded_to_string buffer 4405620607395608627)
  csv2_add_benchmark_checksum(decoded_to_vector buffer 4405620607395608627)
  csv2_add_benchmark_checksum(ranges_pipeline buffer 6437334155717714538)
  csv2_add_benchmark_checksum(integer_conversion buffer 6437334155733299317)
  csv2_add_benchmark_checksum(writer_raw buffer 9730279101474490404)
  csv2_add_benchmark_checksum(writer_escaped buffer 9730279101474490404)
  add_test(NAME csv2.benchmark.allocations.rows_cells
    COMMAND csv2_benchmark_allocations --operation rows_cells
      --input ${csv2_benchmark_fixture} --source buffer --iterations 1
      --track-allocations --expect-allocations 0)
  set_tests_properties(csv2.benchmark.allocations.rows_cells PROPERTIES
    LABELS benchmark-checksum)
  if(CSV2_HAS_MMAP OR NOT DEFINED CSV2_HAS_MMAP)
    add_test(NAME csv2.benchmark.checksum.map_only
      COMMAND csv2_benchmark --operation map_only
        --input ${csv2_benchmark_mmap_fixture} --source mmap --iterations 1
        --expect-checksum 8674000034234391210)
    set_tests_properties(csv2.benchmark.checksum.map_only PROPERTIES
      LABELS benchmark-checksum)
    add_test(NAME csv2.benchmark.checksum.rows_cells_mmap
      COMMAND csv2_benchmark --operation rows_cells
        --input ${csv2_benchmark_mmap_fixture} --source mmap --iterations 1
        --expect-checksum 8674000034234409885)
    set_tests_properties(csv2.benchmark.checksum.rows_cells_mmap PROPERTIES
      LABELS benchmark-checksum)
  endif()
endif()
