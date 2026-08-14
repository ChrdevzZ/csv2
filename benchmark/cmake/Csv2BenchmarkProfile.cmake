include_guard(GLOBAL)

function(csv2_configure_benchmark_profile)
  if(23 IN_LIST csv2_supported_standards)
    set(csv2_current_benchmark_standard 23)
  elseif(20 IN_LIST csv2_supported_standards)
    set(csv2_current_benchmark_standard 20)
  else()
    message(FATAL_ERROR
      "CSV2 current-tree benchmarks require C++20 or newer")
  endif()

  if(CSV2_VERIFICATION_PROFILE STREQUAL "perf")
    set(csv2_benchmark_enable_generated_corpus TRUE)
  else()
    set(csv2_benchmark_enable_generated_corpus FALSE)
  endif()
  set(csv2_current_benchmark_standard
    ${csv2_current_benchmark_standard} PARENT_SCOPE)
  set(csv2_benchmark_enable_generated_corpus
    ${csv2_benchmark_enable_generated_corpus} PARENT_SCOPE)
endfunction()
