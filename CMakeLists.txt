cmake_minimum_required(VERSION 3.15)
project(autonomous_validation_agent CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- pybind11 ---------------------------------------------------------------
# Prefer a version installed via pip (python -m pybind11 --cmakedir)
execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
)
if(PYBIND11_CMAKE_DIR)
    list(APPEND CMAKE_PREFIX_PATH "${PYBIND11_CMAKE_DIR}")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 REQUIRED)

# ---- state machine library --------------------------------------------------
add_library(infotainment_sm_lib STATIC
    cpp/src/infotainment_sm.cpp
)
target_include_directories(infotainment_sm_lib PUBLIC cpp/include)
target_compile_options(infotainment_sm_lib PRIVATE -Wall -Wextra -O2)

# ---- pybind11 extension module ----------------------------------------------
pybind11_add_module(infotainment_sm cpp/src/bindings.cpp)
target_link_libraries(infotainment_sm PRIVATE infotainment_sm_lib)
target_include_directories(infotainment_sm PRIVATE cpp/include)

# Place the .so next to the Python package
set_target_properties(infotainment_sm PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}"
)
