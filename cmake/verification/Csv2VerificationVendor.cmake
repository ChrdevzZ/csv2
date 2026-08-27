include_guard(GLOBAL)

function(csv2_vendor_assert_targets_absent dependency)
  foreach(target IN LISTS ARGN)
    if(TARGET "${target}")
      message(FATAL_ERROR
        "Cannot load vendored ${dependency}: target ${target} already exists")
    endif()
  endforeach()
endfunction()

macro(csv2_vendor_cache_snapshot prefix)
  get_cmake_property(${prefix}_variables CACHE_VARIABLES)
  foreach(csv2_cache_name IN LISTS ${prefix}_variables)
    string(SHA256 csv2_cache_id "${csv2_cache_name}")
    get_property(${prefix}_${csv2_cache_id}_value
      CACHE "${csv2_cache_name}" PROPERTY VALUE)
    get_property(${prefix}_${csv2_cache_id}_type
      CACHE "${csv2_cache_name}" PROPERTY TYPE)
    get_property(${prefix}_${csv2_cache_id}_help
      CACHE "${csv2_cache_name}" PROPERTY HELPSTRING)
    get_property(${prefix}_${csv2_cache_id}_advanced_set
      CACHE "${csv2_cache_name}" PROPERTY ADVANCED SET)
    if(${prefix}_${csv2_cache_id}_advanced_set)
      get_property(${prefix}_${csv2_cache_id}_advanced
        CACHE "${csv2_cache_name}" PROPERTY ADVANCED)
    endif()
    get_property(${prefix}_${csv2_cache_id}_strings_set
      CACHE "${csv2_cache_name}" PROPERTY STRINGS SET)
    if(${prefix}_${csv2_cache_id}_strings_set)
      get_property(${prefix}_${csv2_cache_id}_strings
        CACHE "${csv2_cache_name}" PROPERTY STRINGS)
    endif()
  endforeach()
endmacro()

macro(csv2_vendor_cache_restore prefix)
  get_cmake_property(csv2_cache_after CACHE_VARIABLES)
  foreach(csv2_cache_name IN LISTS csv2_cache_after)
    list(FIND ${prefix}_variables "${csv2_cache_name}" csv2_cache_original_index)
    if(csv2_cache_original_index EQUAL -1)
      unset("${csv2_cache_name}" CACHE)
    endif()
  endforeach()

  foreach(csv2_cache_name IN LISTS ${prefix}_variables)
    string(SHA256 csv2_cache_id "${csv2_cache_name}")
    get_property(csv2_cache_current_type_set
      CACHE "${csv2_cache_name}" PROPERTY TYPE SET)
    if(csv2_cache_current_type_set)
      get_property(csv2_cache_current_value
        CACHE "${csv2_cache_name}" PROPERTY VALUE)
      get_property(csv2_cache_current_type
        CACHE "${csv2_cache_name}" PROPERTY TYPE)
      get_property(csv2_cache_current_help
        CACHE "${csv2_cache_name}" PROPERTY HELPSTRING)
    endif()
    if(NOT csv2_cache_current_type_set OR
       NOT csv2_cache_current_value STREQUAL
         "${${prefix}_${csv2_cache_id}_value}" OR
       NOT csv2_cache_current_type STREQUAL
         "${${prefix}_${csv2_cache_id}_type}" OR
       NOT csv2_cache_current_help STREQUAL
         "${${prefix}_${csv2_cache_id}_help}")
      set("${csv2_cache_name}" "${${prefix}_${csv2_cache_id}_value}"
        CACHE "${${prefix}_${csv2_cache_id}_type}"
        "${${prefix}_${csv2_cache_id}_help}" FORCE)
    endif()

    get_property(csv2_cache_current_advanced_set
      CACHE "${csv2_cache_name}" PROPERTY ADVANCED SET)
    if(csv2_cache_current_advanced_set)
      get_property(csv2_cache_current_advanced
        CACHE "${csv2_cache_name}" PROPERTY ADVANCED)
    endif()
    if(${prefix}_${csv2_cache_id}_advanced_set)
      if(NOT csv2_cache_current_advanced_set OR
         NOT csv2_cache_current_advanced STREQUAL
           "${${prefix}_${csv2_cache_id}_advanced}")
        set_property(CACHE "${csv2_cache_name}" PROPERTY ADVANCED
          "${${prefix}_${csv2_cache_id}_advanced}")
      endif()
    elseif(csv2_cache_current_advanced_set)
      unset("${csv2_cache_name}-ADVANCED" CACHE)
    endif()

    get_property(csv2_cache_current_strings_set
      CACHE "${csv2_cache_name}" PROPERTY STRINGS SET)
    if(csv2_cache_current_strings_set)
      get_property(csv2_cache_current_strings
        CACHE "${csv2_cache_name}" PROPERTY STRINGS)
    endif()
    if(${prefix}_${csv2_cache_id}_strings_set)
      if(NOT csv2_cache_current_strings_set OR
         NOT csv2_cache_current_strings STREQUAL
           "${${prefix}_${csv2_cache_id}_strings}")
        set_property(CACHE "${csv2_cache_name}" PROPERTY STRINGS
          "${${prefix}_${csv2_cache_id}_strings}")
      endif()
    elseif(csv2_cache_current_strings_set)
      unset("${csv2_cache_name}-STRINGS" CACHE)
    endif()
  endforeach()

  # ADVANCED and STRINGS are represented by internal companion Cache entries.
  # Remove any companion created while restoring an originally unset property.
  get_cmake_property(csv2_cache_after_restore CACHE_VARIABLES)
  foreach(csv2_cache_name IN LISTS csv2_cache_after_restore)
    list(FIND ${prefix}_variables "${csv2_cache_name}" csv2_cache_original_index)
    if(csv2_cache_original_index EQUAL -1)
      unset("${csv2_cache_name}" CACHE)
    endif()
  endforeach()
endmacro()
