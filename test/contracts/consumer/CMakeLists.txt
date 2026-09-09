cmake_minimum_required(VERSION 3.10)
project(csv2_install_consumer LANGUAGES CXX)

find_package(csv2 CONFIG REQUIRED)

add_executable(csv2_consumer main.cpp)
target_link_libraries(csv2_consumer PRIVATE csv2::csv2)
target_compile_features(csv2_consumer PRIVATE cxx_std_20)
set_target_properties(csv2_consumer PROPERTIES CXX_EXTENSIONS OFF)

add_executable(csv2_no_mmap_consumer no_mmap.cpp)
target_link_libraries(csv2_no_mmap_consumer PRIVATE csv2::csv2)
target_compile_features(csv2_no_mmap_consumer PRIVATE cxx_std_11)
target_compile_definitions(csv2_no_mmap_consumer PRIVATE CSV2_HAS_MMAP=0)
set_target_properties(csv2_no_mmap_consumer PROPERTIES CXX_EXTENSIONS OFF)
