# patch_step1_14.py — 数据模块迭代施工单 Step 1-14（Step 15 资产层挂起）
# 运行：python tools/patch_step1_14.py （在 game/ 目录）
import io, re

# ============ Step 1：data.js 留档 observable（失败队列 + once 告警 + 重发 + post） ============
p = 'js/data.js'
s = io.open(p, encoding='utf-8').read()

old = """  function clearAll() {
    try { root.localStorage.removeItem(KEY); return true; } catch (e) { return false; }
  }"""
new = """  function clearAll() {
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
    if (!root.location || root.location.protocol !== 'http:') { postQueue.length = 0; return; }
    var batch = postQueue.slice();
    postQueue.length = 0;
    batch.forEach(function (body) { sendBody(body); });
  }
  function post(rec) {
    if (!rec.aid) rec.aid = (rec.ts || String(Date.now())) + '-' + (rec.perspective || 'host');
    record(rec);
    if (!root.location || root.location.protocol !== 'http:') return;   // 静态托管/file：无后端
    sendBody(JSON.stringify(rec));
  }"""
assert s.count(old) == 1, 'S1 data post block'
s = s.replace(old, new)

# Step 5/14：stats 支持 excludeIdle 与 hero 名字集去重
old = """  function stats(records, heroName) {
    heroName = normHero(heroName);
    var rs = (records || []).slice().sort(function (a, b) { return a.ts < b.ts ? -1 : 1; });
    var mine = rs.filter(function (r) { return !heroName || !normHero(r.hero) || normHero(r.hero) === heroName; });"""
new = """  function stats(records, heroName, opts) {
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
    });"""
assert s.count(old) == 1, 'S5/14 stats head'
s = s.replace(old, new)

old = """        if (idx === 0) return;                       // 录入者本人（无论谁的存档）
        if (heroName && p.name === heroName) return; // 导入档里「我」也不算对手"""
new = """        if (idx === 0) return;                       // 录入者本人（无论谁的存档）
        if (p.idle) return;                          // Step 5：离席/代打座位不稀释对手倾向
        if (heroName && (p.name === heroName || heroNames[normHero(p.name)])) return;   // Step 14：改名前的自己也不是对手"""
assert s.count(old) == 1, 'S5/14 opponent loop'
s = s.replace(old, new)

# Step 9：曲线 x 轴手数刻度
old = """    return '<svg class="data-chart" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="累计盈亏曲线">' +
      '<line x1="' + P + '" y1="' + zeroY + '" x2="' + (W - P) + '" y2="' + zeroY + '" class="chart-zero"/>' +
      '<polyline points="' + pts + '" class="chart-line"/>' + dotSvg +
      '<text x="' + P + '" y="13" class="chart-max">' + max + 'bb</text>' +"""
new = """    /* Step 9：x 轴手数刻度（每 ⌈n/6⌉ 手一档小字） */
    var step = Math.max(1, Math.ceil(n / 6));
    var ticks = '';
    for (var ti = 0; ti < n; ti += step) {
      var d2 = dots[ti];
      ticks += '<text x="' + d2.x.toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle" class="chart-tick">' + d2.p.handNo + '</text>';
    }
    return '<svg class="data-chart" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="累计盈亏曲线">' +
      '<line x1="' + P + '" y1="' + zeroY + '" x2="' + (W - P) + '" y2="' + zeroY + '" class="chart-zero"/>' +
      '<polyline points="' + pts + '" class="chart-line"/>' + dotSvg + ticks +
      '<text x="' + P + '" y="13" class="chart-max">' + max + 'bb</text>' +"""
assert s.count(old) == 1, 'S9 ticks'
s = s.replace(old, new)

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('data.js patched (S1 post/queue, S5/14 stats, S9 ticks)')

# ============ Step 10/8/3/7/12：render 层（表头/标注/滚动/aria/checkbox/文件名/轻推） ============
old = """    html += '<div class="data-cards">' +
      '<div class="data-stat"><i>手数</i><b>' + st.hands + '</b></div>' +
      '<div class="data-stat"><i>累计盈亏</i><b class="' + (st.netBB >= 0 ? 'pos' : 'neg') + '">' + (st.netBB >= 0 ? '+' : '') + st.netBB + 'bb</b></div>' +
      '<div class="data-stat"><i>VPIP</i><b>' + st.vpip + '%</b></div>' +
      '<div class="data-stat"><i>PFR</i><b>' + st.pfr + '%</b></div>' +
      '</div>';"""
new = """    html += '<div class="data-cards">' +
      '<div class="data-stat"><i>手数</i><b>' + st.hands + '</b></div>' +
      '<div class="data-stat"><i>累计盈亏</i><b class="' + (st.netBB >= 0 ? 'pos' : 'neg') + '">' + (st.netBB >= 0 ? '+' : '') + st.netBB + 'bb</b></div>' +
      '<div class="data-stat"><i>VPIP</i><b>' + st.vpip + '%</b></div>' +
      '<div class="data-stat"><i>PFR</i><b>' + st.pfr + '%</b></div>' +
      '</div>' +
      /* Step 8：口径标注，消除「打了 3 手为何显示 6」的持续误报 */
      '<div class="muted" style="font-size:12px;margin:2px 0 6px">口径：手数含未至摊牌的手（全弃/跑马都计）；VPIP/PFR 只看翻前主动投入；明细见下方牌谱。</div>';"""
assert s.count(old) == 1, 'S8 note'
s = s.replace(old, new)

# chips aria-pressed（Step 7①）
old = """        return '<button class="ghost data-mode-chip' + (pageMode === m[0] ? ' sel' : '') + '" data-mode="' + m[0] + '" type="button">' + m[1] + '</button>';"""
new = """        return '<button class="ghost data-mode-chip' + (pageMode === m[0] ? ' sel' : '') + '" data-mode="' + m[0] + '" type="button" aria-pressed="' + (pageMode === m[0]) + '">' + m[1] + '</button>';"""
assert s.count(old) == 1, 'S7 chips aria'
s = s.replace(old, new)

# Step 5：剔除代打 checkbox（放范围行同一行尾）
old = """      }).join('') + '</div>';
    html += '<div class="data-cards">' +"""
new = """      }).join('') +
      '<label class="muted" style="font-size:12px;margin-left:auto;display:inline-flex;align-items:center;gap:4px;cursor:pointer">' +
      '<input type="checkbox" id="data-excl-idle"' + (excludeIdle ? ' checked' : '') + '> 剔除代打/离席的手</label></div>';
    html += '<div class="data-cards">' +"""
assert s.count(old) == 1, 'S5 checkbox row'
s = s.replace(old, new)

# Step 10：对手表表头 + 单元格去前缀
old = """    if (opps.length) {
      html += '<h4>对手倾向（同桌昵称入档，仅存本机）</h4><div class="data-table">';
      opps.forEach(function (o) {
        var v = Math.round(o.vpip / o.hands * 100), p = Math.round(o.pfr / o.hands * 100);
        var tag = o.hands < 10
          ? '<span class="muted">样本 ' + o.hands + ' 手</span>'
          : '<span class="' + (v >= 45 ? 'pos' : 'muted') + '">' + (v >= 45 ? '松' : v <= 22 ? '紧' : '中性') + '</span>';
        html += '<div class="data-row">' +
          '<span class="data-opp">' + esc(o.name) + (o.isBot ? ' <span class="mp-tag">部员</span>' : '') + '</span>' +
          '<span>' + o.hands + ' 手</span>' +
          '<span>VPIP ' + v + '%</span>' +
          '<span>PFR ' + p + '%</span>' +
          tag + '</div>';
      });
      html += '</div>';
    }"""
new = """    if (opps.length) {
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
    }"""
assert s.count(old) == 1, 'S10 opp table'
s = s.replace(old, new)

# Step 3：details 展开量高差滚动（替换 nearest）
old = """    Array.prototype.forEach.call(root.document.querySelectorAll('#data-body details.data-hand'), function (d) {
      d.addEventListener('toggle', function () {
        if (d.open) d.scrollIntoView({ block: 'nearest' });
      });
    });"""
new = """    Array.prototype.forEach.call(root.document.querySelectorAll('#data-body details.data-hand'), function (d) {
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
    }"""
assert s.count(old) == 1, 'S3/S7 scroll'
s = s.replace(old, new)

# Step 12：导出文件名带 room
old = """      a.download = 'gto-handlog-' + (heroName || 'my') + '-' + new Date().toISOString().slice(0, 10) + '.json';"""
new = """      var roomTag = String((recs[0] && recs[0].room) || 'mix').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 16) || 'mix';
      a.download = 'gto-handlog-' + (heroName || 'my') + '-' + roomTag + '-' + new Date().toISOString().slice(0, 10) + '.json';"""
assert s.count(old) == 1, 'S12 filename'
s = s.replace(old, new)

# render 头部：excludeIdle 状态 + stats 传 opts + heroName 兼容
old = """    var heroName = '';
    try { heroName = String(root.localStorage.getItem('gto-name') || '').replace(/（你）/g, ''); } catch (e) { /* noop */ }
    var st = stats(recs, heroName);"""
new = """    var heroName = '';
    try { heroName = String(root.localStorage.getItem('gto-name') || '').replace(/（你）/g, ''); } catch (e) { /* noop */ }
    var st = stats(recs, heroName, { excludeIdle: excludeIdle });"""
assert s.count(old) == 1, 'render stats opts'
s = s.replace(old, new)

old = """  var pageMode = '';   // '' 全部 | 'mp' 多人 | 'sp' 单机（R6-R3：mode 字段消费落地）"""
new = """  var pageMode = '';   // '' 全部 | 'mp' 多人 | 'sp' 单机（R6-R3：mode 字段消费落地）
  var excludeIdle = false;   // Step 5：剔除代打/离席的手（页面会话内记忆）"""
assert s.count(old) == 1, 'excludeIdle var'
s = s.replace(old, new)

# checkbox wiring（放 chips wiring 之后）
old = """    Array.prototype.forEach.call(root.document.querySelectorAll('#data-body .data-mode-chip'), function (btn) {
      btn.addEventListener('click', function () {
        pageMode = btn.getAttribute('data-mode') || '';
        render();
      });
    });"""
new = """    Array.prototype.forEach.call(root.document.querySelectorAll('#data-body .data-mode-chip'), function (btn) {
      btn.addEventListener('click', function () {
        pageMode = btn.getAttribute('data-mode') || '';
        render();
      });
    });
    var excl = root.document.getElementById('data-excl-idle');
    if (excl) excl.addEventListener('change', function () {
      excludeIdle = excl.checked;
      render();
    });"""
assert s.count(old) == 1, 'S5 wiring'
s = s.replace(old, new)

# 对手表聚合时顺带记 idleHands（含代打手数）供 chip 展示
old = """        o.hands++;
        var acts = (r.actions || []).filter(function (a) { return a.street === 'preflop' && a.idx === idx; });
        if (acts.some(function (a) { return a.type === 'call' || a.type === 'raise'; })) o.vpip++;
        if (acts.some(function (a) { return a.type === 'raise'; })) o.pfr++;
      });
    });
    return {"""
new = """        o.hands++;
        if (r.idleSeats) o.idleHands = (o.idleHands || 0) + 1;
        var acts = (r.actions || []).filter(function (a) { return a.street === 'preflop' && a.idx === idx; });
        if (acts.some(function (a) { return a.type === 'call' || a.type === 'raise'; })) o.vpip++;
        if (acts.some(function (a) { return a.type === 'raise'; })) o.pfr++;
      });
    });
    return {"""
assert s.count(old) == 1, 'opp idleHands'
s = s.replace(old, new)

# post/flushPosts 导出
old = "  root.DataPage = { all: all, record: record, merge: merge, clear: clearAll, stats: stats, render: render };"
new = "  root.DataPage = { all: all, record: record, post: post, flushPosts: flushPosts, merge: merge, clear: clearAll, stats: stats, render: render };"
assert s.count(old) == 1, 'data export'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('data.js patched (Step 1/3/5/7/8/9/10/12/14)')

# ============ main.js：Step 1/2/5/14 ============
p = 'js/main.js'
s = io.open(p, encoding='utf-8').read()

# Step 1：archiveHand 收尾改走 DataPage.post（含本机 record + 服务器 observable）
old = """      if (window.DataPage && window.DataPage.record) window.DataPage.record(rec);   /* 本机牌谱（静态托管无后端也生效） */
      if (!rec.assert.ok && window.UI && window.UI.appendError) {
        window.UI.appendError('⚠ 第 ' + table.handNo + ' 手账目不平（投 ' + put + ' / 派 ' + paid + '），已留档待查');
      }
      if (window.location && window.location.protocol === 'http:') {
        fetch('/api/handlog', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(rec) }).catch(function () { /* 服务器不在线就算了 */ });
      }
    } catch (e) { /* 留档失败不影响牌局 */ }"""
new = """      rec.perspective = 'host';    /* Step 1：留档视角标记 */
      rec.self = true;             /* Step 14：本机自录标记 */
      rec.idleSeats = rec.players.some(function (q) { return !!q.idle; });   /* Step 5：本手含离席/代打座位 */
      if (window.DataPage && window.DataPage.post) {
        window.DataPage.post(rec);   /* 本机牌谱 + 服务器留档（失败排队重发，见 data.js） */
      }
      if (!rec.assert.ok && window.UI && window.UI.appendError) {
        window.UI.appendError('⚠ 第 ' + table.handNo + ' 手账目不平（投 ' + put + ' / 派 ' + paid + '），已留档待查');
      }
    } catch (e) { /* 留档失败不影响牌局 */ }"""
assert s.count(old) == 1, 'S1 main post'
s = s.replace(old, new)

# Step 5：players map 加 idle 标记
old = """        players: table.players.map(function (p) {
          return { name: p.name, charId: p.charId || '', isBot: !!p.isBot,
            stackEnd: p.stack, committed: p.totalCommitted,
            won: p.wonThisHand || 0, refund: p.refundThisHand || 0, rebuys: p.rebuys || 0 };
        }),"""
new = """        players: table.players.map(function (p) {
          return { name: p.name, charId: p.charId || '', isBot: !!p.isBot,
            stackEnd: p.stack, committed: p.totalCommitted,
            won: p.wonThisHand || 0, refund: p.refundThisHand || 0, rebuys: p.rebuys || 0,
            idle: !!(window.MP && window.MP.isIdleSeat && window.MP.isIdleSeat(p.idx)) };   /* Step 5：离席/代打座位 */
        }),"""
assert s.count(old) == 1, 'S5 players idle'
s = s.replace(old, new)

# Step 5：actions 带 auto 标记
old = """        actions: table.actionHistory.map(function (a) {
          return { idx: a.playerIdx, street: a.street, type: a.type, to: a.to, added: a.added };
        }),"""
new = """        actions: table.actionHistory.map(function (a) {
          return { idx: a.playerIdx, street: a.street, type: a.type, to: a.to, added: a.added, auto: !!a.auto };
        }),"""
assert s.count(old) == 1, 'S5 actions auto'
s = s.replace(old, new)

# Step 2：AFK 降钟 + 真实截止钟广播
old = """            /* R2-P0：人类座位也挂 45s 行动计时——房主挂机不再全桌陪葬 */
            var turnMs = (MP && MP.TURN_MS) || 45000;
            UI.setTurnDeadline(Date.now() + turnMs);"""
new = """            /* R2-P0 + Step 2：人类座位 45s 行动计时；挂机（页面隐藏或 30s 无输入）降为 8s 快钟 */
            var afk = (root.document.visibilityState === 'hidden') ||
                      (Date.now() - lastUserInputAt > 30000);
            var turnMs = afk ? 8000 : ((MP && MP.TURN_MS) || 45000);
            table.humanTurnEndsAt = Date.now() + turnMs;   /* Step 2：快照按真实钟广播给客人 */
            UI.setTurnDeadline(Date.now() + turnMs);"""
assert s.count(old) == 1, 'S2 turnMs'
s = s.replace(old, new)

# Step 5：人类超时动作打 auto 标
old = """              var auto = { type: l2.toCall > 0 ? 'fold' : 'check', timedOut: true };"""
new = """              var auto = { type: l2.toCall > 0 ? 'fold' : 'check', timedOut: true, auto: true };"""
assert s.count(old) == 1, 'S5 human auto'
s = s.replace(old, new)

old = """            if (act2.timedOut || act2.type === '__cancel') {   /* 超时代打：统一一行日志 */
              var l3 = table.legalActions(0);
              act2 = { type: l3.toCall > 0 ? 'fold' : 'check',
                       note: '超时（45s），自动' + (l3.toCall > 0 ? '弃牌' : '过牌') };
            }"""
new = """            if (act2.timedOut || act2.type === '__cancel') {   /* 超时代打：统一一行日志 */
              var l3 = table.legalActions(0);
              act2 = { type: l3.toCall > 0 ? 'fold' : 'check', auto: true,
                       note: '超时，自动' + (l3.toCall > 0 ? '弃牌' : '过牌') };
            }"""
assert s.count(old) == 1, 'S5 human rebuild'
s = s.replace(old, new)

# 远端超时同样打标
old = """              if (act.timeout) act.note = '超时代打';"""
new = """              if (act.timeout) { act.note = '超时代打'; act.auto = true; }"""
assert s.count(old) == 1, 'S5 remote auto'
s = s.replace(old, new)

# lastUserInputAt 模块变量 + 监听
old = """  var lastTick = Date.now(), loopRunning = false, lastRecoverWarn = 0, staleStrikes = 0;"""
new = """  var lastTick = Date.now(), loopRunning = false, lastRecoverWarn = 0, staleStrikes = 0;
  var lastUserInputAt = Date.now();   /* Step 2：挂机判定（页面隐藏或 30s 无输入 → AFK） */"""
assert s.count(old) == 1, 'lastUserInputAt var'
s = s.replace(old, new)

old = """  UI.wireTopbar();"""
new = """  /* Step 2：用户活跃度追踪（pointerdown/keydown/wheel 任一即视为活跃） */
  ['pointerdown', 'keydown', 'wheel'].forEach(function (evt) {
    document.addEventListener(evt, function () { lastUserInputAt = Date.now(); }, { passive: true });
  });

  UI.wireTopbar();"""
assert s.count(old) == 1, 'input listeners'
s = s.replace(old, new)

# 每手开局前重发失败队列
old = """    for (;;) {
      heartbeat();"""
new = """    for (;;) {
      heartbeat();
      if (window.DataPage && window.DataPage.flushPosts) window.DataPage.flushPosts();   /* Step 1：重发留档队列 */"""
assert s.count(old) == 1, 'loop flush'
s = s.replace(old, new)

# Step 14：rec.self（与 perspective 同处）
old = """      rec.perspective = 'host';    /* Step 1：留档视角标记 */
      rec.self = true;             /* Step 14：本机自录标记 */"""
assert s.count(old) == 1, 'self already set'
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('main.js patched (Step 1/2/5/14)')
