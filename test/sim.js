/* sim.js — 无头测试：单元测试 + 机器人互打大量手牌的不变量检验
 * 运行：node test/sim.js （在 game/ 目录下） */
'use strict';
require('../js/cards.js');
require('../js/ranges.js');
require('../js/equity.js');
require('../js/engine.js');
require('../js/gto.js');
var Cards = globalThis.Cards, Ranges = globalThis.Ranges, Equity = globalThis.Equity,
    Table = globalThis.Table, GTO = globalThis.GTO;

var failures = 0;
function assert(cond, msg) {
  if (!cond) { failures++; console.error('  ✗ FAIL: ' + msg); }
  else { console.log('  ✓ ' + msg); }
}
function near(x, target, tol, msg) {
  assert(Math.abs(x - target) <= tol, msg + '（实际 ' + x.toFixed(3) + '，期望 ' + target + '±' + tol + '）');
}
function strToCard(s) {
  var r = Cards.RANK_CHARS.indexOf(s[0]);
  var suit = 'shdc'.indexOf(s[1] === '♠' ? 's' : s[1] === '♥' ? 'h' : s[1] === '♦' ? 'd' : s[1] === '♣' ? 'c' : s[1]);
  return r * 4 + suit;
}
function hand7(strs) { return strs.map(strToCard); }

/* ---------- 1. 范围表 ---------- */
console.log('\n[1] 范围表（ranges.js，组合空间口径）');
assert(Ranges.RANKED.length === 169, '169 个手牌代码，实际 ' + Ranges.RANKED.length);
assert(new Set(Ranges.RANKED).size === 169, '无重复代码');
assert(Ranges.RANKED[0] === 'AA' && Ranges.CODE_INDEX['AA'] === 0, 'AA 排第一');
assert(Ranges.percentileOf('AA') === 0, 'AA 组合百分位为 0');
near(Ranges.percentileOf('A4s'), 0.107, 0.02, 'UTG 截断锚点 A4s 组合百分位 ≈10.7%（类型序 16% 的组合换算）');
near(Ranges.percentileOf('K7s'), 0.215, 0.03, 'CO 截断锚点 K7s 组合百分位 ≈21.5%');
near(Ranges.comboPct(Ranges.topSet(0.16)), 0.16, 0.02, 'topSet(16%) 真实组合宽度 ≈16%');
near(Ranges.comboPct(Ranges.topSet(0.48)), 0.48, 0.02, 'topSet(48%) 真实组合宽度 ≈48%');
near(Ranges.combosOf('AA').length, 6, 0, 'AA 6 组合');
near(Ranges.combosOf('AKs').length, 4, 0, 'AKs 4 组合');
near(Ranges.combosOf('AKo').length, 12, 0, 'AKo 12 组合');

/* ---------- 2. 牌型评估 ---------- */
console.log('\n[2] 牌型评估（cards.js）');
var royal = hand7(['As', 'Ks', 'Qs', 'Js', 'Ts', '2h', '3d']);
var quads = hand7(['Ah', 'Ad', 'Ac', 'As', 'Kd', '2h', '3s']);
assert(Cards.eval7(royal) > Cards.eval7(quads), '皇家同花顺 > 四条A');
var fh = hand7(['Ah', 'Ad', 'Ac', 'Kh', 'Kd', '2h', '3s']);
var flush = hand7(['Ah', 'Qh', '9h', '5h', '3h', '2d', '2s']);
assert(Cards.eval7(fh) > Cards.eval7(flush), '葫芦 > 同花');
var st1 = hand7(['9h', '8d', '7c', '6s', '5h', '2d', '2s']);
var wheel = hand7(['Ah', '2d', '3c', '4s', '5h', 'Kd', 'Qs']);
assert(Cards.eval7(st1) > Cards.eval7(wheel), '9 高顺子 > A2345 轮转顺');
var noStraight = hand7(['Ah', '2d', '3c', '4s', 'Kh', 'Kd', 'Qs']);
assert(Cards.eval7(noStraight) < Cards.eval7(flush), 'A 高无顺（对K） < 同花');
assert(Cards.eval7(hand7(['As', 'Ad', 'Ah', 'Ac', 'Kd', 'Kh', '3s'])) > Cards.eval7(hand7(['As', 'Ad', 'Ah', 'Ac', '2d', '2h', '3s'])), '四条A踢脚K > 四条A踢脚3');
assert(Cards.handName(Cards.eval7(royal)).indexOf('皇家') >= 0, '命名：皇家同花顺 → ' + Cards.handName(Cards.eval7(royal)));
assert(Cards.handName(Cards.eval7(fh)).indexOf('葫芦') >= 0, '命名：葫芦 → ' + Cards.handName(Cards.eval7(fh)));
assert(Cards.evalBest(royal.slice(0, 5)) === Cards.eval5(royal.slice(0, 5)), 'evalBest 与 eval5 一致（5张）');

/* ---------- 3. 蒙特卡洛胜率 ---------- */
console.log('\n[3] 胜率引擎（equity.js）');
var AA = Ranges.combosOf('AA')[0].concat(); // As Ah
var randomSet = Ranges.expand(Ranges.topSet(1), AA);
near(Equity.vsRange(AA, [], randomSet, 6000), 0.852, 0.02, 'AA 翻前对随机范围 ≈ 85%');
var sevenTwo = hand7(['7h', '2d']);
near(Equity.vsRange(sevenTwo, [], Ranges.expand(Ranges.topSet(1), sevenTwo), 6000), 0.349, 0.025, '72o 对随机 ≈ 35%');
var AKs = Ranges.combosOf('AKs')[0];
var QQ = Ranges.combosOf('QQ')[0];
near(Equity.vsRange(AKs, [], Ranges.expand(new Set(['QQ']), AKs), 6000), 0.46, 0.03, 'AKs 对 QQ ≈ 46%（跑马）');
var set = Ranges.expand(new Set(['AA', 'KK']), [51, 47]);
assert(set.length > 0, 'expand 剔除死牌可用');

/* ---------- 4. 机器人互打 300 手（不变量） ---------- */
console.log('\n[4] 机器人互打 300 手（GTO 引擎全流程）');
var t = new Table({ seatCount: 6, sb: 10, bb: 20, startStack: 2000, runoutMode: false });
var actionStats = { fold: 0, check: 0, call: 0, raise: 0 };
var streetStats = { preflop: 0, flop: 0, turn: 0, river: 0, showdown: 0 };
var foldWins = 0, showdowns = 0, totalPot = 0, maxSteps = 0;
var H = 300;
for (var h = 0; h < H; h++) {
  t.startHand();
  var sumAfterStart = t.players.reduce(function (s, p) { return s + p.stack; }, 0) + t.potTotal();
  var steps = 0, reached = 'preflop';
  while (!t.handOver) {
    if (++steps > 600) throw new Error('第 ' + h + ' 手超过 600 步未结束（疑似死循环）');
    var actor = t.currentActor();
    var la = t.legalActions(actor.idx);
    var act = GTO.decide(t, actor.idx);
    actionStats[act.type]++;
    if (act.type === 'raise' && !la.canRaise) throw new Error('非法加注（不能加注时加注）');
    if (act.type === 'raise' && act.to > la.maxTo) throw new Error('加注超过最大值');
    if (act.type === 'check' && la.toCall > 0) throw new Error('面对下注时过牌');
    if (act.type === 'call' && la.toCall <= 0) throw new Error('无注可跟却跟注');
    if (t.street !== reached) { reached = t.street; }
    t.apply(act);
  }
  t.resolve();
  var sumEnd = t.players.reduce(function (s, p) { return s + p.stack; }, 0);
  if (sumEnd !== sumAfterStart) throw new Error('第 ' + h + ' 手金钱不守恒：开局 ' + sumAfterStart + ' → 结束 ' + sumEnd);
  t.players.forEach(function (p) {
    if (p.stack < 0) throw new Error('负筹码：' + p.name);
    if (!Number.isInteger(p.stack)) throw new Error('非整数筹码：' + p.name);
  });
  maxSteps = Math.max(maxSteps, steps);
  totalPot += t.resolved.pots.reduce(function (s, pr) { return s + pr.amount; }, 0);
  if (t.foldWin) { foldWins++; streetStats.preflop++; }
  else {
    showdowns++;
    if (t.board.length === 3) streetStats.flop++;
    else if (t.board.length === 4) streetStats.turn++;
    else streetStats.river++;
  }
}
console.log('  ✓ ' + H + ' 手全部正常结束（最长 ' + maxSteps + ' 步）');
console.log('  ✓ 金钱守恒、无负筹码、动作全部合法');
console.log('    摊牌率 ' + (showdowns / H * 100).toFixed(0) + '%，弃牌胜 ' + (foldWins / H * 100).toFixed(0) + '%，平均底池 ' + Math.round(totalPot / H));
console.log('    动作分布: ' + JSON.stringify(actionStats));
console.log('    成到翻牌 ' + streetStats.flop + ' / 转牌 ' + streetStats.turn + ' / 河牌 ' + streetStats.river + ' / 摊牌对比');

/* ---------- 5. 单挑与 4 人桌快速冒烟 ---------- */
console.log('\n[5] 单挑 / 4 人桌冒烟测试');
[2, 4].forEach(function (n) {
  var t2 = new Table({ seatCount: n, sb: 10, bb: 20, startStack: 2000, runoutMode: false });
  for (var i = 0; i < 120; i++) {
    t2.startHand();
    var sum0 = t2.players.reduce(function (s, p) { return s + p.stack; }, 0) + t2.potTotal();
    var steps = 0;
    while (!t2.handOver) {
      if (++steps > 600) throw new Error(n + '人桌死循环');
      var a = t2.currentActor();
      t2.apply(GTO.decide(t2, a.idx));
    }
    t2.resolve();
    var sum1 = t2.players.reduce(function (s, p) { return s + p.stack; }, 0);
    if (sum1 !== sum0) throw new Error(n + '人桌金钱不守恒');
  }
  console.log('  ✓ ' + n + ' 人桌 120 手通过');
});

/* ---------- 6. 边池单元测试 ---------- */
console.log('\n[6] 边池分层结算');
(function () {
  var t3 = new Table({ seatCount: 4, sb: 10, bb: 20, startStack: 2000 });
  // 手工构造：A 全下 100，KK 弃，C 加注到 300，D 全下 300 → 主池 400 + 边池 400
  function addCommit(p, amt) { p.stack -= amt; p.streetCommitted += amt; p.totalCommitted += amt; }
  var P = t3.players;
  P.forEach(function (p) { p.folded = false; p.hole = hand7(['2h', '3d']); });
  P[0].hole = hand7(['As', 'Ad']);   // 主池赢
  P[1].hole = hand7(['Ks', 'Kd']);
  P[2].hole = hand7(['Qs', 'Qd']);
  P[3].hole = hand7(['Jh', 'Jc']);
  P[1].folded = true;                 // KK 弃
  addCommit(P[0], 100); P[0].allIn = true;
  addCommit(P[1], 100);
  addCommit(P[2], 300);
  addCommit(P[3], 300); P[3].allIn = true;
  t3.board = hand7(['2c', '7h', '9s', 'Kd', '3c']); // 断连无花：三家均为对子
  t3.street = 'river';
  var res = t3.resolve();
  var total = P.reduce(function (s, p) { return s + p.stack; }, 0);
  assert(total === 8000, '边池总额 800 全部分配（总筹码守恒 8000），实际 ' + total);
  var potNames = res.pots.map(function (pr) { return pr.amount + ':' + pr.winners.map(function (i) { return P[i].name; }).join('/') }).join(' | ');
  console.log('    边池分布: ' + potNames);
  // 期望：主池 400（P0/P1/P2/P3 各 100，AA 最大）；边池 400（P2/P3，QQ > JJ）
  assert(res.pots[0].winners[0] === 0, '主池 400 归 AA');
  assert(res.pots[1].winners[0] === 2, '边池 400 归 QQ');
})();

console.log('\n==============================');
if (failures === 0) console.log('全部测试通过 ✅');
else { console.log(failures + ' 项失败 ❌'); process.exit(1); }
