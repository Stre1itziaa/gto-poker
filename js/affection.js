/* affection.js — 部员好感度系统（纯前端，localStorage 持久化）
 *
 * 设计要点（回应"游戏无结局/可无限买入"）：
 *   好感不用裸手数计价，用「质量加权点数」——赢了多拿、摊牌赢多拿、
 *   大赢额外拿、输了也有陪伴分；再叠加每日节奏（首胜奖励），
 *   让"常回来玩"比"一口气肝 200 手"更划算。
 *
 * 点数表（每完成一手，以你当前角色结算）：
 *   完成一手           +4（净赢）/ +2（持平）/ +1（输了也有陪伴分）
 *   摊牌赢下           +4
 *   大赢（净 ≥ +50bb） +5
 *   当日首胜           +10
 *
 * 等级：Lv1=0 · Lv2=150 · Lv3=400 · Lv4=800 · Lv5=1400（满）
 * 服装解锁：p2→Lv.2 · p3→Lv.3 · p4→Lv.5（p0/p1 初始解锁）
 */
(function (root) {
  'use strict';
  var KEY = 'gto-affection';
  var LEVELS = [0, 150, 400, 800, 1400];
  var state = null;

  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
  }
  function load() {
    if (state) return state;
    try { state = JSON.parse(root.localStorage.getItem(KEY) || '{}') || {}; } catch (e) { state = {}; }
    return state;
  }
  function save() {
    try { root.localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* 隐私模式 */ }
    try { root.localStorage.setItem(RANK_KEY, JSON.stringify(rankEntry())); } catch (e) { /* 隐私模式 */ }
  }
  function entry(charId) {
    var s = load();
    var e = s[charId];
    if (!e || typeof e.pts !== 'number') {
      e = s[charId] = { pts: 0, hands: 0, wins: 0, bigWins: 0, daily: null };
    }
    var t = today();
    if (!e.daily || e.daily.date !== t) e.daily = { date: t, hands: 0, firstWin: false };
    return e;
  }
  function levelOf(pts) {
    var lv = 1;
    for (var i = 1; i < LEVELS.length; i++) if (pts >= LEVELS[i]) lv = i + 1;
    return lv;
  }
  function info(charId) {
    var e = entry(charId);
    var lv = levelOf(e.pts);
    var floor = LEVELS[lv - 1];
    var next = LEVELS[lv] || null;
    return {
      pts: e.pts,
      level: lv,
      max: lv >= LEVELS.length,
      floor: floor,
      next: next,
      pct: next ? Math.min(100, Math.round((e.pts - floor) / (next - floor) * 100)) : 100
    };
  }
  function unlockedLevel(key) { return { p0: 1, p1: 1, p2: 2, p3: 3, p4: 5, r1: 3, r2: 4, r3: 5 }[key] || 1; }
  function isCostumeUnlocked(charId, key) { return levelOf(entry(charId).pts) >= unlockedLevel(key); }
  function conditionText(key) { return '好感度达到 Lv.' + unlockedLevel(key) + ' 解锁'; }

  /* 每完成一手调用（main.js 结算处）。rec = DataPage.post 同构留档 */
  function onHand(rec) {
    if (!rec || !rec.players || !rec.players[0]) return null;
    var me = rec.players[0];
    var charId = root.localStorage ? root.localStorage.getItem('gto-char') : null;
    if (!charId && root.Portraits && root.Portraits.ALL && root.Portraits.ALL[0]) {
      charId = root.Portraits.ALL[0].id;   /* 新玩家未设看板娘: 好感落到默认首角色(与大厅 currentChar 同口径) */
    }
    if (!charId) return null;
    var bb = rec.bb || 20;
    var net = (me.won || 0) + (me.refund || 0) - (me.committed || 0);
    var sdWin = (rec.pots || []).some(function (pr) {
      return pr.handName && !pr.foldWin && (pr.winners || []).indexOf(0) >= 0;
    });

    var e = entry(charId);
    var before = levelOf(e.pts);
    var gain = net > 0 ? 4 : net < 0 ? 1 : 2;
    if (sdWin) gain += 4;
    if (net >= bb * 50) gain += 5;
    if (net > 0 && !e.daily.firstWin) { gain += 10; e.daily.firstWin = true; }
    e.daily.hands++;
    e.hands++;
    if (net > 0) e.wins++;
    if (net >= bb * 50) e.bigWins++;
    e.pts += gain;
    var after = levelOf(e.pts);
    save();
    return { charId: charId, gain: gain, level: after, levelUp: after > before, pts: e.pts };
  }

  /* ---------- 段位分（本地排位） ----------
   * 无限买入环境下的排位口径：按每手净胜 bb 计 RP，赢多涨多、输有保底扣。
   * 段位：新人(0) → 青铜(120) → 白银(320) → 黄金(700) → 樱王(1200) */
  var RANK_KEY = 'gto-rank';
  var RANKS = [
    { min: 0,    name: '新员',    color: '#8b93b8' },
    { min: 120,  name: '青铜',    color: '#b08d57' },
    { min: 320,  name: '白银',    color: '#c0c8d8' },
    { min: 700,  name: '黄金',    color: '#f5c96b' },
    { min: 1200, name: '樱王',    color: '#ff9ec7' }
  ];
  var rank = null;
  function rankEntry() {
    if (rank) return rank;
    try { rank = JSON.parse(root.localStorage.getItem(RANK_KEY) || '{}') || {}; } catch (e) { rank = {}; }
    if (typeof rank.rp !== 'number') rank = { rp: 0, hands: 0 };
    return rank;
  }
  function rankInfo() {
    var r = rankEntry();
    var cur = RANKS[0];
    for (var i = 0; i < RANKS.length; i++) if (r.rp >= RANKS[i].min) cur = RANKS[i];
    var next = null;
    for (var j = 0; j < RANKS.length; j++) if (RANKS[j].min > r.rp) { next = RANKS[j]; break; }
    return { rp: r.rp, name: cur.name, color: cur.color, next: next };
  }
  function rankOnHand(rec) {
    if (!rec || !rec.players || !rec.players[0]) return null;
    var me = rec.players[0];
    var bb = rec.bb || 20;
    var net = (me.won || 0) + (me.refund || 0) - (me.committed || 0);
    var netBB = net / bb;
    var r = rankEntry();
    r.hands++;
    var delta;
    if (net > 0) delta = Math.max(2, Math.round(netBB));
    else if (net < 0) delta = -Math.min(6, Math.max(1, Math.round(Math.abs(netBB) / 2)));
    else delta = 0;
    r.rp = Math.max(0, r.rp + delta);
    save();
    return { delta: delta, rank: rankInfo() };
  }

  root.Affection = {
    onHand: onHand,
    info: info,
    levelOf: levelOf,
    isCostumeUnlocked: isCostumeUnlocked,
    conditionText: conditionText,
    rankInfo: rankInfo,
    rankOnHand: rankOnHand
  };
})(typeof window !== 'undefined' ? window : globalThis);
