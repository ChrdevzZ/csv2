set(csv2_benchmark_default_fixture
  "${CMAKE_CURRENT_SOURCE_DIR}/fixtures/short_unquoted.csv" PARENT_SCOPE)

if(csv2_benchmark_enable_generated_corpus)
  if(NOT CSV2_PYTHON_AUDITS_AVAILABLE)
    message(FATAL_ERROR "Generated benchmark corpus requires Python 3.10+")
  endif()
  set(CSV2_BENCHMARK_CORPUS_SCALE "100" CACHE STRING
    "Row multiplier for the generated perf corpus")
  if(NOT CSV2_BENCHMARK_CORPUS_SCALE MATCHES "^[1-9][0-9]*$")
    message(FATAL_ERROR
      "CSV2_BENCHMARK_CORPUS_SCALE must be a positive decimal integer")
  endif()

  set(csv2_generated_corpus_root "${CMAKE_BINARY_DIR}/benchmark-corpus")
  set(csv2_generated_corpus_directory
    "${csv2_generated_corpus_root}/fixtures")
  set(csv2_generated_corpus_manifest
    "${csv2_generated_corpus_root}/manifest.json")
  add_custom_target(csv2_benchmark_corpus
    COMMAND ${CSV2_PYTHON_EXECUTABLE} -B ${CMAKE_CURRENT_SOURCE_DIR}/generate.py
      --output ${csv2_generated_corpus_directory}
      --manifest ${csv2_generated_corpus_manifest}
      --scale ${CSV2_BENCHMARK_CORPUS_SCALE}
    BYPRODUCTS
      ${csv2_generated_corpus_manifest}
    COMMENT
      "Generating deterministic CSV2 perf corpus (scale ${CSV2_BENCHMARK_CORPUS_SCALE})"
    VERBATIM)
endif()
