cmake_minimum_required(VERSION 3.16)
project(quantforge_native VERSION 0.3.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
find_package(Threads REQUIRED)

add_library(quantforge_headers INTERFACE)
target_include_directories(quantforge_headers INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)

add_library(quantforge_native SHARED src/capi.cpp)
target_link_libraries(quantforge_native PRIVATE quantforge_headers Threads::Threads)
set_target_properties(quantforge_native PROPERTIES CXX_VISIBILITY_PRESET hidden)

add_executable(price_option examples/price_option.cpp)
target_link_libraries(price_option PRIVATE quantforge_headers Threads::Threads)

enable_testing()
add_executable(test_engine tests/test_engine.cpp)
target_link_libraries(test_engine PRIVATE quantforge_headers Threads::Threads)
if(MSVC)
  target_compile_options(test_engine PRIVATE /W4)
else()
  target_compile_options(test_engine PRIVATE -Wall -Wextra -Wpedantic)
endif()
add_test(NAME engine COMMAND test_engine)
