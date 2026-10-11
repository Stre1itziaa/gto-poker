/* cards.js — 牌、牌型评估（7 选 5 取最优）
 * 全局命名空间 root.Cards，兼容浏览器与 Node（无头测试）。 */
(function (root) {
  'use strict';

  var RANK_CHARS = '23456789TJQKA';
  var SUIT_CHARS = ['♠', '♥', '♦', '♣'];
  var SUIT_NAMES = ['黑桃', '红桃', '方块', '梅花'];
  var SUIT_RED = [false, true, true, false];
  var CAT_NAMES = ['高牌', '一对', '两对', '三条', '顺子', '同花', '葫芦', '四条', '同花顺'];

  function rankOf(c) { return c >> 2; }            // 0=2 ... 12=A
  function suitOf(c) { return c & 3; }
  function cardStr(c) { return RANK_CHARS[rankOf(c)] + SUIT_CHARS[suitOf(c)]; }
  function isRed(c) { return SUIT_RED[suitOf(c)]; }
  function rankChar(r) { return RANK_CHARS[r]; }
  function rankDisplay(r) { return r === 8 ? '10' : RANK_CHARS[r]; }
  function makeDeck() {
    var d = [];
    for (var c = 0; c < 52; c++) d.push(c);
    return d;
  }
  function shuffle(a, rng) {
    rng = rng || Math.random;
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  /* ---- 5 张评分为可比较整数：cat*15^5 + 5 位 15 进制踢脚 ---- */
  function eval5(c5) {
    var r0 = c5[0] >> 2, r1 = c5[1] >> 2, r2 = c5[2] >> 2, r3 = c5[3] >> 2, r4 = c5[4] >> 2;
    var flush = ((c5[0] & 3) === (c5[1] & 3)) && ((c5[0] & 3) === (c5[2] & 3)) &&
                ((c5[0] & 3) === (c5[3] & 3)) && ((c5[0] & 3) === (c5[4] & 3));
    var cnt = [0,0,0,0,0,0,0,0,0,0,0,0,0];
    cnt[r0]++; cnt[r1]++; cnt[r2]++; cnt[r3]++; cnt[r4]++;
    var groups = [], i;
    for (i = 0; i < 13; i++) if (cnt[i]) groups.push([cnt[i], i]);
    groups.sort(function (a, b) { return b[0] - a[0] || b[1] - a[1]; });
    var uniq = groups.map(function (g) { return g[1]; }).sort(function (a, b) { return b - a; });
    var straightHigh = -1;
    if (uniq.length === 5) {
      if (uniq[0] - uniq[4] === 4) straightHigh = uniq[0];
      else if (uniq[0] === 12 && uniq[1] === 3 && uniq[2] === 2 && uniq[3] === 1 && uniq[4] === 0) straightHigh = 3; // A2345
    }
    var cat, ks;
    if (flush && straightHigh >= 0) { cat = 8; ks = [straightHigh]; }
    else if (groups[0][0] === 4) { cat = 7; ks = [groups[0][1], groups[1][1]]; }
    else if (groups[0][0] === 3 && groups[1][0] === 2) { cat = 6; ks = [groups[0][1], groups[1][1]]; }
    else if (flush) { cat = 5; ks = uniq; }
    else if (straightHigh >= 0) { cat = 4; ks = [straightHigh]; }
    else if (groups[0][0] === 3) { cat = 3; ks = [groups[0][1], groups[1][1], groups[2][1]]; }
    else if (groups[0][0] === 2 && groups[1][0] === 2) { cat = 2; ks = [groups[0][1], groups[1][1], groups[2][1]]; }
    else if (groups[0][0] === 2) { cat = 1; ks = [groups[0][1], groups[1][1], groups[2][1], groups[3][1]]; }
    else { cat = 0; ks = uniq; }
    var score = cat, k;
    for (i = 0; i < 5; i++) { k = (ks[i] !== undefined) ? ks[i] : 0; score = score * 15 + k; }
    return score;
  }

  /* 7 选 5 的 21 种组合索引（预计算） */
  var C75 = (function () {
    var out = [], a, b, c, d, e;
    for (a = 0; a < 3; a++) for (b = a + 1; b < 4; b++) for (c = b + 1; c < 5; c++)
      for (d = c + 1; d < 6; d++) for (e = d + 1; e < 7; e++) out.push([a, b, c, d, e]);
    return out;
  })();

  function eval7(c7) {
    var best = -1, i, s;
    for (i = 0; i < 21; i++) {
      var idx = C75[i];
      s = eval5([c7[idx[0]], c7[idx[1]], c7[idx[2]], c7[idx[3]], c7[idx[4]]]);
      if (s > best) best = s;
    }
    return best;
  }

  /* 5/6/7 张通用最优评估（翻牌 5 张、转牌 6 张时用） */
  function evalBest(cards) {
    var n = cards.length, i, d, k;
    if (n === 5) return eval5(cards);
    if (n === 7) return eval7(cards);
    if (n === 6) {
      var best = -1;
      for (d = 0; d < 6; d++) {
        var h = [];
        for (i = 0, k = 0; i < 6; i++) if (i !== d) h[k++] = cards[i];
        var s = eval5(h);
        if (s > best) best = s;
      }
      return best;
    }
    throw new Error('evalBest 需要 5-7 张牌');
  }

  /* 把 score 解码为 {cat, ks} 用于中文命名 */
  function decodeScore(score) {
    var ks = [0, 0, 0, 0, 0], i;
    for (i = 4; i >= 0; i--) { ks[i] = score % 15; score = Math.floor(score / 15); }
    return { cat: score, ks: ks };
  }
  function handName(score) {
    var d = decodeScore(score), r = d.ks;
    var R = function (x) { return rankDisplay(x); };
    switch (d.cat) {
      case 8: return r[0] === 12 ? '皇家同花顺' : '同花顺（' + R(r[0]) + ' 高）';
      case 7: return '四条（' + R(r[0]) + '）';
      case 6: return '葫芦（' + R(r[0]) + ' 带 ' + R(r[1]) + '）';
      case 5: return '同花（' + R(r[0]) + ' 高）';
      case 4: return '顺子（' + R(r[0]) + ' 高）';
      case 3: return '三条（' + R(r[0]) + '）';
      case 2: return '两对（' + R(r[0]) + ' 和 ' + R(r[1]) + '）';
      case 1: return '一对（' + R(r[0]) + '）';
      default: return '高牌（' + R(r[0]) + '）';
    }
  }

  root.Cards = {
    RANK_CHARS: RANK_CHARS, SUIT_CHARS: SUIT_CHARS, SUIT_NAMES: SUIT_NAMES,
    rankOf: rankOf, suitOf: suitOf, cardStr: cardStr, isRed: isRed,
    rankChar: rankChar, rankDisplay: rankDisplay,
    makeDeck: makeDeck, shuffle: shuffle,
    eval5: eval5, eval7: eval7, evalBest: evalBest, decodeScore: decodeScore, handName: handName
  };
})(typeof window !== 'undefined' ? window : globalThis);
