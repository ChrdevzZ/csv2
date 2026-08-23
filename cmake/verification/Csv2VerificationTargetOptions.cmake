include_guard(GLOBAL)

if(MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
  string(REGEX REPLACE "(^| )[/-]EHsc( |$)" " "
    CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}")
endif()

if(CSV2_ENABLE_SANITIZERS AND
   CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND
   CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
  if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR
     (CMAKE_CXX_COMPILER_ARCHITECTURE_ID AND
      NOT CMAKE_CXX_COMPILER_ARCHITECTURE_ID STREQUAL "x64"))
    message(FATAL_ERROR
      "CSV2 Clang-CL sanitizers currently require an x64 target")
  endif()

  execute_process(
    COMMAND "${CMAKE_CXX_COMPILER}" --print-resource-dir
    RESULT_VARIABLE csv2_clang_resource_result
    OUTPUT_VARIABLE csv2_clang_resource_directory
    OUTPUT_STRIP_TRAILING_WHITESPACE)
  if(NOT csv2_clang_resource_result EQUAL 0 OR
     NOT IS_DIRECTORY "${csv2_clang_resource_directory}/lib/windows")
    message(FATAL_ERROR
      "Unable to locate the Clang-CL compiler-rt directory")
  endif()

  set(csv2_clang_runtime_directory
    "${csv2_clang_resource_directory}/lib/windows")
  set(csv2_clang_asan_library
    "${csv2_clang_runtime_directory}/clang_rt.asan_dynamic-x86_64.lib")
  set(csv2_clang_asan_thunk_library
    "${csv2_clang_runtime_directory}/clang_rt.asan_dynamic_runtime_thunk-x86_64.lib")
  set(csv2_clang_ubsan_libraries
    "${csv2_clang_runtime_directory}/clang_rt.ubsan_standalone-x86_64.lib"
    "${csv2_clang_runtime_directory}/clang_rt.ubsan_standalone_cxx-x86_64.lib")
  set(csv2_clang_required_runtime_files
    "${csv2_clang_asan_library}"
    "${csv2_clang_asan_thunk_library}"
    ${csv2_clang_ubsan_libraries}
    "${csv2_clang_runtime_directory}/clang_rt.asan_dynamic-x86_64.dll")
  foreach(csv2_runtime_file IN LISTS csv2_clang_required_runtime_files)
    if(NOT EXISTS "${csv2_runtime_file}")
      message(FATAL_ERROR
        "Required Clang-CL runtime is missing: ${csv2_runtime_file}")
    endif()
  endforeach()
endif()

function(csv2_set_test_standard target standard)
  set_target_properties(${target} PROPERTIES
    CXX_STANDARD ${standard}
    CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF)
endfunction()

function(csv2_enable_test_options target)
  set(csv2_disables_exceptions FALSE)
  foreach(option IN LISTS ARGN)
    if(option STREQUAL "NO_EXCEPTIONS")
      set(csv2_disables_exceptions TRUE)
    else()
      message(FATAL_ERROR "Unknown csv2 verification option: ${option}")
    endif()
  endforeach()

  if(MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
    target_compile_options(${target} PRIVATE /W4)
    if(csv2_disables_exceptions)
      target_compile_options(${target} PRIVATE /EHs-c-)
    else()
      target_compile_options(${target} PRIVATE /EHsc)
    endif()
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    if(csv2_disables_exceptions)
      target_compile_options(${target} PRIVATE -fno-exceptions)
    endif()
  endif()

  if(CSV2_ENABLE_SANITIZERS)
    if(MSVC OR CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
      # Third-party verification libraries intentionally remain unsanitized.
      # Match their MSVC STL annotation mode while retaining instrumentation
      # of every first-party target.
      target_compile_definitions(${target} PRIVATE _DISABLE_STL_ANNOTATION)
    endif()
    if(CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
      target_compile_options(${target} PRIVATE /fsanitize=address /Zi)
      get_target_property(target_type ${target} TYPE)
      if(NOT target_type STREQUAL "OBJECT_LIBRARY")
        set_property(TARGET ${target} APPEND_STRING PROPERTY LINK_FLAGS " /DEBUG")
      endif()
    elseif(CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND
           CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
      target_compile_options(${target} PRIVATE
        -fsanitize=address,undefined
        -fno-sanitize=object-size
        -fno-sanitize-recover=all
        /Oy-
        /Zi)
      get_target_property(target_type ${target} TYPE)
      if(NOT target_type STREQUAL "OBJECT_LIBRARY")
        target_link_libraries(${target} PRIVATE
          "${csv2_clang_asan_library}"
          ${csv2_clang_ubsan_libraries})
        set_property(TARGET ${target} APPEND_STRING PROPERTY LINK_FLAGS
          " /WHOLEARCHIVE:\"${csv2_clang_asan_thunk_library}\" /DEBUG")
      endif()
    elseif(CMAKE_CXX_COMPILER_FRONTEND_VARIANT STREQUAL "MSVC")
      message(FATAL_ERROR
        "CSV2_ENABLE_SANITIZERS does not support "
        "${CMAKE_CXX_COMPILER_ID} with the MSVC frontend")
    elseif(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
      target_compile_options(${target} PRIVATE
        -fsanitize=address,undefined
        -fno-omit-frame-pointer
        -fno-sanitize-recover=all)
      get_target_property(target_type ${target} TYPE)
      if(NOT target_type STREQUAL "OBJECT_LIBRARY")
        target_link_libraries(${target} PRIVATE -fsanitize=address,undefined)
      endif()
    else()
      message(FATAL_ERROR
        "CSV2_ENABLE_SANITIZERS requires MSVC, GCC, Clang, or AppleClang")
    endif()
  endif()
endfunction()
