cmake_minimum_required(VERSION 3.22)
project(MKMod CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ─── KittyMemory ─────────────────────────────────────────────────────────────
set(KITTY_DIR ${CMAKE_CURRENT_SOURCE_DIR}/KittyMemory)
add_library(KittyMemory STATIC
    ${KITTY_DIR}/KittyMemory.cpp
    ${KITTY_DIR}/MemoryPatch.cpp
    ${KITTY_DIR}/KittyUtils.cpp
)
target_include_directories(KittyMemory PUBLIC ${KITTY_DIR})

# ─── Dobby (pré-compilado pelo CI em Dobby/libs/${ANDROID_ABI}/) ─────────────
add_library(dobby STATIC IMPORTED)
set_target_properties(dobby PROPERTIES
    IMPORTED_LOCATION
    ${CMAKE_CURRENT_SOURCE_DIR}/Dobby/libs/${ANDROID_ABI}/libdobby.a
)
target_include_directories(dobby INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/Dobby/include
)

# ─── MKMod ────────────────────────────────────────────────────────────────────
add_library(MKMod SHARED main.cpp)

target_include_directories(MKMod PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(MKMod
    KittyMemory
    dobby
    log
    android
)

# flags
target_compile_options(MKMod PRIVATE
    -O2
    -fvisibility=hidden
    -ffunction-sections
    -fdata-sections
    -Wno-unused-variable
    -Wno-unused-function
)
target_link_options(MKMod PRIVATE
    -Wl,--gc-sections
    -Wl,--strip-all
)
