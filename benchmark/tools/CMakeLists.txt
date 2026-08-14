if(CSV2_PYTHON_AUDITS_AVAILABLE)
  csv2_add_benchmark_check(csv2.benchmark.tooling_contract
    COMMAND ${CSV2_PYTHON_EXECUTABLE} -m unittest discover
      -s ${CMAKE_CURRENT_SOURCE_DIR}/tests -p test_*.py -v
    TIMEOUT 30)
endif()
