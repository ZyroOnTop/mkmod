// lang: C++17, file: main.cpp
// target: com.wb.goog.mkx v7.4.0 (1449740), Android 7.0+, ARM64
// deps: Dobby (hook), KittyMemory (patch), LGL Menu (overlay)

#include <jni.h>
#include <unistd.h>
#include <pthread.h>
#include <dlfcn.h>
#include <sys/mman.h>
#include <android/log.h>
#include <string>
#include <cstring>
#include <cstdint>

#include "hack.h"
#include "KittyMemory/MemoryPatch.h"
#include "dobby.h"

// ─── LGL Menu API (declarações mínimas para linkar com libMenu.so) ────────────
extern "C" {
    void StartMenuThread(const char* title);
    bool GetToggleState(int id);
    float GetSliderValue(int id);
    void RegisterToggle(int id, const char* label, bool def);
    void RegisterSlider(int id, const char* label, float min, float max, float def);
}

#define LOG_TAG "MKMod"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ─── IDs de feature ──────────────────────────────────────────────────────────
enum : int {
    ID_GOD_MODE     = 0,
    ID_ONE_HIT      = 1,
    ID_DUMB_BOT     = 2,
    ID_NO_COOLDOWN  = 3,
    ID_DMG_MULTI    = 4,
    ID_DEF_MULTI    = 5,
    ID_DMG_SLIDER   = 6,
    ID_DEF_SLIDER   = 7,
};

// ─── PATCHES KITTYMEMORY ─────────────────────────────────────────────────────
static MemoryPatch patch_godmode;
static MemoryPatch patch_nocooldown;

// ─── HOOKS DOBBY ─────────────────────────────────────────────────────────────

// TakeDamage  —  void TakeDamage(UFightingChar* self, float* dmg, void* src)
using FnTakeDamage = void(*)(void*, float*, void*);
static FnTakeDamage orig_TakeDamage = nullptr;

void hook_TakeDamage(void* self, float* dmg, void* src) {
    if (dmg) {
        if (GetToggleState(ID_ONE_HIT))  { *dmg = 999999.0f; }
        else if (GetToggleState(ID_DMG_MULTI)) { *dmg *= GetSliderValue(ID_DMG_SLIDER); }
    }
    if (!GetToggleState(ID_GOD_MODE) && orig_TakeDamage)
        orig_TakeDamage(self, dmg, src);
}

// GetHealth   —  float GetHealth(UFightingChar* self)
using FnGetHealth = float(*)(void*);
static FnGetHealth orig_GetHealth = nullptr;

float hook_GetHealth(void* self) {
    if (GetToggleState(ID_GOD_MODE)) return 99999.0f;
    return orig_GetHealth ? orig_GetHealth(self) : 0.0f;
}

// AITick  —  void TickAI(UAIController* self, float dt)
using FnAITick = void(*)(void*, float);
static FnAITick orig_AITick = nullptr;

void hook_AITick(void* self, float dt) {
    if (GetToggleState(ID_DUMB_BOT)) return; // bot não pensa
    if (orig_AITick) orig_AITick(self, dt);
}

// ─── INIT ────────────────────────────────────────────────────────────────────
static uintptr_t GetLibBase(const char* name) {
    FILE* f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    char line[512];
    uintptr_t base = 0;
    while (fgets(line, sizeof(line), f)) {
        if (strstr(line, name)) {
            base = (uintptr_t)strtoul(line, nullptr, 16);
            break;
        }
    }
    fclose(f);
    return base;
}

static void* hack_thread(void*) {
    // aguarda libgame.so mapear
    uintptr_t base = 0;
    for (int i = 0; i < 120 && !base; i++) {
        base = GetLibBase("libgame.so");
        usleep(500000);
    }
    if (!base) { LOGE("libgame.so not found after 60s"); return nullptr; }
    LOGI("libgame.so base: 0x%lX", (unsigned long)base);

    // KittyMemory patches
    // God Mode: RET (C0 03 5F D6) no início de TakeDamage
    if (Off::TakeDamage) {
        patch_godmode = MemoryPatch::createWithHex(
            "libgame.so", Off::TakeDamage, "C0 03 5F D6");
    }
    // No Cooldown: MOV W0,#0 (00 00 80 52) + RET
    if (Off::GetCooldown) {
        patch_nocooldown = MemoryPatch::createWithHex(
            "libgame.so", Off::GetCooldown, "00 00 80 52 C0 03 5F D6");
    }

    // Dobby hooks
    auto hook = [&](uintptr_t off, void* hk, void** orig, const char* tag) {
        if (!off) { LOGI("skip hook %s (offset 0)", tag); return; }
        void* addr = (void*)(base + off);
        int r = DobbyHook(addr, hk, orig);
        LOGI("Hook %s @ 0x%lX -> %s", tag, (unsigned long)(base+off), r==0?"OK":"FAIL");
    };

    hook(Off::TakeDamage, (void*)hook_TakeDamage, (void**)&orig_TakeDamage, "TakeDamage");
    hook(Off::GetHealth,  (void*)hook_GetHealth,  (void**)&orig_GetHealth,  "GetHealth");
    hook(Off::AITick,     (void*)hook_AITick,     (void**)&orig_AITick,     "AITick");

    // Registra itens do menu LGL
    RegisterToggle(ID_GOD_MODE,    "God Mode",        false);
    RegisterToggle(ID_ONE_HIT,     "One Hit Kill",    false);
    RegisterToggle(ID_DUMB_BOT,    "Dumb Bot",        false);
    RegisterToggle(ID_NO_COOLDOWN, "No Cooldown",     false);
    RegisterToggle(ID_DMG_MULTI,   "Damage Multi",    false);
    RegisterSlider(ID_DMG_SLIDER,  "DMG x",    1.0f, 50.0f, 5.0f);
    RegisterToggle(ID_DEF_MULTI,   "Defense Multi",   false);
    RegisterSlider(ID_DEF_SLIDER,  "DEF x",    1.0f, 50.0f, 5.0f);

    // Inicia overlay
    StartMenuThread("MK Mod 7.4");

    // Loop de sincronização de patches
    bool last_god = false, last_cd = false;
    while (true) {
        bool god = GetToggleState(ID_GOD_MODE);
        bool cd  = GetToggleState(ID_NO_COOLDOWN);
        if (god != last_god) {
            if (god) patch_godmode.get_CurrBytes().Modify();
            else     patch_godmode.get_CurrBytes().Restore();
            last_god = god;
        }
        if (cd != last_cd) {
            if (cd) patch_nocooldown.get_CurrBytes().Modify();
            else    patch_nocooldown.get_CurrBytes().Restore();
            last_cd = cd;
        }
        usleep(100000); // 10Hz
    }
    return nullptr;
}

// ─── JNI ENTRY ───────────────────────────────────────────────────────────────
JNIEXPORT jint JNI_OnLoad(JavaVM* vm, void*) {
    pthread_t t;
    pthread_create(&t, nullptr, hack_thread, nullptr);
    pthread_detach(t);
    return JNI_VERSION_1_6;
}
