/* persona.js — 20 用户画像 × 真实引擎对局模拟
 * 每个画像用参数化的决策函数（松紧/激进/上头/耐心）在座位 0 对 5 台 GTO 机器人
 * 打真实牌局（同一套 engine + gto），输出客观行为数据。
 * 运行：node test/persona.js [每人手数]   （默认 150）
 * 注意：这是「模拟画像」的行为数据，不是真人数据；评价UI/体验时另有浏览器走查。 */
'use strict';
require('../js/cards.js'); require('../js/ranges.js'); require('../js/equity.js');
require('../js/engine.js'); require('../js/gto.js');
var Cards = globalThis.Cards, Ranges = globalThis.Ranges, Equity = globalThis.Equity,
    Table = globalThis.Table, GTO = globalThis.GTO;

var HANDS = parseInt(process.argv[2], 10) || 150;
GTO.setPerf(0.4);

/* ---------- 20 画像（雀魂生态对标，见 persona-research/02-personas.md） ---------- */
var PERSONAS = [
  { id: 'P01', name: '段位卷王·竞技型', seg: '竞技', vpip: 0.22, pfr: 0.16, three: 0.10, callDown: 0.55, bluff: 0.06, val: 1.05, tilt: 0.06, hands: 400 },
  { id: 'P02', name: '角色厨·老婆党', seg: '情感', vpip: 0.45, pfr: 0.10, three: 0.06, callDown: 0.6, bluff: 0.15, val: 0.92, tilt: 0.18, hands: 120 },
  { id: 'P03', name: '收集强迫症', seg: '情感', vpip: 0.30, pfr: 0.12, three: 0.08, callDown: 0.55, bluff: 0.10, val: 0.98, tilt: 0.10, hands: 80 },
  { id: 'P04', name: '碎片时间通勤党', seg: '休闲', vpip: 0.35, pfr: 0.12, three: 0.07, callDown: 0.5, bluff: 0.12, val: 0.95, tilt: 0.08, hands: 40 },
  { id: 'P05', name: '德州老炮（线下）', seg: '竞技', vpip: 0.20, pfr: 0.15, three: 0.11, callDown: 0.5, bluff: 0.08, val: 1.06, tilt: 0.05, hands: 300 },
  { id: 'P06', name: '日麻纯粹党', seg: '规则', vpip: 0.25, pfr: 0.10, three: 0.06, callDown: 0.5, bluff: 0.05, val: 1.0, tilt: 0.06, hands: 100 },
  { id: 'P07', name: '乙女向女玩家', seg: '情感', vpip: 0.40, pfr: 0.10, three: 0.06, callDown: 0.55, bluff: 0.12, val: 0.94, tilt: 0.12, hands: 60 },
  { id: 'P08', name: '赛事云观众', seg: '竞技', vpip: 0.25, pfr: 0.14, three: 0.09, callDown: 0.5, bluff: 0.07, val: 1.02, tilt: 0.06, hands: 250 },
  { id: 'P09', name: '社交好友局党', seg: '社交', vpip: 0.50, pfr: 0.14, three: 0.08, callDown: 0.65, bluff: 0.18, val: 0.9, tilt: 0.2, hands: 80 },
  { id: 'P10', name: '零氪学生党', seg: '休闲', vpip: 0.40, pfr: 0.12, three: 0.08, callDown: 0.6, bluff: 0.14, val: 0.93, tilt: 0.15, hands: 150 },
  { id: 'P11', name: '麻将大爷·大龄休闲', seg: '休闲', vpip: 0.52, pfr: 0.06, three: 0.02, callDown: 0.75, bluff: 0.04, val: 0.85, tilt: 0.05, hands: 60 },
  { id: 'P12', name: 'Solver 数据控', seg: '竞技', vpip: 0.22, pfr: 0.16, three: 0.12, callDown: 0.5, bluff: 0.07, val: 1.07, tilt: 0.03, hands: 350 },
  { id: 'P13', name: '剧情党', seg: '内容', vpip: 0.38, pfr: 0.10, three: 0.06, callDown: 0.6, bluff: 0.10, val: 0.92, tilt: 0.1, hands: 30 },
  { id: 'P14', name: '手感动效党', seg: '体验', vpip: 0.36, pfr: 0.12, three: 0.08, callDown: 0.55, bluff: 0.13, val: 0.94, tilt: 0.1, hands: 60 },
  { id: 'P15', name: '千元机用户', seg: '体验', vpip: 0.33, pfr: 0.11, three: 0.07, callDown: 0.55, bluff: 0.11, val: 0.95, tilt: 0.09, hands: 100 },
  { id: 'P16', name: 'iPhone 桌面图标党', seg: '体验', vpip: 0.34, pfr: 0.12, three: 0.07, callDown: 0.55, bluff: 0.12, val: 0.95, tilt: 0.09, hands: 100 },
  { id: 'P17', name: '女性竞技玩家', seg: '竞技', vpip: 0.24, pfr: 0.15, three: 0.10, callDown: 0.52, bluff: 0.07, val: 1.04, tilt: 0.05, hands: 300 },
  { id: 'P18', name: '主播', seg: '社交', vpip: 0.30, pfr: 0.14, three: 0.09, callDown: 0.55, bluff: 0.12, val: 1.0, tilt: 0.08, hands: 200 },
  { id: 'P19', name: '赌狗·全下成瘾', seg: '休闲', vpip: 0.65, pfr: 0.30, three: 0.25, callDown: 0.8, bluff: 0.30, val: 0.8, tilt: 0.4, hands: 90 },
  { id: 'P20', name: '国际玩家（英语）', seg: '规则', vpip: 0.30, pfr: 0.12, three: 0.08, callDown: 0.55, bluff: 0.10, val: 0.97, tilt: 0.08, hands: 50 }
];

/* ---------- 画像决策函数 ---------- */
function raiseCount(t, street) {
  var n = 0;
  t.actionHistory.forEach(function (a) { if (a.street === street && a.type === 'raise') n++; });
  return n;
}
function callCount(t, street) {
  var n = 0;
  t.actionHistory.forEach(function (a) { if (a.street === street && a.type === 'call') n++; });
  return n;
}
function potOddsReq(t, idx) {
  var la = t.legalActions(idx);
  if (la.toCall <= 0) return 0;
  return la.toCall / (t.potTotal() + la.toCall);
}
/* 画像决策：翻前用组合百分位查表，翻后用 300 次蒙特卡洛对「随机范围」粗估 */
function personaDecide(P, t, idx, mood) {
  var me = t.players[idx];
  var la = t.legalActions(idx);
  var code = Ranges.handCode(me.hole[0], me.hole[1]);
  var p = Ranges.percentileOf(code);
  var loosed = P.vpip + mood.tilt;

  if (t.street === 'preflop') {
    var r = raiseCount(t, 'preflop');
    if (r === 0) {
      if (p <= loosed * 0.5 && Math.random() < P.pfr * 3) return { type: 'raise', to: Math.round(2.5 * t.bb) };
      if (p <= loosed * 0.5) return { type: 'call' };
      if (pos === 'BB' && la.toCall <= 0) return { type: 'check' };
      return { type: 'fold' };
    }
    if (r === 1) {
      if (p <= P.three && Math.random() < 0.7 && la.canRaise)
        return { type: 'raise', to: Math.round(t.currentBet * 3) };
      if (p <= loosed) {
        if (Math.random() < P.pfr && la.canRaise) return { type: 'raise', to: Math.round(t.currentBet * 2.6) };
        return { type: 'call' };
      }
      if (pos === 'BB' && la.toCall <= 0) return { type: 'check' };
      return { type: 'fold' };
    }
    /* 面对 3bet+：赌狗乱推，其他人看牌力 */
    var allinLike = P.allinLike || (P.vpip > 0.6 ? 0.25 : (P.vpip > 0.45 ? 0.06 : 0.015));
    if (Math.random() < allinLike) return { type: 'raise', to: la.maxTo };
    if (p <= 0.07) return { type: 'call' };
    return { type: 'fold' };
  }
  /* 翻后 */
  var dead = t.board.concat(me.hole);
  var villainSets = t.activeUnfolded().filter(function (o) { return o.idx !== idx; }).map(function (o) {
    var s = Ranges.expand(Ranges.topSet(0.55), dead);
    return s.length ? s : Ranges.expand(Ranges.topSet(1), dead);
  });
  var eq = Equity.vsRanges(me.hole, t.board, villainSets, 260);
  var req = potOddsReq(t, idx);
  var canRaise = la.canRaise;
  var pot = t.potTotal();
  var drawB = Equity.drawInfo(me.hole, t.board);
  var isDraw = drawB.flushDraw || drawB.straightOuts >= 4;

  if (la.toCall > 0) {
    if (eq > 0.78 * P.val) {
      if (canRaise && Math.random() < 0.4) return { type: 'raise', to: t.currentBet + Math.round(0.8 * pot) };
      return { type: 'call' };
    }
    if (eq >= req && Math.random() < P.callDown) return { type: 'call' };
    if (isDraw && req < 0.35 && Math.random() < 0.5) return { type: 'call' };
    if (canRaise && Math.random() < P.bluff && eq < 0.4) return { type: 'raise', to: t.currentBet + Math.round(0.9 * pot) };
    return { type: 'fold' };
  }
  /* 无人下注 */
  if (eq > 0.72 * P.val && canRaise) return { type: 'raise', to: Math.round((0.6 + Math.random() * 0.4) * pot) };
  if (isDraw && canRaise && Math.random() < P.bluff * 1.5) return { type: 'raise', to: Math.round(0.5 * pot) };
  if (eq < 0.35 && canRaise && Math.random() < P.bluff * 0.6) return { type: 'raise', to: Math.round(0.5 * pot) };
  if (la.canCheck) return { type: 'check' };
  return { type: 'fold' };
}
var pos = '';

/* ---------- 单画像会话 ---------- */
function runPersona(P) {
  var t = new Table({ seatCount: 6, sb: 10, bb: 20, startStack: 2000, runoutMode: false });
  var st = { hands: 0, vpipIn: 0, pfrIn: 0, folds: 0, raiseCnt: 0, allins: 0, sawFlop: 0, showdowns: 0,
    winHands: 0, netChips: 0, biggestWin: 0, maxLossStreak: 0, lossStreak: 0, rebuys: 0, quitAt: P.hands,
    tilts: 0, bigPotEvents: 0 };
  var mood = { tilt: 0 };
  var preStack = 2000, preReb = 0;
  for (var h = 0; h < Math.min(P.hands, st.quitAt); h++) {
    if (h > 0) { preStack = t.players[0].stack; preReb = t.players[0].rebuys || 0; }
    t.startHand();
    if (t.players[0].rebuys > preReb) st.rebuys += (t.players[0].rebuys - preReb);
    var sawFlopThis = false;
    var guard = 0;
    while (!t.handOver) {
      if (++guard > 400) break;
      var actor = t.currentActor();
      if (actor.idx === 0) {
        pos = t.positionName(0);
        var la = t.legalActions(0);
        var act = personaDecide(P, t, 0, mood);
        if (act.type === 'fold') st.folds++;
        if (act.type === 'raise') {
          st.raiseCnt++;
          if (t.street === 'preflop' && callCount(t, 'preflop') === 0 && raiseCount(t, 'preflop') === 0) {} // RFI 计入 pfr
          if (act.to >= la.maxTo) st.allins++;
        }
        t.apply(act);
      } else {
        t.apply(GTO.decide(t, actor.idx));
      }
      if (t.board.length >= 3) sawFlopThis = true;
      if (!t.handOver && t.currentActor() && t.currentActor().idx === 0) { /* 循环继续 */ }
    }
    t.resolve();
    if (t.handOver && h >= 0) { /* noop */ }
    st.hands++;
    if (sawFlopThis) st.sawFlop++;
    if (!t.foldWin) st.showdowns++;
    var injected = (t.players[0].rebuys || 0) - preReb;
    var delta = t.players[0].stack - preStack - injected * 2000;
    st.netChips += delta;
    if (delta > st.biggestWin) st.biggestWin = delta;
    if (delta < -120) { st.lossStreak++; st.bigPotEvents++; } else st.lossStreak = 0;
    if (st.lossStreak > st.maxLossStreak) st.maxLossStreak = st.lossStreak;
    if (delta < -150 && Math.random() < P.tilt) { mood.tilt = 0.12; st.tilts++; } else if (mood.tilt > 0) mood.tilt = Math.max(0, mood.tilt - 0.04);
    var myActs = t.actionHistory.filter(function (a) { return a.playerIdx === 0 && a.street === 'preflop'; });
    if (myActs.some(function (a) { return a.type === 'call' || a.type === 'raise'; })) st.vpipIn++;
    if (myActs.some(function (a) { return a.type === 'raise'; })) st.pfrIn++;
    if (t.resolved && t.resolved.pots.some(function (pr) { return pr.winners.indexOf(0) >= 0; }) && !t.foldWin) st.winHands++;
  }
  st.bb100 = (st.netChips / t.bb) * 100 / st.hands;
  st.vpipPct = st.hands ? Math.round(st.vpipIn / st.hands * 100) : 0;
  st.pfrPct = st.hands ? Math.round(st.pfrIn / st.hands * 100) : 0;
  st.sawFlopPct = Math.round(st.sawFlop / st.hands * 100);
  st.showdownPct = Math.round(st.showdowns / st.hands * 100);
  return st;
}

/* ---------- 跑全部 ---------- */
var out = [];
PERSONAS.forEach(function (P) {
  var st = runPersona(P);
  out.push({ id: P.id, name: P.name, seg: P.seg, intent: { vpip: P.vpip, hands: P.hands }, result: st });
  console.log(P.id + ' ' + P.name + ' | 局数 ' + st.hands + ' | VPIP ' + st.vpipPct + '% | bb/100 ' + st.bb100.toFixed(1) +
    ' | 见翻牌 ' + st.sawFlopPct + '% | 摊牌 ' + st.showdownPct + '% | 全下 ' + st.allins + ' | 重买 ' + st.rebuys +
    ' | 最长连败 ' + st.maxLossStreak);
});
require('fs').writeFileSync(__dirname + '/persona-results.json', JSON.stringify(out, null, 1));
console.log('\n结果已写入 test/persona-results.json');
