/* audit.js — 行为审计：翻前弃牌率 / c-bet 率 / 面对下注加注率 / 到街率 + 3bet-spam 剥削基准
 * 用法：node test/audit.js [metricsHands] [benchBatches] [benchHandsPerBatch]
 * 口径对齐外部评审（gto_probe）：
 *  - SB/BB 面对单个加注的弃牌率（决策时点：preflop、raises==1）
 *  - 翻牌 c-bet 率（翻前加注者、翻牌无人下注时）
 *  - 面对下注的加注率（所有翻后街）
 *  - 到街率 / 摊牌率 / 人均决策数
 *  - 剥削基准：一个"见加注就加注"的脚本对 5 台引擎机器人的 bb/100
 */
'use strict';
require('../js/cards.js'); require('../js/ranges.js'); require('../js/equity.js');
require('../js/engine.js'); require('../js/gto.js');
var Cards = globalThis.Cards, Table = globalThis.Table, GTO = globalThis.GTO;

var METRICS_HANDS = parseInt(process.argv[2], 10) || 1500;
var BENCH_BATCHES = parseInt(process.argv[3], 10) || 4;
var BENCH_HANDS = parseInt(process.argv[4], 10) || 600;

GTO.setPerf(0.5); // 审计模式：蒙特卡洛迭代减半换速度（比率的统计误差可接受）

function raises(t, street) {
  var n = 0;
  t.actionHistory.forEach(function (a) { if (a.street === street && a.type === 'raise') n++; });
  return n;
}
function lastAggr(t) {
  var i = -1;
  t.actionHistory.forEach(function (a) { if (a.type === 'raise') i = a.playerIdx; });
  return i;
}

/* ---------- 行为指标 ---------- */
var m = {
  hands: 0, endedPreflop: 0, sawFlop: 0, showdown: 0,
  sbTry: 0, sbFold: 0, bbTry: 0, bbFold: 0,
  cbetChance: 0, cbetDo: 0,
  faceBet: 0, faceBetRaise: 0,
  decisions: 0, foldDecisions: 0
};
var t = new Table({ seatCount: 6, sb: 10, bb: 20, startStack: 2000, runoutMode: false });
for (var h = 0; h < METRICS_HANDS; h++) {
  t.startHand();
  m.hands++;
  var guard = 0, aggrPreflop = -1;
  while (!t.handOver) {
    if (++guard > 400) throw new Error('死循环');
    var p = t.currentActor();
    var la = t.legalActions(p.idx);
    var act = GTO.decide(t, p.idx);
    // ---- 指标采集（决策时点）----
    m.decisions++;
    if (act.type === 'fold') m.foldDecisions++;
    if (t.street === 'preflop' && raises(t, 'preflop') === 1) {
      var pos = t.positionName(p.idx);
      if (pos === 'SB') { m.sbTry++; if (act.type === 'fold') m.sbFold++; }
      if (pos === 'BB') { m.bbTry++; if (act.type === 'fold') m.bbFold++; }
    }
    if (t.street === 'flop' && t.currentBet === 0 && lastAggr(t) === p.idx && lastAggr(t) >= 0) {
      m.cbetChance++;
      if (act.type === 'raise') m.cbetDo++;
    }
    if (t.street !== 'preflop' && la.toCall > 0) {
      m.faceBet++;
      if (act.type === 'raise') m.faceBetRaise++;
    }
    t.apply(act);
  }
  t.resolve();
  if (t.foldWin && t.board.length === 0) m.endedPreflop++;
  if (t.board.length >= 3) m.sawFlop++;
  if (!t.foldWin) m.showdown++;
}
console.log('== 行为审计（' + METRICS_HANDS + ' 手，6-max）==');
console.log('翻前结束:      ' + (m.endedPreflop / m.hands * 100).toFixed(0) + '%');
console.log('见到翻牌:      ' + (m.sawFlop / m.hands * 100).toFixed(0) + '%');
console.log('真实摊牌:      ' + (m.showdown / m.hands * 100).toFixed(0) + '%');
console.log('SB 面对加注弃牌: ' + (m.sbFold / m.sbTry * 100).toFixed(0) + '%  (n=' + m.sbTry + ')');
console.log('BB 面对加注弃牌: ' + (m.bbFold / m.bbTry * 100).toFixed(0) + '%  (n=' + m.bbTry + ')');
console.log('翻牌 c-bet 率:  ' + (m.cbetDo / m.cbetChance * 100).toFixed(0) + '%  (n=' + m.cbetChance + ')');
console.log('面对下注加注率: ' + (m.faceBetRaise / m.faceBet * 100).toFixed(1) + '%  (n=' + m.faceBet + ')');
console.log('人均决策数:     ' + (m.decisions / m.hands).toFixed(2) + '（弃牌占 ' + (m.foldDecisions / m.decisions * 100).toFixed(0) + '%）');

/* ---------- 3bet-spam 剥削基准 ---------- */
/* 座位 0 = 剥削脚本：不看手牌。翻前 raises<2 一律加注（开局 2.5bb / 遇加注 3x）；
 * 翻前被 3bet 以上 → 弃；翻后遇到下注 → 弃，无人下注 → 过牌。 */
function spamDecide(tt, idx) {
  var la = tt.legalActions(idx);
  if (tt.street !== 'preflop') {
    if (la.toCall > 0) return { type: 'fold' };
    return la.canCheck ? { type: 'check' } : { type: 'fold' };
  }
  var r = 0;
  tt.actionHistory.forEach(function (a) { if (a.street === 'preflop' && a.type === 'raise') r++; });
  if (r === 0 && la.canRaise) return { type: 'raise', to: Math.round(2.5 * tt.bb) };
  if (r === 1 && la.canRaise) return { type: 'raise', to: Math.round(tt.currentBet * 3) };
  if (la.toCall <= 0) return { type: 'check' };
  return { type: 'fold' };
}

console.log('\n== 3bet/raise-spam 剥削基准（座位0=脚本 vs 5 机器人）==');
var nets = [];
for (var b = 0; b < BENCH_BATCHES; b++) {
  var tb = new Table({ seatCount: 6, sb: 10, bb: 20, startStack: 2000, runoutMode: false });
  var injected = 0;
  for (var h2 = 0; h2 < BENCH_HANDS; h2++) {
    tb.startHand();
    var g2 = 0;
    while (!tb.handOver) {
      if (++g2 > 400) throw new Error('死循环');
      var a2 = tb.currentActor();
      var act2 = (a2.idx === 0) ? spamDecide(tb, 0) : GTO.decide(tb, a2.idx);
      if (a2.idx === 0 && a2.stack === 0) { /* 即将reb由startHand处理 */ }
      tb.apply(act2);
    }
    tb.resolve();
    tb.players.forEach(function (p) {
      if (p.idx === 0 && p.rebuys) { injected += p.rebuys * 2000; p.rebuys = 0; }
    });
  }
  var net = (tb.players[0].stack - 2000 - injected) / tb.bb * 100 / BENCH_HANDS;
  nets.push(net);
  console.log('  批 ' + (b + 1) + ': ' + net.toFixed(1) + ' bb/100');
}
var mean = nets.reduce(function (s, x) { return s + x; }, 0) / nets.length;
var sd = Math.sqrt(nets.reduce(function (s, x) { return s + (x - mean) * (x - mean); }, 0) / (nets.length - 1));
console.log('  平均: ' + mean.toFixed(1) + ' ± ' + (sd / Math.sqrt(nets.length)).toFixed(1) + ' bb/100（SEM）');
