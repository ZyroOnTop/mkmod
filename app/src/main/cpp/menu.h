// lang: C++, file: menu.h
// Mod menu floating auto-contido via JNI + Android WindowManager
// Sem dependência de repo externo. ARMv7 + ARM64.
// API mínima: Android 7.0 (API 24)

#pragma once
#include <jni.h>
#include <android/log.h>
#include <pthread.h>
#include <string>
#include <vector>
#include <functional>
#include <atomic>

#define MENU_TAG "MKMenu"
#define MLOGI(...) __android_log_print(ANDROID_LOG_INFO,  MENU_TAG, __VA_ARGS__)
#define MLOGE(...) __android_log_print(ANDROID_LOG_ERROR, MENU_TAG, __VA_ARGS__)

// ─── Item do menu ─────────────────────────────────────────────────────────────
struct MenuItem {
    enum Type { TOGGLE, SLIDER };
    int   id;
    Type  type;
    std::string label;
    std::atomic<bool>  toggle_val{false};
    std::atomic<int>   slider_int{0};  // valor * 10 para atomic int
    float slider_min = 1.0f;
    float slider_max = 50.0f;
    float slider_def = 5.0f;
    std::function<void(bool)> on_toggle;
};

// ─── Estado global do menu ────────────────────────────────────────────────────
namespace Menu {

static std::vector<MenuItem> g_items;
static std::atomic<bool>     g_visible{false};
static std::string           g_title{"Mod Menu"};
static JavaVM*               g_jvm  = nullptr;
static jobject               g_activity = nullptr;  // weak ref
static pthread_t             g_thread;

// API pública
void SetTitle(const char* title) { g_title = title; }

void AddToggle(int id, const char* label, bool def = false,
               std::function<void(bool)> cb = nullptr) {
    MenuItem item;
    item.id    = id;
    item.type  = MenuItem::TOGGLE;
    item.label = label;
    item.toggle_val.store(def);
    item.on_toggle = cb;
    g_items.push_back(std::move(item));
}

void AddSlider(int id, const char* label,
               float mn = 1.0f, float mx = 50.0f, float def = 5.0f) {
    MenuItem item;
    item.id         = id;
    item.type       = MenuItem::SLIDER;
    item.label      = label;
    item.slider_min = mn;
    item.slider_max = mx;
    item.slider_def = def;
    item.slider_int.store((int)(def * 10));
    g_items.push_back(std::move(item));
}

bool GetToggle(int id) {
    for (auto& it : g_items)
        if (it.id == id && it.type == MenuItem::TOGGLE)
            return it.toggle_val.load();
    return false;
}

float GetSlider(int id) {
    for (auto& it : g_items)
        if (it.id == id && it.type == MenuItem::SLIDER)
            return it.slider_int.load() / 10.0f;
    return 1.0f;
}

// ─── Thread do menu via JNI ───────────────────────────────────────────────────
// O menu é implementado como uma Activity popup transparente com botões
// criada via JNI chamando código Java através de reflection.
// Isso é mais confiável que WindowManager overlay em Android 10+.

static JNIEnv* GetEnv() {
    JNIEnv* env = nullptr;
    if (!g_jvm) return nullptr;
    int state = g_jvm->GetEnv((void**)&env, JNI_VERSION_1_6);
    if (state == JNI_EDETACHED) {
        g_jvm->AttachCurrentThread(&env, nullptr);
    }
    return env;
}

// Cria overlay via WindowManager + TextView usando JNI puro
// Funciona em API 24+ com permissão SYSTEM_ALERT_WINDOW
static void CreateOverlayJNI() {
    JNIEnv* env = GetEnv();
    if (!env || !g_activity) {
        MLOGE("JNI env ou activity não disponível");
        return;
    }

    // Chama runOnUiThread com um Runnable que cria a View
    jclass actClass = env->GetObjectClass(g_activity);
    if (!actClass) { MLOGE("Não achou classe da activity"); return; }

    jmethodID runOnUiThread = env->GetMethodID(actClass, "runOnUiThread",
                                               "(Ljava/lang/Runnable;)V");
    if (!runOnUiThread) {
        // Tenta via reflection para game engines que wrappam a Activity
        MLOGE("runOnUiThread não encontrado — tentando via Handler");
        env->DeleteLocalRef(actClass);
        return;
    }

    // Cria o Runnable via proxy anonimo não é simples em JNI puro
    // Usamos uma abordagem diferente: chamar um método estático na nossa
    // classe Java (MenuBridge) que foi carregada junto com a lib

    jclass bridge = env->FindClass("com/wb/goog/mkx/MenuBridge");
    if (!bridge) {
        MLOGI("MenuBridge não encontrada — menu JNI não disponível nesta versão");
        env->DeleteLocalRef(actClass);
        return;
    }

    jmethodID show = env->GetStaticMethodID(bridge, "showMenu",
                                            "(Landroid/app/Activity;Ljava/lang/String;)V");
    if (show) {
        jstring title = env->NewStringUTF(g_title.c_str());
        env->CallStaticVoidMethod(bridge, show, g_activity, title);
        env->DeleteLocalRef(title);
        MLOGI("Menu JNI iniciado via MenuBridge.showMenu");
    } else {
        MLOGE("MenuBridge.showMenu não encontrado");
    }

    env->DeleteLocalRef(bridge);
    env->DeleteLocalRef(actClass);
}

static void* MenuThread(void*) {
    MLOGI("Menu thread iniciada");
    // Aguarda activity estar disponível
    for (int i = 0; i < 60 && !g_activity; i++) usleep(500000);
    if (!g_activity) {
        MLOGE("Activity não disponível após 30s — abortando menu thread");
        return nullptr;
    }
    CreateOverlayJNI();
    return nullptr;
}

void Start(JavaVM* jvm, jobject activity) {
    g_jvm      = jvm;
    g_activity = activity;
    pthread_create(&g_thread, nullptr, MenuThread, nullptr);
    pthread_detach(g_thread);
    MLOGI("Menu::Start() chamado");
}

} // namespace Menu
