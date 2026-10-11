/* mp-shadow.js — 好友房联机纯逻辑无头测试
 * 覆盖：快照旋转正确性 / 影子桌与权威桌一致性 / 底牌脱敏 /
 *       动作历史旋转 / 摊牌揭示映射。
 * 运行：node test/mp-shadow.js */
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

function mkTable(n) {
  var t = new Table({ seatCount: n, sb: 10, bb: 20, startStack: 2000, runoutMode: false });
  t.players.forEach(function (p, i) {
    p.name = 'P' + i;
    p.charId = ['suzu', 'shiori', 'natsu', 'rin', 'yuki', 'ume'][i];
    p.isBot = i !== 0;   // 0=房主真人，其余机器人占位（测试里脚本代打）
    p.aggro = 1; p.bluff = 1;
  });
  return t;
}

/* 脚本代打：能过牌就 mostly 过，被下注则跟/弃混合，偶尔加注 */
function autoAct(t) {
  var la = t.legalActions(t.currentActor().idx);
  var r = Math.random();
  if (la.toCall <= 0) {
    if (la.canRaise && r < 0.25) return { type: 'raise', to: Math.min(la.maxTo, la.minTo + t.bb * (r < 0.12 ? 3 : 1)) };
    return { type: 'check' };
  }
  if (la.canRaise && r < 0.08) return { type: 'raise', to: Math.min(la.maxTo, la.minTo * 2) };
  if (r < 0.45) return { type: 'call' };
  return { type: 'fold' };
}

/* 把快照应用到影子桌（与 mp.js applySnap 相同的字段拷贝路径，抽出复用） */
function syncShadow(sh, meta) {
  sh.board = meta.board.slice();
  sh.street = meta.street;
  sh.handNo = meta.handId;
  sh.handOver = meta.handOver;
  sh.awaitingRunout = meta.awaitingRunout;
  sh.buttonIdx = meta.buttonRot;
  sh.actorIdx = meta.actorRot;
  sh.currentBet = meta.currentBet;
  sh.minRaiseSize = meta.minRaise;
  sh.actionHistory = meta.actionHistory;
  sh._la = meta.la;
  sh._pos = meta.posNames;
  meta.players.forEach(function (rp, k) {
    var p = sh.players[k];
    p.stack = rp.stack; p.folded = rp.folded; p.allIn = rp.allIn;
    p.streetCommitted = rp.streetCommitted; p.totalCommitted = rp.totalCommitted;
    p.lastAction = rp.lastAction; p.wonThisHand = rp.wonThisHand;
    p.hole = (rp.hole || []).slice();
  });
}

console.log('\n[MP-1] 快照旋转（6 人桌，youAbs=2）');
(function () {
  var t = mkTable(6);
  t.startHand();
  var snap = MP.__test.snapFor(t, 2, false);
  assert(snap.players.length === 6, '快照 6 个座位');
  assert(snap.youAbs === 2, 'youAbs 记录正确');
  assert(snap.players[0].name === 'P2', '0 号位是绝对座位 2（实际 ' + snap.players[0].name + '）');
  assert(snap.players[1].name === 'P3', '旋转顺序 1 号位 = P3');
  assert(snap.players[5].name === 'P1', '旋转顺序 5 号位 = P1');
  var posOk = true;
  for (var i = 0; i < 6; i++) {
    if (snap.posNames[i] !== t.positionName((2 + i) % 6)) posOk = false;
  }
  assert(posOk, '位置名全部旋转一致');
  assert(snap.players[0].hole.length === 2, '收件人看得到自己的底牌');
  assert(snap.players[1].hole.length === 0 && snap.players[5].hole.length === 0, '别人的底牌已脱敏');
  assert(snap.buttonRot === (t.buttonIdx - 2 + 6) % 6, '按钮位旋转正确');
})();

console.log('\n[MP-2] 影子桌与权威桌逐字段一致（连打 20 手，按钮位轮转）');
(function () {
  var t = mkTable(4);
  var youAbs = 1;
  var sh = null, guard = 0, checks = 0, hands = 0, steps = 0;
  while (hands < 20 && guard++ < 20000) {
    if (!sh || t.handOver) {
      if (t.handOver) {
        t.resolve();
        hands++;
      }
      t.startHand();
      sh = MP.__test.buildShadow(MP.__test.snapFor(t, youAbs, false));
      if (sh.potTotal() !== t.potTotal()) { assert(false, '手 ' + hands + '：盲注后底池不一致'); break; }
      continue;
    }
    try { t.apply(autoAct(t)); } catch (e) { assert(false, '手 ' + hands + '：' + e.message); break; }
    steps++;
    syncShadow(sh, MP.__test.snapFor(t, youAbs, t.handOver));
    if (sh.potTotal() !== t.potTotal()) { assert(false, '手 ' + hands + ' 步 ' + steps + '：底池不一致'); break; }
    if (sh.players[0].stack !== t.players[youAbs].stack) { assert(false, '手 ' + hands + ' 步 ' + steps + '：我的筹码映射错误'); break; }
    if (!t.handOver && t.currentActor() && t.currentActor().idx === youAbs) {
      var la1 = sh.legalActions(0), la2 = t.legalActions(youAbs);
      if (!(la1.toCall === la2.toCall && la1.canRaise === la2.canRaise &&
            la1.minTo === la2.minTo && la1.maxTo === la2.maxTo)) {
        assert(false, '手 ' + hands + ' 步 ' + steps + '：影子合法动作与权威不一致'); break;
      }
      checks++;
    }
    if (!t.handOver) {
      var leak = sh.players.some(function (p, k) { return k !== 0 && p.hole.length > 0; });
      if (leak) { assert(false, '手 ' + hands + ' 步 ' + steps + '：对手底牌泄漏'); break; }
    }
  }
  assert(hands >= 20, '20 手完整跑完（共 ' + steps + ' 步）');
  assert(checks > 0, '轮到收件人时合法动作校验 ' + checks + ' 次');
  console.log('  ✓ 每步底池/筹码/脱敏校验通过');

  /* 摊牌揭示映射（用当前已完成的一手） */
  var res = t.resolved || t.resolve();
  var n = 4;
  var mapped = {
    pots: res.pots.map(function (pr) {
      var o = {}; for (var k in pr) o[k] = pr[k];
      o.winners = pr.winners.map(function (w) { return MP.__test.rotIdx(w, youAbs, n); });
      return o;
    }),
    board: res.board.slice()
  };
  var nameOk = mapped.pots.every(function (pr) {
    return pr.winners.every(function (w) {
      /* 影子 0 号位名字带「（你）」后缀，比较时剥掉 */
      return sh.players[w].name.replace('（你）', '') === t.players[(w + youAbs) % n].name;
    });
  });
  assert(nameOk, '摊牌赢家索引映射回正确座位');
})();

console.log('\n[MP-3] 单挑（2 人桌）旋转');
(function () {
  var t = mkTable(2);
  t.startHand();
  var snap = MP.__test.snapFor(t, 1, false);
  assert(snap.players[0].name === 'P1', '单挑 0 号位 = P1');
  assert(snap.players[1].name === 'P0', '单挑 1 号位 = P0');
  assert(snap.posNames[0] === t.positionName(1), '单挑位置名一致');
  var sh = MP.__test.buildShadow(snap);
  assert(sh.potTotal() === t.potTotal(), '单挑底池一致');
})();

console.log('\n[MP-4] 动作历史旋转（教练模型输入面）');
(function () {
  var t = mkTable(6);
  t.startHand();
  var guard = 0;
  while (t.actionHistory.length < 4 && !t.handOver && guard++ < 50) t.apply(autoAct(t));
  var youAbs = 3;
  var meta = MP.__test.snapFor(t, youAbs, false);
  var ok = meta.actionHistory.every(function (a, k) {
    var src = t.actionHistory[k];
    return a.playerIdx === (src.playerIdx - youAbs + 6) % 6 &&
           a.type === src.type && a.to === src.to && a.street === src.street;
  });
  assert(ok, 'actionHistory 全部旋转且保真');
  var sh = MP.__test.buildShadow(meta);
  assert(sh.actionHistory[0].playerIdx === meta.actionHistory[0].playerIdx, '影子保留旋转后历史');
  assert(typeof sh.positionName === 'function' && typeof sh.legalActions === 'function' &&
         typeof sh.potTotal === 'function' && typeof sh.currentActor === 'function' &&
         typeof sh.log === 'function', '影子桌方法面完整（UI/教练依赖）');
})();

console.log('');
if (failures) { console.error('共 ' + failures + ' 项失败'); process.exit(1); }
console.log('★ 好友房联机纯逻辑测试全部通过');
