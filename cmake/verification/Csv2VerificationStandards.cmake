include_guard(GLOBAL)

# Keep optional verification matrices on one compiler/CMake-supported list.
# CXX_STANDARD values 20, 23, and 26 were added in CMake 3.12, 3.20, and
# 3.25. The cxx_std_26 compile feature was added separately in CMake 3.30.
set(csv2_supported_standards)
foreach(csv2_standard IN ITEMS 11 14 17)
  if(cxx_std_${csv2_standard} IN_LIST CMAKE_CXX_COMPILE_FEATURES)
    list(APPEND csv2_supported_standards ${csv2_standard})
  endif()
endforeach()
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.12 AND
   cxx_std_20 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  list(APPEND csv2_supported_standards 20)
endif()
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.20 AND
   cxx_std_23 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  list(APPEND csv2_supported_standards 23)
endif()
if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.30 AND
   cxx_std_26 IN_LIST CMAKE_CXX_COMPILE_FEATURES)
  list(APPEND csv2_supported_standards 26)
endif()

function(csv2_filter_supported_standards output)
  set(csv2_filtered_standards)
  foreach(csv2_standard IN LISTS ARGN)
    if(csv2_standard IN_LIST csv2_supported_standards)
      list(APPEND csv2_filtered_standards ${csv2_standard})
    endif()
  endforeach()
  set(${output} ${csv2_filtered_standards} PARENT_SCOPE)
endfunction()
