/* gto.js — GTO 决策引擎（机器人大脑 + 人类教练）
 *
 * 设计原则（对应知识库 gto-poker/）：
 *  1. 范围思维：机器人从不偷看底牌，只根据公开动作历史给每个对手建"范围模型"，
 *     用蒙特卡洛计算「我的手牌 vs 对手范围」的胜率（01/06 文件）。
 *  2. 翻前图表：各位置 RFI / 3bet / 冷跟 / 4bet 频率来自 03 文件的求解器基线
 *     （UTG≈16% / HJ≈21% / CO≈29% / BTN≈48% / SB≈42%；IP 3bet 偏极化、OOP 偏线性）。
 *  3. 翻后平衡：下注频率看范围优势、下注尺度看坚果优势（04 文件）；
 *     湿度抛物线定 c-bet；胜率实现 EQR 修正跟注（05 文件）。
 *  4. 数学三件套：底池赔率、MDF 防守、价值:诈唬比（02 文件）。
 *  5. 阻断牌：诈唬优先选带 blocker 的牌（05 文件）。
 *  6. 混合策略：边缘决策用随机频率，避免机器人被确定性剥削（01 文件无差别原理）。
 *
 * 全局命名空间 root.GTO。decide(state, idx) 为纯函数（不修改 state）。 */
(function (root) {
  'use strict';
  var Cards = root.Cards, Ranges = root.Ranges, Equity = root.Equity;

  /* ============ 翻前图表（知识库 03 文件的数字） ============ */
  var RFI_PCT = { 'UTG': 0.16, 'HJ': 0.21, 'CO': 0.29, 'BTN': 0.48, 'SB': 0.42 };
  var OPEN_SIZE_BB = { 'UTG': 2.5, 'HJ': 2.5, 'CO': 2.5, 'BTN': 2.5, 'SB': 3.0 };
  var WHEEL_BLUFFS = ['A5s', 'A4s', 'A3s', 'A2s'];   // 极化 3bet 的 blocker 诈唬牌

  /* ============ 工具 ============ */
  var PERF = 1; // 审计/批量仿真时降低蒙特卡洛迭代（setPerf）
  function setPerf(scale) { PERF = scale; }
  function clamp(x, a, b) { return Math.max(a, Math.min(x, b)); }
  function noise(amp) { return (Math.random() - 0.5) * amp; }

  function raiseCount(state, street) {
    var n = 0;
    state.actionHistory.forEach(function (a) { if (a.street === street && a.type === 'raise') n++; });
    return n;
  }
  function callCount(state, street) {
    var n = 0;
    state.actionHistory.forEach(function (a) { if (a.street === street && a.type === 'call') n++; });
    return n;
  }
  /* 最后一个加注信息：{playerIdx, pos, sizeChips, raisesBefore} */
  function lastRaiseInfo(state, street) {
    var info = null, before = 0;
    state.actionHistory.forEach(function (a) {
      if (a.street !== street) return;
      if (a.type === 'raise') { info = { playerIdx: a.playerIdx, pos: state.positionName(a.playerIdx), sizeChips: a.to, raisesBefore: before }; before++; }
      else if (a.type === 'fold' || a.type === 'call' || a.type === 'check') { /* no-op */ }
    });
    return info;
  }
  /* 我是否位置在后（对该对手） */
  function inPositionVs(state, meIdx, oppIdx) {
    var n = state.players.length;
    var relMe = (meIdx - state.buttonIdx + n) % n;
    var relOpp = (oppIdx - state.buttonIdx + n) % n;
    return relMe < relOpp || relMe === 0; // rel 0 = BTN 最优
  }
  function isIP(state, meIdx) {
    var opps = state.activeUnfolded().filter(function (p) { return p.idx !== meIdx; });
    return opps.every(function (o) { return inPositionVs(state, meIdx, o.idx); });
  }
  /* 整手牌的最后加注者（判断谁是翻前主动方） */
  function lastAggressorIdx(state) {
    var idx = -1;
    state.actionHistory.forEach(function (a) { if (a.type === 'raise') idx = a.playerIdx; });
    return idx;
  }

  /* ============ 牌面纹理（知识库 04 文件） ============ */
  function classifyBoard(board) {
    var suitCnt = [0, 0, 0, 0], rankCnt = {}, i;
    board.forEach(function (c) {
      suitCnt[Cards.suitOf(c)]++;
      var r = Cards.rankOf(c); rankCnt[r] = (rankCnt[r] || 0) + 1;
    });
    var maxSuit = Math.max.apply(null, suitCnt);
    var ranks = Object.keys(rankCnt).map(Number).sort(function (a, b) { return b - a; });
    var paired = ranks.length < board.length;
    // 任意 5 连窗口内的最多牌数（含隔张）
    var maxWindow = 0;
    for (var s = 0; s <= 8; s++) {
      var w = 0;
      ranks.forEach(function (r) { if (r >= s && r <= s + 4) w++; });
      if (w > maxWindow) maxWindow = w;
    }
    var high = ranks[0] >= 9; // J 以上
    var mono = maxSuit >= 3;
    var twoTone = !mono && maxSuit === 2;
    var straighty = maxWindow >= 3 && ranks[0] - ranks[ranks.length - 1] <= 4;
    var dry = !mono && !twoTone && !straighty && maxWindow <= 2;
    var mid = !mono && !dry && !straighty;
    return { mono: mono, twoTone: twoTone, paired: paired, straighty: straighty, dry: dry, mid: mid, wet: straighty, high: high, safe: !mono && !straighty && !twoTone };
  }

  /* 我是否持有好阻断牌（知识库 05 文件） */
  function hasGoodBlocker(me, board) {
    var r1 = Cards.rankOf(me.hole[0]), r2 = Cards.rankOf(me.hole[1]);
    if (r1 === 12 || r2 === 12) return true; // 持 A：阻断 AA/AK/Ax
    var tex = classifyBoard(board);
    if (tex.twoTone) {
      var suitCnt = [0, 0, 0, 0];
      board.forEach(function (c) { suitCnt[Cards.suitOf(c)]++; });
      for (var s = 0; s < 4; s++) {
        if (suitCnt[s] === 2 && ((Cards.suitOf(me.hole[0]) === s) || (Cards.suitOf(me.hole[1]) === s))) return true; // 同花阻断
      }
    }
    return false;
  }

  /* ============ 对手范围建模（核心！只用公开信息） ============ */
  /* 范围按翻前动作确定，再按翻后动作的激进度做强牌过滤（保留 top 比例） */
  function modelRange(state, villainIdx) {
    var me = state.players[villainIdx];
    var acts = state.actionHistory.filter(function (a) { return a.playerIdx === villainIdx && a.street === 'preflop'; });
    var set;
    if (acts.length === 0) {
      set = Ranges.topSet(1);
    } else {
      var last = acts[acts.length - 1];
      var raisesBeforeMe = 0;
      state.actionHistory.forEach(function (a) {
        if (a.street === 'preflop' && a.type === 'raise' &&
            state.actionHistory.indexOf(a) < state.actionHistory.indexOf(last)) {
          if (a.playerIdx !== villainIdx) raisesBeforeMe++;
        }
      });
      if (last.type === 'raise') {
        if (raisesBeforeMe === 0) {
          var pos = state.positionName(villainIdx);
          var pct = (state.players.length === 2) ? 0.82 : (RFI_PCT[pos] || 0.29);
          // 尺寸提示：加注越大范围越紧（每多 1bb 收 ~7%）
          var sizeBB = last.to / state.bb;
          var base = state.players.length === 2 ? 2.5 : (OPEN_SIZE_BB[pos] || 2.5);
          pct *= clamp(base / sizeBB, 0.75, 1.2);
          set = Ranges.topSet(pct);
        } else if (raisesBeforeMe === 1) {
          // 3bet：IP 线性偏宽 / OOP 线性 + 轮转 A 诈唬（03 文件）
          set = Ranges.topSet(0.075);
          WHEEL_BLUFFS.forEach(function (c) { set.add(c); });
        } else {
          set = Ranges.topSet(0.04);
          WHEEL_BLUFFS.slice(0, 2).forEach(function (c) { set.add(c); });
        }
      } else if (last.type === 'call') {
        var raisedEarlier = acts.some(function (a) { return a.type === 'raise'; });
        if (raisedEarlier) {
          set = Ranges.topSet(0.07); // 被反加注后跟注：QQ-JJ/AKs 级（03 文件：常跟不常 4bet）
        } else if (raisesBeforeMe === 0 && last.to <= state.bb) {
          set = Ranges.topSet(0.30); // 跟平（limp）：人类专属，宽而弱
        } else {
          // 冷跟：可玩性优先（同花/对子/双高张），IP 宽 OOP 紧（03 文件）
          var wide = inPositionVs(state, villainIdx, lastRaiseInfo(state, 'preflop').playerIdx);
          var pctCall = wide ? 0.17 : 0.13;
          set = new Set();
          Ranges.RANKED.forEach(function (c) { if (Ranges.percentileOf(c) <= pctCall && Ranges.isPlayable(c)) set.add(c); });
        }
      } else { // check（BB 选项）或 fold
        set = Ranges.topSet(1);
      }
    }
    // 翻后激进度过滤
    ['flop', 'turn', 'river'].forEach(function (st) {
      var boardSoFar = state.board.slice(0, st === 'flop' ? 3 : (st === 'turn' ? 4 : 5));
      if (boardSoFar.length < 3) return;
      var streetActs = state.actionHistory.filter(function (a) { return a.playerIdx === villainIdx && a.street === st; });
      if (!streetActs.length) return;
      var lastA = streetActs[streetActs.length - 1];
      if (lastA.type === 'fold') { set = new Set(); return; }
      if (lastA.type === 'check') return;
      var keep;
      if (lastA.type === 'raise') keep = 0.45;
      else if (lastA.type === 'call') keep = lastA.frac > 0.8 ? 0.7 : (lastA.frac > 0.4 ? 0.8 : 0.9);
      else keep = 1;
      if (lastA.type === 'raise' || lastA.type === 'call') {
        set = filterTopByStrength(set, boardSoFar, keep);
      }
    });
    return set;
  }

  /* 范围内按「成手强度+听牌加成」排序，保留 top keep 比例 */
  function filterTopByStrength(codeSet, board, keep) {
    var dead = board.slice();
    var scored = [];
    codeSet.forEach(function (code) {
      var combos = Ranges.combosOf(code);
      var rep = null;
      for (var i = 0; i < combos.length; i++) {
        var ok = combos[i].every(function (c) { return dead.indexOf(c) < 0; });
        if (ok) { rep = combos[i]; break; }
      }
      if (!rep) return;
      var cards = rep.concat(board);
      var d = Equity.drawInfo(rep, board);
      var score = Cards.decodeScore(Cards.evalBest(cards)).cat * 100
        + (d.flushDraw ? 25 : 0) + d.straightOuts * 8 + (d.backdoorFlush ? 4 : 0);
      scored.push([score, code]);
    });
    scored.sort(function (a, b) { return b[0] - a[0]; });
    var n = Math.max(1, Math.round(scored.length * keep));
    var out = new Set();
    for (var i = 0; i < n; i++) out.add(scored[i][1]);
    return out;
  }

  /* ============ 翻前决策 ============ */
  function preflopDecide(state, meIdx) {
    var me = state.players[meIdx];
    var pos = state.positionName(meIdx);
    var pers = me.aggro || 1, persB = me.bluff || 1;   // 角色性格系数（夜樱部员各有打法倾向）
    var code = Ranges.handCode(me.hole[0], me.hole[1]);
    var p = Ranges.percentileOf(code);
    var bb = state.bb;
    var la = state.legalActions(meIdx);
    var toCall = la.toCall;
    var raises = raiseCount(state, 'preflop');
    var callers = callCount(state, 'preflop');
    var headsUp = state.players.length === 2;
    var effBB = (me.streetCommitted + me.stack) / bb;
    var roll = Math.random();

    /* —— 短码 push/fold（≤11bb，知识库 03 文件） —— */
    if (effBB <= 11) {
      var jamPct = effBB >= 11 ? 0.16 : effBB >= 10 ? 0.20 : effBB >= 9 ? 0.25 : effBB >= 8 ? 0.30 :
                   effBB >= 7 ? 0.36 : effBB >= 6 ? 0.44 : effBB >= 5 ? 0.55 : effBB >= 4 ? 0.70 : 0.85;
      if (raises === 0) {
        if (p <= jamPct + noise(0.02)) {
          if (la.canRaise) return { type: 'raise', to: la.maxTo, note: '短码纳什推全下' };
          return { type: 'call', note: '短码全下跟注' };
        }
        if (pos === 'BB' && toCall <= 0) return { type: 'check', note: '免费看牌' };
        return { type: 'fold', note: '短码弃牌' };
      }
      var raiseBB = state.currentBet / bb;
      var callPct = clamp(0.08 + Math.max(0, 14 - effBB) * 0.02 + (raiseBB <= 3 ? 0.05 : 0), 0.08, 0.5);
      if (p <= callPct + noise(0.02)) return { type: 'call', note: '短码防守' };
      return { type: 'fold', note: '短码弃牌' };
    }

    /* —— 无人加注：RFI 开门（03 文件图表）。UTG..BTN 的 toCall = 一个大盲 —— */
    if (raises === 0 && toCall <= bb) {
      var openPct = headsUp ? 0.82 : (pos === 'BB' ? 0.24 : (RFI_PCT[pos] || 0.29));
      var isoVsLimp = (pos === 'BB' || pos === 'SB') && callers > 0;   // P3-2：对溜入者是隔离加注，不是 RFI
      if (p <= openPct * pers + noise(0.035)) {
        if (!la.canRaise) return { type: 'call', note: '筹码不足加注，随上' };
        var sizeBB = (OPEN_SIZE_BB[pos] || 2.5) + callers; // 每个跟平者 +1bb
        var to = Math.round(sizeBB * bb);
        if (headsUp && pos === 'BTN') to = Math.round(2.5 * bb);
        var note = isoVsLimp
          ? pos + ' 隔离加注（iso，惩罚溜入者，范围 ' + Math.round(openPct * 100) + '%）'
          : pos + ' 开门加注（RFI ' + Math.round(openPct * 100) + '% 范围）';
        return { type: 'raise', to: clamp(to, la.minTo, la.maxTo), note: note };
      }
      if (pos === 'BB' && toCall <= 0) return { type: 'check', note: 'BB 免费看牌' };
      if (pos === 'SB' && toCall > 0 && toCall <= bb * 0.6 && p <= 0.62 && roll < 0.5)
        return { type: 'call', note: 'SB 补齐盲注' };
      return { type: 'fold', note: '范围外弃牌' };
    }

    /* —— 面对一个加注：3bet / 冷跟 / 弃牌（03 文件：IP 偏极化宽、OOP 偏线性紧） —— */
    if (raises === 1) {
      var raiser = lastRaiseInfo(state, 'preflop');
      var tb, callPct2;
      if (headsUp) { tb = 0.18; callPct2 = 0.45; }
      else {
        var ip = inPositionVs(state, meIdx, raiser.playerIdx);
        tb = ip ? 0.085 : 0.065;
        if ((pos === 'SB' || pos === 'BB') && (raiser.pos === 'CO' || raiser.pos === 'BTN' || raiser.pos === 'HJ')) tb = 0.10; // 打劫加注反制
        callPct2 = (ip ? 0.24 : 0.18) * (0.85 + 0.15 * pers);
        if (pos === 'SB') callPct2 = 0.18;
        if (pos === 'BB') callPct2 = (raiser.pos === 'BTN') ? 0.45 : 0.36; // BB 赔率最宽（研究：总防守 45-50%）
      }
      if (callers >= 1) { tb = Math.min(tb, 0.05); callPct2 *= 0.7; }   // 多人锅收紧
      if (raises >= 1 && state.currentBet / bb <= 2.1) callPct2 *= 1.25; // min-raise 防守放宽
      var polarBluff = (pos === 'SB' || pos === 'BB') && WHEEL_BLUFFS.indexOf(code) >= 0 && roll < 0.35 * persB;
      if (p <= tb * pers + noise(0.02) || polarBluff) {
        if (!la.canRaise) return { type: 'call', note: '不足加注筹码，全下跟注' };
        var mult = inPositionVs(state, meIdx, raiser.playerIdx) ? 3 : 4;   // OOP 4x（03 文件）
        var to3 = Math.round(state.currentBet * mult);
        if (to3 >= (me.streetCommitted + me.stack) * 0.6) to3 = la.maxTo;   // 接近全下就直接推
        return { type: 'raise', to: clamp(to3, la.minTo, la.maxTo), note: polarBluff ? '极化 3bet（A 高阻断牌诈唬）' : '3bet（' + (inPositionVs(state, meIdx, raiser.playerIdx) ? 'IP 线性' : 'OOP 线性+轮转A') + '）' };
      }
      var cut = Ranges.isPlayable(code) ? callPct2 : callPct2 * 0.55; // P1-4：不再叠加过滤，杂色用 55% 宽度档
      if (p <= cut + noise(0.02))
        return { type: 'call', note: '冷跟（可玩性优先，位置' + (inPositionVs(state, meIdx, raiser.playerIdx) ? '好' : '差') + '）' };
      if (pos === 'BB' && toCall <= 0) return { type: 'check', note: 'BB 选项过牌' };
      return { type: 'fold', note: 'MDF 之外弃牌' };
    }

    /* —— 面对 3bet：4bet / 跟注 / 弃牌（03 文件：QQ/JJ/AK 100bb 常跟不常 4bet） —— */
    if (raises === 2) {
      var fb = 0.035;
      var bluff4 = WHEEL_BLUFFS.slice(0, 2).indexOf(code) >= 0 && roll < 0.3 * persB && effBB >= 40;
      if (p <= fb + noise(0.01) || bluff4) {
        if (!la.canRaise) return { type: 'call', note: '不足加注筹码，全下跟注' };
        var to4 = Math.round(state.currentBet * 2.3);
        if (effBB < 25 || to4 >= (me.streetCommitted + me.stack) * 0.6) return { type: 'raise', to: la.maxTo, note: '短码 4bet 全下' };
        return { type: 'raise', to: clamp(to4, la.minTo, la.maxTo), note: '4bet（价值+轮转A诈唬）' };
      }
      var callTh = (inPositionVs(state, meIdx, lastRaiseInfo(state, 'preflop').playerIdx) ? 0.085 : 0.06) + noise(0.015);
      var cut3 = Ranges.isPlayable(code) ? callTh : callTh * 0.55;
      if (p <= cut3 + noise(0.015) && effBB >= 30)
        return { type: 'call', note: '跟 3bet（保留 A 阻断、控制底池）' };
      if (pos === 'BB' && toCall <= 0) return { type: 'check', note: 'BB 选项过牌' };
      return { type: 'fold', note: '对 3bet 弃牌' };
    }

    /* —— 面对 4bet+ —— */
    if (p <= 0.05 + noise(0.01)) {
      if (toCall >= me.stack) return { type: 'call', note: '全下跟注' };
      if (!la.canRaise) return { type: 'call', note: '不足加注（被不足额全下压制），跟注' };
      return { type: 'raise', to: la.maxTo, note: '对 4bet 全下' };
    }
    return { type: 'fold', note: '对 4bet 弃牌（除非 AA/KK）' };
  }

  /* ============ 翻后决策 ============ */
  function slackOf(street) { return street === 'river' ? 0.02 : (street === 'turn' ? 0.03 : 0.03); }

  function postflopDecide(state, meIdx) {
    var me = state.players[meIdx];
    var pers = me.aggro || 1, persB = me.bluff || 1;   // 角色性格系数
    var board = state.board;
    var street = state.street;
    var opponents = state.activeUnfolded().filter(function (pl) { return pl.idx !== meIdx; });
    var dead = board.concat(me.hole);
    var villainSets = opponents.map(function (o) {
      var s = Ranges.expand(modelRange(state, o.idx), dead);
      return s.length ? s : Ranges.expand(Ranges.topSet(1), dead);
    });
    var iters = Math.round((opponents.length > 1 ? 1100 : 1800) * PERF);
    var eq = Equity.vsRanges(me.hole, board, villainSets, iters);          // 范围胜率
    var draws = Equity.drawInfo(me.hole, board);
    var cat = Equity.madeCategory(me.hole, board);
    var pot = state.potTotal();
    var la = state.legalActions(meIdx);
    var toCall = la.toCall;
    var IP = isIP(state, meIdx);
    var roll = Math.random();
    var multiway = opponents.length >= 2;

    // 胜率实现 EQR 修正（05 文件）：OOP 打折，听牌可玩性加分
    var rf = IP ? 1.0 : 0.85;
    if ((draws.flushDraw || draws.straightOuts >= 4) && cat < 2) rf = Math.min(1.0, rf + 0.05);
    var eqA = eq * rf;
    var tex = classifyBoard(board);
    var aggrIdx = lastAggressorIdx(state);
    var iAmAggressor = aggrIdx === meIdx;
    var rangeAdv = iAmAggressor && !(tex.mono && cat < 5 && !draws.flushDraw); // 单色且无花=范围优势失效

    function raiseTo(frac, note) {
      if (!la.canRaise) return { type: 'call', note: note + '（不足加注，全下跟注）' };
      var to = (state.currentBet === 0)
        ? Math.round(frac * pot)
        : state.currentBet + Math.round(frac * (pot + toCall));
      to = clamp(to, la.minTo, la.maxTo);
      return { type: 'raise', to: to, note: note };
    }
    function betTo(frac, note) { return raiseTo(frac, note); }

    /* —— 面对下注：价值加注 / 半诈唬加注 / 底池赔率跟注 / MDF 防守 / 弃牌 —— */
    if (toCall > 0) {
      var req = toCall / (pot + toCall);          // 底池赔率（02 文件）
      var canRaise = la.canRaise;
      if (canRaise && eqA >= 0.82 && roll < (street === 'river' ? 0.55 : 0.35)) {
        var f = (eq >= 0.92 && street === 'river' && roll < 0.35 && !multiway) ? 1.3 : (0.75 + roll * 0.3);
        return raiseTo(f, '强牌价值加注（胜率 ' + Math.round(eq * 100) + '% vs 范围）');
      }
      /* 价值加注 / check-raise：三条街都有路径，按成手强度分档给频率
       * （solver 翻牌面对下注的 raise 率约 8-14%，转河递减） */
      var raiseDamp = multiway ? 0.5 : 1;
      if (canRaise && cat >= 3 && roll < 0.35 * raiseDamp)
        return raiseTo(0.75, (street === 'flop' ? 'check-raise' : '加注') + '价值（三条以上）');
      if (canRaise && cat === 2 && roll < 0.22 * raiseDamp)
        return raiseTo(0.7, '价值加注（两对）');
      if (canRaise && cat === 1 && eqA >= 0.62 && street !== 'river' && roll < 0.06 * raiseDamp)
        return raiseTo(0.6, '价值加注（顶对型）');
      if (canRaise && street !== 'river' && !multiway && (draws.flushDraw || draws.straightOuts >= 4) && roll < 0.07 * raiseDamp)
        return raiseTo(1.0, '听牌半诈唬加注');
      var implied = 0;
      if (street !== 'river' && draws.flushDraw) implied += 0.04;   // 隐含赔率（02 文件）
      if (street !== 'river' && draws.straightOuts >= 4) implied += 0.03;
      if (eqA >= req + slackOf(street) + implied)
        return { type: 'call', note: '底池赔率足够（需 ' + Math.round(req * 100) + '%，有 ' + Math.round(eq * 100) + '%）' };
      if (!multiway && eqA >= req * 0.72 && (cat >= 1 || draws.flushDraw || draws.straightOuts >= 4))
        return { type: 'call', note: '按 MDF 防守（范围保护）' };
      if (canRaise && street === 'flop' && !multiway && cat === 0 && hasGoodBlocker(me, board) && roll < 0.05)
        return raiseTo(1.1, '阻断牌诈唬加注');
      return { type: 'fold', note: '胜率不足弃牌（需 ' + Math.round(req * 100) + '%，只有 ' + Math.round(eq * 100) + '%）' };
    }

    /* —— 可以下注：强牌 / c-bet / 半诈唬 / 权益剥夺 / 慢打 —— */
    if (street === 'river') {
      if (eq >= 0.88) {
        if (roll < 0.3 && tex.safe && !multiway) return betTo(1.4, '超池价值（坚果优势）');
        return betTo(1.0, '满池价值');
      }
      if (eq >= 0.65) return betTo(0.75, '价值下注（' + Math.round(eq * 100) + '%）');
      if (eq >= 0.56 && roll < 0.5 && !multiway) return betTo(0.35, '薄价值下注');
      var air = cat === 0;
      if (air && !multiway && roll < (hasGoodBlocker(me, board) ? 0.38 : 0.26)) {
        var bf = roll < 0.4 ? 0.75 : 1.15;
        return betTo(bf, '河牌诈唬（阻断牌+无摊牌价值）');
      }
      return { type: 'check', note: '摊牌过牌' };
    }

    if (eqA >= 0.90 && street === 'flop' && roll < 0.12 && state.spr(meIdx) > 4)
      return { type: 'check', note: '慢打设 trap（范围保护）' };
    if (eqA >= 0.78) {
      var f2 = street === 'turn' ? (0.7 + roll * 0.3) : (0.6 + roll * 0.25);
      return betTo(f2, '强牌造池（几何尺寸思维）');
    }
    // c-bet：翻前主动方按牌面纹理频率「全范围」施压（solver 口径——
    // 逐手胜率门槛会导致 c-bet 远低于求解器频率，弱牌由诈唬配额覆盖）
    var cbf;
    if (tex.mono) cbf = { f: 0.30, s: 0.33 };
    else if (tex.dry) cbf = { f: 0.85, s: 0.40 };
    else if (tex.wet) cbf = { f: 0.50, s: 0.75 };
    else cbf = { f: 0.65, s: 0.60 };
    if (!rangeAdv) cbf.f *= 0.55;
    cbf.f *= (0.85 + 0.15 * pers);
    if (multiway) cbf.f *= 0.6;
    if (street === 'turn') cbf.f *= 0.85;
    if (roll < cbf.f)
      return betTo(cbf.s, (rangeAdv ? '范围优势 c-bet' : 'c-bet') + '（' + texName(tex) + '面）');
    var semi = draws.flushDraw || draws.straightOuts >= 4 || (draws.backdoorFlush && draws.straightOuts >= 1);
    if (semi) {
      var sf = (rangeAdv ? 0.5 : 0.28) * (0.8 + 0.2 * persB);
      if (multiway) sf *= 0.5;
      if (roll < sf) return betTo(street === 'turn' ? 0.66 : 0.5, '半诈唬（有再改善权益）');
      return { type: 'check', note: '听牌过牌（免费实现胜率）' };
    }
    if (rangeAdv && cat === 0 && !multiway && hasGoodBlocker(me, board) && roll < 0.15)
      return betTo(0.33, '权益剥夺小注（好阻断牌）');
    return { type: 'check', note: '过牌（控制底池）' };
  }

  function texName(tex) { return tex.mono ? '单调' : tex.wet ? '湿润' : tex.dry ? '干燥' : '中等'; }

  /* ============ 对外接口 ============ */
  function decide(state, meIdx) {
    var me = state.players[meIdx];
    if (state.street === 'preflop') return preflopDecide(state, meIdx);
    return postflopDecide(state, meIdx);
  }

  /* 教练面板：给人类的 GTO 分析（同样只看公开信息） */
  function coach(state, meIdx) {
    var me = state.players[meIdx];
    var board = state.board;
    var opponents = state.activeUnfolded().filter(function (pl) { return pl.idx !== meIdx; });
    var dead = board.concat(me.hole);
    var perOpp = [];
    var villainSets = [];
    opponents.forEach(function (o) {
      var set = modelRange(state, o.idx);
      var combos = Ranges.expand(set, dead);
      if (!combos.length) { set = Ranges.topSet(1); combos = Ranges.expand(set, dead); }
      villainSets.push(combos);
      var eq = Equity.vsRange(me.hole, board, combos, Math.round(500 * PERF));
      var entered = state.actionHistory.some(function (a) { return a.playerIdx === o.idx && (a.type === 'call' || a.type === 'raise'); }); // 仅 call/raise 算入池（P2-5）
      perOpp.push({ name: o.name, rangePct: Ranges.comboPct(set), combos: combos.length, equity: eq, entered: entered });
    });
    var multiEq = Equity.vsRanges(me.hole, board, villainSets, Math.round(800 * PERF));
    var pot = state.potTotal();
    var toCall = state.legalActions(meIdx).toCall;
    var req = toCall > 0 ? toCall / (pot + toCall) : 0;
    var mdf = toCall > 0 ? (pot - toCall) / pot : null;
    var handName = board.length >= 3 ? Cards.handName(Cards.evalBest(me.hole.concat(board))) : null;
    var draws = board.length >= 3 ? Equity.drawInfo(me.hole, board) : null;
    /* 已弃牌 → 复盘模式：只给范围与胜率，不给建议 */
    var suggestion = me.folded ? null : decide(state, meIdx);
    return {
      perOpp: perOpp, multiEq: multiEq, req: req, mdf: mdf,
      toCall: toCall, pot: pot, handName: handName, draws: draws,
      suggestion: suggestion
    };
  }

  root.GTO = { decide: decide, coach: coach, modelRange: modelRange, classifyBoard: classifyBoard, setPerf: setPerf };
})(typeof window !== 'undefined' ? window : globalThis);
