// lang: C++17, file: main.cpp
// target: com.wb.goog.mkx v7.4.0 (1449740), libUE4.so armeabi-v7a
// deps: Dobby (hook), KittyMemory (patch), MenuBridge.java (overlay)

#include <jni.h>
#include <unistd.h>
#include <pthread.h>
#include <android/log.h>
#include <string>
#include <cstring>
#include <cstdint>
#include <atomic>

#include "hack.h"
#include "KittyMemory/MemoryPatch.h"
#include "dobby.h"
#include "menu.h"

#define LOG_TAG "MKMod"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ─── IDs de feature ───────────────────────────────────────────────────────────
enum FeatureID : int {
    ID_GOD_MODE     = 0,
    ID_ONE_HIT      = 1,
    ID_DUMB_BOT     = 2,
    ID_NO_COOLDOWN  = 3,
    ID_DMG_MULTI    = 4,
    ID_DMG_SLIDER   = 5,
    ID_DEF_MULTI    = 6,
    ID_DEF_SLIDER   = 7,
};

// ─── KittyMemory patches ──────────────────────────────────────────────────────
static MemoryPatch patch_godmode;
static MemoryPatch patch_nocooldown;

// ─── Dobby hooks ─────────────────────────────────────────────────────────────
// ARMv7: TakeDamage(UFighter* self, float* dmg, void* instigator)
// Offset bit0 = Thumb — Dobby detecta automaticamente
using FnTakeDamage = void(*)(void*, float*, void*);
static FnTakeDamage orig_TakeDamage = nullptr;

void hook_TakeDamage(void* self, float* dmg, void* instigator) {
    if (dmg) {
        if (Menu::GetToggle(ID_ONE_HIT))
            *dmg = 999999.0f;
        else if (Menu::GetToggle(ID_DMG_MULTI))
            *dmg *= Menu::GetSlider(ID_DMG_SLIDER);
    }
    // god mode: não chama original (player não recebe dano)
    if (!Menu::GetToggle(ID_GOD_MODE) && orig_TakeDamage)
        orig_TakeDamage(self, dmg, instigator);
}

using FnGetHealth = float(*)(void*);
static FnGetHealth orig_GetHealth = nullptr;

float hook_GetHealth(void* self) {
    if (Menu::GetToggle(ID_GOD_MODE)) return 99999.0f;
    return orig_GetHealth ? orig_GetHealth(self) : 0.0f;
}

using FnAITick = void(*)(void*, float);
static FnAITick orig_AITick = nullptr;

void hook_AITick(void* self, float dt) {
    if (Menu::GetToggle(ID_DUMB_BOT)) return;
    if (orig_AITick) orig_AITick(self, dt);
}

// ─── GetLibBase ───────────────────────────────────────────────────────────────
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

// ─── Setup de hooks ───────────────────────────────────────────────────────────
static void SetupHooks(uintptr_t base) {
    auto DoHook = [&](uintptr_t off, void* hk, void** orig, const char* tag) {
        if (!off) { LOGI("skip hook %s (offset 0)", tag); return; }
        // ARMv7 Thumb: Dobby espera endereço sem bit0 — o offset do scanner
        // já tem bit0 removido. Passamos direto.
        void* addr = reinterpret_cast<void*>(base + off);
        int r = DobbyHook(addr, hk, orig);
        LOGI("Hook %s @ 0x%lX: %s", tag, (unsigned long)(base + off),
             r == 0 ? "OK" : "FAIL");
    };

    DoHook(Off::TakeDamage, (void*)hook_TakeDamage,
           reinterpret_cast<void**>(&orig_TakeDamage), "TakeDamage");
    DoHook(Off::GetHealth,  (void*)hook_GetHealth,
           reinterpret_cast<void**>(&orig_GetHealth),  "GetHealth");
    DoHook(Off::AITick,     (void*)hook_AITick,
           reinterpret_cast<void**>(&orig_AITick),     "AITick");
}

// ─── Setup de patches ─────────────────────────────────────────────────────────
static void SetupPatches(uintptr_t base) {
    if (Off::TakeDamage)
        patch_godmode = MemoryPatch::createWithHex("libUE4.so",
            Off::TakeDamage, "70 47");  // BX lr (Thumb16 RET) — ARMv7
    if (Off::GetCooldown)
        patch_nocooldown = MemoryPatch::createWithHex("libUE4.so",
            Off::GetCooldown, "00 20 70 47");  // MOV r0,#0 + BX lr — ARMv7 Thumb
}

// ─── Thread principal ─────────────────────────────────────────────────────────
static void* hack_thread(void*) {
    // aguarda libUE4.so carregar
    uintptr_t base = 0;
    for (int i = 0; i < 120 && !base; i++) {
        base = GetLibBase("libUE4.so");
        usleep(500000);
    }
    if (!base) { LOGE("libUE4.so não encontrado após 60s"); return nullptr; }
    LOGI("libUE4.so base: 0x%lX", (unsigned long)base);

    SetupPatches(base);
    SetupHooks(base);

    // Registra items do menu
    Menu::SetTitle("MK Mod 7.4");
    Menu::AddToggle(ID_GOD_MODE,    "God Mode",      false);
    Menu::AddToggle(ID_ONE_HIT,     "One Hit Kill",  false);
    Menu::AddToggle(ID_DUMB_BOT,    "Dumb Bot",      false);
    Menu::AddToggle(ID_NO_COOLDOWN, "No Cooldown",   false);
    Menu::AddToggle(ID_DMG_MULTI,   "Damage Multi",  false);
    Menu::AddSlider(ID_DMG_SLIDER,  "DMG x", 1.0f, 50.0f, 5.0f);
    Menu::AddToggle(ID_DEF_MULTI,   "Defense Multi", false);
    Menu::AddSlider(ID_DEF_SLIDER,  "DEF x", 1.0f, 50.0f, 5.0f);

    // Loop de sincronização de patches
    bool last_god = false, last_cd = false;
    while (true) {
        bool god = Menu::GetToggle(ID_GOD_MODE);
        bool cd  = Menu::GetToggle(ID_NO_COOLDOWN);
        if (god != last_god) {
            god ? patch_godmode.get_CurrBytes().Modify()
                : patch_godmode.get_CurrBytes().Restore();
            last_god = god;
        }
        if (cd != last_cd) {
            cd ? patch_nocooldown.get_CurrBytes().Modify()
              : patch_nocooldown.get_CurrBytes().Restore();
            last_cd = cd;
        }
        usleep(100000);
    }
    return nullptr;
}

// ─── JNI — Menu callbacks do Java ────────────────────────────────────────────
extern "C" {

JNIEXPORT void JNICALL
Java_com_wb_goog_mkx_MenuBridge_nativeOnToggle(JNIEnv*, jclass, jint id, jboolean val) {
    for (auto& it : Menu::g_items) {
        if (it.id == id && it.type == Menu::MenuItem::TOGGLE) {
            it.toggle_val.store(val);
            if (it.on_toggle) it.on_toggle(val);
            break;
        }
    }
}

JNIEXPORT void JNICALL
Java_com_wb_goog_mkx_MenuBridge_nativeOnSlider(JNIEnv*, jclass, jint id, jfloat val) {
    for (auto& it : Menu::g_items) {
        if (it.id == id && it.type == Menu::MenuItem::SLIDER) {
            it.slider_int.store((int)(val * 10));
            break;
        }
    }
}

// ─── JNI_OnLoad ───────────────────────────────────────────────────────────────
JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void*) {
    Menu::g_jvm = vm;
    pthread_t t;
    pthread_create(&t, nullptr, hack_thread, nullptr);
    pthread_detach(t);
    LOGI("JNI_OnLoad: hack_thread launched");
    return JNI_VERSION_1_6;
}

} // extern "C"
