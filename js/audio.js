/* audio.js — 程序化音效（WebAudio 合成，零音频资产、离线可用）
 * 五件套：click 按钮 / deal 发牌 / chip 筹码 / win 胜利 / allin 全下。
 * 首次用户手势后解锁 AudioContext；🔇 可静音（localStorage 记忆）。 */
(function (root) {
  'use strict';
  var ctx = null, enabled = localStorage.getItem('gto-sfx') !== 'off';

  function ac() {
    if (!enabled) return null;
    if (!ctx) {
      try { ctx = new (root.AudioContext || root.webkitAudioContext)(); } catch (e) { return null; }
    }
    if (ctx && ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  function tone(freq, dur, type, vol, when) {
    var c = ac();
    if (!c) return;
    var o = c.createOscillator(), g = c.createGain();
    o.type = type || 'sine';
    o.frequency.value = freq;
    o.connect(g); g.connect(c.destination);
    var t = c.currentTime + (when || 0);
    g.gain.setValueAtTime(vol || 0.07, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.start(t); o.stop(t + dur + 0.03);
  }

  root.SFX = {
    unlock: function () { ac(); },
    setEnabled: function (v) { enabled = v; localStorage.setItem('gto-sfx', v ? 'on' : 'off'); },
    isEnabled: function () { return enabled; },
    click: function () { tone(660, 0.05, 'square', 0.045); tone(440, 0.05, 'square', 0.035, 0.03); },
    fold: function () { tone(320, 0.08, 'sine', 0.05); },
    deal: function () { tone(880, 0.045, 'triangle', 0.06); tone(1320, 0.04, 'triangle', 0.045, 0.045); },
    chip: function () { tone(520, 0.05, 'triangle', 0.07); tone(700, 0.05, 'triangle', 0.06, 0.05); tone(380, 0.06, 'triangle', 0.05, 0.1); },
    allin: function () { tone(165, 0.35, 'sawtooth', 0.07); tone(120, 0.45, 'sawtooth', 0.055, 0.14); },
    win: function () { [523, 659, 784, 1047].forEach(function (f, i) { tone(f, 0.15, 'triangle', 0.07, i * 0.09); }); },
    /* 触觉反馈（手游标准即时反馈；无 vibrate API 的平台静默跳过） */
    haptic: function (pattern) {
      try { if (root.navigator && root.navigator.vibrate) root.navigator.vibrate(pattern || 30); } catch (e) { /* noop */ }
    }
  };
})(typeof window !== 'undefined' ? window : globalThis);
