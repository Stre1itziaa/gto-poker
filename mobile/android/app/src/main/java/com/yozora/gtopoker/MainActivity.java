package com.yozora.gtopoker;

import android.os.Bundle;
import android.view.Window;

import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(AntiAddictionPlugin.class);
        super.onCreate(savedInstanceState);
        /* 沉浸式全屏（游戏标配）：隐藏状态栏+导航栏，白边根除；
         * 从屏幕边缘滑动可临时呼出系统栏（BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE） */
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        hideSystemBars();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        /* BridgeActivity.onResume 为 final 不可覆盖；
         * 切出再回来（或权限弹窗后）系统栏会复现，窗口重获焦点时再隐藏 */
        if (hasFocus) hideSystemBars();
    }

    private void hideSystemBars() {
        Window w = getWindow();
        if (w == null) return;
        WindowInsetsControllerCompat ctl = WindowCompat.getInsetsController(w, w.getDecorView());
        if (ctl == null) return;
        ctl.setSystemBarsBehavior(
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        ctl.hide(WindowInsetsCompat.Type.systemBars());
    }
}
