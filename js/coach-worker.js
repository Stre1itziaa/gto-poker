/* coach-worker.js — GTO 教练的 Worker 线程
 * 主线程发 {type:'init', base} 后 importScripts 四个逻辑文件；
 * 之后每条 {type:'coach', id, state} 返回 {type:'coach', id, result}。
 * state 是纯数据快照（函数过不了 postMessage），方法在这里挂回。 */
'use strict';

function attachMethods(st) {
  st.activeUnfolded = function () {
    return this.players.filter(function (p) { return !p.folded; });
  };
  st.potTotal = function () {
    var s = 0;
    this.players.forEach(function (p) { s += p.totalCommitted; });
    return s;
  };
  st.spr = function (idx) {
    var p = this.players[idx];
    return (p.stack + p.streetCommitted) / Math.max(1, this.potTotal());
  };
  st.legalActions = function (idx) {
    var p = this.players[idx];
    var toCall = Math.max(0, this.currentBet - p.streetCommitted);
    var maxTo = p.streetCommitted + p.stack;
    var minTo = this.currentBet === 0
      ? Math.min(maxTo, this.bb)
      : Math.min(maxTo, this.currentBet + this.minRaiseSize);
    return { toCall: toCall, canCheck: toCall <= 0, canRaise: maxTo > this.currentBet, minTo: minTo, maxTo: maxTo };
  };
  st.positionName = function (idx) {
    var n = this.players.length;
    var rel = (idx - this.buttonIdx + n) % n;
    if (n === 2) return rel === 0 ? 'BTN' : 'BB';
    var names = n >= 6 ? ['BTN', 'SB', 'BB', 'UTG', 'HJ', 'CO']
      : n === 5 ? ['BTN', 'SB', 'BB', 'UTG', 'CO']
      : n === 4 ? ['BTN', 'SB', 'BB', 'CO']
      : ['BTN', 'SB', 'BB'];
    return names[rel];
  };
  return st;
}

self.onmessage = function (e) {
  var d = e.data;
  if (d.type === 'init') {
    importScripts(
      d.base + 'js/cards.js',
      d.base + 'js/ranges.js',
      d.base + 'js/equity.js',
      d.base + 'js/engine.js',
      d.base + 'js/gto.js'
    );
    if (d.perf && self.GTO.setPerf) self.GTO.setPerf(d.perf);   // 手机降载
    self.postMessage({ type: 'ready' });
    return;
  }
  if (d.type === 'coach') {
    try {
      var result = self.GTO.coach(attachMethods(d.state), 0);
      self.postMessage({ type: 'coach', id: d.id, seq: d.seq, result: result });
    } catch (err) {
      self.postMessage({ type: 'coach', id: d.id, seq: d.seq, error: String(err && err.message || err) });
    }
  }
};
