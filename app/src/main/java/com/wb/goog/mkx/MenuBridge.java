// lang: Java, file: MenuBridge.java
// Overlay flutuante chamado via JNI pelo mod menu nativo.
// Cria um floating window com toggles e sliders usando Android Views.
// Requer permissão SYSTEM_ALERT_WINDOW (pedida na inicialização).

package com.wb.goog.mkx;

import android.app.Activity;
import android.content.Context;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;

public class MenuBridge {

    // ── Referência ao mod nativo ──────────────────────────────────────────────
    private static native void nativeOnToggle(int id, boolean value);
    private static native void nativeOnSlider(int id, float value);

    // ── Estado do menu ────────────────────────────────────────────────────────
    private static WindowManager  sWm;
    private static View           sMenuView;
    private static View           sFabView;
    private static boolean        sMenuOpen = false;
    private static boolean        sStarted  = false;

    // ── Items registrados do lado nativo ─────────────────────────────────────
    static final int TYPE_TOGGLE = 0;
    static final int TYPE_SLIDER = 1;

    static class Item {
        int    id, type;
        String label;
        boolean toggleDef;
        float   sliderMin, sliderMax, sliderDef;
    }
    private static final List<Item> sItems = new ArrayList<>();

    // Chamado pelo nativo para registrar toggles
    public static void registerToggle(int id, String label, boolean def) {
        Item it = new Item();
        it.id = id; it.type = TYPE_TOGGLE;
        it.label = label; it.toggleDef = def;
        sItems.add(it);
    }

    // Chamado pelo nativo para registrar sliders
    public static void registerSlider(int id, String label,
                                      float min, float max, float def) {
        Item it = new Item();
        it.id = id; it.type = TYPE_SLIDER;
        it.label = label;
        it.sliderMin = min; it.sliderMax = max; it.sliderDef = def;
        sItems.add(it);
    }

    // ── Ponto de entrada chamado pelo nativo ──────────────────────────────────
    public static void showMenu(final Activity activity, final String title) {
        if (sStarted) return;
        sStarted = true;

        // Verifica permissão SYSTEM_ALERT_WINDOW
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (!android.provider.Settings.canDrawOverlays(activity)) {
                // Abre tela de permissão
                android.content.Intent intent = new android.content.Intent(
                    android.provider.Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    android.net.Uri.parse("package:" + activity.getPackageName())
                );
                activity.startActivity(intent);
            }
        }

        new Handler(Looper.getMainLooper()).post(() -> {
            buildMenu(activity, title);
        });
    }

    // ── Construção da UI ──────────────────────────────────────────────────────
    private static void buildMenu(Activity activity, String title) {
        sWm = (WindowManager) activity.getSystemService(Context.WINDOW_SERVICE);
        Context ctx = activity;

        // ── FAB (botão flutuante para abrir/fechar) ───────────────────────────
        TextView fab = new TextView(ctx);
        fab.setText("MOD");
        fab.setTextColor(Color.WHITE);
        fab.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
        fab.setBackgroundColor(Color.parseColor("#CC1a0a2e"));
        fab.setGravity(Gravity.CENTER);
        fab.setPadding(16, 16, 16, 16);
        fab.setElevation(8f);

        WindowManager.LayoutParams fabParams = new WindowManager.LayoutParams(
            dp(ctx, 56), dp(ctx, 40),
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        );
        fabParams.gravity = Gravity.TOP | Gravity.START;
        fabParams.x = 20; fabParams.y = 200;

        // Drag do FAB
        final int[] fabXY = new int[2];
        fab.setOnTouchListener((v, e) -> {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    fabXY[0] = (int)e.getRawX() - fabParams.x;
                    fabXY[1] = (int)e.getRawY() - fabParams.y;
                    break;
                case MotionEvent.ACTION_MOVE:
                    fabParams.x = (int)e.getRawX() - fabXY[0];
                    fabParams.y = (int)e.getRawY() - fabXY[1];
                    sWm.updateViewLayout(fab, fabParams);
                    break;
                case MotionEvent.ACTION_UP:
                    toggleMenu(ctx, title);
                    break;
            }
            return true;
        });

        // ── Painel do menu ─────────────────────────────────────────────────────
        LinearLayout panel = buildPanel(ctx, title);

        WindowManager.LayoutParams panelParams = new WindowManager.LayoutParams(
            dp(ctx, 260), WindowManager.LayoutParams.WRAP_CONTENT,
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
                | WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
            PixelFormat.TRANSLUCENT
        );
        panelParams.gravity = Gravity.TOP | Gravity.START;
        panelParams.x = 20; panelParams.y = 250;
        panel.setVisibility(View.GONE);

        sWm.addView(fab, fabParams);
        sWm.addView(panel, panelParams);
        sFabView  = fab;
        sMenuView = panel;
    }

    private static LinearLayout buildPanel(Context ctx, String title) {
        LinearLayout root = new LinearLayout(ctx);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#E61a0a2e"));  // roxo escuro semi-opaco
        root.setPadding(0, 0, 0, dp(ctx, 8));
        root.setElevation(12f);

        // Header
        LinearLayout header = new LinearLayout(ctx);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setBackgroundColor(Color.parseColor("#FF6200"));  // laranja MK
        header.setPadding(dp(ctx,12), dp(ctx,8), dp(ctx,8), dp(ctx,8));
        header.setGravity(Gravity.CENTER_VERTICAL);

        TextView titleTv = new TextView(ctx);
        titleTv.setText(title);
        titleTv.setTextColor(Color.WHITE);
        titleTv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        titleTv.setTypeface(null, android.graphics.Typeface.BOLD);
        titleTv.setLayoutParams(new LinearLayout.LayoutParams(0,
            LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        TextView closeTv = new TextView(ctx);
        closeTv.setText("✕");
        closeTv.setTextColor(Color.WHITE);
        closeTv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        closeTv.setPadding(dp(ctx,8), 0, dp(ctx,8), 0);
        closeTv.setOnClickListener(v -> toggleMenu(ctx, title));

        header.addView(titleTv);
        header.addView(closeTv);
        root.addView(header);

        // Scroll com os items
        ScrollView scroll = new ScrollView(ctx);
        scroll.setLayoutParams(new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(ctx, 360)));

        LinearLayout itemsLayout = new LinearLayout(ctx);
        itemsLayout.setOrientation(LinearLayout.VERTICAL);
        itemsLayout.setPadding(dp(ctx,4), dp(ctx,4), dp(ctx,4), dp(ctx,4));

        for (Item item : sItems) {
            if (item.type == TYPE_TOGGLE) {
                itemsLayout.addView(buildToggleRow(ctx, item));
            } else {
                itemsLayout.addView(buildSliderRow(ctx, item));
            }
        }

        scroll.addView(itemsLayout);
        root.addView(scroll);
        return root;
    }

    private static View buildToggleRow(Context ctx, final Item item) {
        LinearLayout row = new LinearLayout(ctx);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setPadding(dp(ctx,12), dp(ctx,6), dp(ctx,12), dp(ctx,6));
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setBackgroundColor(Color.parseColor("#1A1A2E"));

        TextView label = new TextView(ctx);
        label.setText(item.label);
        label.setTextColor(Color.parseColor("#E8E8F0"));
        label.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        label.setLayoutParams(new LinearLayout.LayoutParams(0,
            LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        Switch sw = new Switch(ctx);
        sw.setChecked(item.toggleDef);
        sw.setOnCheckedChangeListener((btn, checked) -> {
            try { nativeOnToggle(item.id, checked); } catch (Throwable ignored) {}
        });

        // Separator
        View sep = new View(ctx);
        sep.setBackgroundColor(Color.parseColor("#2A2A3E"));
        LinearLayout.LayoutParams sepParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 1);
        sepParams.topMargin = 0;

        row.addView(label);
        row.addView(sw);

        LinearLayout wrapper = new LinearLayout(ctx);
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.addView(row);
        wrapper.addView(sep, sepParams);
        return wrapper;
    }

    private static View buildSliderRow(Context ctx, final Item item) {
        LinearLayout col = new LinearLayout(ctx);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(dp(ctx,12), dp(ctx,6), dp(ctx,12), dp(ctx,2));
        col.setBackgroundColor(Color.parseColor("#12122A"));

        float range = item.sliderMax - item.sliderMin;
        int progress = (int)(((item.sliderDef - item.sliderMin) / range) * 100);

        LinearLayout labelRow = new LinearLayout(ctx);
        labelRow.setOrientation(LinearLayout.HORIZONTAL);

        TextView labelTv = new TextView(ctx);
        labelTv.setText(item.label);
        labelTv.setTextColor(Color.parseColor("#A0A0C0"));
        labelTv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        labelTv.setLayoutParams(new LinearLayout.LayoutParams(0,
            LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        TextView valTv = new TextView(ctx);
        valTv.setText(String.format("%.1f", item.sliderDef));
        valTv.setTextColor(Color.parseColor("#FF6200"));
        valTv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);

        labelRow.addView(labelTv);
        labelRow.addView(valTv);

        SeekBar seek = new SeekBar(ctx);
        seek.setMax(100);
        seek.setProgress(progress);
        seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            public void onProgressChanged(SeekBar s, int prog, boolean fromUser) {
                float val = item.sliderMin + (prog / 100f) * (item.sliderMax - item.sliderMin);
                valTv.setText(String.format("%.1f", val));
                if (fromUser) {
                    try { nativeOnSlider(item.id, val); } catch (Throwable ignored) {}
                }
            }
            public void onStartTrackingTouch(SeekBar s) {}
            public void onStopTrackingTouch(SeekBar s) {}
        });

        col.addView(labelRow);
        col.addView(seek);
        return col;
    }

    private static void toggleMenu(Context ctx, String title) {
        if (sMenuView == null) return;
        sMenuOpen = !sMenuOpen;
        sMenuView.setVisibility(sMenuOpen ? View.VISIBLE : View.GONE);
    }

    private static int dp(Context ctx, int dp) {
        return (int)(dp * ctx.getResources().getDisplayMetrics().density);
    }
}
