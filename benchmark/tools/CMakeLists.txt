find_package(Python3 3.10 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
  csv2_add_benchmark_check(csv2.benchmark.tooling_contract
    COMMAND ${Python3_EXECUTABLE} -m unittest discover
      -s ${CMAKE_CURRENT_SOURCE_DIR}/tests -p test_*.py -v
    TIMEOUT 30)
endif()
