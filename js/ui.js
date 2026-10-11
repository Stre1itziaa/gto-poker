/* ui.js — 渲染与交互（座位/牌面/操作栏/GTO 教练面板/日志/弹窗） */
(function (root) {
  'use strict';
  var Cards = root.Cards;

  /* 昵称等外部字符串进 innerHTML 前必须过这里（多人局远端名可含 HTML） */
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var table = null;
  var coachOn = true;
  var coachAvailable = true;   // 多人局对真人禁用教练（公平性）：面板+开关一并隐藏
  var lastLogIdx = 0;
  var seatEls = [];
  var pendingResolve = null;
  var thinkingIdx = -1;
  var nextHandResolve = null;
  var nextHandTimer = null;
  var portraitCache = {};   // seatIdx -> charId:expr
  var standingCache = '';   // 立绘 -> charId:expr
  var emoteTimers = {};
  var cardCache = {};       // seatIdx -> 手牌渲染键（换手/亮牌时才重绘，保证入场动画只播一次）
  /* 角色渲染后端：PNG 立绘系统（SVG 系统已废弃删除） */
  function chars() { return root.Portraits; }
  /* 资产就绪后需要重绘一次（PNG 存在性探测是异步的） */
  var portraitsReady = false;

  var SEAT_POS = {
    6: [[50, 85], [9, 74], [16, 26], [50, 14], [84, 26], [91, 74]],
    4: [[50, 85], [11, 52], [50, 14], [89, 52]],
    2: [[50, 85], [50, 14]]
  };
  /* 窄屏（手机）专用：座位整体内收，避免与顶栏重叠或被屏幕边缘裁切 */
  var SEAT_POS_MOBILE = {
    6: [[50, 84], [16, 73], [21, 23], [50, 20], [79, 23], [84, 73]],
    4: [[50, 84], [22, 52], [50, 20], [78, 52]],
    2: [[50, 84], [50, 20]]
  };
  /* ≤380 极限窄档：座位贴边收窄, 让出中央公共牌区 */
  var SEAT_POS_380 = {
    6: [[50, 86], [9, 72], [13, 24], [50, 19], [87, 24], [91, 72]],
    4: [[50, 86], [15, 52], [50, 19], [85, 52]],
    2: [[50, 86], [50, 20]]
  };
  /* 横屏矮窗(≤650h)专用：中列上下差 76%——两排 ~125px 极简座位板零重叠(360 高 wrap 250 的物理极限) */
  /* 横屏矮窗(≤650h) 两档——坐标由页面内求解器产出(零重叠+让开顶栏/行动条, 牌区 z 层高于座位无需避让):
   * 451-650h(折叠展开/矮平板): 座位132x199 上带三座+下带 me居中 */
  var SEAT_POS_LAND = {   /* 中心语义: 求解器顶点坐标已换算(顶带上带 y22/下带 y78) */
    6: [[44, 78], [10, 22], [50, 22], [90, 22], [10, 78], [90, 78]],
    4: [[44, 78], [12, 22], [88, 22], [94, 78]],
    2: [[44, 78], [44, 22]]
  };
  /* ≤450h(手机横屏): 座位122x120 定高小卡 */
  var SEAT_POS_LAND_SLIM = {
    6: [[50, 73], [16, 25], [50, 25], [84, 25], [16, 73], [84, 73]],
    4: [[50, 73], [18, 25], [82, 25], [92, 73]],
    2: [[50, 73], [50, 25]]
  };
  function seatPos() {
    var n = table.players.length;
    var w = window.innerWidth;
    var mLand = window.matchMedia && window.matchMedia('(orientation: landscape) and (max-height: 650px)').matches;
    var mSlim = window.matchMedia && window.matchMedia('(orientation: landscape) and (max-height: 450px)').matches;
    var map = w <= 380 ? SEAT_POS_380
      : mSlim ? SEAT_POS_LAND_SLIM
      : mLand ? SEAT_POS_LAND
      : (w <= 860 ? SEAT_POS_MOBILE : SEAT_POS);
    return map[n];
  }

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, parent, text) {
    var d = document.createElement(tag);
    if (cls) d.className = cls;
    if (text !== undefined && text !== '') d.textContent = text;
    if (parent) parent.appendChild(d);
    return d;
  }

  var SUIT_PATH = {
    0: 'M12 2 C9 7 4 9.5 4 13.5 C4 16 6 17.5 8.2 17.5 C9.3 17.5 10.3 17 11 16.2 C10.8 18 10 19.5 8.5 21 L15.5 21 C14 19.5 13.2 18 13 16.2 C13.7 17 14.7 17.5 15.8 17.5 C18 17.5 20 16 20 13.5 C20 9.5 15 7 12 2 Z',
    1: 'M12 20.5 C12 20.5 3.2 14.6 3.2 9 C3.2 6.1 5.5 4 8.1 4 C9.8 4 11.3 4.9 12 6.3 C12.7 4.9 14.2 4 15.9 4 C18.5 4 20.8 6.1 20.8 9 C20.8 14.6 12 20.5 12 20.5 Z',
    2: 'M12 2 C13.6 6 16.4 9.4 20 12 C16.4 14.6 13.6 18 12 22 C10.4 18 7.6 14.6 4 12 C7.6 9.4 10.4 6 12 2 Z',
    3: 'M12 2.5 C14.3 2.5 16.2 4.3 16.2 6.6 C16.2 8 15.6 9.2 14.6 10 C15.4 9.7 16.2 9.5 17 9.5 C19.5 9.5 21.5 11.5 21.5 14 C21.5 16.5 19.5 18.5 17 18.5 C15.4 18.5 14 17.7 13.2 16.5 C13.4 18.2 14.2 19.8 15.5 21 L8.5 21 C9.8 19.8 10.6 18.2 10.8 16.5 C10 17.7 8.6 18.5 7 18.5 C4.5 18.5 2.5 16.5 2.5 14 C2.5 11.5 4.5 9.5 7 9.5 C7.8 9.5 8.6 9.7 9.4 10 C8.4 9.2 7.8 8 7.8 6.6 C7.8 4.3 9.7 2.5 12 2.5 Z'
  };
  function suitSVG(suit) {
    return '<svg class="ssvg" viewBox="0 0 24 24" aria-hidden="true"><path d="' + SUIT_PATH[suit] + '"/></svg>';
  }
  function rankTxt(c) { return Cards.rankDisplay(Cards.rankOf(c)); }
  /* 图像牌面 (assets/cards/ 由 tools/make_cards.py 产出)；suitSVG 保留给非牌面图标用途 */
  var RANK_FILE = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
  var SUIT_FILE = ['s', 'h', 'd', 'c'];
  var CARD_IMG = 'assets/cards/';
  function cardFile(c) {
    return CARD_IMG + 'face_' + RANK_FILE[Cards.rankOf(c)] + SUIT_FILE[Cards.suitOf(c)] + '.png';
  }
  function cardHTML(c, small, dealIdx) {
    var d = dealIdx || 0;
    var down = (c === null || c === undefined);
    var cls = 'card' + (down ? ' back' : '') + (small ? ' small' : '') + ' d' + d;
    var src = down ? CARD_IMG + 'back_classic.png' : cardFile(c);
    var dc = down ? '' : ' data-card="' + Cards.cardStr(c) + '"';
    return '<div class="' + cls + '"' + dc + '>' +
      '<img class="cface" src="' + src + '" alt="" aria-hidden="true" draggable="false">' +
      '</div>';
  }
  function handText(c1, c2) {
    return Cards.cardStr(c1) + Cards.cardStr(c2);
  }

  function init(t) {
    table = t;
    lastLogIdx = 0;
    portraitCache = {};
    standingCache = '';
    cardCache = {};
    $('log').innerHTML = '';
    buildSeats();
    initEmoteStrip();
    // 转屏/改窗口尺寸时重排座位
    var lastMobile = window.innerWidth <= 860;
    window.addEventListener('resize', function () {
      var nowMobile = window.innerWidth <= 860;
      if (nowMobile !== lastMobile) { lastMobile = nowMobile; buildSeats(); render(); }
    });
  }

  /* ---------- 快捷表情条：让玩家从「被表演」变成能主动表达 ---------- */
  var EMOTE_CHIPS = ['你好♪', '打得漂亮！', '呜…', '就这？'];   // 批1-T1.4：轮盘首发 4 固定短语
  var emoteWired = false, emoteLastAt = 0;
  /* T1.2：表情发送统一入口（4s 防刷屏）；键盘数字键与 chip 共用 */
  function sendQuickEmote(txt) {
    var now = Date.now();
    if (now - emoteLastAt < 4000) return;
    emoteLastAt = now;
    var sent = root.MP && root.MP.sendEmote ? root.MP.sendEmote(txt) : false;
    if (!sent) showEmote(0, txt);            // 单机/非对局态：本地直接显示
  }

  /* 遮挡审计 P0-1 附属：操作栏换行时实高变化，浮标 bottom 跟随（CSS 变量驱动） */
  function watchActionbar() {
    var bar = root.document.getElementById('actionbar');
    if (!bar) return;
    var apply = function () {
      root.document.documentElement.style.setProperty('--actionbar-h', bar.offsetHeight + 'px');
    };
    apply();
    if (typeof root.ResizeObserver === 'function') {
      new root.ResizeObserver(apply).observe(bar);
    }
    root.addEventListener('resize', apply);
  }

  function initEmoteStrip() {
    var strip = root.document.getElementById('emote-strip');
    if (!strip) return;
    strip.classList.remove('hidden');
    watchActionbar();
    if (emoteWired) return;
    emoteWired = true;
    /* 遮挡审计 P0-1：窄屏表情 chips 会压住行动按钮——移动端收成一颗浮标，点击展开 */
    var fab = root.document.createElement('button');
    fab.id = 'emote-fab';
    fab.type = 'button';
    fab.textContent = '(・ω・)';
    fab.title = '快捷表情';
    fab.addEventListener('click', function () { strip.classList.toggle('open'); });
    strip.appendChild(fab);
    EMOTE_CHIPS.forEach(function (txt, i) {
      var b = root.document.createElement('button');
      b.className = 'emote-chip';
      b.innerHTML = txt + '<span class="khint">' + (i + 1) + '</span>';   // T1.2：数字角标=快捷键
      b.addEventListener('click', function () {
        sendQuickEmote(txt);
        strip.classList.remove('open');          // 选完即收（窄屏浮标模式）
      });
      strip.appendChild(b);
    });
  }

  function buildSeats() {
    var wrap = $('seats');
    wrap.innerHTML = '';
    seatEls = [];
    table.players.forEach(function (p, i) {
      var pos = seatPos()[i];
      var d = el('div', 'seat' + (pos[1] < 35 ? ' seat-top' : ''), wrap);
      /* 遮挡审计 P1-1：上排座位的徽章/气泡改为向卡片下方弹出，不再上溢进顶栏 */
      d.style.left = pos[0] + '%';
      d.style.top = pos[1] + '%';
      d.innerHTML =
        '<div class="emote"></div>' +
        '<div class="pos"></div>' +
        '<div class="name"></div>' +
        '<div class="stack"></div>' +
        '<div class="portrait"></div>' +
        '<div class="cards"></div>' +
        '<div class="action"></div>';
      seatEls.push(d);
    });
  }

  function streetName(s) {
    return { preflop: '翻前', flop: '翻牌', turn: '转牌', river: '河牌', showdown: '摊牌', idle: '—' }[s] || s;
  }
  /* P2-18：全弃结束的手没有「摊牌」，标签要分开说 */
  function handStageLabel() {
    if (table.street !== 'showdown') return streetName(table.street);
    if (table.resolved && table.resolved.pots.every(function (pr) { return pr.foldWin || pr.uncalled; })) {
      return '结束（无人摊牌）';
    }
    return '摊牌';
  }

  function render() {
    if (!table) return;
    if (table.handNo !== actionHandNo) {
      actionHandNo = table.handNo; actionCache = {};
      /* 跨手清场（P0-1 门控：只在跨手边界执行，气泡在手内存活满 4.5s） */
      Array.prototype.forEach.call(root.document.querySelectorAll('.emote.show'), function (el) { el.classList.remove('show'); });
      var cb = $('coach-body');
      if (cb && coachAvailable && !pendingResolve) cb.innerHTML = '<div class="muted">新的一手——轮到你行动时给出建议。</div>';
    }
    var bkey = table.board.map(function (c) { return Cards.cardStr(c); }).join(',');
    if (bkey !== boardShownKey) {
      var prevLen = boardShownLen;
      $('board').innerHTML = table.board.map(function (c, k) {
        return cardHTML(c, false, Math.max(0, k - prevLen));   // 新发的公共牌带错峰入场
      }).join('');
      boardShownKey = bkey;
      boardShownLen = table.board.length;
    }
    /* 批1-T1.5：底池数值变化时脉冲一下 */
    var potNow = table.potTotal();
    var potInner = '<span id="pot-inner"><span class="pchip"></span>底池 ' + potNow + '（' + (Math.round(potNow * 10 / table.bb) / 10) + 'bb）</span>';
    $('pot').innerHTML = potInner;
    if (potNow !== lastPotVal) {
      if (lastPotVal !== null && potNow > 0) {
        var pi = root.document.getElementById('pot-inner');
        if (pi) { pi.classList.remove('pot-pulse'); void pi.offsetWidth; pi.classList.add('pot-pulse'); }
      }
      lastPotVal = potNow;
    }
    $('hand-info').textContent = '第 ' + table.handNo + ' 手 · ' + handStageLabel() +
      ' · 按钮位：' + table.players[table.buttonIdx].name;

    var winners = {};
    if (table.resolved) {
      table.resolved.pots.forEach(function (pr) { pr.winners.forEach(function (i) { winners[i] = true; }); });
    }
    var revealAll = table.street === 'showdown' || !!table.resolved;
    var actorIdx = (!table.handOver && !table.awaitingRunout && table.currentActor()) ? table.currentActor().idx : -1;

    table.players.forEach(function (p, i) {
      var s = seatEls[i];
      var cls = 'seat';
      if (i === 0) cls += ' me';
      if (p.folded) cls += ' folded';
      if (winners[i]) cls += ' winner';
      if (i === actorIdx) cls += ' active';
      s.className = cls;
      /* 位置徽章全中文（SB 等英文缩写在中文语境有歧义；盲注位蓝色区分） */
      var posRaw = table.positionName(i);
      /* P2-8: 徽章中文化+盲注数值入 title */
      var POS_CN = { BTN: '庄', SB: '小盲', BB: '大盲', UTG: '枪口', HJ: '劫', CO: '关' };
      var posTitle = posRaw === 'SB' ? ('小盲 ' + table.sb) : posRaw === 'BB' ? ('大盲 ' + table.bb) : posRaw;
      var posZh = { BTN: '庄', SB: '小盲', BB: '大盲', UTG: '枪口', HJ: '劫持', CO: '关煞' }[posRaw] || posRaw;
      var posEl = s.querySelector('.pos');
      posEl.textContent = POS_CN[posRaw] || posRaw;
      posEl.title = posTitle + ' · ' + posRaw;
      posEl.textContent = posZh;
      posEl.classList.toggle('pos-blind', posRaw === 'SB' || posRaw === 'BB');
      posEl.classList.toggle('pos-dealer', posRaw === 'BTN');   /* 批1-T1.9：庄位实体扣 */
      s.querySelector('.name').innerHTML = escHtml(p.name) + (p.isBot ? '<span class="bot-tag">GTO</span>' : '');
      var bbVal = p.stack / table.bb;
      var bbTxt = bbVal >= 10 ? Math.round(bbVal) : Math.round(bbVal * 10) / 10;
      /* P2-9 + R6-R2：字段 chip 化（nowrap 分段，换行不再悬挂「·」）；「已投」改本手总额+本街双段 */
      var segs = [p.stack];   /* P1-7: 筹码恒纯数字防换行, bb 换算入 title(底池/教练面板仍带 bb 口径) */
      if (p.rebuys) segs.push('补' + p.rebuys);
      if (p.totalCommitted > 0) {
        var stackHtml = '<span class="betstack">' + betStackHtml(p.totalCommitted) + '</span>';
        segs.push(stackHtml + (p.streetCommitted > 0 && p.streetCommitted !== p.totalCommitted
          ? '已投 ' + p.totalCommitted + '（本街 ' + p.streetCommitted + '）'
          : '已投 ' + p.totalCommitted));
      }
      s.querySelector('.stack').title = '筹码 ' + p.stack + '（' + bbTxt + 'bb）';
      s.querySelector('.stack').innerHTML = segs.map(function (t) {
        return '<span class="seg">' + t + '</span>';
      }).join('');
      /* 角色头像 + 表情差分（idle/think/happy/sad） */
      var expr = exprFor(i, p, winners);
      var chKey = (root.Portraits ? root.Portraits.getCostume() : '') + ':' +
                  (p.charId || 'none') + ':' + expr;
      if (portraitCache[i] !== chKey) {
        portraitCache[i] = chKey;
        s.querySelector('.portrait').innerHTML = p.charId
          ? chars().charSVG(p.charId, expr, 66, root.Portraits ? 'bust' : undefined) : '';
      }
      var cardsEl = s.querySelector('.cards');
      var ckey = table.handNo + ':' + (p.hole.length ? p.hole.map(Cards.cardStr).join('') : '') + ':' + (i === 0 || (!p.folded && revealAll));
      if (cardCache[i] !== ckey) {
        cardCache[i] = ckey;
        if (p.hole.length === 0) {
          /* 联机防作弊面：客人看不到对手底牌（hole 为空）——
           * 牌局进行中用牌背占位，别让座位下方留着 54px 的空洞 */
          cardsEl.innerHTML = (table.handOver || table.handNo === 0)
            ? ''
            : cardHTML(null, true) + cardHTML(null, true, 1);
        }
        else if (i === 0 || (!p.folded && revealAll)) cardsEl.innerHTML = p.hole.map(function (cc, k) { return cardHTML(cc, true, k); }).join('');
        else cardsEl.innerHTML = p.hole.map(function (_, k) { return cardHTML(null, true, k); }).join('');
      }
      var actEl = s.querySelector('.action');
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
      }
    });
    renderLog();
    renderStanding(winners);
  }

  /* 表情判定：思考中 → think；结算赢家 → happy；输家 → sad；其余 idle */
  function exprFor(i, p, winners) {
    if (i === thinkingIdx && !table.handOver) return 'think';
    if (table.resolved) {
      if (winners[i] && !p.folded) return 'happy';
      if (!p.folded) return 'sad';
    }
    return 'idle';
  }

  /* 玩家立绘常驻面板（对标雀魂右侧立绘；移动端隐藏） */
  function renderStanding(winners) {
    var panel = $('portrait-panel');
    var me = table.players[0];
    if (!me || !me.charId) { panel.innerHTML = ''; return; }
    var expr = exprFor(0, me, winners);
    var key = (root.Portraits ? root.Portraits.getCostume() : '') + ':' + me.charId + ':' + expr;
    var c = chars().byId(me.charId);
    var head = '<div class="pname">' + c.name + '</div><div class="ptitle">' + c.title + '</div>';
    if (standingCache !== key) {
      standingCache = key;
      panel.innerHTML = chars().charSVG(me.charId, expr, 240, "standing") + head;
    }
  }

  /* 表情气泡（雀魂式 emote）；批1-T1.3：同屏最多 3 个可见，多的挤掉最旧 */
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
  }

  /* 下注金额 -> 筹码堆 (贪心面值拆解, 最多 6 枚) */
  var CHIP_DENOMS = [1000, 500, 100, 50, 10];
  function betStackHtml(amount) {
    var imgs = '', left = amount, count = 0;
    for (var i = 0; i < CHIP_DENOMS.length && count < 6; i++) {
      var v = CHIP_DENOMS[i];
      while (left >= v && count < 6) {
        imgs += '<img class="chipi" src="assets/chips/chip_' + v + '.png" alt="" draggable="false">';
        left -= v; count++;
      }
    }
    return imgs;
  }

  /* 演出：下注筹码从座位飞向底池 */
  function flyChips(fromIdx) {
    var seat = seatEls[fromIdx], pot = $('pot');
    if (!seat || !pot) return;
    if (root.SFX) root.SFX.chip();
    var pl = table.players[fromIdx];
    var amt = pl ? (pl.streetCommitted || pl.totalCommitted || 0) : 0;
    var denom = amt >= 500 ? 500 : amt >= 100 ? 100 : amt >= 50 ? 50 : 10;
    var a = seat.getBoundingClientRect(), b = pot.getBoundingClientRect();
    for (var k = 0; k < 3; k++) {
      (function (k) {
        var c = document.createElement('i');
        c.className = 'flychip';
        c.style.background = 'url("assets/chips/chip_' + denom + '.png") center/cover no-repeat';
        c.style.border = 'none';
        document.body.appendChild(c);
        var sx = a.left + a.width / 2 + (k - 1) * 12, sy = a.top + 14;
        var mx = (sx + b.left + b.width / 2) / 2, my = Math.min(sy, b.top) - 30;
        var ex = b.left + b.width / 2, ey = b.top + b.height / 2;
        var anim = c.animate([
          { transform: 'translate(' + sx + 'px,' + sy + 'px) scale(1)', opacity: 1 },
          { transform: 'translate(' + mx + 'px,' + my + 'px) scale(.92)', opacity: 1, offset: .55 },
          { transform: 'translate(' + ex + 'px,' + ey + 'px) scale(.5)', opacity: .85 }
        ], { duration: 430 + k * 80, easing: 'cubic-bezier(.3,.7,.4,1)' });
        anim.onfinish = function () { c.remove(); };
      })(k);
    }
  }

  /* 演出：赢池星爆 */
  function winBurst(idx) {
    var seat = seatEls[idx];
    if (!seat) return;
    if (root.SFX) { root.SFX.win(); root.SFX.haptic([40, 70, 40]); }
    var b = document.createElement('div');
    b.className = 'winburst';
    b.innerHTML = '<svg viewBox="0 0 100 100">' +
      '<g stroke="#ffd8a8" stroke-width="4" stroke-linecap="round">' +
      '<path d="M50 6 V26 M50 74 V94 M6 50 H26 M74 50 H94 M19 19 L33 33 M67 33 L81 19 M19 81 L33 67 M67 67 L81 81"/></g>' +
      '<circle cx="50" cy="50" r="10" fill="#ffd8a8"/></svg>';
    seat.appendChild(b);
    setTimeout(function () { b.remove(); }, 900);
  }

  function renderLog() {
    var logEl = $('log');
    var added = false;
    for (; lastLogIdx < table.logLines.length; lastLogIdx++) {
      var line = table.logLines[lastLogIdx];
      var div = document.createElement('div');
      if (line.indexOf('════') === 0 || line.indexOf('──') === 0) div.className = 'street';
      else if (line.indexOf('↳') === 0) div.className = 'act note';   /* A8: 教练理由行次级化 */
      else div.className = 'act';
      div.textContent = line;
      logEl.appendChild(div);
      added = true;
    }
    if (added) logEl.scrollTop = logEl.scrollHeight;
  }

  /* ---------- 行动栏 ---------- */
  var lastLA = null;   // 最近一次人类行动的合法动作集（供教练建议联动按钮使用）

  /* 两态化：raise-open 挂 #actionbar（横屏文档流/竖屏 fixed 下它都是 #raise-box 浮层的定位锚点） */
  function setRaiseOpen(v) {
    var bar = root.document.getElementById('actionbar');
    if (bar) bar.classList.toggle('raise-open', !!v);
  }

  function beginDecision() {
    decisionSeq++;
    lastSuggest = {};
  }

  function getHumanAction() {
    return new Promise(function (resolve) {
      pendingResolve = resolve;
      lastSuggest = {};                  /* 旧建议清除；序号由 updateCoach 请求时推进 */
      var la = table.legalActions(0);
      lastLA = la;
      $('action-hint').classList.add('hidden');
      $('action-controls').classList.remove('hidden');
      $('btn-fold').disabled = la.toCall <= 0;
      $('btn-fold').innerHTML = '弃牌 <span class="khint">F</span>';
      /* P1-2：被超注时显示实际可下注额（全下），名义额只作括注——不再骗人「跟注 2810」 */
      if (la.toCall <= 0) $('btn-checkcall').innerHTML = '过牌 <span class="khint">C</span>';
      else if (la.toCall >= table.players[0].stack) {
        $('btn-checkcall').innerHTML = '全下跟注 ' + table.players[0].stack +
          '（对方要 ' + la.toCall + '）<span class="khint">C</span>';
      }
      else $('btn-checkcall').innerHTML = '跟注 <span class="khint">C</span>' + la.toCall;
      /* 两态化：滑条+快捷注收进「▾调注」浮层（#raise-box 默认 display:none）；
       * 无加注权时连加注主键与调注钮一起收起（对齐旧版整盒隐藏的行为） */
      $('raise-box').style.display = la.canRaise ? '' : 'none';
      $('btn-raise').style.display = la.canRaise ? '' : 'none';
      $('raise-tune').style.display = la.canRaise ? '' : 'none';
      if (!la.canRaise) setRaiseOpen(false);
      if (la.canRaise) {
        var slider = $('raise-slider');
        slider.min = la.minTo; slider.max = la.maxTo; slider.step = table.sb;
        buildPresets(la);
        applySuggestPreset(la, decisionSeq);   // P0-B：建议绑定当前决策序号，过期不显示
        updateRaiseLabel();
      }
    });
  }

  function buildPresets(la) {
    var pot = table.potTotal(), toCall = la.toCall, cur = table.currentBet;
    /* P2-8：五档恒定（⅓/½/¾/满池 + 全下），街间不再漂移——
     * 面对下注时同一组分数作用到「底池+跟注额」，按钮集合跨街一致 */
    var list = [[1 / 3, '33%池'], [1 / 2, '50%池'], [3 / 4, '75%池'], [1, '满池']].map(function (it) {
      var target = cur === 0 ? Math.round(it[0] * pot) : cur + Math.round(it[0] * (pot + toCall));
      var to = Math.max(la.minTo, Math.min(target, la.maxTo));
      return [it[1], to];
    }).filter(function (it) { return it[1] >= la.minTo; });
    list.push(['全下', la.maxTo]);
    var box = $('presets');
    box.innerHTML = '';
    list.forEach(function (it) {
      var b = el('button', '', box, it[0]);
      b.addEventListener('click', function () {
        $('raise-slider').value = it[1];
        updateRaiseLabel();
      });
    });
    /* 滑条默认 ½ 池档，不再重置为最小加注 */
    var half = list.filter(function (it) { return it[0].indexOf('½') === 0; })[0];
    if (half) $('raise-slider').value = half[1];
  }

  /* P0-B：「按建议 X」预设——吸附到滑杆步进、绑定决策序号防过期、
   * 不自动写滑杆（点击才应用，pulse 提示可点） */
  function snapToSlider(la, v) {
    var st = la.step || table.sb;
    return Math.max(la.minTo, Math.min(la.maxTo, la.minTo + Math.round((v - la.minTo) / st) * st));
  }
  function applySuggestPreset(la, seq) {
    var box = $('presets');
    if (!box) return;
    if (seq !== decisionSeq) return;                     // 过期建议（非当前决策）不显示
    if (lastSuggest.type !== 'raise' || !lastSuggest.to) return;
    var snapped = snapToSlider(la, lastSuggest.to);
    var old = box.querySelector('.preset-suggest');
    if (old) old.remove();
    var b = el('button', 'preset-suggest', box, '按建议 ' + snapped);
    b.style.borderColor = 'var(--gold)';
    b.style.color = 'var(--gold)';
    b.addEventListener('click', function () {
      $('raise-slider').value = snapped;
      updateRaiseLabel();
    });
    box.insertBefore(b, box.firstChild);
  }
  var decisionSeq = 0, lastSuggestSeq = -1, lastSuggest = {};
  var boardShownKey = '', boardShownLen = 0;   // 公共牌入场动效追踪
  var lastPotVal = null, actionCache = {}, actionHandNo = 0;   // 批1：底池脉冲/下注弹入追踪

  function updateRaiseLabel() {
    var la = table.legalActions(0);
    var v = parseInt($('raise-slider').value, 10);
    $('btn-raise').innerHTML = (v >= la.maxTo ? '全下 ' + v : '加注到 ' + v) + ' <span class="khint">R</span>';
  }

  /* 行动倒计时钟：任何人（含房主）的 45s 时限从此可见，不再有无预警代打 */
  var turnDeadline = 0, turnTotal = 1;
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
  }

  /* 超时/状态回收：收起行动控件并放行挂起的决策 Promise（不发送任何动作） */
  function cancelDecision() {
    if (pendingResolve) {
      var r = pendingResolve;
      pendingResolve = null;
      r({ type: '__cancel' });
    }
    setRaiseOpen(false);   /* 两态化：状态回收时浮层一并收起 */
    $('action-controls').classList.add('hidden');
    $('action-hint').classList.remove('hidden');
    turnDeadline = 0;
  }

  function commitHuman(act) {
    if (!pendingResolve) return;
    if (root.SFX) {
      if (act.type === 'fold') root.SFX.fold();
      else root.SFX.click();
      /* 全下（加注到全部筹码）：重音+长震，仪式感 */
      if (act.type === 'raise' && act.to != null && table && table.players && table.players[0] &&
          act.to >= table.players[0].stack + (table.players[0].streetCommitted || 0)) {
        root.SFX.allin(); root.SFX.haptic([30, 40, 30, 40, 80]);
      }
    }
    var r = pendingResolve;
    pendingResolve = null;
    setRaiseOpen(false);   /* 两态化：行动提交后浮层收回（下个决策默认三键态） */
    $('action-controls').classList.add('hidden');
    $('action-hint').classList.remove('hidden');
    $('action-hint').textContent = '等待其他玩家行动…';
    r(act);
  }

  /* ---------- 教练面板 ----------
   * 优先在 Web Worker 里算（不阻塞主线程，点按钮零延迟）；
   * file:// 下 Worker 被浏览器禁止时，回退为主线程 setTimeout 同步计算。 */
  var coachWorker = null, coachWorkerBroken = false, coachJobId = 0;

  function ensureCoachWorker() {
    if (coachWorkerBroken || typeof root.Worker !== 'function') return null;
    if (coachWorker) return coachWorker;
    try {
      var base = location.href.replace(/[^/]*$/, '');
      var w = new Worker(base + 'js/coach-worker.js');
      var smallScreen = false;
      try {
        smallScreen = (window.matchMedia && window.matchMedia('(max-width: 860px)').matches) ||
          ((navigator.maxTouchPoints || 0) > 0 && 'ontouchstart' in window);
      } catch (e) { /* noop */ }
      w.postMessage({ type: 'init', base: base, perf: smallScreen ? 0.45 : 1 });
      w.onmessage = function (e) {
        var d = e.data;
        if (d.type === 'coach' && d.id === coachJobId) {
          if (d.error) { $('coach-body').innerHTML = '<div class="muted">教练离线：' + d.error + '</div>'; return; }
          renderCoach(d.result, d.seq);
        }
      };
      w.onerror = function () {
        coachWorkerBroken = true;
        try { w.terminate(); } catch (x) { /* noop */ }
        if (coachWorker === w) coachWorker = null;
      };
      coachWorker = w;
      return w;
    } catch (err) {
      coachWorkerBroken = true;
      return null;
    }
  }

  function snapshotState() {
    return {
      players: table.players.map(function (p) {
        return {
          idx: p.idx, name: p.name, stack: p.stack,
          hole: p.hole.slice(), folded: p.folded, allIn: p.allIn,
          streetCommitted: p.streetCommitted, totalCommitted: p.totalCommitted
        };
      }),
      board: table.board.slice(),
      street: table.street,
      actionHistory: table.actionHistory.map(function (a) {
        return { playerIdx: a.playerIdx, street: a.street, type: a.type, to: a.to, added: a.added, frac: a.frac };
      }),
      buttonIdx: table.buttonIdx, currentBet: table.currentBet,
      minRaiseSize: table.minRaiseSize, bb: table.bb, sb: table.sb,
      actorIdx: table.actorIdx
    };
  }

  function updateCoach() {
    if (!coachAvailable) return;
    var body = $('coach-body');
    if (!coachOn) return;
    body.innerHTML = '<div class="muted">正在按 GTO 逻辑计算范围与胜率…</div>';
    var id = ++coachJobId;
    var seqAtReq = decisionSeq;
    var w = ensureCoachWorker();
    if (w) {
      root.__coachMode = 'worker';
      w.postMessage({ type: 'coach', id: id, seq: seqAtReq, state: snapshotState() });
    } else {
      root.__coachMode = 'sync';
      setTimeout(function () {
        if (id !== coachJobId || seqAtReq !== decisionSeq) return;
        try { renderCoach(root.GTO.coach(table, 0), seqAtReq); }
        catch (e) { $('coach-body').innerHTML = '<div class="muted">教练离线：' + e.message + '</div>'; }
      }, 30);
    }
  }

  function renderCoach(c, seq) {
    var body = $('coach-body');
    var html = '';
    var meNow = table.players[0];
    if (meNow.folded && !c.suggestion) {
      html += '<div class="suggest" style="border-color:var(--muted)"><b>🔁 复盘模式</b><br><span class="muted">你已弃牌。接下来每条街都会更新对手范围与你的残余胜率——把死时间变成学习时间。</span></div>';
    }
    html += '<div class="kv"><span>你的手牌</span><span>' + handText(table.players[0].hole[0], table.players[0].hole[1]) +
      (c.handName ? ' · ' + c.handName : '') + '</span></div>';
    if (c.draws && (c.draws.flushDraw || c.draws.straightOuts > 0)) {
      var dtxt = [];
      if (c.draws.flushDraw) dtxt.push('同花听牌');
      if (c.draws.straightOuts > 0) dtxt.push('顺子补牌 ' + c.draws.straightOuts + ' 张');
      html += '<div class="kv"><span>听牌</span><span>' + dtxt.join(' + ') + '</span></div>';
    }
    var unacted = [];
    c.perOpp.forEach(function (o) {
      if (!o.entered) { unacted.push(o.name); return; }   // 未入池的不占胜率行
      var pctRaw = o.equity * 100;
      var pct = (pctRaw > 0 && pctRaw < 2) ? '<2%' : Math.round(pctRaw) + '%';
      html += '<div class="row"><span style="width:52px">' + o.name + '</span>' +
        '<div class="bar"><i style="width:' + Math.max(2, Math.round(pctRaw)) + '%"></i></div>' +
        '<span style="width:74px;text-align:right"><span title="你的牌对抗其范围的胜率">胜率</span> ' + pct + ' <span title="对手入池范围宽度">vs范围</span> ' + Math.round(o.rangePct * 100) + '%</span></div>';
    });
    if (unacted.length) html += '<div class="muted" title="本手尚未自愿投注入池的部员">未入池(未跟注)：' + unacted.join('、') + '</div>';
    if (c.toCall > 0) {
      html += '<div class="kv" title="跟注后需达到的对抗胜率门槛（底池赔率）"><span>跟注' + c.toCall + '需胜率(赔率)</span><span>' + Math.round(c.req * 100) + '%</span></div>';
      html += '<div class="kv" title="最小防守频率：不弃牌的最低比例，低于此对手诈唬即可盈利"><span>MDF最小防守频率</span><span>' + Math.round(c.mdf * 100) + '%</span></div>';
    }
    var sug = c.suggestion;
    if (sug) {
      var sugTxt = { fold: '弃牌', check: '过牌', call: '跟注 ' + (sug.to || c.toCall || ''), raise: (table.currentBet === 0 ? '下注 ' : '加注到 ') + (sug.to || '') }[sug.type];
      html += '<div class="suggest"><b>★ GTO 建议：' + sugTxt + '</b><br><span class="muted">' + (sug.note || '') + '</span></div>';
    }
    body.innerHTML = html;
    /* P0-2：建议动作联动行动键光圈——视觉权重指向教练答案（教学闭环），
     * 不改变弃牌窄/加注主的本职主次，只给建议键加脉冲描边 */
    var glowMap = { fold: 'btn-fold', check: 'btn-checkcall', call: 'btn-checkcall', raise: 'btn-raise' };
    ['btn-fold', 'btn-checkcall', 'btn-raise'].forEach(function (id) {
      var b = $(id);
      if (b) b.classList.remove('coach-glow');
    });
    if (sug && glowMap[sug.type]) {
      var gb = $(glowMap[sug.type]);
      if (gb) gb.classList.add('coach-glow');
    }
    /* P1-3：建议额联动到「按建议 X」预设按钮（教学闭环：给答案也给按钮） */
    lastSuggest = sug || {};
    lastSuggestSeq = seq;
    if (pendingResolve && seq === decisionSeq) {
      if (lastLA) applySuggestPreset(lastLA, seq);
      updateRaiseLabel();
    }
  }

  /* ---------- 摊牌弹窗 ---------- */
  function showShowdown(res, extraNote, quotes) {
    var body = $('overlay-body');
    var html = '';
    /* 部员发言横幅：赢家必说、输家看概率——结算演出从「收据」升「谢幕」 */
    if (quotes && quotes.length) {
      html += '<div class="ov-quotes">';
      quotes.forEach(function (q) {
        html += '<div class="ov-quote"><b>' + q.name + '</b>：「' + q.txt + '」</div>';
      });
      html += '</div>';
    }
    if (res.board.length) {
      html += '<div style="margin:6px 0">公共牌</div><div class="ov-board">';
      res.board.forEach(function (c, k) {
        html += cardHTML(c, true, k % 2);
      });
      html += '</div>';
    }
    if (extraNote) html += '<div style="margin:4px 0">' + extraNote + '</div>';
    /* 分池合并：同一组赢家的边池不再复读四行 */
    var merged = [];
    res.pots.forEach(function (pr) {
      var key = pr.winners.join(',') + '|' + (pr.foldWin ? 'f' : pr.uncalled ? 'u' : (pr.handName || ''));
      var last = merged[merged.length - 1];
      if (last && last.key === key) { last.amount += pr.amount; last.labels.push(pr.label || '底池'); }
      else {
        var cp = {}; for (var k in pr) if (Object.prototype.hasOwnProperty.call(pr, k)) cp[k] = pr[k];
        cp.labels = [pr.label || '底池']; cp.key = key;
        merged.push(cp);
      }
    });
    merged.forEach(function (pr) {
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
    });
    /* P1-5：全座位净数一行一个——赢家侧的钱从此可审计
     * 净 = 赢得 + 收回（未跟注退还） - 投入（退还不算赢，所以分开记） */
    var seatLines = '<div style="margin-top:8px;border-top:1px solid var(--line,#4a3a55);padding-top:6px">';
    table.players.forEach(function (p, i) {
      var inv = p.totalCommitted, won = p.wonThisHand || 0, ref = p.refundThisHand || 0;
      if (inv <= 0 && won <= 0 && ref <= 0) return;
      var net = won + ref - inv;
      var nsign = net >= 0 ? '+' : '−';
      var ncol = net > 0 ? '#7ee2a8' : net < 0 ? '#ff9d9d' : 'var(--muted,#9a8aa8)';
      var me0 = i === 0;
      seatLines += '<div class="hole-line"' + (me0 ? ' style="font-weight:bold"' : '') + '>' +
        (me0 ? '▶ ' : '') + p.name + '：投入 ' + inv +
        (won ? ' · 赢 ' + won : '') + (ref ? ' · 收回 ' + ref : '') +
        ' · 净 <b style="color:' + ncol + '">' + nsign + Math.abs(net) +
        '（' + nsign + (Math.abs(net) / table.bb).toFixed(1) + 'bb）</b></div>';
    });
    seatLines += '</div>';
    html += seatLines;
    var live = table.players.filter(function (p) { return !p.folded && p.hole.length === 2; });
    if (!res.pots.some(function (p) { return p.foldWin; }) && live.length > 1) {
      html += '<div style="margin-top:8px">';
      live.forEach(function (p) {
        html += '<div class="hole-line">' + p.name + '：' + handText(p.hole[0], p.hole[1]) +
          '（' + Cards.handName(p.score) + '）</div>';
      });
      html += '</div>';
    }
    body.innerHTML = html;
    rollNumbers();            /* 金额终值直出（本函数已无逐帧滚动） */
    $('overlay').classList.remove('hidden');
    /* Step 4：停留从内容就绪起算；全下摊牌档给 8s，常规 5s */
    var allInShowdown = table.players.some(function (p) { return p.allIn; }) &&
      res.pots.some(function (pr) { return !pr.foldWin && !pr.uncalled; });
    scheduleNextHand(allInShowdown ? 8000 : 5000);
  }

  /* 批1-T1.6 → R6 修订：结算金额终值立即上屏（不再从 0 滚动——动画期 DOM 是假数，
   * 截图/程序读数/核账全被坑），改为一次性高亮脉冲表达「这里变了」。 */
  function rollSpan(v) {
    v = v || 0;
    return '<span class="roll-num roll-pulse">' + v + '</span>';
  }
  function rollNumbers() {
    /* 兼容保留：数值已终值直出，无需逐帧滚动。 */
  }

  function scheduleNextHand(ms) {
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
  }
  function finishWaitNextHand() {
    if (nextHandTimer) { clearTimeout(nextHandTimer); nextHandTimer = null; }
    if (nextHandResolve) { var r = nextHandResolve; nextHandResolve = null; r(); }
  }
  function waitNextHand() {
    /* Step 2 补丁：手间等待期挂心跳钩子（main.js 注入 __waitHeartbeat）——
     * auto-next 关闭+无人点击时牌局安全停在结算画面，看门狗不再烧手（E2E 实锤 62 手被烧） */
    var hb = null;
    if (typeof root.__waitHeartbeat === 'function') hb = setInterval(root.__waitHeartbeat, 2000);
    return new Promise(function (resolve) {
      nextHandResolve = function (v) {
        if (hb) clearInterval(hb);
        resolve(v);
      };
    });
  }
  function hideOverlay() {
    $('overlay').classList.add('hidden');
    var bn = $('btn-next');   /* R6-R3：重置客人端「已请求」态 */
    if (bn) { bn.disabled = false; bn.innerHTML = '下一局 ▶ <span class="khint">空格</span>'; }
  }

  /* ---------- 顶栏 ---------- */
  /* 多人局关教练：隐藏面板与开关；回单机时恢复 */
  function setCoachAvailable(v) {
    coachAvailable = !!v;
    if (!coachAvailable) coachOn = false;
    var panel = $('coach');
    if (panel) panel.style.display = (coachAvailable && $('coach-toggle').checked) ? '' : 'none';
    var lbl = $('coach-toggle-label');
    if (lbl) lbl.style.display = coachAvailable ? '' : 'none';
  }

  function wireTopbar() {
    $('coach-toggle').addEventListener('change', function () {
      if (!coachAvailable) return;
      coachOn = this.checked;
      $('coach').style.display = coachOn ? '' : 'none';
    });
    var savedAuto = false;
    try { savedAuto = localStorage.getItem('gto-auto') === 'on'; } catch (e) { /* 隐私模式 */ }
    $('auto-next').checked = savedAuto;
    $('auto-next-2').checked = savedAuto;
    ['auto-next', 'auto-next-2'].forEach(function (id) {
      $(id).addEventListener('change', function () {
        var v = this.checked;
        try { localStorage.setItem('gto-auto', v ? 'on' : 'off'); } catch (e) { /* 隐私模式 */ }
        $('auto-next').checked = v;
        $('auto-next-2').checked = v;
        /* P1-C：弹窗开着时勾选 → 立即补建自动续局定时器
         * Step 6：多人客人勾选 = 立即向房主请求下一局（客人无本地 nextHandResolve） */
        if (v && root.MP && root.MP.isGuest && root.MP.isGuest() && root.MP.requestNext) root.MP.requestNext();
        if (v && nextHandResolve && !nextHandTimer) scheduleNextHand();
      });
    });
    $('btn-restart').addEventListener('click', function () {
      /* P2-3: 破坏性操作二次确认——当前牌局与战绩会被清 */
      if (!window.confirm('重新开局将结束当前牌局并清空本局进度，确定？')) return;
      location.reload();
    });
    /* 程序化音效开关（WebAudio 合成，零资产；SVG 描边图标与夜樱主题统一） */
    var SVG_SND_ON = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9.5 9.5 0 0 1 0 13"/></svg>';
    var SVG_SND_OFF = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="m16 9 6 6M22 9l-6 6"/></svg>';
    var sfxBtn = el('button', 'ghost', null);
    sfxBtn.id = 'btn-sfx';
    sfxBtn.title = '程序化音效 开/关';
    sfxBtn.innerHTML = root.SFX.isEnabled() ? SVG_SND_ON : SVG_SND_OFF;
    sfxBtn.addEventListener('click', function () {
      root.SFX.setEnabled(!root.SFX.isEnabled());
      sfxBtn.innerHTML = root.SFX.isEnabled() ? SVG_SND_ON : SVG_SND_OFF;
      if (root.SFX.isEnabled()) root.SFX.click();
    });
    $('topbar').querySelector('.controls').insertBefore(sfxBtn, $('btn-restart'));
    $('btn-fold').addEventListener('click', function () { commitHuman({ type: 'fold' }); });
    $('btn-checkcall').addEventListener('click', function () {
      var la = table.legalActions(0);
      commitHuman({ type: la.toCall <= 0 ? 'check' : 'call' });
    });
    $('btn-raise').addEventListener('click', function () {
      commitHuman({ type: 'raise', to: parseInt($('raise-slider').value, 10) });
    });
    /* 行动条两态化：▾调注 切换下注调整浮层（滑条+快捷注），不提交任何行动 */
    $('raise-tune').addEventListener('click', function () {
      var bar = root.document.getElementById('actionbar');
      setRaiseOpen(!(bar && bar.classList.contains('raise-open')));
    });
    $('raise-slider').addEventListener('input', updateRaiseLabel);
    /* R6-R3（fulu/sanbaiman）：多人局客人点「下一局」= 向房主发请求（此前是死按钮）
     * R6-R4（wupa）：5s 无响应自动恢复可点（幂等重发），房主掉线不再永久禁用 */
    $('btn-next').addEventListener('click', function () {
      if (root.MP && root.MP.requestNext && root.MP.isGuest()) {
        root.MP.requestNext();
        var bn = $('btn-next');
        if (bn) {
          bn.disabled = true; bn.textContent = '已请求，等待房主开下一手…';
          clearTimeout(bn._nextT);
          bn._nextT = setTimeout(function () {
            if (bn && bn.disabled) { bn.disabled = false; bn.innerHTML = '下一局 ▶ <span class="khint">空格</span>'; }
          }, 5000);
        }
        return;
      }
      finishWaitNextHand();
    });
    // 键盘快捷键：F 弃牌 / C 或空格 过牌·跟注 / R 加注 / ↑↓ 调整加注额（Shift 步进×5）
    // 结算弹层开着时：空格/回车 = 下一局（R4 反馈：手不离键盘）
    document.addEventListener('keydown', function (e) {
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
      if (!pendingResolve) return;
      if (k === 'f' && !$('btn-fold').disabled) { commitHuman({ type: 'fold' }); }
      else if (k === 'c' || k === ' ') {
        e.preventDefault();
        var la = table.legalActions(0);
        commitHuman({ type: la.toCall <= 0 ? 'check' : 'call' });
      }
      else if (k === 'r' && $('raise-box').style.display !== 'none') {
        var rv = parseInt($('raise-slider').value, 10);
        commitHuman({ type: 'raise', to: isFinite(rv) ? rv : table.legalActions(0).minTo });
      }
      else if (k === 'arrowup' || k === 'arrowdown') {
        if ($('raise-box').style.display === 'none') return;
        e.preventDefault();
        setRaiseOpen(true);   /* 键盘调注时浮层展开，滑条可见（对齐旧版常显联动） */
        var s = $('raise-slider');
        var step = table.sb * (e.shiftKey ? 5 : 1);
        s.value = parseInt(s.value, 10) + (k === 'arrowup' ? step : -step);
        updateRaiseLabel();
      }
    });
  }

  /* ---------- 选人大厅（对标雀魂：网格 + 大预览 + 台词） ---------- */
  function wireCharSelect() {
    var grid = $('char-grid');
    if (!grid) return;

    function buildGrid(sel) {
      /* V11：全高立绘条（对标 ref-select.png）——签名色底/选中金框光柱/未选去饱和 */
      grid.innerHTML = '';
      grid.classList.add('strip-row');
      chars().ALL.forEach(function (c) {
        var strip = el('div', 'char-strip' + (c.id === sel ? ' sel' : ''), grid);
        strip.style.setProperty('--sig', c.accent || '#f5c96b');
        var img = el('img', 'strip-img', strip);
        img.alt = c.name;
        img.draggable = false;
        if (root.Portraits && root.Portraits.srcOf) {
          img.src = root.Portraits.srcOf(c.id, 'idle', 300);
          img.onerror = function () { root.__ptFallback(img); };
        }
        var plate = el('div', 'strip-plate', strip);
        plate.innerHTML = '<b>' + c.name + '</b><span>' + c.title + '</span>';
        strip.addEventListener('click', function () {
          sel = c.id;
          try { localStorage.setItem('gto-char', sel); } catch (e) { /* 隐私模式 */ }
          grid.querySelectorAll('.char-strip').forEach(function (x) { x.classList.remove('sel'); });
          strip.classList.add('sel');
          renderPreview(sel);
        });
      });
    }
    function renderPreview(sel) {
      var c = chars().byId(sel);
      var host = $('char-preview');
      var imgSrc = (root.Portraits && root.Portraits.srcOf) ? root.Portraits.srcOf(sel, 'idle', 420) : '';
      host.innerHTML =
        '<img class="preview-img" src="' + imgSrc + '" alt="" draggable="false" onerror="__ptFallback(this)">' +
        '<div class="pname">' + c.name + '</div>' +
        '<div class="ptitle">' + c.title + '</div>' +
        '<div class="pquote">「' + c.quote + '」</div>';
    }

    var sel = chars().ALL[0].id;
    try { sel = localStorage.getItem('gto-char') || sel; } catch (e) { /* 隐私模式 */ }
    buildGrid(sel);
    renderPreview(sel);
    buildCostumeTabs();

    /* 服装页签：默认服 / 部服（第二套立绘，Portraits.setCostume 全局切换）。
     * 监听用事件委托挂在 row 上：按钮被任何重建替换后依然有效。 */
    function buildCostumeTabs() {
      /* 服装只在大厅选（lobby.js 页签），选人弹窗不再二次选择 */
      var row = $('costume-row');
      if (!row) return;
      row.hidden = true;
      row.innerHTML = '';
    }

    function wireCostumeRow() {
      var row = $('costume-row');
      if (!row || row.dataset.wired) return;
      row.dataset.wired = '1';
      row.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('.costume-tab') : null;
        if (!b || b.dataset.costume === chars().getCostume()) return;
        chars().setCostume(b.dataset.costume).then(function () {
          portraitCache = {};
          standingCache = '';
          buildGrid(sel);
          renderPreview(sel);
          buildCostumeTabs();   // 重画 sel 高亮（委托监听不受 innerHTML 重建影响）
        });
      });
    }

    wireCostumeRow();
    buildCostumeTabs();

    /* 大厅切装/选角后的同步（lobby.js 派发 gto-costume / gto-char 事件） */
    root.addEventListener('gto-costume', function () {
      portraitCache = {};
      standingCache = '';
      buildGrid(sel);
      renderPreview(sel);
      buildCostumeTabs();
    });
    root.addEventListener('gto-char', function () {
      portraitCache = {};
      standingCache = '';
      try { var saved = localStorage.getItem('gto-char'); if (saved) sel = saved; } catch (e) { /* noop */ }
      buildGrid(sel);
      renderPreview(sel);
      buildCostumeTabs();
    });

    /* PNG 资产扫描完成后重绘一次：未出图的角色会自动回退，
     * 不会再插一个必定 404 的 <img> 造成裂图。 */
    if (root.Portraits && root.Portraits.scan) {
      root.Portraits.scan().then(function () {
        portraitCache = {};
        standingCache = '';
        buildGrid(sel);
        renderPreview(sel);
        buildCostumeTabs();   // 扫描完成后刷新页签（部服可用性已确认）
      });
    }
  }

  function hideStart() { $('start-modal').classList.add('hidden'); }

  function setHint(text) {
    if (!pendingResolve) {
      $('action-controls').classList.add('hidden');
      $('action-hint').classList.remove('hidden');
      $('action-hint').textContent = text;
    }
  }

  /* P0-A：可见错误提示（toast + 日志） */
  function appendError(text) {
    var t = el('div', '', document.body, '⚠ ' + text);
    t.style.cssText = 'position:fixed;top:56px;left:50%;transform:translateX(-50%);z-index:120;' +
      'background:#3a1420;color:#ffb0b0;border:1.5px solid #e8607f;border-radius:10px;' +
      'padding:8px 16px;font-size:13px;box-shadow:0 8px 24px rgba(0,0,0,.5)';
    setTimeout(function () { t.remove(); }, 5000);
    try { if (table) { table.log('⚠ ' + text); renderLog(); } } catch (x) { /* ignore */ }
  }

  /* 会话战绩：只统计真实筹码转移（重买注入不计入盈亏） */
  function setSessionStats(s) {
    var pl = (s.bb >= 0 ? '+' : '') + s.bb.toFixed(1);
    var vpip = s.hands ? Math.round((s.vpip || 0) / s.hands * 100) + '%' : '—';
    var pfr = s.hands ? Math.round((s.pfr || 0) / s.hands * 100) + '%' : '—';
    $('session-stats').textContent = '本会话 ' + s.hands + ' 手 · 盈亏 ' + pl + 'bb · VPIP ' + vpip + ' / PFR ' + pfr +
      (s.rebuys ? ' · 重买 ' + s.rebuys : '');
  }

  root.UI = {
    init: init, render: render, getHumanAction: getHumanAction,
    cardHTML: cardHTML, cardFile: cardFile,
    setThinking: function (i) { thinkingIdx = i; },
    clearThinking: function () { thinkingIdx = -1; },
    updateCoach: updateCoach, showShowdown: showShowdown,
    waitNextHand: waitNextHand, hideOverlay: hideOverlay,
    wireTopbar: wireTopbar, hideStart: hideStart, setHint: setHint, setSessionStats: setSessionStats,
    wireCharSelect: wireCharSelect, showEmote: showEmote, flyChips: flyChips, winBurst: winBurst,
    appendError: appendError, beginDecision: beginDecision, setCoachAvailable: setCoachAvailable,
    cancelDecision: cancelDecision, setTurnDeadline: setTurnDeadline,
    requestNextHand: finishWaitNextHand   /* Step 6：房主代点「下一局」（客人请求协议复用） */
  };
})(typeof window !== 'undefined' ? window : globalThis);
