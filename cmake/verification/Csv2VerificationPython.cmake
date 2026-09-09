include_guard(GLOBAL)

function(csv2_configure_python_audits component)
  get_property(csv2_python_checked GLOBAL PROPERTY CSV2_PYTHON_AUDITS_CHECKED)
  if(NOT csv2_python_checked)
    find_package(Python3 3.10 COMPONENTS Interpreter QUIET)
    if(Python3_Interpreter_FOUND)
      set_property(GLOBAL PROPERTY CSV2_PYTHON_AUDITS_AVAILABLE TRUE)
      set_property(GLOBAL PROPERTY CSV2_PYTHON_AUDITS_EXECUTABLE
        "${Python3_EXECUTABLE}")
    else()
      set_property(GLOBAL PROPERTY CSV2_PYTHON_AUDITS_AVAILABLE FALSE)
    endif()
    set_property(GLOBAL PROPERTY CSV2_PYTHON_AUDITS_CHECKED TRUE)
  endif()

  get_property(csv2_python_available GLOBAL
    PROPERTY CSV2_PYTHON_AUDITS_AVAILABLE)
  get_property(csv2_python_executable GLOBAL
    PROPERTY CSV2_PYTHON_AUDITS_EXECUTABLE)
  set(csv2_python_required FALSE)
  if(CSV2_REQUIRE_PYTHON_AUDITS OR
     CSV2_VERIFICATION_PROFILE STREQUAL "full" OR
     CSV2_VERIFICATION_PROFILE STREQUAL "perf")
    set(csv2_python_required TRUE)
  endif()

  if(NOT csv2_python_available)
    if(csv2_python_required)
      message(FATAL_ERROR
        "Python 3.10+ is required for ${component} audits when "
        "CSV2_REQUIRE_PYTHON_AUDITS=ON or the verification profile is "
        "full/perf")
    endif()
    message(WARNING
      "Python 3.10+ was not found; quick verification is incomplete. "
      "Skipped ${component} audits. Set CSV2_REQUIRE_PYTHON_AUDITS=ON to "
      "make this a configuration error.")
  endif()

  set(CSV2_PYTHON_AUDITS_AVAILABLE "${csv2_python_available}" PARENT_SCOPE)
  set(CSV2_PYTHON_EXECUTABLE "${csv2_python_executable}" PARENT_SCOPE)
endfunction()
