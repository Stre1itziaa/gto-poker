/* anti-addiction.js · TapTap 合规认证（实名+防沉迷）JS 封装
 *
 * 仅在 Capacitor APP 态生效；Web/浏览器态为 no-op。
 * 启用前提（两步，缺一自动降级为跳过）：
 *   1. 本文件 CONFIG.clientId/clientToken 填入 TapTap 开发者中心的 Client ID / Token
 *      （开发者中心 > 游戏服务 > 开发与构建 > 合规认证 开通「暂无版号」方案后可建应用拿值）
 *   2. APK 由 mobile/android 构建（原生桥 AntiAddictionPlugin 已注册）
 * 回调码: 500 正常 / 1030 时段限制 / 1050 时长耗尽 / 1100 年龄限制 /
 *         1200 网络或配置错误 / 9002 认证窗被关可重试 / 1000 退出 / 1001 切换账号
 */
(function (root) {
  'use strict';

  var CONFIG = {
    clientId: '',     // ← TapTap 开发者中心 Client ID（填空字符串 = 防沉迷关闭）
    clientToken: ''   // ← TapTap 开发者中心 Client Token
  };

  var MSG = {
    500: '认证通过，欢迎回到夜樱扑克部',
    1000: '已退出认证',
    1001: '账号已切换，请重新认证',
    1030: '根据防沉迷规定，当前时间无法游戏（未成年人 20:00-次日 8:00 禁玩）',
    1050: '今日可玩时长已用完，明天再来吧',
    1100: '根据相关规定，该账号无法进行游戏',
    1200: '实名服务网络异常，请检查网络后重试',
    9002: '实名认证未完成'
  };
  var BLOCK = { 1030: 1, 1050: 1, 1100: 1, 1000: 1, 1001: 1 };

  var state = { enabled: false, plugin: null, gateEl: null, styleEl: null, retrying: false };

  function uid() {
    var k = 'yozora_aa_uid';
    var v = null;
    try { v = root.localStorage.getItem(k); } catch (e) { /* 隐私模式 */ }
    if (!v) {
      v = 'dev-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
      try { root.localStorage.setItem(k, v); } catch (e) { /* ignore */ }
    }
    return v;
  }

  function ensureStyles() {
    if (state.styleEl) return;
    var st = root.document.createElement('style');
    st.textContent = [
      '#aa-gate{position:fixed;inset:0;z-index:100000;display:flex;align-items:center;justify-content:center;',
      'background:rgba(12,10,24,.94);backdrop-filter:blur(6px);}',
      '#aa-gate .aa-card{max-width:min(420px,86vw);padding:32px 28px;border-radius:16px;text-align:center;',
      'background:rgba(30,26,54,.9);border:1px solid rgba(255,170,200,.25);box-shadow:0 18px 60px rgba(0,0,0,.5);}',
      '#aa-gate .aa-title{font-size:20px;font-weight:700;color:#ffd7e6;margin-bottom:14px;letter-spacing:1px;}',
      '#aa-gate .aa-msg{font-size:14px;line-height:1.8;color:#cfc9e8;margin-bottom:22px;}',
      '#aa-gate .aa-btn{display:inline-block;padding:10px 34px;border-radius:999px;border:0;cursor:pointer;',
      'font-size:14px;font-weight:600;color:#2b1533;background:linear-gradient(135deg,#ffb3d1,#ff8fb8);}',
      '#aa-gate .aa-btn:disabled{opacity:.5;cursor:default;}'
    ].join('');
    root.document.head.appendChild(st);
    state.styleEl = st;
  }

  function showGate(msg, retryable) {
    ensureStyles();
    if (!state.gateEl) {
      state.gateEl = root.document.createElement('div');
      state.gateEl.id = 'aa-gate';
      root.document.body.appendChild(state.gateEl);
    }
    state.gateEl.innerHTML =
      '<div class="aa-card">' +
      '<div class="aa-title">夜樱扑克部 · 防沉迷提示</div>' +
      '<div class="aa-msg"></div>' +
      '<button class="aa-btn"></button>' +
      '</div>';
    state.gateEl.querySelector('.aa-msg').textContent = msg || '';
    var btn = state.gateEl.querySelector('.aa-btn');
    if (retryable) {
      btn.textContent = '重新认证';
      btn.disabled = false;
      btn.onclick = function () { retry(); };
    } else {
      btn.textContent = '知道了';
      btn.disabled = true;
      btn.onclick = null;
    }
    state.gateEl.style.display = 'flex';
  }

  function hideGate() {
    if (state.gateEl) state.gateEl.style.display = 'none';
  }

  function toast(msg) {
    try {
      var t = root.document.createElement('div');
      t.textContent = msg;
      t.style.cssText = 'position:fixed;left:50%;top:14%;transform:translateX(-50%);z-index:100001;' +
        'padding:10px 22px;border-radius:999px;background:rgba(30,26,54,.92);color:#ffd7e6;' +
        'font-size:14px;border:1px solid rgba(255,170,200,.3);transition:opacity .5s;';
      root.document.body.appendChild(t);
      setTimeout(function () { t.style.opacity = '0'; }, 2400);
      setTimeout(function () { t.remove(); }, 3000);
    } catch (e) { /* ignore */ }
  }

  function retry() {
    if (state.retrying) return;
    state.retrying = true;
    var btn = state.gateEl && state.gateEl.querySelector('.aa-btn');
    if (btn) { btn.disabled = true; btn.textContent = '认证中…'; }
    var p = state.plugin;
    p.startup({ userId: uid() }).then(function () { state.retrying = false; },
                                      function () { state.retrying = false; });
  }

  function onResult(res) {
    var code = res && res.code;
    if (code == null) return;
    if (code === 500) { hideGate(); toast(MSG[500]); return; }
    if (code === 9002) { showGate(MSG[9002] + '，请完成实名认证后进入游戏', true); return; }
    if (BLOCK[code]) { showGate(MSG[code] || ('限制 code=' + code), false); return; }
    if (code === 1200) { toast(MSG[1200]); return; }
    /* 未知 code：仅记录不拦截 */
    try { console.info('[anti-addiction] code', code, res.extra); } catch (e) { /* */ }
  }

  function boot() {
    if (state.plugin) return;
    var cap = root.Capacitor;
    var plugin = cap && cap.Plugins && cap.Plugins.AntiAddiction;
    if (!plugin) return;                       // Web 浏览器态：无原生桥，跳过
    if (!CONFIG.clientId) {
      try { console.info('[anti-addiction] clientId 未配置，防沉迷关闭（开发态）'); } catch (e) { /* */ }
      return;
    }
    state.plugin = plugin;
    plugin.init({ clientId: CONFIG.clientId, clientToken: CONFIG.clientToken })
      .then(function (res) {
        if (!res || !res.enabled) {
          try { console.warn('[anti-addiction] init 失败:', res && res.reason); } catch (e) { /* */ }
          return;
        }
        state.enabled = true;
        plugin.addListener('result', onResult);
        return plugin.startup({ userId: uid() }).then(function (r2) {
          if (!r2 || !r2.started) {
            try { console.warn('[anti-addiction] startup 失败:', r2 && r2.reason); } catch (e) { /* */ }
          }
        });
      })
      .catch(function (err) {
        try { console.warn('[anti-addiction] 异常:', err); } catch (e) { /* */ }
      });
  }

  root.AntiAddiction = {
    boot: boot,
    get enabled() { return state.enabled; },
    remainingSeconds: function () {
      if (!state.enabled) return Promise.resolve(-1);
      return state.plugin.getRemainingTime().then(function (r) { return r.seconds; });
    }
  };

  if (root.document.readyState === 'loading') {
    root.document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})(window);
