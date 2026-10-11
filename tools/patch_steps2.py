# patch_steps2.py — 施工单 Step 2/5/6/11/13 第二部分：mp.js + ui.js + engine + serve + index + mp_guest
# 运行：python tools/patch_steps2.py （在 game/ 目录）
import io, re

# ============ mp.js ============
p = 'js/mp.js'
s = io.open(p, encoding='utf-8').read()

# Step 2：snapFor 按真实钟广播 turnEndsAt
old = """      turnEndsAt: actorAbs >= 0 ? (Date.now() + TURN_MS) : 0,"""
new = """      turnEndsAt: (function () {
        /* Step 2：按行动者真实钟广播——远端真人 45s / 房主真人（AFK 已降 8s）/ 机器人 ~1s 思考窗 */
        if (actorAbs < 0) return 0;
        if (seatPeer[actorAbs]) return Date.now() + TURN_MS;
        if (actorAbs === 0 && table.humanTurnEndsAt) return table.humanTurnEndsAt;
        return Date.now() + 1100;
      })(),"""
assert s.count(old) == 1, 'S2 snapFor clock'
s = s.replace(old, new)

# Step 5：snapFor 玩家带 idle 标记 + 动作带 auto
old = """        lastAction: p.lastAction || '', wonThisHand: p.wonThisHand || 0,
        refundThisHand: p.refundThisHand || 0,
        score: showHole ? (p.score || 0) : 0
      });"""
new = """        lastAction: p.lastAction || '', wonThisHand: p.wonThisHand || 0,
        refundThisHand: p.refundThisHand || 0,
        idle: !!deadSeats[abs],      /* Step 5：离席/代打座位标记 */
        score: showHole ? (p.score || 0) : 0
      });"""
assert s.count(old) == 1, 'S5 snapFor idle'
s = s.replace(old, new)

old = """      actionHistory: table.actionHistory.map(function (a) {
        return { playerIdx: rotIdx(a.playerIdx, youAbs, n), street: a.street,
          type: a.type, to: a.to, added: a.added, frac: a.frac };
      }),"""
new = """      actionHistory: table.actionHistory.map(function (a) {
        return { playerIdx: rotIdx(a.playerIdx, youAbs, n), street: a.street,
          type: a.type, to: a.to, added: a.added, frac: a.frac, auto: !!a.auto };
      }),"""
assert s.count(old) == 1, 'S5 snapFor auto'
s = s.replace(old, new)

# Step 5：applySnap 把 idle 拷进影子座位
old = """      p.streetCommitted = rp.streetCommitted; p.totalCommitted = rp.totalCommitted;
      p.lastAction = rp.lastAction; p.wonThisHand = rp.wonThisHand || 0;
      p.refundThisHand = rp.refundThisHand || 0;
      p.score = rp.score || 0;"""
new = """      p.streetCommitted = rp.streetCommitted; p.totalCommitted = rp.totalCommitted;
      p.lastAction = rp.lastAction; p.wonThisHand = rp.wonThisHand || 0;
      p.refundThisHand = rp.refundThisHand || 0;
      p.idle = !!rp.idle;   /* Step 5：离席座位标记透传给客人端 */
      p.score = rp.score || 0;"""
assert s.count(old) == 1, 'S5 applySnap idle'
s = s.replace(old, new)

# Step 5：客人超时 → 本手 selfAuto 标记；新手重置
old = """      case 'timedout':
        toast('⏱ 你超时了，本回合已自动代打');
        if (st.deciding) {
          st.deciding = false;
          if (root.UI && root.UI.cancelDecision) root.UI.cancelDecision();
        }
        break;"""
new = """      case 'timedout':
        toast('⏱ 你超时了，本回合已自动代打');
        st.autoThisHand = true;   /* Step 5：本手含代打，留档打标 */
        if (st.deciding) {
          st.deciding = false;
          if (root.UI && root.UI.cancelDecision) root.UI.cancelDecision();
        }
        break;"""
assert s.count(old) == 1, 'S5 timedout flag'
s = s.replace(old, new)

old = """      /* 盲注前的起始筹码 = 快照筹码 + 本街已投入（盲注额） */
      st.handStartStack = d.players[0].stack + d.players[0].streetCommitted;
      st.vpipDone = false;
      st.pfrDone = false;"""
new = """      /* 盲注前的起始筹码 = 快照筹码 + 本街已投入（盲注额） */
      st.handStartStack = d.players[0].stack + d.players[0].streetCommitted;
      st.vpipDone = false;
      st.pfrDone = false;
      st.autoThisHand = false;   /* Step 5：新一手重置代打标记 */"""
assert s.count(old) == 1, 'S5 reset'
s = s.replace(old, new)

# Step 5/14：客人记录补 idle/selfAuto/self/perspective/aid + 改走 post
old = """      rec.hero = String(rec.players[0].name || '').replace(/（你）/g, '');
      rec.players[0].name = rec.hero;
      rec.mode = 'mp';
      if (!rec.assert.ok && root.UI && root.UI.appendError) {
        root.UI.appendError('⚠ 第 ' + st.handId + ' 手账目不平（投 ' + putG + ' / 派 ' + paidG + '），已留档待查');
      }
      root.DataPage.record(rec);"""
new = """      rec.hero = String(rec.players[0].name || '').replace(/（你）/g, '');
      rec.players[0].name = rec.hero;
      rec.mode = 'mp';
      rec.perspective = 'guest';   /* Step 1：留档视角标记 */
      rec.self = true;             /* Step 14：本机自录标记 */
      rec.idleSeats = rec.players.some(function (q) { return !!q.idle; });   /* Step 5 */
      rec.heroAuto = !!st.autoThisHand;   /* Step 5：本手自己被代打过 */
      if (!rec.assert.ok && root.UI && root.UI.appendError) {
        root.UI.appendError('⚠ 第 ' + st.handId + ' 手账目不平（投 ' + putG + ' / 派 ' + paidG + '），已留档待查');
      }
      if (root.DataPage && root.DataPage.post) root.DataPage.post(rec);   /* Step 1：本机 + observable POST */
      else root.DataPage.record(rec);"""
assert s.count(old) == 1, 'S1/S5 guest record'
s = s.replace(old, new)

# 客人记录里 players 补 idle（shadow 已带）
old = """        players: shadow.players.map(function (p) {
          return { name: p.name, charId: p.charId || '', isBot: !!p.isBot,
            stackEnd: p.stack, committed: p.totalCommitted,
            won: p.wonThisHand || 0, refund: p.refundThisHand || 0, rebuys: p.rebuys || 0,
            hole: (p.hole || []).map(cstr) };
        }),"""
new = """        players: shadow.players.map(function (p) {
          return { name: p.name, charId: p.charId || '', isBot: !!p.isBot,
            stackEnd: p.stack, committed: p.totalCommitted,
            won: p.wonThisHand || 0, refund: p.refundThisHand || 0, rebuys: p.rebuys || 0,
            idle: !!p.idle, hole: (p.hole || []).map(cstr) };
        }),"""
assert s.count(old) == 1, 'S5 guest players idle'
s = s.replace(old, new)

# Step 5：超时代打的动作在 actionHistory 打 auto（引擎层）
old = """              if (act.timeout) { act.note = '超时代打'; act.auto = true; }"""
marker = "if (act.timeout) { act.note = '超时代打'; act.auto = true; }"
if marker not in s:
    # 该行在 main.js，不在 mp.js——mp 端动作来自房主快照（auto 已随快照带），无需处理
    pass
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('mp.js patched (Step 2/5/14 + requestnext 复用既有 next 协议)')

# ============ engine.js：actionHistory 透传 auto 标记 ============
p = 'js/engine.js'
s = io.open(p, encoding='utf-8').read()
old = """    this.actionHistory.push({
      playerIdx: p.idx, street: this.street, type: type,
      to: p.streetCommitted, added: added,
      frac: added / Math.max(1, potBefore + (type === 'raise' ? la.toCall : 0))
    });"""
new = """    this.actionHistory.push({
      playerIdx: p.idx, street: this.street, type: type,
      to: p.streetCommitted, added: added,
      frac: added / Math.max(1, potBefore + (type === 'raise' ? la.toCall : 0)),
      auto: !!action.auto   /* Step 5：代打/超时动作打标，供留档与统计 */
    });"""
assert s.count(old) == 1, 'engine auto'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('engine.js patched')

# ============ ui.js：Step 4 分档停留 + Step 6 客人自动续局真请求 + Step 11 aria ============
p = 'js/ui.js'
s = io.open(p, encoding='utf-8').read()

old = """  function scheduleNextHand() {
    if (nextHandTimer) { clearTimeout(nextHandTimer); nextHandTimer = null; }
    var auto = $('auto-next').checked || $('auto-next-2').checked;
    if (auto) nextHandTimer = setTimeout(function () { finishWaitNextHand(); }, 5000);   /* R6-R4：2.2s 太快，结算读不完 */
  }"""
new = """  function scheduleNextHand(ms) {
    if (nextHandTimer) { clearTimeout(nextHandTimer); nextHandTimer = null; }
    var auto = $('auto-next').checked || $('auto-next-2').checked;
    if (!auto) return;
    var stay = Math.max(3000, ms || 5000);
    /* Step 6：多人客人自动续局 = 幂等真请求（立即 + 兜底重发），不再 resolve 无人消费的本地 promise */
    if (root.MP && root.MP.isGuest && root.MP.isGuest() && root.MP.requestNext) {
      root.MP.requestNext();
      nextHandTimer = setTimeout(function () { root.MP.requestNext(); }, Math.max(4000, stay - 500));
      return;
    }
    nextHandTimer = setTimeout(function () { finishWaitNextHand(); }, stay);
  }"""
assert s.count(old) == 1, 'S6 scheduleNextHand'
s = s.replace(old, new)

# Step 4：全下摊牌档 8s（showShowdown 调用处传参）
old_show_call = s
m = list(__import__('re').finditer(r'scheduleNextHand\(\);', s))
assert len(m) >= 1, 'scheduleNextHand calls'
s = s.replace("""    body.innerHTML = html;
    rollNumbers();            /* 批1-T1.6：金额从 0 滚动到实际值 */
    $('overlay').classList.remove('hidden');
    scheduleNextHand();
  }""", """    body.innerHTML = html;
    rollNumbers();            /* 金额终值直出（本函数已无逐帧滚动） */
    $('overlay').classList.remove('hidden');
    /* Step 4：停留从内容就绪起算；全下摊牌档给 8s，常规 5s */
    var allInShowdown = table.players.some(function (p) { return p.allIn; }) &&
      res.pots.some(function (pr) { return !pr.foldWin && !pr.uncalled; });
    scheduleNextHand(allInShowdown ? 8000 : 5000);
  }""")
assert s.count('scheduleNextHand(allInShowdown ? 8000 : 5000);') == 1, 'S4 showShowdown call'

# Step 11：卡牌角标对读屏隐藏（textContent 双写问题）
old = """    return '<div class="card ' + col + (small ? ' small' : '') + ' d' + d + '" data-card="' + Cards.cardStr(c) + '">' +
      '<div class="cc tl"><span class="ccr">' + r + '</span><span class="ccs">' + sym + '</span></div>' +
      '<div class="cpip" aria-hidden="true">' + sym + '</div>' +
      '<div class="cc br"><span class="ccr">' + r + '</span><span class="ccs">' + sym + '</span></div>' +
      '</div>';"""
new = """    return '<div class="card ' + col + (small ? ' small' : '') + ' d' + d + '" data-card="' + Cards.cardStr(c) + '">' +
      '<div class="cc tl"><span class="ccr">' + r + '</span><span class="ccs">' + sym + '</span></div>' +
      '<div class="cpip" aria-hidden="true">' + sym + '</div>' +
      '<div class="cc br" aria-hidden="true"><span class="ccr">' + r + '</span><span class="ccs">' + sym + '</span></div>' +
      '</div>';"""
assert s.count(old) == 1, 'S11 card aria'
s = s.replace(old, new)

# 导出 UI.requestNextHand（mp.js hostOnData 的 'next' 协议复用房主续局路径）
old = """    cancelDecision: cancelDecision, setTurnDeadline: setTurnDeadline
  };"""
new = """    cancelDecision: cancelDecision, setTurnDeadline: setTurnDeadline,
    requestNextHand: finishWaitNextHand   /* Step 6：房主代点「下一局」（客人请求协议复用） */
  };"""
assert s.count(old) == 1, 'UI export'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('ui.js patched (Step 4/6/11)')

# ============ serve.js：Step 1 GET 审计端点 ============
p = 'serve.js'
s = io.open(p, encoding='utf-8').read()
old = """  /* R5-施工 P1-3：手牌留档——房主每手 POST 一份 JSON，按房间落盘 test/hand-logs/<房码>/ */
  if (req.method === 'POST' && urlPath === '/api/handlog') {"""
new = """  /* Step 1：留档审计端点——GET /api/handlog?room=XXX 返回该房全部留档 */
  if (req.method === 'GET' && urlPath === '/api/handlog') {
    var qs2 = req.url.split('?')[1] || '';
    var qRoom = '';
    qs2.split('&').forEach(function (kv) {
      var p2 = kv.split('=');
      if (p2[0] === 'room') { try { qRoom = decodeURIComponent(p2[1] || ''); } catch (e) { qRoom = ''; } }
    });
    qRoom = qRoom.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 16) || 'local';
    var qdir = path.join(root, 'test', 'hand-logs', qRoom);
    var hands = [];
    try {
      fs.readdirSync(qdir).sort().forEach(function (name) {
        try { hands.push(JSON.parse(fs.readFileSync(path.join(qdir, name), 'utf8'))); } catch (e) { /* 坏档跳过 */ }
      });
    } catch (e) { /* 目录不存在 → 空列表 */ }
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-cache' });
    res.end(JSON.stringify({ room: qRoom, count: hands.length, hands: hands }));
    return;
  }
  /* R5-施工 P1-3：手牌留档——房主每手 POST 一份 JSON，按房间落盘 test/hand-logs/<房码>/ */
  if (req.method === 'POST' && urlPath === '/api/handlog') {"""
assert s.count(old) == 1, 'S1 serve GET'
s = s.replace(old, new)

# Step 1：服务器按 aid 落盘（重发天然去重）
old = """        fs.mkdirSync(dir, { recursive: true });
        var name = 'hand_' + String(rec.handNo || 0).padStart(4, '0') + '_' + Date.now() + '.json';"""
new = """        fs.mkdirSync(dir, { recursive: true });
        var aid = String(rec.aid || Date.now()).replace(/[^A-Za-z0-9_-]/g, '').slice(0, 48) || String(Date.now());
        var name = 'hand_' + String(rec.handNo || 0).padStart(4, '0') + '_' + aid + '.json';   /* 重发按 aid 覆盖，不产生重复 */"""
assert s.count(old) == 1, 'S1 serve aid filename'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('serve.js patched (Step 1 GET + aid 去重)')

# ============ index.html：Step 6 tooltip + 版本 ============
p = 'index.html'
s = io.open(p, encoding='utf-8').read()
old = """      <label class="toggle"><input type="checkbox" id="auto-next"> 自动下一局</label>"""
new = """      <label class="toggle" title="多人局：自动向房主请求下一局"><input type="checkbox" id="auto-next"> 自动下一局</label>"""
assert s.count(old) == 1, 'auto-next tooltip'
s = s.replace(old, new)
old = """      <label class="toggle inline"><input type="checkbox" id="auto-next-2"> 自动继续</label>"""
new = """      <label class="toggle inline" title="多人局：自动向房主请求下一局"><input type="checkbox" id="auto-next-2"> 自动继续</label>"""
assert s.count(old) == 1, 'auto-next-2 tooltip'
s = s.replace(old, new)
for f in ['ui', 'mp', 'main', 'data']:
    s = re.sub(r'js/' + f + r'\.js\?v=[0-9a-z]+', 'js/' + f + '.js?v=20260919e', s)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('index.html patched')

# ============ css：Step 7 focus-visible + 底缘渐隐 ============
p = 'css/style.css'
s = io.open(p, encoding='utf-8').read()
s += """
/* ==================== Step 7/9 数据页发现性 ==================== */
.data-mode-chip:focus-visible, .emote-chip:focus-visible, .mp-tab:focus-visible,
.ghost:focus-visible, .primary:focus-visible, button:focus-visible {
  outline: 2px solid var(--gold, #e8b96a); outline-offset: 2px;
}
#data-body {
  -webkit-mask-image: linear-gradient(180deg, #000 calc(100% - 26px), transparent 100%);
  mask-image: linear-gradient(180deg, #000 calc(100% - 26px), transparent 100%);
}
.data-row.data-head { color: var(--gold); font-weight: bold; background: rgba(0,0,0,.35); font-size: 12px; }
.chart-tick { fill: var(--muted, #9a8aa8); font-size: 10px; }
"""
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('css patched')
