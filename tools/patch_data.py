# patch_data.py — 数据分析板块接线
# 运行：python tools/patch_data.py （在 game/ 目录）
import io, re

# ============ index.html：启用第三张卡 + 真 modal + data.js ============
p = 'index.html'
s = io.open(p, encoding='utf-8').read()

old = """        <div class="mode-card disabled" id="mc-data" tabindex="0">
          <div class="mc-icon"><svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="#9aa3c7" stroke-width="1.6" stroke-linecap="round"><path d="M4 20V10M10 20V4M16 20v-8M21 20H3"/></svg></div>
          <div class="mc-title">数据分析</div>
          <div class="mc-desc">手牌历史回看 · 牌谱导出<br>胜率曲线 · 对手倾向统计</div>
          <div class="mc-tags"><span>数据</span><span class="soon">制作中</span></div>
        </div>"""
new = """        <div class="mode-card" id="mc-data" tabindex="0">
          <div class="mc-icon"><svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="#9aa3c7" stroke-width="1.6" stroke-linecap="round"><path d="M4 20V10M10 20V4M16 20v-8M21 20H3"/></svg></div>
          <div class="mc-title">数据分析</div>
          <div class="mc-desc">盈亏曲线 · 对手倾向 · 牌谱逐手回看<br>本机记录 · 导出/导入 JSON</div>
          <div class="mc-tags"><span>数据</span><span>本机记录</span></div>
        </div>"""
assert s.count(old) == 1, 'mc-data card'
s = s.replace(old, new)

old = """      <h1><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#ff9ec7" stroke-width="1.8" stroke-linecap="round" style="vertical-align:-3px"><path d="M4 20V10M10 20V4M16 20v-8M21 20H3"/></svg> 数据分析</h1>
      <p class="lead">手牌历史回看、牌谱导出、胜率曲线、对手倾向统计——功能开发中。<br>当前版本的教练面板已提供实时胜率与建议。</p>
      <button id="btn-data-back" class="primary big">返回大厅</button>"""
new = """      <h1><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#ff9ec7" stroke-width="1.8" stroke-linecap="round" style="vertical-align:-3px"><path d="M4 20V10M10 20V4M16 20v-8M21 20H3"/></svg> 数据分析 <span style="font-size:14px;color:var(--muted)">· 本机记录 · 不上传</span></h1>
      <div id="data-body"><p class="lead">正在载入牌谱…</p></div>
      <button id="btn-data-back" class="primary big">返回大厅</button>"""
assert s.count(old) == 1, 'data modal body'
s = s.replace(old, new)

old = '  <script src="js/ui.js?v=20260919b"></script>'
new = '  <script src="js/data.js?v=20260919a"></script>\n  <script src="js/ui.js?v=20260919b"></script>'
assert s.count(old) == 1, 'script insert'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('index.html patched')

# ============ main.js：单机/房主每手写本机牌谱 + mc-data 渲染 ============
p = 'js/main.js'
s = io.open(p, encoding='utf-8').read()

old = """      rec.assert = { sumPaid: paid, sumPut: put, ok: paid === put };"""
new = """      rec.assert = { sumPaid: paid, sumPut: put, ok: paid === put };
      rec.players[0].hole = (table.players[0].hole || []).map(function (c) { return window.Cards.cardStr(c); });   /* 数据板块：留自己的底牌 */
      if (window.DataPage && window.DataPage.record) window.DataPage.record(rec);   /* 本机牌谱（静态托管无后端也生效） */"""
assert s.count(old) == 1, 'archive record hook'
s = s.replace(old, new)

old = """  document.getElementById('mc-data').addEventListener('click', function () {
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('data-modal').classList.remove('hidden');
  });"""
new = """  document.getElementById('mc-data').addEventListener('click', function () {
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('data-modal').classList.remove('hidden');
    if (window.DataPage && window.DataPage.render) window.DataPage.render();
  });"""
assert s.count(old) == 1, 'mc-data handler'
s = s.replace(old, new)

s = re.sub(r'js/main\.js\?v=[0-9a-z]+', 'js/main.js?v=20260919c', s)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('main.js patched')

# ============ mp.js：客人端也逐手留档 ============
p = 'js/mp.js'
s = io.open(p, encoding='utf-8').read()
old = """    /* 弹层延迟 600ms：先让桌面表情气泡露脸，再暗场出结算（R3 反馈：气泡总被遮罩吞掉） */"""
new = """    /* 数据板块：客人也留本手牌谱（自己视角，仅存本机） */
    try {
      var CS = root.Cards;
      var cstr = function (c) { return CS ? CS.cardStr(c) : String(c); };
      root.DataPage.record({
        room: st.roomCode || 'mp', handNo: st.handId, ts: new Date().toISOString(),
        sb: shadow.sb, bb: shadow.bb,
        players: shadow.players.map(function (p) {
          return { name: p.name, charId: p.charId || '', isBot: !!p.isBot,
            stackEnd: p.stack, committed: p.totalCommitted,
            won: p.wonThisHand || 0, refund: p.refundThisHand || 0, rebuys: p.rebuys || 0,
            hole: (p.hole || []).map(cstr) };
        }),
        board: shadow.board.map(cstr),
        actions: (shadow.actionHistory || []).map(function (a) {
          return { idx: a.playerIdx, street: a.street, type: a.type, to: a.to, added: a.added };
        }),
        pots: (mapped.pots || []).map(function (pr) {
          return { amount: pr.amount, winners: pr.winners, label: pr.label || '',
            handName: pr.handName || null, foldWin: !!pr.foldWin, uncalled: !!pr.uncalled, split: !!pr.split };
        })
      });
    } catch (e) { /* 留档失败不影响对局 */ }
    /* 弹层延迟 600ms：先让桌面表情气泡露脸，再暗场出结算（R3 反馈：气泡总被遮罩吞掉） */"""
assert s.count(old) == 1, 'mp guest record'
s = s.replace(old, new)

s = re.sub(r'js/mp\.js\?v=[0-9a-z]+', 'js/mp.js?v=20260919c', s) if 'js/mp.js?v=' in s else s
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('mp.js patched')

# ============ css：数据页样式 ============
p = 'css/style.css'
s = io.open(p, encoding='utf-8').read()
s += """
/* ==================== 数据分析板块 ==================== */
#data-body h4 { color: var(--gold); font-size: 14px; margin: 16px 0 8px; }
.data-cards { display: flex; gap: 12px; flex-wrap: wrap; margin: 10px 0 4px; }
.data-stat { flex: 1; min-width: 118px; background: rgba(0,0,0,.25); border: 1px solid var(--line, #4a3a55); border-radius: 12px; padding: 10px 14px; text-align: center; }
.data-stat i { display: block; font-style: normal; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
.data-stat b { font-size: 20px; }
.data-stat b.pos { color: #7ee2a8; }
.data-stat b.neg { color: #ff9d9d; }
.data-chart { width: 100%; height: auto; background: rgba(0,0,0,.25); border-radius: 10px; }
.chart-line { fill: none; stroke: var(--gold, #e8b96a); stroke-width: 2.5; stroke-linejoin: round; }
.chart-zero { stroke: var(--line, #4a3a55); stroke-dasharray: 4 4; }
.chart-max, .chart-min { fill: var(--muted, #9a8aa8); font-size: 11px; }
.chart-last { fill: var(--gold, #e8b96a); font-size: 11px; }
.data-table { display: flex; flex-direction: column; gap: 4px; }
.data-row { display: flex; gap: 14px; font-size: 13px; padding: 5px 10px; background: rgba(0,0,0,.2); border-radius: 8px; flex-wrap: wrap; }
.data-row span { min-width: 70px; }
.data-row .data-opp { min-width: 110px; font-weight: bold; }
.data-row .pos { color: #7ee2a8; }
.data-row .neg { color: #ff9d9d; }
details.data-hand { border: 1px solid var(--line, #4a3a55); border-radius: 10px; padding: 8px 12px; margin: 6px 0; }
details.data-hand summary { cursor: pointer; font-size: 13px; }
details.data-hand summary b.pos { color: #7ee2a8; }
details.data-hand summary b.neg { color: #ff9d9d; }
details.data-hand[open] { background: rgba(0,0,0,.2); }
.data-acts { font-size: 12px; line-height: 1.8; margin-top: 4px; word-break: break-all; }
.data-import-label { display: inline-flex; align-items: center; cursor: pointer; position: relative; }
"""
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('css patched')
