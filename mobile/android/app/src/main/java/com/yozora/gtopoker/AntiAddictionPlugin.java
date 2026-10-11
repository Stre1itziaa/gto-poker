package com.yozora.gtopoker;

import android.app.Activity;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.Map;

import com.taptap.sdk.core.TapTapSdk;
import com.taptap.sdk.core.TapTapSdkOptions;
import com.taptap.sdk.core.TapTapRegion;
import com.taptap.sdk.compliance.TapTapCompliance;
import com.taptap.sdk.compliance.TapTapComplianceCallback;
import com.taptap.sdk.compliance.option.TapTapComplianceOptions;
import com.taptap.sdk.compliance.constants.ComplianceMessage;

/**
 * TapTap 合规认证（实名+防沉迷） Capacitor 桥接。
 * JS 侧: Capacitor.Plugins.AntiAddiction.init/startup/exit/getRemainingTime/getAgeRange
 * 回调事件: addListener('result', ({code}) => {})  code 见 ComplianceMessage。
 * clientId 未配置时 init 返回 {enabled:false}，游戏照常运行（开发态）。
 */
@CapacitorPlugin(name = "AntiAddiction")
public class AntiAddictionPlugin extends Plugin {

    private volatile boolean inited = false;

    @PluginMethod
    public void init(PluginCall call) {
        String clientId = call.getString("clientId", "");
        String clientToken = call.getString("clientToken", "");
        JSObject ret = new JSObject();
        if (clientId.isEmpty()) {
            ret.put("enabled", false);
            ret.put("reason", "clientId not configured");
            call.resolve(ret);
            return;
        }
        final Activity activity = bridge.getActivity();
        activity.runOnUiThread(() -> {
            try {
                TapTapSdkOptions sdkOptions =
                        new TapTapSdkOptions(clientId, clientToken, TapTapRegion.CN);
                // showSwitchAccount=true: 受限时玩家可切换 TapTap 账号重走实名
                // useAgeRange=false: 无适龄限制需求，静默授权不弹年龄段确认
                TapTapComplianceOptions complianceOptions =
                        new TapTapComplianceOptions(true, false);
                TapTapSdk.init(activity, sdkOptions,
                        new TapTapComplianceOptions[]{ complianceOptions });

                TapTapCompliance.registerComplianceCallback(
                        (TapTapComplianceCallback) (code, extra) -> {
                            JSObject data = new JSObject();
                            data.put("code", code);
                            if (extra != null) {
                                JSObject x = new JSObject();
                                for (Map.Entry<String, ?> e : extra.entrySet()) {
                                    Object v = e.getValue();
                                    if (v instanceof Number || v instanceof Boolean
                                            || v instanceof String) {
                                        x.put(e.getKey(), v);
                                    } else if (v != null) {
                                        x.put(e.getKey(), String.valueOf(v));
                                    }
                                }
                                data.put("extra", x);
                            }
                            notifyListeners("result", data);
                        });

                inited = true;
                ret.put("enabled", true);
                call.resolve(ret);
            } catch (Throwable t) {
                ret.put("enabled", false);
                ret.put("reason", String.valueOf(t));
                call.resolve(ret);
            }
        });
    }

    @PluginMethod
    public void startup(PluginCall call) {
        JSObject ret = new JSObject();
        if (!inited) {
            ret.put("started", false);
            ret.put("reason", "not inited");
            call.resolve(ret);
            return;
        }
        final String userId = call.getString("userId", "");
        final Activity activity = bridge.getActivity();
        activity.runOnUiThread(() -> {
            try {
                TapTapCompliance.startup(activity, userId);
                ret.put("started", true);
            } catch (Throwable t) {
                ret.put("started", false);
                ret.put("reason", String.valueOf(t));
            }
            call.resolve(ret);
        });
    }

    @PluginMethod
    public void getRemainingTime(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("seconds", inited ? TapTapCompliance.getRemainingTime() : -1);
        call.resolve(ret);
    }

    @PluginMethod
    public void getAgeRange(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("ageRange", inited ? TapTapCompliance.getAgeRange() : -1);
        call.resolve(ret);
    }

    @PluginMethod
    public void exit(PluginCall call) {
        if (inited) {
            bridge.getActivity().runOnUiThread(TapTapCompliance::exit);
        }
        call.resolve();
    }
}
