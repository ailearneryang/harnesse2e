# B60VS-F03 越野信息算法 — CMakeLists.txt
#
# 需求追溯:
# - architecture.md §6.3 C++ 算法核心模块
# - [NFR-001] ≤ 12MB (strip 后 .so ≤ 4MB)
# - [NFR-002] 禁止动态内存分配

cmake_minimum_required(VERSION 3.22.1)
project("offroad" LANGUAGES CXX)

# 内存优化编译选项 [NFR-001, NFR-002]
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Os -fno-exceptions -fno-rtti -fvisibility=hidden")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -Wl,--gc-sections -Wl,--strip-all")

# 定义 liboffroad.so
add_library(offroad SHARED
    offroad_jni.cpp
    attitude_engine.cpp
    altitude_engine.cpp
    compass_engine.cpp
    pressure_filter.cpp
    calib_manager.cpp
    can_encoder.cpp
)

# 链接 Android 日志库
find_library(log-lib log)
target_link_libraries(offroad ${log-lib})

# 不链接 STL 动态库(减小体积)
target_compile_definitions(offroad PRIVATE
    OFFROAD_VERSION="1.0.0"
)
