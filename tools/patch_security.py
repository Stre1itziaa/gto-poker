# patch_security.py — 安全加固：S1-S5 + R1/R2（健康报告 P0/P1 全项）
# 运行：python tools/patch_security.py （在 game/ 目录）
import io

# ============ S1：charId 白名单（mp.js 入口） + portraits.js 渲染层消毒 ============
p = 'js/mp.js'
s = io.open(p, encoding='utf-8').read()
old = """        var cid = meta && meta.charId;
        if (!cid || charTaken(cid)) cid = firstFreeChar();"""
new = """        /* S1：charId 必须在内置角色白名单内，否则回退分配（堵属性注入 XSS） */
        var cid = meta && meta.charId;
        var cidOk = false;
        for (var ci = 0; ci < CHARS.length; ci++) if (CHARS[ci].id === cid) { cidOk = true; break; }
        if (!cidOk || charTaken(cid)) cid = firstFreeChar();"""
assert s.count(old) == 1, 'S1 mp charId'
s = s.replace(old, new)

# S3+R1：hostOnData 动作白名单 + hand 序号校验
old = """    if (d.t === 'act') {
      var seat = seatByPeer(pid);
      if (hostPending && hostPending.seat === seat) {
        var table = hostPending.table;
        var la = table.legalActions(seat);
        var act = { type: d.type, to: d.to };
        if (act.type === 'raise' && (typeof act.to !== 'number' || !isFinite(act.to))) act.to = la.minTo;
        if (act.type === 'check' && la.toCall > 0) {
          act = { type: la.toCall >= table.players[seat].stack ? 'call' : 'fold' };
        }
        hostPending.resolve(act);
      } else {
        /* 竞态缓冲：快照广播先于 nextRemoteAction 挂起，客人秒点会先到——暂存待消费 */
        earlyActs[pid] = d;
        try { console.info('[mp] act buffered for seat', seat); } catch (e) { /* noop */ }
      }
    } else if (d.t === 'ready' && st.phase === 'lobby') {"""
new = """    if (d.t === 'act') {
      var seat = seatByPeer(pid);
      /* S3：动作类型白名单在 normalizeAct 内统一执行；
       * R1：动作必须携带当前手号（d.hand），旧手/未来手的动作一律丢弃 */
      if (hostPending && hostPending.seat === seat && d.hand === hostPending.table.handNo) {
        hostPending.resolve(normalizeAct(hostPending.table, seat, d));
      } else if (typeof d.hand === 'number' && st.hostHandNo === d.hand) {
        /* 竞态缓冲：快照广播先于 nextRemoteAction 挂起，客人秒点会先到——暂存待消费 */
        earlyActs[pid] = d;
        try { console.info('[mp] act buffered for seat', seat); } catch (e) { /* noop */ }
      }
      /* 其余（旧手迟到/非法序号）直接丢弃 */
    } else if (d.t === 'ready' && st.phase === 'lobby') {"""
assert s.count(old) == 1, 'S3/R1 hostOnData'
s = s.replace(old, new)

old = """  function normalizeAct(table, seat, d) {
    var la = table.legalActions(seat);
    var act = { type: d.type, to: d.to };
    if (act.type === 'raise' && (typeof act.to !== 'number' || !isFinite(act.to))) act.to = la.minTo;
    if (act.type === 'check' && la.toCall > 0) {
      act = { type: la.toCall >= table.players[seat].stack ? 'call' : 'fold' };
    }
    return act;
  }"""
new = """  function normalizeAct(table, seat, d) {
    var la = table.legalActions(seat);
    var act = { type: d.type, to: d.to };
    if (act.type === 'raise' && (typeof act.to !== 'number' || !isFinite(act.to))) act.to = la.minTo;
    if (act.type === 'check' && la.toCall > 0) {
      act = { type: la.toCall >= table.players[seat].stack ? 'call' : 'fold' };
    }
    /* S3：动作类型白名单——非法类型按「能过则过、不能过则弃」降级，绝不进引擎 */
    if (act.type !== 'fold' && act.type !== 'check' && act.type !== 'call' && act.type !== 'raise') {
      act = { type: la.toCall > 0 ? 'fold' : 'check' };
    }
    return act;
  }"""
assert s.count(old) == 1, 'S3 normalizeAct'
s = s.replace(old, new)

# R1：nextRemoteAction 消费缓冲时校验手号
old = """      var pid = seatPeer[seat];
      if (pid && earlyActs[pid]) {
        var buf = earlyActs[pid];
        delete earlyActs[pid];
        resolve(normalizeAct(table, seat, buf));
        return;
      }"""
new = """      var pid = seatPeer[seat];
      if (pid && earlyActs[pid]) {
        var buf = earlyActs[pid];
        delete earlyActs[pid];
        if (buf.hand === table.handNo) { resolve(normalizeAct(table, seat, buf)); return; }
        /* 手号不匹配 = 旧手迟到动作，丢弃后继续走正常等待 */
      }"""
assert s.count(old) == 1, 'R1 consume'
s = s.replace(old, new)

# R1：客人发送动作携带手号
old = """      if (act.type === '__cancel') return;   // 被回收（超时/新手）——不发动作
      Net.sendTo('host', { t: 'act', type: act.type, to: act.to });"""
new = """      if (act.type === '__cancel') return;   // 被回收（超时/新手）——不发动作
      Net.sendTo('host', { t: 'act', hand: st.handId, type: act.type, to: act.to });   /* R1：带手号防串手 */"""
assert s.count(old) == 1, 'R1 guest send'
s = s.replace(old, new)

# R4：导出 normalizeAct 供无头测试
old = "    __test: { snapFor: snapFor, buildShadow: buildShadow, rotIdx: rotIdx, _st: st }"
new = "    __test: { snapFor: snapFor, buildShadow: buildShadow, rotIdx: rotIdx, normalizeAct: normalizeAct, _st: st }"
assert s.count(old) == 1, 'R4 export'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('mp.js patched (S1/S3/R1/R4)')

# ============ S1 深防：portraits.js 渲染层对 id 消毒 ============
p = 'js/portraits.js'
s = io.open(p, encoding='utf-8').read()
old = """  function portraitHTML(id, expr, px, mode) {
    var c = byId(id);"""
new = """  function portraitHTML(id, expr, px, mode) {
    /* S1 深防：id 只允许安全字符进 HTML 拼接（入口已白名单，这里是最后防线） */
    id = String(id == null ? '' : id).replace(/[^A-Za-z0-9_-]/g, '');
    var c = byId(id);"""
assert s.count(old) == 1, 'S1 portraits sanitize'
s = s.replace(old, new)

# R2：assign 内裸 localStorage 包裹
old = """  function assign(table, playerId) {
    var selId = localStorage.getItem('gto-char') || CHARS[0].id;"""
new = """  function assign(table, playerId) {
    var selId = CHARS[0].id;
    try { selId = localStorage.getItem('gto-char') || selId; } catch (e) { /* 隐私模式 */ }"""
assert s.count(old) == 1, 'R2 portraits assign'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('portraits.js patched (S1 deep/R2)')

# ============ S2：main.js 会话存档解析保护 ============
p = 'js/main.js'
s = io.open(p, encoding='utf-8').read()
old = """  var SESS = Object.assign({ hands: 0, bb: 0.0, vpip: 0, pfr: 0, rebuys: 0 },
    JSON.parse(localStorage.getItem('gto-sess') || '{}'));"""
new = """  var SESS = { hands: 0, bb: 0.0, vpip: 0, pfr: 0, rebuys: 0 };
  try {
    var savedSess = JSON.parse(localStorage.getItem('gto-sess') || '{}');
    if (savedSess && typeof savedSess === 'object') Object.assign(SESS, savedSess);
  } catch (e) {
    try { localStorage.removeItem('gto-sess'); } catch (e2) { /* noop */ }   /* S2：坏档自清，防启动瘫痪 */
  }"""
assert s.count(old) == 1, 'S2 SESS'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('main.js patched (S2)')

# ============ R2：ui.js 四处裸 localStorage 包裹 ============
p = 'js/ui.js'
s = io.open(p, encoding='utf-8').read()
old = "    var savedAuto = localStorage.getItem('gto-auto') === 'on';"
new = "    var savedAuto = false;\n    try { savedAuto = localStorage.getItem('gto-auto') === 'on'; } catch (e) { /* 隐私模式 */ }"
assert s.count(old) == 1, 'R2 savedAuto'
s = s.replace(old, new)

old = """        localStorage.setItem('gto-auto', v ? 'on' : 'off');"""
new = """        try { localStorage.setItem('gto-auto', v ? 'on' : 'off'); } catch (e) { /* 隐私模式 */ }"""
assert s.count(old) == 1, 'R2 setAuto'
s = s.replace(old, new)

old = """          localStorage.setItem('gto-char', sel);"""
new = """          try { localStorage.setItem('gto-char', sel); } catch (e) { /* 隐私模式 */ }"""
assert s.count(old) == 1, 'R2 setChar'
s = s.replace(old, new)

old = "    var sel = localStorage.getItem('gto-char') || chars().ALL[0].id;"
new = "    var sel = chars().ALL[0].id;\n    try { sel = localStorage.getItem('gto-char') || sel; } catch (e) { /* 隐私模式 */ }"
assert s.count(old) == 1, 'R2 getChar'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('ui.js patched (R2)')

# ============ S4：serve.js handlog 房间文件数上限 ============
p = 'serve.js'
s = io.open(p, encoding='utf-8').read()
old = """        var dir = path.join(root, 'test', 'hand-logs', room);
        fs.mkdirSync(dir, { recursive: true });
        var name = 'hand_' + String(rec.handNo || 0).padStart(4, '0') + '_' + Date.now() + '.json';"""
new = """        var dir = path.join(root, 'test', 'hand-logs', room);
        var existing = fs.existsSync(dir) ? fs.readdirSync(dir).length : 0;
        if (existing > 500) {   /* S4：单房留档上限，防磁盘被灌 */
          res.writeHead(429); res.end('{"ok":false,"reason":"room log full"}'); return;
        }
        fs.mkdirSync(dir, { recursive: true });
        var name = 'hand_' + String(rec.handNo || 0).padStart(4, '0') + '_' + Date.now() + '.json';"""
assert s.count(old) == 1, 'S4 handlog cap'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('serve.js patched (S4)')
