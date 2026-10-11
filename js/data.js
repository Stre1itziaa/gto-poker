/* data.js — 数据分析板块（批外插单：第三张卡）
 *
 * 数据面：每手牌局在结算时由 main.js（单机/房主）或 mp.js（客人）写入本机
 * localStorage（gto-handlog，上限 300 手，新者在前）。生产站为静态托管，
 * 不上服务器——数据归本机所有，可导出 JSON / 再导入合并。
 *
 * 录入结构（与 serve.js 留档同构，另加 hero 专属字段）：
 *   { room, handNo, ts, sb, bb,
 *     players: [{name,charId,isBot,stackEnd,committed,won,refund,rebuys,hole?}],
 *     board: ['A♠',...], actions: [{idx,street,type,to,added}], pots: [...], assert? }
 *
 * 纯函数 stats() 可在 Node 无头测试（test/data-stats.js）。
 */
(function (root) {
  'use strict';
  var KEY = 'gto-handlog';
  var CAP = 300;

  function safeGet() {
    try { return JSON.parse(root.localStorage.getItem(KEY) || '[]') || []; }
    catch (e) { return []; }
  }
  function safeSet(v) {
    try { root.localStorage.setItem(KEY, JSON.stringify(v)); return true; }
    catch (e) { return false; }   // 配额满/隐私模式：静默丢，不影响牌局
  }

  function all() { return safeGet(); }

  function record(rec) {
    if (!rec || !rec.ts) return false;
    var arr = safeGet();
    arr.unshift(rec);
    if (arr.length > CAP) arr.length = CAP;
    return safeSet(arr);
  }

  function normHero(s) { return String(s == null ? '' : s).replace(/（你）/g, ''); }
  function keyOf(r) { return (r.room || '') + '#' + (r.handNo || 0) + '#' + (normHero(r.hero) || '?'); }

  function merge(list) {
    if (!list || !list.length) return 0;
    var cur = safeGet();
    var seen = {};
    cur.forEach(function (r) { seen[keyOf(r)] = true; });
    var added = 0;
    list.forEach(function (r) {
      if (r && r.ts && !seen[keyOf(r)]) { cur.unshift(r); added++; }
    });
    if (cur.length > CAP) cur.length = CAP;
    return safeSet(cur) ? added : -1;
  }

  function clearAll() {
    try { root.localStorage.removeItem(KEY); return true; } catch (e) { return false; }
  }

  /* ---------- Step 1：留档 observable ----------
   * post() = 本机 record + 服务器 POST（仅 http 环境，生产静态站自动跳过）。
   * 失败 → 排队 + 首次红字告警（once，防刷屏）→ 后续成功/下一手自动 flushPosts 重发。
   * 每条记录带 aid（时间戳+视角），服务器按 aid 落盘 → 重发天然去重。 */
  var postQueue = [], archiveWarned = false;
  function sendBody(body) {
    root.fetch('/api/handlog', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        flushPosts();
      })
      .catch(function () {
        if (postQueue.indexOf(body) < 0) postQueue.push(body);
        if (!archiveWarned) {
          archiveWarned = true;
          if (root.UI && root.UI.appendError) root.UI.appendError('⚠ 牌局留档服务不可达，已排队并将在后续手自动重发（本机记录不受影响）');
        }
      });
  }
  function flushPosts() {
    if (!postQueue.length) return;
    if (root.Capacitor) { postQueue.length = 0; return; }
    if (!root.location || root.location.protocol !== 'http:') { postQueue.length = 0; return; }
    var batch = postQueue.slice();
    postQueue.length = 0;
    batch.forEach(function (body) { sendBody(body); });
  }
  function post(rec) {
    if (!rec.aid) rec.aid = (rec.ts || String(Date.now())) + '-' + (rec.perspective || 'host');
    record(rec);
    if (!root.location || root.location.protocol !== 'http:') return;   // 静态托管/file：无后端
    if (root.Capacitor) return;   /* APP 打包态：无后端, 只留本机 */
    sendBody(JSON.stringify(rec));
  }

  function heroNet(p) { return (p.won || 0) + (p.refund || 0) - (p.committed || 0); }

  /* ---------- 聚合统计（纯函数） ----------
   * heroName：只统计该玩家的记录（个人 KPI/曲线）；对手表仍用全部记录。
   * 无 heroName 或记录无 hero（旧档）时退回全量，保持向后兼容。 */
  function stats(records, heroName, opts) {
    opts = opts || {};
    heroName = normHero(heroName);
    var rs = (records || []).slice().sort(function (a, b) { return a.ts < b.ts ? -1 : 1; });
    /* Step 5：剔除代打/离席的手（标记见 main.js/mp.js 落档） */
    if (opts.excludeIdle) rs = rs.filter(function (r) { return !r.idleSeats && !r.heroAuto; });
    var mine = rs.filter(function (r) { return !heroName || !normHero(r.hero) || normHero(r.hero) === heroName; });
    /* Step 14：收集 hero 名字集（含改名前的旧名）——这些人永远不算「对手」 */
    var heroNames = {};
    rs.forEach(function (r) {
      var me = r.players && r.players[0];
      if (me) heroNames[normHero(me.name)] = true;
    });
    var hands = 0, netBB = 0, vpip = 0, pfr = 0;
    var series = [], opponents = {};
    mine.forEach(function (r) {
      var me = r.players && r.players[0];
      if (!me) return;
      hands++;
      var bb = r.bb || 20;
      var net = heroNet(me);
      netBB += net / bb;
      series.push({ handNo: r.handNo || 0, netBB: net / bb, room: r.room || '', ts: r.ts });
      var pre = (r.actions || []).filter(function (a) { return a.street === 'preflop' && a.idx === 0; });
      if (pre.some(function (a) { return a.type === 'call' || a.type === 'raise'; })) vpip++;
      if (pre.some(function (a) { return a.type === 'raise'; })) pfr++;
    });
    rs.forEach(function (r) {
      (r.players || []).forEach(function (p, idx) {
        if (idx === 0) return;                       // 录入者本人（无论谁的存档）
        if (p.idle) return;                          // Step 5：离席/代打座位不稀释对手倾向
        if (heroName && (p.name === heroName || heroNames[normHero(p.name)])) return;   // Step 14：改名前的自己也不是对手
        var o = opponents[p.name] || (opponents[p.name] = { hands: 0, vpip: 0, pfr: 0, name: p.name, charId: p.charId || '', isBot: !!p.isBot });
        o.hands++;
        if (r.idleSeats) o.idleHands = (o.idleHands || 0) + 1;
        var acts = (r.actions || []).filter(function (a) { return a.street === 'preflop' && a.idx === idx; });
        if (acts.some(function (a) { return a.type === 'call' || a.type === 'raise'; })) o.vpip++;
        if (acts.some(function (a) { return a.type === 'raise'; })) o.pfr++;
      });
    });
    return {
      hands: hands,
      totalHands: rs.length,
      netBB: Math.round(netBB * 10) / 10,
      vpip: hands ? Math.round(vpip / hands * 100) : 0,
      pfr: hands ? Math.round(pfr / hands * 100) : 0,
      series: series,
      opponents: opponents
    };
  }

  /* ---------- 页面渲染（仅浏览器） ---------- */
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

  /* ---------- 图表（canvas 版 · 2026-10-03 横屏适配） ----------
   * 原 SVG width:100%/height:auto：高度随容器宽被动缩放，横屏矮窗被压扁，
   * 且外层几何审计量不到图表实体高。改 canvas 后：
   *   - 布局高交给 CSS（横屏矮窗档定死 170px，竖屏/桌面保持 640:170 等比）；
   *   - 位图按容器实尺寸 × devicePixelRatio 重建，不糊不压；
   *   - 初始属性 640×170 与原 viewBox 同比例 → 非横屏档几何与旧 SVG 一致。
   * 代价：圆点 <title> 悬浮提示随 SVG 去掉（数据点数值见最新/极值标注）。 */
  var chartSeries = [];
  function chartCanvas(series) {
    chartSeries = series || [];
    return '<canvas class="data-chart" width="640" height="170" role="img" aria-label="累计盈亏曲线"></canvas>';
  }
  function cssVar(el, name, fb) {
    try {
      var v = root.getComputedStyle(el).getPropertyValue(name);
      return (v && v.trim()) || fb;
    } catch (e) { return fb; }
  }
  function drawChart(c) {
    var box = c.getBoundingClientRect();
    /* 宽兜底防 0（隐藏态误量）；高不设下限——高度由 CSS 定（横屏 170px 定死，
     * 其余档 640:170 等比），这里若强行抬底会把等比档的画布拉变形 */
    var W = Math.round(box.width) || 640;
    var H = Math.round(box.height) || 170;
    var dpr = Math.min(3, root.devicePixelRatio || 1);
    c.width = Math.round(W * dpr);
    c.height = Math.round(H * dpr);
    var ctx = c.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    var gold = cssVar(c, '--gold', '#e8b96a');
    var muted = cssVar(c, '--muted', '#9a8aa8');
    var lineC = cssVar(c, '--line', '#4a3a55');
    var font = '"LXGW WenKai Screen", system-ui, sans-serif';
    if (!chartSeries.length) {
      ctx.fillStyle = muted;
      ctx.font = '12px ' + font;
      ctx.textAlign = 'center';
      ctx.fillText('暂无数据——去打几手，回来看曲线。', W / 2, H / 2);
      return;
    }
    var cum = [], c0 = 0;
    chartSeries.forEach(function (s) {
      c0 += s.netBB;
      cum.push({ v: Math.round(c0 * 10) / 10, handNo: s.handNo });
    });
    var P = 26;
    var vals = cum.map(function (p) { return p.v; }).concat([0]);
    var min = Math.min.apply(null, vals);
    var max = Math.max.apply(null, vals);
    if (max === min) max = min + 1;
    var n = cum.length;
    var dots = cum.map(function (p, i) {
      var x = P + (W - 2 * P) * (n === 1 ? 0.5 : i / (n - 1));
      var y = H - P - (H - 2 * P) * ((p.v - min) / (max - min));
      return { x: x, y: y, v: p.v, handNo: p.handNo };
    });
    var zeroY = H - P - (H - 2 * P) * ((0 - min) / (max - min));
    var last = cum[n - 1].v;
    /* 零轴：虚线 */
    ctx.strokeStyle = lineC;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(P, zeroY); ctx.lineTo(W - P, zeroY); ctx.stroke();
    ctx.setLineDash([]);
    /* 累计折线 */
    ctx.strokeStyle = gold;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    dots.forEach(function (d, i) { if (i) ctx.lineTo(d.x, d.y); else ctx.moveTo(d.x, d.y); });
    ctx.stroke();
    /* 数据点：负值红、正值金（同旧 .chart-dot.neg 规则） */
    dots.forEach(function (d) {
      ctx.beginPath();
      ctx.arc(d.x, d.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = d.v >= 0 ? gold : '#ff9d9d';
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,.4)';
      ctx.lineWidth = 1;
      ctx.stroke();
    });
    /* Step 9：x 轴手数刻度（每 ⌈n/6⌉ 手一档小字） */
    var step = Math.max(1, Math.ceil(n / 6));
    ctx.fillStyle = muted;
    ctx.font = '10px ' + font;
    ctx.textAlign = 'center';
    for (var ti = 0; ti < n; ti += step) {
      ctx.fillText(String(dots[ti].handNo), dots[ti].x, H - 8);
    }
    /* 极值/最新标注 */
    ctx.font = '11px ' + font;
    ctx.textAlign = 'left';
    ctx.fillText(max + 'bb', P, 13);
    ctx.fillText(min + 'bb', P, H - 8);
    ctx.fillStyle = gold;
    ctx.textAlign = 'right';
    ctx.fillText('最新 ' + (last >= 0 ? '+' : '') + last + 'bb', W - P, 13);
  }
  function drawCharts() {
    if (!root.document) return;
    Array.prototype.forEach.call(
      root.document.querySelectorAll('#data-body canvas.data-chart'), drawChart);
  }

  var pageMode = '';   // '' 全部 | 'mp' 多人 | 'sp' 单机（R6-R3：mode 字段消费落地）
  var excludeIdle = false;   // Step 5：剔除代打/离席的手（页面会话内记忆）

  function render() {
    if (!root.document) return;
    var body = root.document.getElementById('data-body');
    if (!body) return;
    var recs = all();
    if (pageMode) {
      recs = recs.filter(function (r) { return (r.mode || (r.room === 'local' ? 'sp' : 'mp')) === pageMode; });
    }
    var heroName = '';
    try { heroName = String(root.localStorage.getItem('gto-name') || '').replace(/（你）/g, ''); } catch (e) { /* noop */ }
    var st = stats(recs, heroName, { excludeIdle: excludeIdle });

    var html = '<div class="mp-row" style="gap:8px;margin:0 0 8px">' +
      '<span class="muted" style="font-size:12px">范围：</span>' +
      [['', '全部'], ['mp', '多人'], ['sp', '单机']].map(function (m) {
        return '<button class="ghost data-mode-chip' + (pageMode === m[0] ? ' sel' : '') + '" data-mode="' + m[0] + '" type="button" aria-pressed="' + (pageMode === m[0]) + '">' + m[1] + '</button>';
      }).join('') +
      '<label class="muted" style="font-size:12px;margin-left:auto;display:inline-flex;align-items:center;gap:4px;cursor:pointer">' +
      '<input type="checkbox" id="data-excl-idle"' + (excludeIdle ? ' checked' : '') + '> 剔除代打/离席的手</label></div>';
    html += '<div class="data-cards">' +
      '<div class="data-stat"><i>手数</i><b>' + st.hands + '</b></div>' +
      '<div class="data-stat"><i>累计盈亏</i><b class="' + (st.netBB >= 0 ? 'pos' : 'neg') + '">' + (st.netBB >= 0 ? '+' : '') + st.netBB + 'bb</b></div>' +
      '<div class="data-stat"><i>VPIP</i><b>' + st.vpip + '%</b></div>' +
      '<div class="data-stat"><i>PFR</i><b>' + st.pfr + '%</b></div>' +
      '</div>' +
      /* Step 8：口径标注，消除「打了 3 手为何显示 6」的持续误报 */
      '<div class="muted" style="font-size:12px;margin:2px 0 6px">口径：手数含未至摊牌的手（全弃/跑马都计）；VPIP/PFR 只看翻前主动投入；明细见下方牌谱。</div>';
    if (recs.length > st.hands) {
      html += '<div class="muted" style="font-size:12px">另有导入记录 ' + (recs.length - st.hands) + ' 手（他人视角，不计入个人曲线，对手表含其对手）。</div>';
    }
    html += '<h4>累计盈亏曲线（bb / 手）</h4>' + chartCanvas(st.series);

    var opps = Object.keys(st.opponents).map(function (k) { return st.opponents[k]; })
      .filter(function (o) { return o.hands > 0; })
      .sort(function (a, b) { return b.hands - a.hands; });
    if (opps.length) {
      html += '<h4>对手倾向（同桌昵称入档，仅存本机）</h4><div class="data-table">' +
        /* Step 10：表头行 + 单元格去「VPIP/PFR」前缀 */
        '<div class="data-row data-head"><span class="data-opp">对手</span><span>手数</span><span>VPIP</span><span>PFR</span><span>判定</span></div>';
      opps.forEach(function (o) {
        var v = Math.round(o.vpip / o.hands * 100), p = Math.round(o.pfr / o.hands * 100);
        var idleTag = o.idleHands ? ' <span class="mp-tag">含代打</span>' : '';
        var tag = o.hands < 10
          ? '<span class="muted">样本 ' + o.hands + ' 手</span>'
          : '<span class="' + (v >= 45 ? 'pos' : 'muted') + '">' + (v >= 45 ? '松' : v <= 22 ? '紧' : '中性') + '</span>';
        html += '<div class="data-row">' +
          '<span class="data-opp">' + esc(o.name) + (o.isBot ? ' <span class="mp-tag">部员</span>' : '') + idleTag + '</span>' +
          '<span>' + o.hands + '</span>' +
          '<span>' + v + '%</span>' +
          '<span>' + p + '%</span>' +
          tag + '</div>';
      });
      html += '</div>';
    }

    var show = recs.slice(0, 30);
    if (show.length) {
      html += '<h4>牌谱（最近 ' + show.length + ' 手，导出含全部 ' + recs.length + ' 手）</h4>';
      var streetZh = { preflop: '翻前', flop: '翻牌', turn: '转牌', river: '河牌', showdown: '摊牌' };
      show.forEach(function (r) {
        var me = r.players && r.players[0];
        var net = me ? heroNet(me) : 0;
        var bb = r.bb || 20;
        var sign = net >= 0 ? '+' : '−';
        var col = net > 0 ? 'pos' : net < 0 ? 'neg' : 'muted';
        var board = (r.board || []).join(' ') || '（未进翻牌）';
        var hole = me && me.hole && me.hole.length ? ' · 底牌 ' + me.hole.join(' ') : '';
        var tm = '';
        try { tm = ' · ' + new Date(r.ts).toTimeString().slice(0, 5); } catch (e) { /* noop */ }
        /* 行动流：人名化 + 中文动作 + 按街分组
         * R6-R3：街内首个 raise = 「下注 N」，其余 = 「加注到 N」（去掉「到→」双标记）；
         * fold/check 不带尾巴；call 用本街增量 */
        var actZh = { fold: '弃牌', check: '过牌', call: '跟注', raise: '加注到' };
        var actsHtml = '';
        var streets = ['preflop', 'flop', 'turn', 'river', 'showdown'];
        streets.forEach(function (sName) {
          var seg = (r.actions || []).filter(function (a) { return a.street === sName; });
          if (!seg.length) return;
          var betSeen = (sName === 'preflop');   /* R6-R4：翻前盲注已开局，首攻仍是「加注」；翻后首攻才是「下注」 */
          var segStr = seg.map(function (a) {
            var nm = (r.players && r.players[a.idx] && r.players[a.idx].name) || ('P' + (a.idx + 1));
            var zh = actZh[a.type] || a.type;
            var suffix = '';
            if (a.type === 'raise') {
              if (!betSeen) { zh = '下注'; betSeen = true; }
              suffix = ' ' + (a.to || '');
            } else if (a.type === 'call' && (a.added || a.to)) {
              suffix = ' ' + (a.added || a.to);
            }
            return esc(nm) + ' ' + zh + suffix;
          }).join(' · ');
          actsHtml += '<div class="muted data-acts"><b>' + (streetZh[sName] || sName) + '</b> ' + segStr + '</div>';
        });
        if (!actsHtml) actsHtml = '<div class="muted data-acts">（无行动记录）</div>';
        /* 胜负手：同赢家同牌型的多池合并为一行带合计 */
        var mergedPots = [];
        (r.pots || []).forEach(function (pr) {
          var key = (pr.winners || []).join(',') + '|' + (pr.foldWin ? 'f' : pr.uncalled ? 'u' : (pr.handName || ''));
          var last = mergedPots[mergedPots.length - 1];
          if (last && last.key === key) { last.amount += pr.amount || 0; last.labels.push(pr.label || '底池'); }
          else {
            var cp = {}; for (var k in pr) if (Object.prototype.hasOwnProperty.call(pr, k)) cp[k] = pr[k];
            cp.labels = [pr.label || '底池']; cp.key = key;
            mergedPots.push(cp);
          }
        });
        var potLines = mergedPots.map(function (pr) {
          var names = (pr.winners || []).map(function (w) {
            return esc((r.players && r.players[w] && r.players[w].name) || '?');
          }).join('、');
          var potLabel = pr.labels.length > 1
            ? pr.labels[0] + '+' + pr.labels.slice(1).join('+') + '（共 ' + pr.amount + '）'
            : (pr.label || '底池') + ' ' + pr.amount;
          if (pr.foldWin) return '<div class="muted">★ ' + names + ' 收下' + potLabel + '（其余全弃）</div>';
          if (pr.uncalled) return '<div class="muted">★ ' + names + ' 收回未被跟注的 ' + pr.amount + '</div>';
          return '<div class="muted">★ ' + names + ' 以「' + esc(pr.handName || '？') + '」赢得 ' + potLabel + (pr.split ? '（平分）' : '') + '</div>';
        }).join('');
        /* 摊牌亮出的底牌（含对手，摊牌即公共信息） */
        var showHoles = (r.players || []).slice(1).filter(function (p) { return p.hole && p.hole.length === 2; })
          .map(function (p) { return esc(p.name) + ' ' + p.hole.join(' '); });
        var holeLine = showHoles.length ? '<div class="muted">摊牌 ' + showHoles.join(' · ') + '</div>' : '';
        html += '<details class="data-hand"><summary>第 ' + r.handNo + ' 手 · ' + esc(r.room || '') + tm +
          ' · <b class="' + col + '">' + sign + Math.abs(net) + '（' + sign + (Math.abs(net) / bb).toFixed(1) + 'bb）</b></summary>' +
          '<div class="muted">公共牌 ' + board + hole + '</div>' +
          potLines + holeLine + actsHtml +
          '</details>';
      });
    } else {
      html += '<div class="muted">还没有牌谱记录——打几手之后这里会逐手留档。</div>';
    }

    html += '<div class="mp-row" style="margin-top:16px">' +
      '<button id="data-export" class="ghost" type="button">导出 JSON</button>' +
      '<label class="ghost data-import-label">导入 JSON<input type="file" id="data-import-file" accept=".json,application/json" hidden></label>' +
      '<button id="data-clear" class="ghost" type="button">清空本机记录</button>' +
      '<span class="muted" style="font-size:12px">记录含同桌昵称 · 仅存本机（上限 300 手）· 不做任何上传</span>' +
      '</div>';

    body.innerHTML = html;
    drawCharts();   /* canvas 位图按容器实尺寸重建（innerWidth 变化后 render 也走这里） */

    /* R6-R3：范围 chips + 牌谱展开滚动到位（sticky 按钮条会盖住展开尾部） */
    Array.prototype.forEach.call(root.document.querySelectorAll('#data-body .data-mode-chip'), function (btn) {
      btn.addEventListener('click', function () {
        pageMode = btn.getAttribute('data-mode') || '';
        render();
      });
    });
    var excl = root.document.getElementById('data-excl-idle');
    if (excl) excl.addEventListener('change', function () {
      excludeIdle = excl.checked;
      render();
    });
    Array.prototype.forEach.call(root.document.querySelectorAll('#data-body details.data-hand'), function (d) {
      d.addEventListener('toggle', function () {
        if (!d.open) return;
        /* Step 3（wupa 配方）：nearest 对超高元素会忽略 scroll-margin——
         * 量高差：展开体高 + 96px 安全边超过容器视高 → 手动滚到尾部，否则 nearest */
        var cont = root.document.getElementById('data-modal');
        if (!cont) { d.scrollIntoView({ block: 'nearest' }); return; }
        var rr = d.getBoundingClientRect(), cr = cont.getBoundingClientRect();
        if (rr.height + 96 > cr.height) {
          cont.scrollTop += (rr.bottom - cr.bottom) + 96;
        } else {
          d.scrollIntoView({ block: 'nearest' });
        }
      });
    });
    /* Step 7②：打开数据页轻推一次滚动，提示下方还有内容可滚 */
    var dcont = root.document.getElementById('data-modal');
    if (dcont && dcont.scrollHeight > dcont.clientHeight + 40) {
      dcont.scrollTop = 56;
      root.setTimeout(function () { try { dcont.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) { dcont.scrollTop = 0; } }, 150);
    }

    /* 按钮行为 */
    var ex = root.document.getElementById('data-export');
    if (ex) ex.addEventListener('click', function () {
      var blob = new root.Blob([JSON.stringify(all(), null, 1)], { type: 'application/json' });
      var a = root.document.createElement('a');
      a.href = root.URL.createObjectURL(blob);
      var roomTag = String((recs[0] && recs[0].room) || 'mix').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 16) || 'mix';
      a.download = 'gto-handlog-' + (heroName || 'my') + '-' + roomTag + '-' + new Date().toISOString().slice(0, 10) + '.json';
      root.document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { root.URL.revokeObjectURL(a.href); }, 2000);
    });
    var im = root.document.getElementById('data-import-file');
    if (im) im.addEventListener('change', function () {
      var file = im.files && im.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        var added = -1, msg = '导入失败：文件不是有效的牌谱 JSON';
        try {
          var parsed = JSON.parse(String(reader.result));
          var list = Array.isArray(parsed) ? parsed : (parsed.hands || null);
          if (Array.isArray(list)) added = merge(list);
          if (added >= 0) msg = '导入成功：新增 ' + added + ' 手';
        } catch (e) { /* 保持失败提示 */ }
        if (root.UI && root.UI.appendError) root.UI.appendError(msg);
        render();
      };
      reader.readAsText(file);
    });
    var cl = root.document.getElementById('data-clear');
    if (cl) cl.addEventListener('click', function () {
      if (cl.dataset.arm !== '1') {
        cl.dataset.arm = '1';
        cl.textContent = '再点一次确认清空';
        setTimeout(function () { cl.dataset.arm = ''; cl.textContent = '清空本机记录'; }, 3000);
        return;
      }
      clearAll();
      render();
      if (root.UI && root.UI.appendError) root.UI.appendError('本机牌谱记录已清空');
    });
  }

  /* 旋转/改窗时数据页若开着，按新容器尺寸重绘 canvas（竖屏↔横屏高度口径不同） */
  if (root.document && root.addEventListener) {
    var rzTimer = 0;
    root.addEventListener('resize', function () {
      root.clearTimeout(rzTimer);
      rzTimer = root.setTimeout(function () {
        var m = root.document.getElementById('data-modal');
        if (m && !m.classList.contains('hidden')) drawCharts();
      }, 120);
    });
  }

  root.DataPage = { all: all, record: record, post: post, flushPosts: flushPosts, merge: merge, clear: clearAll, stats: stats, render: render };
  if (typeof module !== 'undefined' && module.exports) module.exports = { stats: stats, heroNet: heroNet };
})(typeof window !== 'undefined' ? window : globalThis);
