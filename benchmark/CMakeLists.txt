add_executable(csv2_benchmark main.cpp)
target_link_libraries(csv2_benchmark PRIVATE csv2::csv2)
set_target_properties(csv2_benchmark PROPERTIES
  CXX_STANDARD 11
  CXX_STANDARD_REQUIRED ON
  CXX_EXTENSIONS OFF)
