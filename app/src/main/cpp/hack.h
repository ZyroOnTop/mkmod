// lang: C++, file: hack.h
// target: com.wb.goog.mkx v7.4.0 (versionCode 1449740), libgame.so ARM64
// Offsets [RE] = injetados pelo script find_offsets.py no CI antes do build.

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

// ─── OFFSETS libgame.so 1449740 ARM64 ────────────────────────────────────────
// Valores substituídos pelo CI via sed antes de compilar.
// Se ficarem 0x0: CI não achou o pattern — baixe o libgame.so do artifact
// e derive manualmente no Ghidra (ver README).

namespace Off {
    constexpr uintptr_t TakeDamage      = OFFSET_TAKEDAMAGE;
    constexpr uintptr_t GetHealth       = OFFSET_GETHEALTH;
    constexpr uintptr_t GetCooldown     = OFFSET_GETCOOLDOWN;
    constexpr uintptr_t AITick          = OFFSET_AITICK;
}
