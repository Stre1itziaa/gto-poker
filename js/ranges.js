/* ranges.js — 169 手牌排序（近似求解器 RFI 排序）、组合计数、范围工具
 * 依据知识库 03-preflop：组合计数（对 6 / 同花 4 / 杂色 12，共 1326）、
 * 各位置 RFI 宽度（UTG≈16% / HJ≈21% / CO≈29% / SB≈42% / BTN≈48%）。
 * 全局命名空间 root.Ranges。 */
(function (root) {
  'use strict';
  var Cards = root.Cards;

  /* 前 113 位：显式排序（对 RFI 截断有影响的区域）；其余按启发式分数排序。
   * 口径说明：范围宽度一律用「组合空间」（前序组合数/1326），类型序号/169 的旧口径已废弃。
   * 组合口径实测 RFI 宽度：UTG 16.3% / HJ 21.4% / CO 29.1% / SB 42.1% / BTN 48.1%（审计 2026-09-16）。 */
  var RANKED_TOP = [
    'AA','KK','QQ','JJ','TT','AKs','99','AQs','AJs','ATs',
    '88','AQo','A9s','KQs','77','A8s','KJs','QTs','A5s','AJo',
    'KTs','A7s','JTs','66','Q9s','K9s','ATo','A4s','KQo','QJo',
    'A3s','55','KJo','J9s','A2s','T9s','Q8s','J8s','98s','KTo',
    'K8s','Q7s','J7s','T8s','87s','QTo','76s','A9o','JTo','K7s',
    'K6s','65s','Q6s','A8o','K5s','J9o','T7s','K9o','A7o','54s',
    'Q5s','44','K4s','Q4s','K8o','T6s','75s','A6o','J5s','K3s',
    'Q3s','96s','A5o','Q2s','K2s','86s','J4s','33','T5s','J6s',
    '85s','64s','J3s','A4o','T4s','Q9o','J2s','T3s','53s','95s',
    '22','T9o','T2s','A3o','84s','74s','94s','32s','63s','42s',
    '93s','A2o','52s','62s','82s','72s'
  ];

  var ALL_CODES = (function () {
    var R = '23456789TJQKA', out = [], i, j;
    for (i = 0; i < 13; i++) {
      out.push(R[i] + R[i]); // 口袋对
      for (j = i + 1; j < 13; j++) {
        out.push(R[j] + R[i] + 's'); // 高位在前（AKs），与 handCode 一致
        out.push(R[j] + R[i] + 'o');
      }
    }
    return out;
  })();

  var RANKED = RANKED_TOP.slice();
  var seen = {};
  RANKED_TOP.forEach(function (c) { seen[c] = true; });
  var rest = ALL_CODES.filter(function (c) { return !seen[c]; });
  function tailScore(code) {
    var hi = Cards.RANK_CHARS.indexOf(code[0]);
    var lo = Cards.RANK_CHARS.indexOf(code[1]);
    var s = hi * 20 + lo;
    if (code[2] === 's') s += 6;
    return s;
  }
  rest.sort(function (a, b) { return tailScore(b) - tailScore(a); });
  RANKED = RANKED.concat(rest);

  var CODE_INDEX = {};
  RANKED.forEach(function (c, i) { CODE_INDEX[c] = i; });

  /* 手牌代码：两张牌 → 'TT' / 'AKs' / 'AKo' */
  function handCode(c1, c2) {
    var r1 = Cards.rankOf(c1), r2 = Cards.rankOf(c2);
    if (r1 === r2) return Cards.RANK_CHARS[r1] + Cards.RANK_CHARS[r2];
    var hi = Math.max(r1, r2), lo = Math.min(r1, r2);
    var suited = (c1 & 3) === (c2 & 3);
    return Cards.RANK_CHARS[hi] + Cards.RANK_CHARS[lo] + (suited ? 's' : 'o');
  }
  /* 代码 → 具体组合列表（对 6 / 同花 4 / 杂色 12） */
  function combosOf(code) {
    var r1 = Cards.RANK_CHARS.indexOf(code[0]);
    var r2 = Cards.RANK_CHARS.indexOf(code[1]);
    var out = [], s1, s2;
    if (r1 === r2) {
      for (s1 = 0; s1 < 4; s1++) for (s2 = s1 + 1; s2 < 4; s2++)
        out.push([r1 * 4 + s1, r1 * 4 + s2]);
    } else {
      var suited = code[2] === 's';
      for (s1 = 0; s1 < 4; s1++) for (s2 = 0; s2 < 4; s2++) {
        if (suited && s1 !== s2) continue;
        if (!suited && s1 === s2) continue;
        out.push([r1 * 4 + s1, r2 * 4 + s2]);
      }
    }
    return out;
  }

  /* RANKED 前 pct 比例 → 手牌集合（按组合宽度：pct × 1326，与研究数字同口径） */
  function topSet(pct) {
    var target = pct * 1326, c = 0, s = new Set();
    for (var i = 0; i < RANKED.length; i++) {
      s.add(RANKED[i]);
      c += combosOf(RANKED[i]).length;
      if (c >= target) break;
    }
    return s;
  }
  /* 「可玩性」过滤：口袋对 / 同花 / 双 9+ / 轮转A —— 冷跟偏好 */
  function isPlayable(code) {
    var hi = Cards.RANK_CHARS.indexOf(code[0]);
    var lo = Cards.RANK_CHARS.indexOf(code[1]);
    if (code.length === 2) return true;                  // 口袋对
    if (code[2] === 's') return true;                    // 同花
    if (hi === 12) return lo <= 4 || lo >= 8;            // 轮转 A / AT+o
    if (hi >= 7 && lo >= 7) return true;                 // 双 9+（T9o/K9o 等可冷跟）
    return false;
  }

  /* 范围集合 → 具体 combo 列表（剔除死牌），供蒙特卡洛采样 */
  function expand(codeSet, deadCards) {
    var dead = {};
    (deadCards || []).forEach(function (c) { dead[c] = true; });
    var out = [];
    codeSet.forEach(function (code) {
      combosOf(code).forEach(function (combo) {
        if (!dead[combo[0]] && !dead[combo[1]]) out.push(combo);
      });
    });
    return out;
  }

  /* 组合空间百分位：RANKED 中排在 code 之前的组合数 / 1326。
   * 研究图表的百分比（RFI 16% 等）都是组合占比，阈值比较必须用同口径——
   * 早期版本误用「类型序号/169」，导致所有范围实际收紧 30-50%。 */
  var CUM_COMBOS = (function () {
    var m = {}, c = 0;
    RANKED.forEach(function (code) {
      m[code] = c / 1326;
      c += combosOf(code).length;
    });
    return m;
  })();
  function percentileOf(code) { return CUM_COMBOS[code]; }

  /* 范围集合占全部 1326 组合的比例 */
  function comboPct(codeSet) {
    var n = 0;
    codeSet.forEach(function (code) { n += combosOf(code).length; });
    return n / 1326;
  }

  root.Ranges = {
    RANKED: RANKED, CODE_INDEX: CODE_INDEX, ALL_CODES: ALL_CODES,
    handCode: handCode, combosOf: combosOf, topSet: topSet,
    isPlayable: isPlayable, expand: expand, percentileOf: percentileOf,
    comboPct: comboPct
  };
})(typeof window !== 'undefined' ? window : globalThis);
