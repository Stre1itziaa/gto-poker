/* equity.js — 蒙特卡洛胜率引擎
 * 核心纪律：机器人从不"偷看"对手底牌。所有胜率都是
 * 「我的手牌 vs 对手建模范围」的随机采样期望——这正是 GTO 的"范围思维"。
 * 全局命名空间 root.Equity。 */
(function (root) {
  'use strict';
  var Cards = root.Cards;

  function pickCombos(sets, rng, used) {
    /* sets: 每个对手一个 combo 数组；互不碰撞地各采一个 combo。
     * 返回 combo 数组或 null（碰撞过多时退化）。 */
    var picked = [], i, tries;
    for (i = 0; i < sets.length; i++) {
      var set = sets[i];
      if (!set || set.length === 0) return null;
      var combo = null;
      for (tries = 0; tries < 40; tries++) {
        var cand = set[Math.floor(rng() * set.length)];
        if (!used[cand[0]] && !used[cand[1]]) { combo = cand; break; }
      }
      if (!combo) {
        // 罕见：逐个找
        for (var k = 0; k < set.length; k++) {
          if (!used[set[k][0]] && !used[set[k][1]]) { combo = set[k]; break; }
        }
        if (!combo) return null;
      }
      used[combo[0]] = used[combo[1]] = true;
      picked.push(combo);
    }
    return picked;
  }

  /* 多人胜率份额：hole 对阵 villainsRanges（每个是对手 combo 数组）
   * 返回 [0,1]（平分时按 1/n 计）。 */
  function vsRanges(hole, board, villainSets, iters, rng) {
    rng = rng || Math.random;
    iters = iters || 1500;
    var share = 0, it, i;
    var base = hole.concat(board);
    for (it = 0; it < iters; it++) {
      var used = {};
      base.forEach(function (c) { used[c] = true; });
      var villains = pickCombos(villainSets, rng, used);
      if (!villains) { iters--; continue; }
      // 补全公共牌
      var full = board.slice();
      var deck = [];
      for (var c = 0; c < 52; c++) if (!used[c]) deck.push(c);
      while (full.length < 5) {
        var j = Math.floor(rng() * deck.length);
        full.push(deck[j]);
        deck.splice(j, 1);
      }
      var myScore = Cards.eval7(hole.concat(full));
      var best = myScore, ties = 1;
      for (i = 0; i < villains.length; i++) {
        var s = Cards.eval7(villains[i].concat(full));
        if (s > best) { best = s; ties = 0; }
        if (s === myScore) ties++;
      }
      if (best === myScore) share += 1 / ties;
    }
    return iters > 0 ? share / iters : 0;
  }

  /* 单挑精确一些的便利封装 */
  function vsRange(hole, board, villainSet, iters, rng) {
    return vsRanges(hole, board, [villainSet], iters, rng);
  }

  /* 对手具体底牌（仅用于教练复盘/摊牌后讲解） */
  function vsHand(hole, board, villainHole, iters, rng) {
    rng = rng || Math.random;
    iters = iters || 3000;
    var dead = {}; hole.concat(board, villainHole).forEach(function (c) { dead[c] = true; });
    var share = 0, it;
    for (it = 0; it < iters; it++) {
      var full = board.slice(), deck = [];
      for (var c = 0; c < 52; c++) if (!dead[c]) deck.push(c);
      while (full.length < 5) {
        var j = Math.floor(rng() * deck.length);
        full.push(deck[j]); deck.splice(j, 1);
      }
      var a = Cards.eval7(hole.concat(full)), b = Cards.eval7(villainHole.concat(full));
      if (a > b) share += 1; else if (a === b) share += 0.5;
    }
    return share / iters;
  }

  /* 听牌侦测：{flushDraw, straightOuts, backdoor, outs} */
  function drawInfo(hole, board) {
    var known = hole.concat(board);
    var suitCnt = [0, 0, 0, 0], i;
    var mySuitCnt = [0, 0, 0, 0];
    known.forEach(function (c) { suitCnt[Cards.suitOf(c)]++; });
    hole.forEach(function (c) { mySuitCnt[Cards.suitOf(c)]++; });
    var flushDraw = false, backdoorFlush = false;
    for (i = 0; i < 4; i++) {
      if (suitCnt[i] === 4 && mySuitCnt[i] >= 1) flushDraw = true;
      if (suitCnt[i] === 3 && mySuitCnt[i] >= 2) backdoorFlush = true;
    }
    // 顺子听牌：straightOuts = 真实补牌张数（每个能补成顺子的 rank 计 4−已见张数）。
    // 例：OESD=8、两头顺听牌同值、卡顺听牌=4、已成顺=0。
    var cnt = [0,0,0,0,0,0,0,0,0,0,0,0,0];
    known.forEach(function (c) { cnt[Cards.rankOf(c)]++; });
    function straightWith(rank) {
      var c2 = cnt.slice(); c2[rank]++;
      for (var start = 0; start <= 8; start++) {
        var ok = true;
        for (var k = 0; k < 5; k++) if (!c2[start + k]) { ok = false; break; }
        if (ok) return true;
      }
      // 轮转 A2345：A(12),2,3,4,5
      if (c2[12] && c2[0] && c2[1] && c2[2] && c2[3]) return true;
      return false;
    }
    var outs = 0, r;
    for (r = 0; r < 13; r++) {
      if (cnt[r] >= 4) continue;
      if (straightWith(r)) outs += 4 - cnt[r];
    }
    // 已成顺判断：任取窗口
    var hasStraight = false;
    for (var start2 = 0; start2 <= 8; start2++) {
      var ok2 = true;
      for (var k2 = 0; k2 < 5; k2++) if (!cnt[start2 + k2]) { ok2 = false; break; }
      if (ok2) { hasStraight = true; break; }
    }
    if (cnt[12] && cnt[0] && cnt[1] && cnt[2] && cnt[3]) hasStraight = true;
    if (hasStraight) outs = 0;
    var boardDrawy = board.length >= 4; // 转牌后 backdoor 不算
    return {
      flushDraw: flushDraw,
      backdoorFlush: backdoorFlush && !boardDrawy,
      straightOuts: outs,
      hasStraight: hasStraight
    };
  }

  /* 成手类别（不含踢脚）：0高牌 1对 2两对 3三条 4顺 5花 6葫芦 7四条 8同花顺 */
  function madeCategory(hole, board) {
    if (board.length < 3) return -1;
    return Cards.decodeScore(Cards.eval7(hole.concat(board))).cat;
  }

  root.Equity = {
    vsRanges: vsRanges, vsRange: vsRange, vsHand: vsHand,
    drawInfo: drawInfo, madeCategory: madeCategory
  };
})(typeof window !== 'undefined' ? window : globalThis);
