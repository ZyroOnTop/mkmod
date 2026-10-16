// lang: C++, file: hack.h
// target: com.wb.goog.mkx v7.4.0 (1449740), libUE4.so armeabi-v7a
// Offsets injetados pelo CI via #define — compatíveis com PYOFFSETS8.

#pragma once
#include <cstdint>

// ─── FEATURE TOGGLES ─────────────────────────────────────────────────────────
inline bool  g_god_mode     = false;
inline bool  g_one_hit_kill = false;
inline bool  g_dumb_bot     = false;
inline bool  g_no_cooldown  = false;
inline bool  g_dmg_multi    = false;
inline bool  g_def_multi    = false;
inline float g_dmg_value    = 5.0f;
inline float g_def_value    = 5.0f;

// ─── OFFSETS libUE4.so armeabi-v7a ───────────────────────────────────────────
// CI substitui os valores 0x0 abaixo via regex em #define.
// Formato #define é o único que PYOFFSETS8 consegue patch de forma não-ambígua.

#define OFFSET_TAKEDAMAGE  0x0
#define OFFSET_GETHEALTH   0x0
#define OFFSET_GETCOOLDOWN 0x0
#define OFFSET_AITICK      0x0

namespace Off {
    constexpr uintptr_t TakeDamage  = OFFSET_TAKEDAMAGE;
    constexpr uintptr_t GetHealth   = OFFSET_GETHEALTH;
    constexpr uintptr_t GetCooldown = OFFSET_GETCOOLDOWN;
    constexpr uintptr_t AITick      = OFFSET_AITICK;
}
