cmake_minimum_required(VERSION 3.22)
project(MKMod CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ─── KittyMemory ─────────────────────────────────────────────────────────────
set(KITTY_SRC
    ${CMAKE_CURRENT_SOURCE_DIR}/KittyMemory/KittyMemory.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/KittyMemory/MemoryPatch.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/KittyMemory/KittyUtils.cpp
)
add_library(KittyMemory STATIC ${KITTY_SRC})
target_include_directories(KittyMemory PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/KittyMemory)

# ─── Dobby (pré-compilado pelo CI) ───────────────────────────────────────────
add_library(dobby STATIC IMPORTED)
set_target_properties(dobby PROPERTIES
    IMPORTED_LOCATION
    ${CMAKE_CURRENT_SOURCE_DIR}/dobby/libs/${ANDROID_ABI}/libdobby.a
)
target_include_directories(dobby INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/dobby/include
)

# ─── LGL Menu (pré-compilado pelo CI) ────────────────────────────────────────
add_library(MenuLib SHARED IMPORTED)
set_target_properties(MenuLib PROPERTIES
    IMPORTED_LOCATION
    ${CMAKE_CURRENT_SOURCE_DIR}/Menu/libs/${ANDROID_ABI}/libMenu.so
)
target_include_directories(MenuLib INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/Menu/include
)

# ─── MKMod ───────────────────────────────────────────────────────────────────
add_library(MKMod SHARED main.cpp)

target_include_directories(MKMod PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(MKMod
    KittyMemory
    dobby
    MenuLib
    log
    android
)

# flags de segurança (dificultam detecção)
target_compile_options(MKMod PRIVATE
    -O3
    -fvisibility=hidden
    -ffunction-sections
    -fdata-sections
)
target_link_options(MKMod PRIVATE
    -Wl,--gc-sections
    -Wl,--strip-all
)
