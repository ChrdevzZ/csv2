function(csv2_add_header_self_containment target header_definition include_directory standard)
  add_library(${target} OBJECT headers/self_containment.cpp)
  target_compile_definitions(${target} PRIVATE
    CSV2_TEST_HEADER_ONLY
    ${header_definition})
  target_include_directories(${target} PRIVATE ${include_directory})
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

function(csv2_add_config_contract target standard)
  add_library(${target} OBJECT config/config.cpp)
  target_link_libraries(${target} PRIVATE csv2::csv2)
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

function(csv2_add_config_fallback_contract target standard single_header)
  add_library(${target} OBJECT config/config_fallback.cpp)
  if(single_header)
    target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
    target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
  else()
    target_link_libraries(${target} PRIVATE csv2::csv2)
  endif()
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

csv2_filter_supported_standards(csv2_config_standards 11 20 23)
foreach(standard IN LISTS csv2_config_standards)
  csv2_add_config_contract(csv2_config_contract_cxx${standard} ${standard})
endforeach()

csv2_filter_supported_standards(csv2_config_fallback_standards 17 20 23)
foreach(standard IN LISTS csv2_config_fallback_standards)
  csv2_add_config_fallback_contract(
    csv2_config_fallback_module_cxx${standard} ${standard} FALSE)
  csv2_add_config_fallback_contract(
    csv2_config_fallback_single_cxx${standard} ${standard} TRUE)
endforeach()

csv2_filter_supported_standards(csv2_mmap_path_standards 11 17 20 23)
foreach(standard IN LISTS csv2_mmap_path_standards)
  add_library(csv2_mmap_path_contract_cxx${standard} OBJECT mmap/path.cpp)
  target_link_libraries(csv2_mmap_path_contract_cxx${standard} PRIVATE csv2::csv2)
  csv2_set_test_standard(csv2_mmap_path_contract_cxx${standard} ${standard})
  csv2_enable_test_options(csv2_mmap_path_contract_cxx${standard})

  add_library(csv2_mmap_path_contract_single_cxx${standard} OBJECT mmap/path.cpp)
  target_compile_definitions(csv2_mmap_path_contract_single_cxx${standard} PRIVATE
    CSV2_TEST_SINGLE_HEADER)
  target_include_directories(csv2_mmap_path_contract_single_cxx${standard} PRIVATE
    ${csv2_SOURCE_DIR}/single_include)
  csv2_set_test_standard(csv2_mmap_path_contract_single_cxx${standard} ${standard})
  csv2_enable_test_options(csv2_mmap_path_contract_single_cxx${standard})

  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_mmap_path_contract_no_mmap_single_cxx${standard})
    else()
      set(target csv2_mmap_path_contract_no_mmap_module_cxx${standard})
    endif()
    add_library(${target} OBJECT mmap/path.cpp)
    target_compile_definitions(${target} PRIVATE CSV2_HAS_MMAP=0)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${target} ${standard})
    csv2_enable_test_options(${target})
  endforeach()
endforeach()

csv2_filter_supported_standards(csv2_header_standards 11 17 20 23)
foreach(standard IN LISTS csv2_header_standards)
  set(suffix "_cxx${standard}")
  if(standard EQUAL 11)
    set(suffix "")
  endif()

  csv2_add_header_self_containment(csv2_header_mio${suffix}
    CSV2_TEST_HEADER_MIO ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_parameters${suffix}
    CSV2_TEST_HEADER_PARAMETERS ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_errors${suffix}
    CSV2_TEST_HEADER_ERRORS ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_reader${suffix}
    CSV2_TEST_HEADER_READER ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_writer${suffix}
    CSV2_TEST_HEADER_WRITER ${csv2_SOURCE_DIR}/include ${standard})
  csv2_add_header_self_containment(csv2_header_single${suffix}
    CSV2_TEST_SINGLE_HEADER ${csv2_SOURCE_DIR}/single_include ${standard})
endforeach()

foreach(standard IN LISTS csv2_header_standards)
  set(suffix "_cxx${standard}")
  if(standard EQUAL 11)
    set(suffix "")
  endif()

  csv2_add_header_self_containment(csv2_header_single_without_mmap${suffix}
    CSV2_TEST_SINGLE_HEADER ${csv2_SOURCE_DIR}/single_include ${standard})
  target_compile_definitions(csv2_header_single_without_mmap${suffix} PRIVATE
    CSV2_HAS_MMAP=0 CSV2_EXPECT_NO_MIO)

  csv2_add_header_self_containment(csv2_header_reader_without_mmap${suffix}
    CSV2_TEST_HEADER_READER ${csv2_SOURCE_DIR}/include ${standard})
  target_compile_definitions(csv2_header_reader_without_mmap${suffix} PRIVATE
    CSV2_HAS_MMAP=0 CSV2_EXPECT_NO_MIO)

  csv2_add_header_self_containment(csv2_header_mio_without_mmap${suffix}
    CSV2_TEST_HEADER_MIO ${csv2_SOURCE_DIR}/include ${standard})
  target_compile_definitions(csv2_header_mio_without_mmap${suffix} PRIVATE
    CSV2_HAS_MMAP=0 CSV2_EXPECT_NO_MIO)
endforeach()

function(csv2_add_degraded_standard_contract standard)
  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_standard_contract_degraded_single_cxx${standard})
    else()
      set(target csv2_standard_contract_degraded_module_cxx${standard})
    endif()
    add_library(${target} OBJECT standards/standard_cxx${standard}.cpp)
    target_compile_definitions(${target} PRIVATE
      CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES
      CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${target} ${standard})
    csv2_enable_test_options(${target})

    if(single_header)
      set(mmap_target csv2_mmap_path_contract_degraded_single_cxx${standard})
    else()
      set(mmap_target csv2_mmap_path_contract_degraded_module_cxx${standard})
    endif()
    add_library(${mmap_target} OBJECT mmap/path.cpp)
    target_compile_definitions(${mmap_target} PRIVATE
      CSV2_DETAIL_DISABLE_OPTIONAL_FACILITIES
      CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
    if(single_header)
      target_compile_definitions(${mmap_target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${mmap_target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${mmap_target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${mmap_target} ${standard})
    csv2_enable_test_options(${mmap_target})
  endforeach()
endfunction()

set(csv2_degraded_headers_directory
  "${CMAKE_CURRENT_BINARY_DIR}/degraded_standard_library")
file(MAKE_DIRECTORY "${csv2_degraded_headers_directory}")
file(WRITE "${csv2_degraded_headers_directory}/version"
  "/* Deliberately empty partial <version> fixture. */\n")
file(WRITE "${csv2_degraded_headers_directory}/string_view"
  "#pragma GCC system_header\n#include_next <string_view>\n"
  "#ifndef __cpp_lib_string_view\n"
  "#define __cpp_lib_string_view 201606L\n#endif\n")
file(WRITE "${csv2_degraded_headers_directory}/filesystem"
  "#pragma GCC system_header\n#include_next <filesystem>\n"
  "#ifndef __cpp_lib_filesystem\n"
  "#define __cpp_lib_filesystem 201703L\n#endif\n")
file(WRITE "${csv2_degraded_headers_directory}/span"
  "#pragma GCC system_header\n#include_next <span>\n"
  "#ifndef __cpp_lib_span\n#define __cpp_lib_span 202002L\n#endif\n")
file(WRITE "${csv2_degraded_headers_directory}/ranges"
  "#pragma GCC system_header\n#include_next <ranges>\n"
  "#ifndef __cpp_lib_ranges\n#define __cpp_lib_ranges 201911L\n#endif\n")

set(csv2_empty_headers_directory
  "${CMAKE_CURRENT_BINARY_DIR}/empty_standard_library")
file(MAKE_DIRECTORY "${csv2_empty_headers_directory}")
foreach(header IN ITEMS
    version string_view filesystem charconv memory_resource span ranges expected)
  file(WRITE "${csv2_empty_headers_directory}/${header}"
    "#pragma once\n#pragma GCC system_header\n#pragma GCC diagnostic push\n"
    "#pragma GCC diagnostic ignored \"-Wpedantic\"\n"
    "#include_next <${header}>\n#pragma GCC diagnostic pop\n")
endforeach()
file(APPEND "${csv2_empty_headers_directory}/version"
  "#undef __cpp_lib_string_view\n#undef __cpp_lib_filesystem\n"
  "#undef __cpp_lib_to_chars\n#undef __cpp_lib_memory_resource\n"
  "#undef __cpp_lib_span\n#undef __cpp_lib_ranges\n"
  "#undef __cpp_lib_ranges_to_container\n#undef __cpp_lib_expected\n")
file(APPEND "${csv2_empty_headers_directory}/string_view"
  "#undef __cpp_lib_string_view\n")
file(APPEND "${csv2_empty_headers_directory}/filesystem"
  "#undef __cpp_lib_filesystem\n")
file(APPEND "${csv2_empty_headers_directory}/charconv"
  "#undef __cpp_lib_to_chars\n")
file(APPEND "${csv2_empty_headers_directory}/memory_resource"
  "#undef __cpp_lib_memory_resource\n")
file(APPEND "${csv2_empty_headers_directory}/span"
  "#undef __cpp_lib_span\n")
file(APPEND "${csv2_empty_headers_directory}/ranges"
  "#undef __cpp_lib_ranges\n#undef __cpp_lib_ranges_to_container\n")
file(APPEND "${csv2_empty_headers_directory}/expected"
  "#undef __cpp_lib_expected\n")

csv2_filter_supported_standards(csv2_degraded_standards 17 20 23)
foreach(standard IN LISTS csv2_degraded_standards)
  csv2_add_degraded_standard_contract(${standard})

  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_standard_contract_partial_headers_single_cxx${standard})
    else()
      set(target csv2_standard_contract_partial_headers_module_cxx${standard})
    endif()
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang" AND
       NOT CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
      add_library(${target} OBJECT standards/standard_cxx${standard}.cpp)
      target_include_directories(${target} BEFORE PRIVATE
        ${csv2_degraded_headers_directory})
      if(single_header)
        target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
        target_include_directories(${target} PRIVATE
          ${csv2_SOURCE_DIR}/single_include)
      else()
        target_link_libraries(${target} PRIVATE csv2::csv2)
      endif()
      csv2_set_test_standard(${target} ${standard})
      csv2_enable_test_options(${target})

      if(single_header)
        set(degraded_target
          csv2_standard_contract_empty_headers_single_cxx${standard})
      else()
        set(degraded_target
          csv2_standard_contract_empty_headers_module_cxx${standard})
      endif()
      add_library(${degraded_target} OBJECT standards/standard_cxx${standard}.cpp)
      target_compile_definitions(${degraded_target} PRIVATE
        CSV2_TEST_DEGRADED_OPTIONAL_FACILITIES)
      target_include_directories(${degraded_target} BEFORE PRIVATE
        ${csv2_empty_headers_directory})
      if(single_header)
        target_compile_definitions(${degraded_target} PRIVATE CSV2_TEST_SINGLE_HEADER)
        target_include_directories(${degraded_target} PRIVATE
          ${csv2_SOURCE_DIR}/single_include)
      else()
        target_link_libraries(${degraded_target} PRIVATE csv2::csv2)
      endif()
      csv2_set_test_standard(${degraded_target} ${standard})
      csv2_enable_test_options(${degraded_target})
    endif()
  endforeach()
endforeach()

function(csv2_add_version_guard_contract standard single_header)
  if(single_header)
    set(target csv2_version_guard_single_cxx${standard})
  else()
    set(target csv2_version_guard_module_cxx${standard})
  endif()
  add_library(${target} OBJECT config/config.cpp)
  if(single_header)
    target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
    target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
  else()
    target_link_libraries(${target} PRIVATE csv2::csv2)
  endif()
  csv2_set_test_standard(${target} ${standard})
  csv2_enable_test_options(${target})
endfunction()

csv2_filter_supported_standards(csv2_pre_cxx20_standards 11 14 17)
foreach(standard IN LISTS csv2_pre_cxx20_standards)
  csv2_add_version_guard_contract(${standard} FALSE)
  csv2_add_version_guard_contract(${standard} TRUE)
endforeach()

function(csv2_add_standard_contract standard)
  foreach(single_header IN ITEMS FALSE TRUE)
    if(single_header)
      set(target csv2_standard_contract_single_cxx${standard})
    else()
      set(target csv2_standard_contract_module_cxx${standard})
    endif()
    add_library(${target} OBJECT standards/standard_cxx${standard}.cpp)
    if(single_header)
      target_compile_definitions(${target} PRIVATE CSV2_TEST_SINGLE_HEADER)
      target_include_directories(${target} PRIVATE ${csv2_SOURCE_DIR}/single_include)
    else()
      target_link_libraries(${target} PRIVATE csv2::csv2)
    endif()
    csv2_set_test_standard(${target} ${standard})
    csv2_enable_test_options(${target})
  endforeach()
endfunction()

foreach(standard IN LISTS csv2_supported_standards)
  csv2_add_standard_contract(${standard})
endforeach()

foreach(csv2_superproject_mode IN ITEMS
    normal catch_collision benchmark_collision)
  add_test(NAME csv2.vendor.superproject.${csv2_superproject_mode}
    COMMAND ${CMAKE_COMMAND}
      -DCSV2_TEST_CONTRACT_ROOT=${CMAKE_CURRENT_BINARY_DIR}/superproject/${csv2_superproject_mode}
      -DCSV2_TEST_CONTRACT_SOURCE=${CMAKE_CURRENT_SOURCE_DIR}/superproject
      -DCSV2_TEST_CONTRACT_CSV2_SOURCE=${csv2_SOURCE_DIR}
      -DCSV2_TEST_CONTRACT_GENERATOR=${CMAKE_GENERATOR}
      -DCSV2_TEST_CONTRACT_GENERATOR_PLATFORM=${CMAKE_GENERATOR_PLATFORM}
      -DCSV2_TEST_CONTRACT_GENERATOR_TOOLSET=${CMAKE_GENERATOR_TOOLSET}
      -DCSV2_TEST_CONTRACT_CXX_COMPILER=${CMAKE_CXX_COMPILER}
      -DCSV2_TEST_CONTRACT_CMAKE_RC_COMPILER=${CMAKE_RC_COMPILER}
      -DCSV2_TEST_CONTRACT_CMAKE_MT=${CMAKE_MT}
      -DCSV2_TEST_CONTRACT_MODE=${csv2_superproject_mode}
      -P ${CMAKE_CURRENT_SOURCE_DIR}/../cmake/superproject_contract.cmake)
  set_tests_properties(csv2.vendor.superproject.${csv2_superproject_mode}
    PROPERTIES LABELS "vendor-isolation;verification" TIMEOUT 180)
endforeach()
