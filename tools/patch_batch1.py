# patch_batch1.py — 批 1 快赢周：表情快捷键/气泡合并/轮盘 + 数字动效三件套 + 读秒环 + 庄位扣
# 运行：python tools/patch_batch1.py （在 game/ 目录）
import io, re

# ============ ui.js ============
p = 'js/ui.js'
s = io.open(p, encoding='utf-8').read()

# T1.4 表情缩到 4 固定短语（GG/讨回来 归入 G-08 扩盘）
old = "  var EMOTE_CHIPS = ['你好♪', '打得漂亮！', '呜…', '就这？', 'GG', '下一手讨回来'];"
new = "  var EMOTE_CHIPS = ['你好♪', '打得漂亮！', '呜…', '就这？'];   // 批1-T1.4：轮盘首发 4 固定短语"
assert s.count(old) == 1, 'EMOTE_CHIPS'
s = s.replace(old, new)

# 抽出发送函数 + chip 带数字角标
old = """    EMOTE_CHIPS.forEach(function (txt) {
      var b = root.document.createElement('button');
      b.className = 'emote-chip';
      b.textContent = txt;
      b.addEventListener('click', function () {
        var now = Date.now();
        if (now - emoteLastAt < 4000) return;    // 4s 防刷屏
        emoteLastAt = now;
        if (root.MP && root.MP.sendEmote) root.MP.sendEmote(txt);
        else showEmote(0, txt);                  // 单机：本地直接显示
        strip.classList.remove('open');          // 选完即收（窄屏浮标模式）
      });
      strip.appendChild(b);
    });"""
new = """    EMOTE_CHIPS.forEach(function (txt, i) {
      var b = root.document.createElement('button');
      b.className = 'emote-chip';
      b.innerHTML = txt + '<span class="khint">' + (i + 1) + '</span>';   // T1.2：数字角标=快捷键
      b.addEventListener('click', function () {
        sendQuickEmote(txt);
        strip.classList.remove('open');          // 选完即收（窄屏浮标模式）
      });
      strip.appendChild(b);
    });"""
assert s.count(old) == 1, 'chip loop'
s = s.replace(old, new)

# sendQuickEmote 函数（键盘与 chip 共用）
old = """  /* 遮挡审计 P0-1 附属：操作栏换行时实高变化，浮标 bottom 跟随（CSS 变量驱动） */"""
new = """  /* T1.2：表情发送统一入口（4s 防刷屏）；键盘数字键与 chip 共用 */
  function sendQuickEmote(txt) {
    var now = Date.now();
    if (now - emoteLastAt < 4000) return;
    emoteLastAt = now;
    if (root.MP && root.MP.sendEmote) root.MP.sendEmote(txt);
    else showEmote(0, txt);                  // 单机：本地直接显示
  }

  /* 遮挡审计 P0-1 附属：操作栏换行时实高变化，浮标 bottom 跟随（CSS 变量驱动） */"""
assert s.count(old) == 1, 'sendQuickEmote anchor'
s = s.replace(old, new)

# T1.3 气泡堆叠合并：最多 3 个可见，多的挤掉最旧
old = """  /* 表情气泡（雀魂式 emote） */
  function showEmote(idx, text) {
    var el = seatEls[idx] && seatEls[idx].querySelector('.emote');
    if (!el) return;
    el.textContent = text;
    el.classList.add('show');
    if (emoteTimers[idx]) clearTimeout(emoteTimers[idx]);
    emoteTimers[idx] = setTimeout(function () { el.classList.remove('show'); }, 4500);
  }"""
new = """  /* 表情气泡（雀魂式 emote）；批1-T1.3：同屏最多 3 个可见，多的挤掉最旧 */
  var emoteOrder = [];
  function showEmote(idx, text) {
    var el = seatEls[idx] && seatEls[idx].querySelector('.emote');
    if (!el) return;
    var at = emoteOrder.indexOf(idx);
    if (at >= 0) emoteOrder.splice(at, 1);
    while (emoteOrder.length >= 3) {
      var oldIdx = emoteOrder.shift();
      var oldEl = seatEls[oldIdx] && seatEls[oldIdx].querySelector('.emote');
      if (oldEl) oldEl.classList.remove('show');
      if (emoteTimers[oldIdx]) { clearTimeout(emoteTimers[oldIdx]); emoteTimers[oldIdx] = null; }
    }
    emoteOrder.push(idx);
    el.textContent = text;
    el.classList.add('show');
    if (emoteTimers[idx]) clearTimeout(emoteTimers[idx]);
    emoteTimers[idx] = setTimeout(function () {
      el.classList.remove('show');
      var at2 = emoteOrder.indexOf(idx);
      if (at2 >= 0) emoteOrder.splice(at2, 1);
    }, 4500);
  }"""
assert s.count(old) == 1, 'showEmote'
s = s.replace(old, new)

# 动效缓存变量
old = """  var decisionSeq = 0, lastSuggestSeq = -1, lastSuggest = {};
  var boardShownKey = '', boardShownLen = 0;   // 公共牌入场动效追踪"""
new = """  var decisionSeq = 0, lastSuggestSeq = -1, lastSuggest = {};
  var boardShownKey = '', boardShownLen = 0;   // 公共牌入场动效追踪
  var lastPotVal = null, actionCache = {}, actionHandNo = 0;   // 批1：底池脉冲/下注弹入追踪"""
assert s.count(old) == 1, 'cache vars'
s = s.replace(old, new)

# T1.5 底池脉冲 + T1.9 庄位扣 + T1.7 下注弹入
old = """    $('pot').innerHTML = '<span class="pchip"></span>底池 ' + table.potTotal() + '（' + (Math.round(table.potTotal() * 10 / table.bb) / 10) + 'bb）';"""
new = """    /* 批1-T1.5：底池数值变化时脉冲一下 */
    var potNow = table.potTotal();
    var potInner = '<span id="pot-inner"><span class="pchip"></span>底池 ' + potNow + '（' + (Math.round(potNow * 10 / table.bb) / 10) + 'bb）</span>';
    $('pot').innerHTML = potInner;
    if (potNow !== lastPotVal) {
      if (lastPotVal !== null && potNow > 0) {
        var pi = root.document.getElementById('pot-inner');
        if (pi) { pi.classList.remove('pot-pulse'); void pi.offsetWidth; pi.classList.add('pot-pulse'); }
      }
      lastPotVal = potNow;
    }"""
assert s.count(old) == 1, 'pot line'
s = s.replace(old, new)

old = """      s.querySelector('.pos').textContent = posZh;
      s.querySelector('.pos').classList.toggle('pos-blind', posRaw === 'SB' || posRaw === 'BB');"""
new = """      var posEl = s.querySelector('.pos');
      posEl.textContent = posZh;
      posEl.classList.toggle('pos-blind', posRaw === 'SB' || posRaw === 'BB');
      posEl.classList.toggle('pos-dealer', posRaw === 'BTN');   /* 批1-T1.9：庄位实体扣 */"""
assert s.count(old) == 1, 'pos line'
s = s.replace(old, new)

old = """      var actEl = s.querySelector('.action');
      if (i === thinkingIdx) actEl.innerHTML = '<span class="thinking">思考中…</span>';
      else {
        var extra = '';
        if (winners[i] && p.wonThisHand > 0) extra = ' <span class="win-amt">+' + p.wonThisHand + '</span>';
        actEl.innerHTML = (p.lastAction ? '<span class="bold">' + p.lastAction + '</span>' : '') + extra;
      }"""
new = """      var actEl = s.querySelector('.action');
      if (i === thinkingIdx) actEl.innerHTML = '<span class="thinking">思考中…</span>';
      else {
        var extra = '';
        if (winners[i] && p.wonThisHand > 0) extra = ' <span class="win-amt">+' + p.wonThisHand + '</span>';
        var actChanged = actionCache[i] !== p.lastAction;
        actEl.innerHTML = (p.lastAction ? '<span class="bold">' + p.lastAction + '</span>' : '') + extra;
        if (actChanged && p.lastAction) {
          actEl.classList.remove('act-pop'); void actEl.offsetWidth; actEl.classList.add('act-pop');   /* 批1-T1.7：下注弹入 */
        }
        actionCache[i] = p.lastAction;
      }"""
assert s.count(old) == 1, 'action line'
s = s.replace(old, new)

# render 开头按手号清空动作缓存
old = """  function render() {
    if (!table) return;
    var bkey = table.board.map(function (c) { return Cards.cardStr(c); }).join(',');"""
new = """  function render() {
    if (!table) return;
    if (table.handNo !== actionHandNo) { actionHandNo = table.handNo; actionCache = {}; }
    var bkey = table.board.map(function (c) { return Cards.cardStr(c); }).join(',');"""
assert s.count(old) == 1, 'render head'
s = s.replace(old, new)

# T1.6 结算数字滚动：金额包 roll-num，showShowdown 后滚动
old = """    merged.forEach(function (pr) {
      var names = pr.winners.map(function (i) { return table.players[i].name; }).join('、');
      var potLabel = pr.labels.length > 1 ? pr.labels[0] + '+' + pr.labels.slice(1).join('+') + '（共 ' + pr.amount + '）' : (pr.label || '底池') + ' ' + pr.amount;
      if (pr.foldWin) {
        /* P2-12：「收下底池」含自己投入时拆两行——赢的才是赢的，收回的是收回的 */
        var w0 = pr.winners[0];
        var own = table.players[w0] ? table.players[w0].totalCommitted : 0;
        if (own > 0 && own < pr.amount) {
          html += '<div class="win-line gold">★ ' + names + ' 收回自己的投入 ' + own + '</div>' +
                  '<div class="win-line gold">★ ' + names + ' 净赢得' + (pr.label || '底池') + ' ' + (pr.amount - own) + '（其余全弃）</div>';
        } else {
          html += '<div class="win-line gold">★ ' + names + ' 收下' + potLabel + '（其余全弃）</div>';
        }
      }
      else if (pr.uncalled) html += '<div class="win-line gold">★ ' + names + ' 收回未被跟注的 ' + pr.amount + '</div>';
      else html += '<div class="win-line gold">★ ' + names + ' 以「' + pr.handName + '」赢得 ' + potLabel + (pr.split ? '（平分）' : '') + '</div>';
    });"""
new = """    merged.forEach(function (pr) {
      var names = pr.winners.map(function (i) { return table.players[i].name; }).join('、');
      var potLabel = pr.labels.length > 1 ? pr.labels[0] + '+' + pr.labels.slice(1).join('+') + '（共 ' + rollSpan(pr.amount) + '）' : (pr.label || '底池') + ' ' + rollSpan(pr.amount);
      if (pr.foldWin) {
        /* P2-12：「收下底池」含自己投入时拆两行——赢的才是赢的，收回的是收回的 */
        var w0 = pr.winners[0];
        var own = table.players[w0] ? table.players[w0].totalCommitted : 0;
        if (own > 0 && own < pr.amount) {
          html += '<div class="win-line gold">★ ' + names + ' 收回自己的投入 ' + own + '</div>' +
                  '<div class="win-line gold">★ ' + names + ' 净赢得' + (pr.label || '底池') + ' ' + rollSpan(pr.amount - own) + '（其余全弃）</div>';
        } else {
          html += '<div class="win-line gold">★ ' + names + ' 收下' + potLabel + '（其余全弃）</div>';
        }
      }
      else if (pr.uncalled) html += '<div class="win-line gold">★ ' + names + ' 收回未被跟注的 ' + rollSpan(pr.amount) + '</div>';
      else html += '<div class="win-line gold">★ ' + names + ' 以「' + pr.handName + '」赢得 ' + potLabel + (pr.split ? '（平分）' : '') + '</div>';
    });"""
assert s.count(old) == 1, 'showdown roll wrap'
s = s.replace(old, new)

old = """    body.innerHTML = html;
    $('overlay').classList.remove('hidden');
    scheduleNextHand();
  }"""
new = """    body.innerHTML = html;
    rollNumbers();            /* 批1-T1.6：金额从 0 滚动到实际值 */
    $('overlay').classList.remove('hidden');
    scheduleNextHand();
  }

  /* 批1-T1.6：结算金额滚动动画 */
  function rollSpan(v) {
    v = v || 0;
    return '<span class="roll-num" data-to="' + v + '">' + v + '</span>';
  }
  function rollNumbers() {
    var els = root.document.querySelectorAll('#overlay-body .roll-num');
    Array.prototype.forEach.call(els, function (el) {
      var to = parseInt(el.getAttribute('data-to'), 10) || 0;
      if (!to) return;
      var t0 = null;
      function step(t) {
        if (t0 === null) t0 = t;
        var k = Math.min(1, (t - t0) / 750);
        var eased = 1 - Math.pow(1 - k, 3);
        el.textContent = Math.round(to * eased);
        if (k < 1) root.requestAnimationFrame(step);
      }
      root.requestAnimationFrame(step);
    });
  }"""
assert s.count(old) == 1, 'rollNumbers insert'
s = s.replace(old, new)

# T1.8 读秒环：setTurnDeadline 与 tick 改为环+数字双写
old = """  var turnDeadline = 0;
  function setTurnDeadline(t) {
    turnDeadline = t;
    var clock = root.document.getElementById('turn-clock');   // 首帧立即写，不等 tick
    if (clock && t) { clock.textContent = '⏱ 45s'; clock.style.color = ''; clock.style.fontWeight = 'normal'; }
  }
  if (typeof root.document !== 'undefined' && root.document.getElementById('turn-clock') !== null) {
    setInterval(function () {
      var clock = root.document.getElementById('turn-clock');
      if (!clock) return;
      if (!turnDeadline) { clock.textContent = ''; return; }
      var left = Math.ceil((turnDeadline - Date.now()) / 1000);
      clock.textContent = left > 0 ? '⏱ ' + left + 's' : '代打中…';
      clock.style.color = left <= 10 ? 'var(--red)' : 'var(--muted)';
      clock.style.fontWeight = left <= 10 ? 'bold' : 'normal';
    }, 500);
  }"""
new = """  var turnDeadline = 0, turnTotal = 1;
  var RING_LEN = 97.39;   // 2πr（r=15.5）
  function applyRing(frac, urgent) {
    var fg = root.document.getElementById('turn-ring-fg');
    var num = root.document.getElementById('turn-clock-num');
    var clock = root.document.getElementById('turn-clock');
    if (fg) fg.style.strokeDashoffset = String(RING_LEN * (1 - Math.max(0, Math.min(1, frac))));
    if (num) {
      num.textContent = frac > 0 ? Math.ceil(frac * turnTotal / 1000) + 's' : '代打';
      num.style.color = urgent ? 'var(--red)' : 'var(--muted)';
      num.style.fontWeight = urgent ? 'bold' : 'normal';
    }
    if (clock) clock.classList.toggle('urgent', !!urgent);
  }
  function setTurnDeadline(t) {
    turnDeadline = t;
    var clock = root.document.getElementById('turn-clock');
    if (clock) clock.style.display = t ? 'inline-flex' : 'none';   // 批1-T1.8：读秒环
    if (t) {
      turnTotal = Math.max(1, t - Date.now());
      applyRing(1, false);   // 首帧立即写，不等 tick
    }
  }
  if (typeof root.document !== 'undefined' && root.document.getElementById('turn-clock') !== null) {
    setInterval(function () {
      if (!turnDeadline) { var c0 = root.document.getElementById('turn-clock'); if (c0) c0.style.display = 'none'; return; }
      var leftMs = turnDeadline - Date.now();
      if (leftMs <= 0) { applyRing(0, true); return; }
      applyRing(leftMs / turnTotal, leftMs <= 10000);
    }, 500);
  }"""
assert s.count(old) == 1, 'turn clock block'
s = s.replace(old, new)

# T1.2 键盘数字快捷表情 + 输入框保护
old = """    document.addEventListener('keydown', function (e) {
      var k = e.key.toLowerCase();
      if (!pendingResolve && (k === ' ' || k === 'enter') &&
          !$('overlay').classList.contains('hidden')) {
        e.preventDefault();
        $('btn-next').click();
        return;
      }
      if (!pendingResolve) return;"""
new = """    document.addEventListener('keydown', function (e) {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      var k = e.key.toLowerCase();
      if (!pendingResolve && (k === ' ' || k === 'enter') &&
          !$('overlay').classList.contains('hidden')) {
        e.preventDefault();
        $('btn-next').click();
        return;
      }
      /* 批1-T1.2：数字键 1-4 快捷表情 */
      if (k >= '1' && k <= String(EMOTE_CHIPS.length)) {
        sendQuickEmote(EMOTE_CHIPS[+k - 1]);
        return;
      }
      if (!pendingResolve) return;"""
assert s.count(old) == 1, 'keydown block'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('ui.js patched')

# ============ mp.js：读秒环单写手（删客人端重复写手） ============
p = 'js/mp.js'
s = io.open(p, encoding='utf-8').read()
old = """    if (st.gameTick) clearInterval(st.gameTick);
    st.gameTick = setInterval(function () {
      if (!st.deciding) refreshActionHint();
      var clock = root.document.getElementById('turn-clock');
      if (clock && st.deciding && st.turnEndsAt) {
        var left = Math.ceil((st.turnEndsAt - Date.now()) / 1000);
        clock.textContent = left > 0 ? '⏱ ' + left + 's' : '代打中…';
        clock.style.color = left <= 10 ? 'var(--red)' : 'var(--muted)';
      }
    }, 1000);"""
new = """    if (st.gameTick) clearInterval(st.gameTick);
    st.gameTick = setInterval(function () {
      if (!st.deciding) refreshActionHint();
      /* 批1-T1.8：读秒环由 ui.js 的 setTurnDeadline + 内部 tick 统一驱动，此处不再直写 */
    }, 1000);"""
assert s.count(old) == 1, 'mp gameTick'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('mp.js patched')

# ============ index.html：读秒环结构 + 版本 ============
p = 'index.html'
s = io.open(p, encoding='utf-8').read()
old = '    <span id="turn-clock"></span>'
new = """    <span id="turn-clock" style="display:none"><svg viewBox="0 0 36 36" aria-hidden="true"><circle class="ring-bg" cx="18" cy="18" r="15.5"></circle><circle class="ring-fg" id="turn-ring-fg" cx="18" cy="18" r="15.5"></circle></svg><b id="turn-clock-num"></b></span>"""
assert s.count(old) == 1, 'turn-clock markup'
s = s.replace(old, new)
s = re.sub(r'js/ui\.js\?v=[0-9a-z]+', 'js/ui.js?v=20260919a', s)
s = re.sub(r'js/mp\.js\?v=[0-9a-z]+', 'js/mp.js?v=20260919a', s)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('index.html patched')

# ============ 遮挡审计脚本：表情轮盘展开态（T1.1） ============
p = 'test/ui_occlusion_audit.py'
s = io.open(p, encoding='utf-8').read()
old = '''        collect(pg, "game_start", results)
        play_single_until_overlay(pg, results, "")'''
new = '''        collect(pg, "game_start", results)
        if args.vw <= 900:
            try:
                pg.locator("#emote-fab").click(timeout=1500); pg.wait_for_timeout(600)
                collect(pg, "emote_wheel", results)
                pg.locator("#emote-fab").click(timeout=800); pg.wait_for_timeout(300)
            except Exception as e:
                print("  emote_wheel 状态失败:", e, flush=True)
        play_single_until_overlay(pg, results, "")'''
assert s.count(old) == 1, 'audit emote state'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('audit script patched')
