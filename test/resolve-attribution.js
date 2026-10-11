/* resolve-attribution.js — R5-施工 P1-1 结算归因专项测试
 * 覆盖：单人可赢层=收回未被跟注 / 空可赢层退还（修复筹码泄漏）/ 净数零和。
 * 运行：node test/resolve-attribution.js */
'use strict';
require('../js/cards.js');
require('../js/ranges.js');
require('../js/equity.js');
require('../js/engine.js');
var Cards = globalThis.Cards;
var Table = globalThis.Table;

var failures = 0;
function assert(cond, msg) {
  if (!cond) { failures++; console.error('  ✗ FAIL: ' + msg); }
  else console.log('  ✓ ' + msg);
}

function strToCard(s) {
  var r = Cards.RANK_CHARS.indexOf(s[0]);
  var suit = 'shdc'.indexOf(s[1]);
  return r * 4 + suit;
}

/* 直接摆好桌面状态再结算（绕过下注轮，聚焦 resolve 归因） */
function mkStacked(committed, folded, holes, board) {
  var t = new Table({ seatCount: committed.length, sb: 10, bb: 20, startStack: 2000, runoutMode: false });
  committed.forEach(function (c, i) {
    var p = t.players[i];
    p.name = 'P' + i;
    p.totalCommitted = c;
    p.folded = !!folded[i];
    p.stack = 2000 - c;
    p.hole = (holes[i] || []).map(strToCard);
    p.rebuys = 0;
  });
  t.board = board.map(strToCard);
  t.street = 'river';
  t.buttonIdx = 0;
  return t;
}

function checkZeroSum(t, tag) {
  var sum = 0;
  t.players.forEach(function (p) {
    sum += (p.wonThisHand || 0) + (p.refundThisHand || 0) - p.totalCommitted;
  });
  assert(sum === 0, tag + '：净数零和（实际 ' + sum + '）');
  var stackSum = t.players.reduce(function (s, p) { return s + p.stack; }, 0);
  var expect = t.players.length * 2000;
  assert(stackSum === expect, tag + '：筹码守恒（桌上有 ' + stackSum + '，应有 ' + expect + '）');
}

console.log('\n[RA-1] 未被跟注的超出部分 → 退还（非「赢得」）');
(function () {
  /* A 下注 500，B 只有 200 全下跟注（仍活着进摊牌）：L200 对局 + L300 只有 A 出钱 */
  var t = mkStacked([500, 200], [false, false],
    [['As','Ks'], ['2h','3h']], ['As', 'Ks', 'Qh', 'Jh', '2c']);
  var res = t.resolve();
  var uncalled = res.pots.filter(function (p) { return p.uncalled; });
  var contest = res.pots.filter(function (p) { return !p.uncalled && !p.foldWin; });
  assert(uncalled.length === 1 && uncalled[0].amount === 300, '超额 300 归因为「收回未被跟注」');
  assert(contest.length === 1 && contest[0].amount === 400, '200 底注 ×2 = 400 照常对局');
  assert(t.players[0].refundThisHand === 300, 'A.refundThisHand = 300（不计入赢得）');
  checkZeroSum(t, 'RA-1');
})();

console.log('\n[RA-2] 单人可赢的层 → 收回未被跟注（弃牌者死钱归入，但不再标「赢得边池」）');
(function () {
  /* A 活着投入 2000，D 活着 500 全下；B 弃牌前投入了 2000。
   * L500 四人争；L2000 只有 A 可赢 → 按「收回未被跟注」归因。 */
  var t = mkStacked([2000, 2000, 500, 500], [false, true, true, false],
    [['As','Ks'], [], [], ['2c','3c']], ['As', 'Ks', 'Qh', 'Jh', '2d']);
  var res = t.resolve();
  var contest = res.pots.filter(function (p) { return !p.uncalled && !p.foldWin; });
  var refunded = res.pots.filter(function (p) { return p.uncalled; });
  assert(contest.length === 1 && contest[0].amount === 2000, 'L500 ×4 = 2000 照常对局（实际 ' +
    (contest[0] ? contest[0].amount : '无') + '）');
  assert(refunded.length === 1 && refunded[0].amount === 3000, 'L2000 层 3000 归因为「收回未被跟注」');
  assert(t.players[0].refundThisHand === 3000, 'A.refundThisHand = 3000');
  checkZeroSum(t, 'RA-2');
})();

console.log('\n[RA-3] 全员弃牌的空可赢层 → 各自拿回（修复旧版筹码泄漏）');
(function () {
  /* A 弃牌前 900、B 弃牌前 1000、C/D 活着各 800。
   * L800 四人争；L900 只有 A 出钱；L1000 只有 B 出钱——旧版这两层直接蒸发。 */
  var t = mkStacked([900, 1000, 800, 800], [true, true, false, false],
    [[], [], ['As','Ks'], ['2c','3c']], ['As', 'Ks', 'Qh', 'Jh', '2d']);
  var res = t.resolve();
  assert(t.players[0].refundThisHand === 100, 'A 收回自己的超额 100');
  assert(t.players[1].refundThisHand === 200, 'B 收回自己的超额 200');
  var back = t.players[0].stack + t.players[1].stack;
  assert(back === 2400, '弃牌者筹码本金+超额全归位（实际 ' + back + '）');
  checkZeroSum(t, 'RA-3');
})();

console.log('\n[RA-4] 正常对局不受影响（两层边池+平分）');
(function () {
  var t = mkStacked([2000, 1500, 1500, 500], [false, false, false, true],
    [['Ac','Kc'], ['Ah','Kh'], ['2c','3c'], []], ['As', 'Ks', 'Qh', 'Jh', '2d']);
  var res = t.resolve();
  var contest = res.pots.filter(function (p) { return !p.uncalled && !p.foldWin; });
  var total = contest.reduce(function (s, p) { return s + p.amount; }, 0);
  var refunded = res.pots.filter(function (p) { return p.uncalled; })
    .reduce(function (s, p) { return s + p.amount; }, 0);
  assert(contest.length === 2, '主池+边池两层照常生成');
  assert(total === 5000 && refunded === 500, '对局 5000 + 退还 500 = 投入 5500（实际对局 ' + total + ' / 退还 ' + refunded + '）');
  assert(contest.some(function (p) { return p.split; }), 'A/B 同为两对 A/K → 平分标记');
  checkZeroSum(t, 'RA-4');
})();

console.log('');
if (failures) { console.error('共 ' + failures + ' 项失败'); process.exit(1); }
console.log('★ 结算归因测试全部通过');
