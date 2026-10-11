/* lobby.js — 雀魂式大厅 v2（活体立绘 / 好感度 / 服装解锁 / 部员切换 / 图鉴）
 * 依赖: portraits.js (window.Portraits) · affection.js (window.Affection) · css/landing.css
 * 挂点: #landing 内 #lobby-backdrop/#lobby-stats/#lobby-player/#stage-portrait/
 *       #stage-plate/#lobby-seats/#lobby-lib/#lobby-book（#stage-chars/#stage-costumes 已随旧版撤除）
 * 约定: 选中角色 'gto-char' · 每角色服装 'gto-costume-map'（Portraits.setCharCostume）
 */
(function (root) {
  'use strict';
  var P = root.Portraits;
  var AFF = root.Affection;
  var EXPRS = (P && P.EXPRS) || ['idle', 'happy', 'think', 'sad', 'blink'];
  var PACK_KEYS = ['p0', 'p1', 'p2', 'p3', 'p4'];   /* 五包 */
  var ALL_KEYS = PACK_KEYS.concat(['r1', 'r2', 'r3']);   /* 五包 + 好感度奖励三档 */
  var state = { charId: null, exprIdx: 0, revert: null };

  function currentChar() {
    var saved = null;
    try { saved = root.localStorage.getItem('gto-char'); } catch (e) { /* noop */ }
    var all = P.ALL;
    for (var i = 0; i < all.length; i++) if (all[i].id === saved) return all[i];
    return all[0];
  }
  function selChar(id) {
    state.charId = id;
    try { root.localStorage.setItem('gto-char', id); } catch (e) { /* 隐私模式 */ }
    try { root.dispatchEvent(new CustomEvent('gto-char')); } catch (e) { /* noop */ }
  }

  /* ---------- 台词气泡 ---------- */
  var bubbleTimer = null;
  function bubble(text) {
    var stage = document.getElementById('lobby-stage');
    var el = document.getElementById('stage-bubble');
    if (!stage) return;
    if (!el) {
      el = document.createElement('div');
      el.id = 'stage-bubble';
      stage.appendChild(el);
    }
    el.textContent = text;
    el.classList.add('show');
    if (bubbleTimer) clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(function () { el.classList.remove('show'); }, 3200);
  }

  /* ---------- 角色舞台（活体立绘：呼吸/摇曳/眨眼） ---------- */
  function stageHeight() {
    /* 大屏撑满感染力, 窄屏收敛防溢出(≤860 走移动布局) */
    if (root.innerWidth < 860) return Math.max(300, Math.round(root.innerHeight * 0.42));
    return Math.max(460, Math.min(940, Math.round(root.innerHeight * 0.9)));
  }
  function renderStage() {
    var c = currentChar();
    state.charId = c.id;
    var host = document.getElementById('stage-portrait');
    if (!host) return;
    host.innerHTML = P.html(c.id, EXPRS[state.exprIdx], stageHeight());

    var plate = document.getElementById('stage-plate');
    if (plate) {
      plate.style.setProperty('--sig', c.accent);
      var ai = AFF ? AFF.info(c.id) : null;
      var aff = '';
      if (ai) {
        aff = '<div class="aff">' +
          '<span class="aff-lv">好感 Lv.' + ai.level + '</span>' +
          '<span class="aff-bar"><i style="width:' + ai.pct + '%"></i></span>' +
          '<span class="aff-num">' + (ai.max ? 'MAX · ' + ai.pts : ai.pts + '/' + ai.next) + '</span>' +
          '</div>';
      }
      plate.innerHTML =
        '<div class="pname">' + c.name + '</div>' +
        '<span class="ptitle">' + c.title + '</span>' +
        '<div class="pquote">「' + c.quote + '」</div>' + aff;
    }
    var bd = document.getElementById('lobby-backdrop');
    if (bd) bd.style.backgroundImage = 'url("' + P.srcOf(c.id, 'idle', 420) + '")';

  }

  function onPortraitClick() {
    var c = currentChar();
    state.exprIdx = (state.exprIdx + 1) % EXPRS.length;
    renderStage();
    if (state.revert) clearTimeout(state.revert);
    if (EXPRS[state.exprIdx] !== 'idle') {
      state.revert = setTimeout(function () {
        state.exprIdx = 0;
        renderStage();
      }, 2600);
    } else {
      bubble(c.name + '「' + c.quote + '」');
    }
  }

  /* ---------- 服装页签（好感度解锁） ---------- */
  /* ---------- 图鉴弹窗（角色分页签：一次一人，滚动归零 2026-10-03） ---------- */
  var bookIdx = 0;   /* 当前角色页下标（顶部 .book-tab 切换） */
  function costumeLabel(key) {
    if (!P.COSTUMES) return key;
    for (var i = 0; i < P.COSTUMES.length; i++) if (P.COSTUMES[i].key === key) return P.COSTUMES[i].label;
    return key;
  }
  /* 只重绘当前角色页：角色分页签一行 + 该角色服装格（.book-cell 生成/equipped/lock 逻辑沿用） */
  function renderBookPage() {
    var m = document.getElementById('book-modal');
    if (!m) return;
    var tabs = m.querySelector('.book-tabs');
    var body = m.querySelector('#book-body');
    if (!tabs || !body) return;
    var total = P.ALL.length;
    var idx = ((bookIdx % total) + total) % total;
    var c = P.ALL[idx];

    /* 顶部角色分页签：小头像 + 名字，横向不换行，选中高亮描边 */
    var th = '';
    P.ALL.forEach(function (cc, i) {
      th += '<button type="button" class="book-tab' + (i === idx ? ' active' : '') + '" data-idx="' + i + '">' +
        '<img src="' + P.srcOf(cc.id, 'idle', 64) + '" alt="" draggable="false" onerror="__ptFallback(this)">' +
        '<span>' + cc.name + '</span></button>';
    });
    tabs.innerHTML = th;

    /* 内容区只渲染当前角色的服装格（原 48 格纵堆 → 每页 8 格一屏收尽） */
    var ai = AFF ? AFF.info(c.id) : null;
    var html = '<div class="book-head"><b>' + c.name + '</b><span class="book-title">' + c.title + '</span>' +
      (ai ? '<span class="book-lv">好感 Lv.' + ai.level + (ai.max ? ' · MAX' : ' · ' + ai.pts + '/' + ai.next) + '</span>' : '') +
      '</div><div class="book-row">';
    ALL_KEYS.forEach(function (k) {
      var unlocked = AFF ? AFF.isCostumeUnlocked(c.id, k) : true;
      var equipped = (P.getCharCostume ? P.getCharCostume(c.id) : '') === k;
      html += '<div class="book-cell' + (unlocked ? '' : ' lock') + (equipped ? ' equipped' : '') + '"' +
        ' data-char="' + c.id + '" data-key="' + k + '">' +
        '<img src="' + P.srcOfCostume(c.id, k, 'idle', 118) + '" alt="" draggable="false" onerror="__ptFallback(this)">' +
        '<span>' + costumeLabel(k) + '</span>' +
        (equipped ? '<em class="eq">已穿戴</em>' : unlocked ? '' : '<em>🔒 ' + (AFF ? AFF.conditionText(k) : '') + '</em>') +
        '</div>';
    });
    html += '</div>';
    body.innerHTML = html;
  }
  function openBook() {
    var m = document.getElementById('book-modal');
    if (!m) return;
    var kbId = currentChar().id;              /* 打开时定位到当前看板娘 */
    for (var i = 0; i < P.ALL.length; i++) if (P.ALL[i].id === kbId) { bookIdx = i; break; }
    renderBookPage();
    m.classList.remove('hidden');
  }
  function buildBookModal() {
    if (document.getElementById('book-modal')) return;
    var m = document.createElement('div');
    m.id = 'book-modal';
    m.className = 'hidden';
    m.innerHTML = '<div id="book-card">' +
      '<div class="book-top"><h3>📖 图鉴 · 服装</h3>' +
      '<button id="book-close" type="button" aria-label="关闭">✕</button></div>' +
      '<div class="book-tabs"></div>' +
      '<div id="book-body"></div>' +
      '</div>';
    document.body.appendChild(m);
    m.querySelector('#book-close').addEventListener('click', function () { m.classList.add('hidden'); });
    m.addEventListener('click', function (e) {
      if (e.target === m) { m.classList.add('hidden'); return; }
      var tab = e.target.closest ? e.target.closest('.book-tab') : null;
      if (tab) { bookIdx = +tab.getAttribute('data-idx') || 0; renderBookPage(); return; }
      var cell = e.target.closest ? e.target.closest('.book-cell') : null;   /* 点格行为与旧版一致 */
      if (cell) {
        var charId = cell.getAttribute('data-char'), key = cell.getAttribute('data-key');
        var unlocked = AFF ? AFF.isCostumeUnlocked(charId, key) : true;
        if (!unlocked) {
          var c = P.byId(charId);
          bubble('🔒 与' + c.name + '的' + (AFF ? AFF.conditionText(key) : '好感度不足'));
          return;
        }
        selChar(charId);
        P.setCharCostume(charId, key).then(function () {
          renderStage();
          renderBookPage();          /* 重绘当前页：已穿戴描边随格移动 */
          try { root.dispatchEvent(new CustomEvent('gto-costume')); } catch (e2) { /* noop */ }
          bubble(P.byId(charId).name + ' · ' + costumeLabel(key) + ' 已穿戴');
        });
      }
    });
  }
  function wireBook() {
    buildBookModal();
    var btn = document.getElementById('lobby-book');
    if (btn && !btn.dataset.wired) {
      btn.dataset.wired = '1';
      btn.addEventListener('click', openBook);
    }
  }

  /* ---------- 顶栏 ---------- */
  /* 昵称口径与 main.js:80 / data.js:270 对齐：未设 gto-name 时回退「我」。
     旧值 '部员' 的问题（2026-10-03 复测实锤）：头像取首字 →「部」，昵称 →「部员」，
     与段位「新员」并排后整块被读成「部门 / 部员 / 新员」三个分类标签，而不是「这是我」。 */
  var NAME_DEFAULT = '我';
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function playerName() {
    try { return root.localStorage.getItem('gto-name') || NAME_DEFAULT; } catch (e) { return NAME_DEFAULT; }
  }
  function savePlayerName(v) {
    var s = String(v == null ? '' : v).replace(/[\u0000-\u001f\u007f]/g, '').replace(/\s+/g, ' ').trim();
    if (s.length > 8) s = s.slice(0, 8);
    if (!s) s = NAME_DEFAULT;
    try { root.localStorage.setItem('gto-name', s); } catch (e) { /* noop */ }
    return s;
  }
  /* 内联改名：gto-name 此前的唯一写入点是好友房 mp.js readName()，
     单机玩家没有任何改名入口，只能永远显示默认值。 */
  function beginRename(host, span) {
    if (!host || !span || host.querySelector('.lb-name-edit')) return;
    var input = document.createElement('input');
    input.className = 'lb-name-edit';
    input.type = 'text';
    input.maxLength = 8;
    input.value = playerName();
    input.setAttribute('aria-label', '修改昵称');
    span.replaceWith(input);
    try { input.focus(); input.select(); } catch (e) { /* noop */ }
    var done = false;
    function commit(keep) {
      if (done) return;
      done = true;
      if (keep) savePlayerName(input.value);
      renderTopbar();
    }
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); commit(true); }
      else if (ev.key === 'Escape') { ev.preventDefault(); commit(false); }
    });
    input.addEventListener('blur', function () { commit(true); });
    input.addEventListener('click', function (ev) { ev.stopPropagation(); });
  }
  function renderTopbar() {
    var sess = {};
    try { sess = JSON.parse(root.localStorage.getItem('gto-sess') || '{}') || {}; } catch (e) { /* noop */ }
    var name = playerName();
    var stats = document.getElementById('lobby-stats');
    if (stats) {
      var bb = typeof sess.bb === 'number' ? sess.bb : 0;
      var sign = bb >= 0 ? '+' : '−';
      var cls = bb > 0 ? 'pos' : bb < 0 ? 'neg' : '';
      stats.innerHTML =
        '<span class="lb-stat"><i>手数</i><b>' + (sess.hands || 0) + '</b></span>' +
        '<span class="lb-stat"><i>盈亏</i><b class="' + cls + '">' + sign + Math.abs(bb).toFixed(1) + 'bb</b></span>' +
        '<span class="lb-stat"><i>VPIP</i><b>' + (sess.hands ? Math.round((sess.vpip || 0) / sess.hands * 100) : 0) + '%</b></span>';
    }
    var player = document.getElementById('lobby-player');
    if (player) {
      var rk = AFF ? AFF.rankInfo() : null;
      player.innerHTML =
        '<span class="lb-avatar">' + escHtml(String(name).charAt(0)) + '</span>' +
        '<span class="nm" title="点击改名">' + escHtml(name) + '</span>' +
        (rk ? '<span class="lb-rank" style="color:' + rk.color + '">' + escHtml(rk.name) + '</span>' : '') +
        '<span class="lb-edit" role="button" tabindex="0" title="修改昵称" aria-label="修改昵称">' +
          '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" ' +
          'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3z"/></svg>' +
        '</span>';
      var nmEl = player.querySelector('.nm');
      var edEl = player.querySelector('.lb-edit');
      function openEditor(ev) {
        if (ev) ev.stopPropagation();
        beginRename(player, player.querySelector('.nm'));
      }
      if (nmEl) nmEl.addEventListener('click', openEditor);
      if (edEl) {
        edEl.addEventListener('click', openEditor);
        edEl.addEventListener('keydown', function (ev) {
          if (ev.key === 'Enter' || ev.key === ' ') openEditor(ev);
        });
      }
    }
  }

  /* ---------- 服装默认（无设置的角色落 p1） ---------- */
  function ensureCostumes() {
    var jobs = [];
    P.ALL.forEach(function (c) {
      if (!P.getCharCostume || !P.getCharCostume(c.id)) {
        jobs.push(P.setCharCostume(c.id, 'p1'));
      }
    });
    return Promise.all(jobs);
  }

  function greet() {
    var h = new Date().getHours();
    var g = h < 5 ? '夜这么深了，还要来一手？'
      : h < 11 ? '早。部室的椅子还热着。'
      : h < 18 ? '下午的牌局，正合适。'
      : '晚上的部室，是黄金时间。';
    bubble(g);
  }

  function renderSeats() {
    var row = document.getElementById('lobby-seats');
    if (!row) return;
    var cur = '6';
    try { cur = root.localStorage.getItem('gto-seats') || '6'; } catch (e) { /* noop */ }
    row.innerHTML = '<span class="muted" style="font-size:12.5px;align-self:center">桌型</span>';
    [['6', '6人桌'], ['4', '4人桌'], ['2', '单挑']].forEach(function (o) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'costume-tab' + (o[0] === cur ? ' sel' : '');
      b.textContent = o[1];
      b.addEventListener('click', function () {
        try { root.localStorage.setItem('gto-seats', o[0]); } catch (e) { /* noop */ }
        renderSeats();
      });
      row.appendChild(b);
    });
  }

  /* ---------- 新手引导（首次进入一次性，手游审查 P1） ---------- */
  function firstRunHint() {
    var KEY = 'gto-tutored';
    var done = false;
    try { done = !!root.localStorage.getItem(KEY); } catch (e) { /* noop */ }
    if (done) return;
    var m = document.createElement('div');
    m.id = 'tut-modal';
    m.innerHTML = '<div id="tut-card"><h3>🌸 欢迎来到夜樱扑克部</h3>' +
      '<ol>' +
      '<li><b>选模式上桌</b>——右侧「单机练习」即刻开局，与部员对练德州扑克；「好友房」发房码给朋友，跨网络联机。</li>' +
      '<li><b>轮到你时</b>——底部三个按钮：弃牌 / 过牌·跟注 / 加注（拖滑条或点快捷注选金额）。</li>' +
      '<li><b>养成你的看板娘</b>——点「角色库」换部员与服装；打牌涨好感度，解锁更多装扮。</li>' +
      '</ol><button id="tut-go" class="tut-btn" type="button">开始游戏</button></div>';
    document.body.appendChild(m);
    function close() {
      m.remove();
      try { root.localStorage.setItem(KEY, '1'); } catch (e2) { /* noop */ }
    }
    m.querySelector('#tut-go').addEventListener('click', close);
    m.addEventListener('click', function (e) { if (e.target === m) close(); });
  }

  /* 雀魂式大厅(横屏): 主CTA+桌型搬出 #lobby-side(其 absolute/transform 会捕获子级定位),
   * 挂到 #lobby-main 直属使 CSS absolute 左下生效; 竖屏搬回原位随文档流 */
  function placeLobbyCTA() {
    var main = document.getElementById('lobby-main');
    var side = document.getElementById('lobby-side');
    var train = document.getElementById('mc-train');
    var seats = document.getElementById('lobby-seats');
    if (!main || !side || !train || !seats) return;
    var land = root.matchMedia && root.matchMedia('(orientation: landscape) and (max-height: 650px)').matches;
    /* 雀魂式右列小钮用短文案(78px 窄钮装不下长名, wrap 三行撑爆列高) */
    var lib = document.getElementById('lobby-lib'), book = document.getElementById('lobby-book');
    if (lib) lib.textContent = land ? '🎭 角色库' : '🎭 角色库 · 看板娘与服装';
    if (book) book.textContent = land ? '📖 图鉴' : '📖 图鉴 · 服装收集';
    if (land) {
      if (train.parentElement !== main) { main.appendChild(seats); main.appendChild(train); }
    } else {
      var cards = side.querySelector('.mode-cards');
      if (cards && train.parentElement === main) {
        cards.insertBefore(train, cards.firstChild);
        side.insertBefore(seats, side.querySelector('#lobby-lib'));
      }
    }
  }

  function init() {
    if (!P) return;
    wireLib();
    renderSeats();
    firstRunHint();
    placeLobbyCTA();
    try {
      root.matchMedia('(orientation: landscape) and (max-height: 650px)').addEventListener('change', placeLobbyCTA);
    } catch (e) { /* 老WebView无change事件, 布局以进厅时为准 */ }
    /* 舞台点击用容器委托：renderStage 重建 innerHTML 后绑定不丢（试玩报告 P0 项） */
    var stageHost = document.getElementById('stage-portrait');
    if (stageHost) stageHost.addEventListener('click', onPortraitClick);
    var plChip = document.getElementById('lobby-player');
    if (plChip) {
      plChip.style.cursor = 'pointer';
      plChip.title = '战绩与数据分析';
      plChip.addEventListener('click', function () {
        var t = document.getElementById('mc-data');
        if (t) t.click();
      });
    }
    var sel = null;
    try { sel = root.localStorage.getItem('gto-char'); } catch (e) { /* noop */ }
    if (sel) state.charId = sel;
    wireBook();
    renderTopbar();
    ensureCostumes().then(function () {
      renderStage();
      greet();
    });
    if (P.scan) P.scan().then(function () {
      renderStage();
      /* scan 完成后 2.5s 才后台补齐差分探测——3s 后再刷一次，眨眼层就位 */
      setTimeout(renderStage, 3000);
    });
  }

  /* ---------- 角色库 · 看板娘设置（单页切换：一次一人，滚动深度归零） ---------- */
  var libIdx = 0;   /* 当前展示角色下标（左右循环切换） */
  function libAffBar(c) {
    if (!AFF) return '';
    var ai = AFF.info(c.id);
    return '<div class="aff">' +
      '<span class="aff-lv">好感 Lv.' + ai.level + '</span>' +
      '<span class="aff-bar"><i style="width:' + ai.pct + '%"></i></span>' +
      '<span class="aff-num">' + (ai.max ? 'MAX · ' + ai.pts : ai.pts + '/' + ai.next) + '</span>' +
      '</div>';
  }
  /* 只重绘当前页：名字/好感/服装 chips/看板 CTA/页码（切换角色或穿戴后调用） */
  function renderLibPage() {
    var m = document.getElementById('lib-modal');
    if (!m) return;
    var total = P.ALL.length;
    var idx = ((libIdx % total) + total) % total;
    var c = P.ALL[idx];
    var isKb = c.id === currentChar().id;
    var curCos = P.getCharCostume ? (P.getCharCostume(c.id) || 'p1') : 'p1';
    var chips = '';
    ['p0', 'p1', 'p2', 'p3', 'p4', 'r1', 'r2', 'r3'].forEach(function (k) {
      var unlocked = AFF ? AFF.isCostumeUnlocked(c.id, k) : true;
      var equipped = curCos === k;
      chips += '<button type="button" class="lib-cos' + (equipped ? ' sel' : '') + (unlocked ? '' : ' lock') + '"' +
        ' data-char="' + c.id + '" data-key="' + k + '">' +
        (unlocked ? '' : '🔒 ') + costumeLabel(k) + '</button>';
    });
    var prevImg = m.querySelector('.lib-img.preview-lock');
    if (prevImg) { prevImg.classList.remove('preview-lock'); var oldTip = m.querySelector('.lib-lock-tip'); if (oldTip) oldTip.remove(); }
    var body = m.querySelector('#lib-body');
    body.style.setProperty('--sig', c.accent);
    body.innerHTML =
      '<div class="lib-hero">' +
      '<button type="button" class="lib-arrow lib-arrow-prev" aria-label="上一位">‹</button>' +
      '<img class="lib-img" src="' + P.srcOf(c.id, 'idle', 480) + '" data-full="' + P.srcOf(c.id, 'idle', 900) + '" alt="' + c.name + '" draggable="false" onerror="__ptFallback(this)">' +
      '<button type="button" class="lib-arrow lib-arrow-next" aria-label="下一位">›</button>' +
      '</div>' +
      '<div class="lib-info">' +
      '<div class="lib-name"><b>' + c.name + '</b><span>' + c.title + '</span>' +
      (isKb ? '<em class="kb-badge">✦ 看板中</em>' : '') + '</div>' +
      libAffBar(c) +
      '<div class="lib-cos">' + chips + '</div>' +
      '<button type="button" class="lib-set"' + (isKb ? ' disabled' : '') + ' data-char="' + c.id + '">' +
      (isKb ? '✦ 当前看板娘' : '★ 设为看板娘') + '</button>' +
      '</div>';
    var num = m.querySelector('#lib-page-num');
    if (num) num.textContent = (idx + 1) + ' / ' + total;
  }
  function libSwitch(dir) {
    var total = P.ALL.length;
    libIdx = ((libIdx + dir) % total + total) % total;
    renderLibPage();
  }
  function openLibrary() {
    var m = document.getElementById('lib-modal');
    if (!m) return;
    var kbId = currentChar().id;              /* 打开时定位到当前看板娘 */
    for (var i = 0; i < P.ALL.length; i++) if (P.ALL[i].id === kbId) { libIdx = i; break; }
    renderLibPage();
    m.classList.remove('hidden');
  }
  function wireLib() {
    buildLibModal();
    var btn = document.getElementById('lobby-lib');
    if (btn && !btn.dataset.wired) {
      btn.dataset.wired = '1';
      btn.addEventListener('click', openLibrary);
    }
  }
  function buildLibModal() {
    if (document.getElementById('lib-modal')) return;
    var m = document.createElement('div');
    m.id = 'lib-modal';
    m.className = 'hidden';
    m.innerHTML = '<div id="lib-card">' +
      '<span id="lib-page-num"></span>' +
      '<button id="lib-close" type="button" aria-label="关闭">✕</button>' +
      '<div id="lib-body"></div>' +
      '</div>';
    document.body.appendChild(m);
    m.querySelector('#lib-close').addEventListener('click', function () { m.classList.add('hidden'); });
    m.addEventListener('click', function (e) { if (e.target === m) m.classList.add('hidden'); });
    /* 全屏预览层：点立绘放大看完整服装，点任意处收起 */
    var fv = document.createElement('div');
    fv.id = 'lib-fullview';
    fv.className = 'lib-fullview hidden';
    fv.innerHTML = '<img alt=""><span class="fv-hint">点按任意处返回</span>';
    document.body.appendChild(fv);
    fv.addEventListener('click', function () { fv.classList.add('hidden'); });
    m.querySelector('#lib-body').addEventListener('click', function (e) {
      var arrow = e.target.closest ? e.target.closest('.lib-arrow') : null;
      if (arrow) { libSwitch(arrow.classList.contains('lib-arrow-prev') ? -1 : 1); return; }
      var libImg = e.target.closest ? e.target.closest('.lib-img') : null;
      if (libImg) {
        var fvEl = document.getElementById('lib-fullview');
        if (fvEl) {
          fvEl.querySelector('img').src = libImg.getAttribute('data-full') || libImg.src;
          fvEl.classList.remove('hidden');
        }
        return;
      }
      var cos = e.target.closest ? e.target.closest('.lib-cos') : null;
      var setBtn = e.target.closest ? e.target.closest('.lib-set') : null;
      if (cos) {
        var charId = cos.getAttribute('data-char'), key = cos.getAttribute('data-key');
        var kbChar = currentChar();
        var heroImg = m.querySelector('.lib-img');
        if (cos.classList.contains('lock')) {
          if (AFF) bubble('🔒 与' + P.byId(charId).name + '的' + AFF.conditionText(key));
          /* 锁定皮肤也给预览: 立绘临时换装+灰度+锁标, 点其他/关闭恢复 */
          if (heroImg && charId === kbChar.id) {
            heroImg.src = P.srcOfCostume ? P.srcOfCostume(charId, key, 'idle', 480) : P.srcOf(charId, 'idle', 480);
            heroImg.classList.add('preview-lock');
            var tip = m.querySelector('.lib-lock-tip');
            if (!tip) { tip = document.createElement('div'); tip.className = 'lib-lock-tip'; heroImg.parentElement.appendChild(tip); }
            tip.textContent = '🔒 ' + AFF.conditionText(key);
          }
          return;
        }
        if (heroImg) { heroImg.classList.remove('preview-lock'); var oldTip = m.querySelector('.lib-lock-tip'); if (oldTip) oldTip.remove(); }
        if (cos.classList.contains('sel')) return;
        P.setCharCostume(charId, key).then(function () {
          renderLibPage();          // 重绘当前页（chips 已穿戴态）
          renderStage();
          try { root.dispatchEvent(new CustomEvent('gto-costume')); } catch (e2) { /* noop */ }
          bubble(P.byId(charId).name + ' · ' + costumeLabel(key) + ' 已穿戴');
        });
      } else if (setBtn) {
        selChar(setBtn.getAttribute('data-char'));
        state.exprIdx = 0;
        renderStage();
        var nc = P.byId(setBtn.getAttribute('data-char'));
        bubble('看板娘已更换为 ' + nc.name);
        renderLibPage();            // 重绘徽章与 CTA 态
      }
    });
    /* 键盘左右箭头切换角色（仅弹窗打开时生效） */
    document.addEventListener('keydown', function (e) {
      if (m.classList.contains('hidden')) return;
      if (e.key === 'ArrowLeft') libSwitch(-1);
      else if (e.key === 'ArrowRight') libSwitch(1);
    });
  }
  root.Lobby = { init: init, renderStage: renderStage, openBook: openBook, openLibrary: openLibrary };
})(typeof window !== 'undefined' ? window : globalThis);
