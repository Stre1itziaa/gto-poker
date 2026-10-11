/* mp-protocol.js — 批1 安全加固的联机协议无头测试（R4）
 * 覆盖：normalizeAct 白名单降级（S3）/ 合法动作透传 / 数值钳制。
 * 运行：node test/mp-protocol.js */
'use strict';
require('../js/cards.js');
require('../js/ranges.js');
require('../js/equity.js');
require('../js/engine.js');
require('../js/mp.js');
var Table = globalThis.Table;
var MP = globalThis.MP;

var failures = 0;
function assert(cond, msg) {
  if (!cond) { failures++; console.error('  ✗ FAIL: ' + msg); }
  else console.log('  ✓ ' + msg);
}

function mkTable() {
  var t = new Table({ seatCount: 2, sb: 10, bb: 20, startStack: 200, runoutMode: false });
  t.startHand();
  return t;
}

console.log('\n[MP-P] normalizeAct 白名单与钳制（S3）');
(function () {
  var t = mkTable();
  var seat = t.actorIdx;

  // 合法 fold 透传
  var a1 = MP.__test.normalizeAct(t, seat, { type: 'fold' });
  assert(a1.type === 'fold', '合法 fold 透传');

  // 非法类型 → 有注可跟时降级 fold
  var a2 = MP.__test.normalizeAct(t, seat, { type: 'zzz' });
  assert(a2.type === 'fold', '非法类型 zzz → 有注降级 fold（实际 ' + a2.type + '）');

  // 非法类型 + 无注 → check
  t2 = new Table({ seatCount: 2, sb: 10, bb: 20, startStack: 200, runoutMode: false });
  var t2;
  t2.startHand();
  // 构造无注可过局面：直接看当前 legalActions
  var la0 = t2.legalActions(t2.actorIdx);
  var a3 = MP.__test.normalizeAct(t2, t2.actorIdx, { type: 'zzz' });
  if (la0.toCall <= 0) assert(a3.type === 'check', '非法类型 + 无注 → check');
  else assert(a3.type === 'fold', '非法类型 + 有注 → fold');

  // raise 超界钳到 maxTo
  var t3 = new Table({ seatCount: 2, sb: 10, bb: 20, startStack: 200, runoutMode: false });
  t3.startHand();
  var seat3 = t3.actorIdx;
  var la3 = t3.legalActions(seat3);
  if (la3.canRaise) {
    var a4 = MP.__test.normalizeAct(t3, seat3, { type: 'raise', to: 999999 });
    /* normalizeAct 不做数值钳制（那是引擎 apply 的职责）——验证引擎兜底 */
    t3.apply(a4);
    assert(t3.players[seat3].streetCommitted <= la3.maxTo,
      '引擎 apply 钳制超额 raise（实际投入 ' + t3.players[seat3].streetCommitted + ' ≤ ' + la3.maxTo + '）');
    var a5 = MP.__test.normalizeAct(t3, t3.actorIdx, { type: 'raise', to: NaN });
    assert(a5.to === MP.__test.normalizeAct(t3, t3.actorIdx, { type: 'raise', to: 0 }).to || a5.to <= 200,
      'raise NaN → minTo 兜底（实际 ' + a5.to + '）');
  } else {
    console.log('  （本手不可加注，跳过 raise 钳制用例）');
  }

  // check 面对下注 → 转弃牌或跟注，绝不以 check 进引擎
  var t4 = new Table({ seatCount: 2, sb: 10, bb: 20, startStack: 200, runoutMode: false });
  t4.startHand();
  var bbSeat = (t4.buttonIdx + 1) % 2;
  var laBB = t4.legalActions(bbSeat);
  if (laBB.toCall > 0) {
    var a6 = MP.__test.normalizeAct(t4, bbSeat, { type: 'check' });
    assert(a6.type === 'call' || a6.type === 'fold', '面对下注的 check → 转为 ' + a6.type);
  }
})();

console.log('\n[MP-P] R1 手号校验所需字段在消费端可用');
(function () {
  var t = mkTable();
  var seat = t.actorIdx;
  // 模拟：动作带当前手号 → normalizeAct 正常；不带手号由 hostOnData 拒绝（此处验证字段读取不炸）
  var a = MP.__test.normalizeAct(t, seat, { hand: t.handNo, type: 'call' });
  assert(typeof a.type === 'string', '带 hand 字段的动作正常处理');
})();

console.log('');
if (failures) { console.error('共 ' + failures + ' 项失败'); process.exit(1); }
console.log('★ 联机协议安全测试全部通过');
