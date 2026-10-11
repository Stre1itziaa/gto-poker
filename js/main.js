/* main.js — 游戏主循环：驱动引擎与 UI，节奏控制
 * P0-A：loop 全程 try/catch + 看门狗，任何异常都不会永久卡死牌局。 */
(function () {
  'use strict';
  var APP_VERSION = '0.9';   /* 发版必 bump: 大厅页脚+对局顶栏自动带出, 截图即可判版本 */
  var Table = window.Table, GTO = window.GTO, UI = window.UI;
  /* 角色渲染后端：PNG 立绘系统（旧 SVG 系统已删除） */
  var Characters = window.Portraits;
  var Equity = window.Equity, SFX = window.SFX;
  /* 好友房联机（mp.js）：房主权威模式下的快照广播与远端动作等待 */
  var MP = window.MP;
  var table = null;
  /* P0-A：主循环健康监控（回访审计重构版）
   * 心跳贯穿循环体；看门狗只打 forceKill 标记，由活着的循环在 await 返回点自愈；
   * 不再重入 loop()（旧实现每次误报叠加一个僵尸循环）。 */
  var lastTick = Date.now(), loopRunning = false, lastRecoverWarn = 0, staleStrikes = 0;
  var lastUserInputAt = Date.now();   /* Step 2：挂机判定（页面隐藏或 30s 无输入 → AFK） */
  function heartbeat() { lastTick = Date.now(); }
  function mkForceKill() {
    var e = new Error('对局失去响应（看门狗中断）');
    e.forceKill = true;
    return e;
  }

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

  /* 会话战绩（重买注入不计入盈亏）；持久化到 localStorage（游戏性评审建议④） */
  var SESS = { hands: 0, bb: 0.0, vpip: 0, pfr: 0, rebuys: 0 };
  try {
    var savedSess = JSON.parse(localStorage.getItem('gto-sess') || '{}');
    if (savedSess && typeof savedSess === 'object') Object.assign(SESS, savedSess);
  } catch (e) {
    try { localStorage.removeItem('gto-sess'); } catch (e2) { /* noop */ }   /* S2：坏档自清，防启动瘫痪 */
  }

  function saveSess() {
    try { localStorage.setItem('gto-sess', JSON.stringify(SESS)); } catch (e) { /* file:// 隐私模式 */ }
  }

  function recordSession() {
    var me = table.players[0];
    var preflopActs = table.actionHistory.filter(function (a) { return a.street === 'preflop' && a.playerIdx === 0; });
    SESS.hands++;
    if (preflopActs.some(function (a) { return a.type === 'call' || a.type === 'raise'; })) SESS.vpip++;
    if (preflopActs.some(function (a) { return a.type === 'raise'; })) SESS.pfr++;
    UI.setSessionStats(SESS);
    saveSess();
  }

  /* R5-施工 P1-3：服务端手牌留档——每手落盘 JSON（投入/行动流/派彩/筹码），
   * 上报前本地断言 Σ派彩=Σ投入，不平红字告警。留档失败静默（不影响牌局）。 */
  function archiveHand(table, res) {
    try {
      var rec = {
        room: (MP && MP.roomCode && MP.roomCode()) || 'local',
        handNo: table.handNo,
        ts: new Date().toISOString(),
        sb: table.sb, bb: table.bb,
        players: table.players.map(function (p) {
          return { name: p.name, charId: p.charId || '', isBot: !!p.isBot,
            stackEnd: p.stack, committed: p.totalCommitted,
            won: p.wonThisHand || 0, refund: p.refundThisHand || 0, rebuys: p.rebuys || 0,
            idle: !!(window.MP && window.MP.isIdleSeat && window.MP.isIdleSeat(p.idx)) };   /* Step 5：离席/代打座位 */
        }),
        board: res.board.map(function (c) { return window.Cards.cardStr(c); }),
        actions: table.actionHistory.map(function (a) {
          return { idx: a.playerIdx, street: a.street, type: a.type, to: a.to, added: a.added, auto: !!a.auto };
        }),
        pots: res.pots.map(function (pr) {
          return { amount: pr.amount, winners: pr.winners, label: pr.label || '',
            handName: pr.handName || null, foldWin: !!pr.foldWin, uncalled: !!pr.uncalled, split: !!pr.split };
        })
      };
      var paid = 0, put = 0;
      rec.pots.forEach(function (pr) { paid += pr.amount; });
      rec.players.forEach(function (q) { put += q.committed; });
      rec.assert = { sumPaid: paid, sumPut: put, ok: paid === put };
      /* R6-R2 修复：hero 与 mp 端同口径——剥「（你）」，优先用玩家昵称（gto-name），回退角色名 */
      rec.hero = String(window.localStorage.getItem('gto-name') || table.players[0].name || '')
        .replace(/（你）/g, '').trim() || '我';
      rec.players[0].name = rec.hero;   /* R6-R3（ribaora）：单机动作流人名同步剥后缀 */
      rec.mode = (typeof MP !== 'undefined' && MP && MP.hosting && MP.hosting()) ? 'mp' : 'sp';
      rec.players[0].hole = (table.players[0].hole || []).map(function (c) { return window.Cards.cardStr(c); });   /* 数据板块：留自己的底牌 */
      /* 摊牌局的公开信息补全：非弃牌者的底牌在摊牌时已公开，一并留档（与客人端口径对齐） */
      if (res.pots.some(function (pr) { return !pr.foldWin && !pr.uncalled; })) {
        rec.players.forEach(function (q, k) {
          var tp = table.players[k];
          if (!q.hole && !tp.folded && tp.hole && tp.hole.length === 2) {
            q.hole = tp.hole.map(function (c) { return window.Cards.cardStr(c); });
          }
        });
      }
      rec.perspective = 'host';    /* Step 1：留档视角标记 */
      rec.self = true;             /* Step 14：本机自录标记 */
      rec.idleSeats = rec.players.some(function (q) { return !!q.idle; });   /* Step 5：本手含离席/代打座位 */
      if (window.DataPage && window.DataPage.post) {
        window.DataPage.post(rec);   /* 本机牌谱 + 服务器留档（失败排队重发，见 data.js） */
      }
      if (window.Affection && window.Affection.onHand) {
        var aff = window.Affection.onHand(rec);
        if (aff && aff.levelUp && window.UI && window.UI.appendError) {
          var pc = window.Portraits && window.Portraits.byId ? window.Portraits.byId(aff.charId) : null;
          window.UI.appendError('💗 ' + (pc ? pc.name : aff.charId) + ' 好感度达到 Lv.' + aff.level + '！');
        }
      }
      if (!rec.assert.ok && window.UI && window.UI.appendError) {
        window.UI.appendError('⚠ 第 ' + table.handNo + ' 手账目不平（投 ' + put + ' / 派 ' + paid + '），已留档待查');
      }
    } catch (e) { /* 留档失败不影响牌局 */ }
  }

  async function loop() {
    if (loopRunning) return;               /* 单例：禁止僵尸循环叠加 */
    loopRunning = true;
    for (;;) {
      heartbeat();
      if (window.DataPage && window.DataPage.flushPosts) window.DataPage.flushPosts();   /* Step 1：重发留档队列 */
      var handBroken = false;
      var res = null, extraNote = null;
      var preStack = table.players[0].stack;
      var preRebuys = table.players[0].rebuys || 0;
      try {
        table.startHand();
        if (MP && MP.hosting()) MP.hostHandStart(table);   /* 好友房：广播新手快照 */
        UI.setHint('翻前下注中…');
        var lastBoardLen = 0;
        var lastFoldBoard = -1;
        UI.render();
        while (!table.handOver) {
          heartbeat();
          if (table.forceKill) throw mkForceKill();   /* P0-A：看门狗判定失联 → 本手自愈出口 */
          if (table.awaitingRunout) {           // 全下后逐街揭晓（聚焦演出 + 慢放）
            heartbeat();
            if (!document.body.classList.contains('runout')) document.body.classList.add('runout');
            await sleep(1250);
            table.runoutStep();
            if (MP && MP.hosting()) MP.hostSync(table);   /* 好友房：跑牌逐街推送 */
            UI.render();
            continue;
          }
          if (table.board.length !== lastBoardLen) { SFX.deal(); lastBoardLen = table.board.length; }
          var actor = table.currentActor();
          /* 好友房：真人客人座位与机器人同一条分支（动作从网络等待） */
          var remote = MP && MP.hosting() && MP.isRemoteSeat(actor.idx);
          if (actor.isBot || remote) {
            UI.setThinking(actor.idx);
            if (remote) MP.hostThink(actor.idx, true);
            UI.render();
            await sleep(400 + Math.random() * 500);
            heartbeat();
            var la = table.legalActions(actor.idx);
            var act;
            if (remote) {
              /* 客人长考期间心跳不断，否则看门狗会误判失联 */
              var remoteHB = setInterval(heartbeat, 1000);
              act = await MP.nextRemoteAction(table, actor.idx);
              clearInterval(remoteHB);
              MP.hostThink(actor.idx, false);
              heartbeat();
              if (act.timeout) { act.note = '超时代打'; act.auto = true; }
            } else {
              act = GTO.decide(table, actor.idx);
            }
            UI.clearThinking();
            table.apply(act);
            if (MP && MP.hosting()) MP.hostSync(table);   /* 好友房：每步动作后广播 */
            if (act.type === 'raise' || act.type === 'call') {
              UI.flyChips(actor.idx);
              if (MP && MP.hosting()) MP.fxFly(actor.idx);
            }
            if (actor.allIn) { SFX.allin(); if (MP && MP.hosting()) MP.fxSfx('allin'); }
            // 日志降噪：翻前无人加注时的常规弃牌不写理由；代打动作无 note 不输出
            if (act.note && (act.type === 'raise' || la.toCall > 0 || table.street !== 'preflop')) {
              table.log('↳ ' + act.note);
            }
            UI.render();
            await sleep(220);
          } else {
            UI.render();
            UI.beginDecision();                    /* P0-B：决策序号在此推进（教练请求绑定本轮） */
            UI.updateCoach();
            /* P2-E：人类长考 8 秒后也切「思考」表情 */
            var thinkTimer = setTimeout(function () { UI.setThinking(0); UI.render(); }, 8000);
            var humanHB = setInterval(heartbeat, 1000);   /* 长考期间心跳不断 */
            /* R2-P0 + Step 2：人类座位 45s 行动计时；挂机（页面隐藏或 30s 无输入）降为 8s 快钟 */
            var afk = (window.document.visibilityState === 'hidden') ||
                      (Date.now() - lastUserInputAt > 30000);
            var turnMs = afk ? 8000 : ((MP && MP.TURN_MS) || 45000);
            table.humanTurnEndsAt = Date.now() + turnMs;   /* Step 2：快照按真实钟广播给客人 */
            UI.setTurnDeadline(Date.now() + turnMs);
            var res2Human = null;
            var humanTimer = setTimeout(function () {
              var l2 = table.legalActions(0);
              UI.setTurnDeadline(0);
              UI.cancelDecision();
              /* 不另写 ⏱ 行：act 带 note 走 apply 的统一日志（去重，R3 反馈） */
              var auto = { type: l2.toCall > 0 ? 'fold' : 'check', timedOut: true, auto: true };
              res2Human(auto);
            }, turnMs);
            var act2 = await Promise.race([
              UI.getHumanAction(),
              new Promise(function (resH) { res2Human = resH; })
            ]);
            clearTimeout(humanTimer);
            UI.setTurnDeadline(0);
            clearInterval(humanHB);
            heartbeat();                           /* 玩家长考不是故障 */
            clearTimeout(thinkTimer);
            UI.clearThinking();
            if (act2.timedOut || act2.type === '__cancel') {   /* 超时代打：统一一行日志 */
              var l3 = table.legalActions(0);
              act2 = { type: l3.toCall > 0 ? 'fold' : 'check', auto: true,
                       note: '超时，自动' + (l3.toCall > 0 ? '弃牌' : '过牌') };
            }
            table.apply(act2);
            if (MP && MP.hosting()) MP.hostSync(table);
            if (act2.type === 'raise' || act2.type === 'call') {
              UI.flyChips(0);
              if (MP && MP.hosting()) MP.fxFly(0);
            }
            if (table.players[0].allIn) {
              SFX.allin();
              if (MP && MP.hosting()) MP.fxSfx('allin');
            }
            UI.render();
          }
          /* 弃牌后进入复盘模式：每条街刷新教练面板（对手范围与你的残余胜率） */
          if (table.players[0].folded && lastFoldBoard !== table.board.length) {
            lastFoldBoard = table.board.length;
            UI.updateCoach();
          }
        }
        document.body.classList.remove('runout');
        res = table.resolve();
        archiveHand(table, res);   /* P1-3：每手落盘 + 守恒断言 */
      } catch (err) {
        /* P0-A：任何异常都不许杀死循环——安全终止本手、可见报错、继续下一手 */
        handBroken = true;
        document.body.classList.remove('runout');
        var msg = err && err.forceKill ? '对局失去响应（看门狗中断）' : (err && err.message ? err.message : String(err));
        try { table.log('⚠ 本手异常中断：' + msg); UI.render(); } catch (e2) { /* ignore */ }
        if (window.UI && window.UI.appendError) window.UI.appendError('⚠ 本手异常中断，已自动恢复（' + msg + '）');
        console.error('[loop]', err);
      }
      document.body.classList.remove('runout');
      /* 结算与统计（异常手不计分，直接进入下一手） */
      var me = table.players[0];
      if (!handBroken) {
        var postRebuys = me.rebuys || 0;
        var injected = (postRebuys - preRebuys) * table.startStack;
        SESS.bb += (me.stack - preStack - injected) / table.bb;
        SESS.rebuys = postRebuys;
        recordSession();
        /* P2-E：玩家情绪气泡（净 ±50bb，重买不计） */
        var meNetNow = me.stack - preStack - injected;
        if (meNetNow <= -1000) UI.showEmote(0, pick(Characters.EMOTES.playerLose));
        else if (meNetNow >= 1000 && Math.random() < 0.8) UI.showEmote(0, pick(Characters.EMOTES.playerWin));
        // 赢池星爆
        var burstDone = {};
        res.pots.forEach(function (pr) { if (!pr.foldWin) pr.winners.forEach(function (i) { burstDone[i] = true; }); });
        Object.keys(burstDone).forEach(function (k) {
          var wi = +k;
          if (!table.players[wi].folded) {
            UI.winBurst(wi);
            if (MP && MP.hosting()) MP.fxBurst(wi);
          }
        });
        // 表情包：赢家必出得意、输家 60% 不甘——真人赢家也用角色声线发言（R4：覆盖率）
        // R5：同屏撞词去重（连续两手/双赢家不再复读同一句）
        // R5-施工 P1-7：分角色声线台词池；净亏 ≥50bb 的输家 100% 出安抚
        var quotes = [];
        var usedQuotes = {};
        function pickFresh(draw) {
          var t = draw(), guard = 0;
          while (usedQuotes[t] && guard++ < 4) t = draw();
          usedQuotes[t] = true;
          return t;
        }
        table.players.forEach(function (p) {
          var isW = res.pots.some(function (pr) { return pr.winners.indexOf(p.idx) >= 0; }) && !p.folded;
          var netP = (p.wonThisHand || 0) + (p.refundThisHand || 0) - p.totalCommitted;
          var bigLoss = netP <= -50 * table.bb;
          if (isW) {
            var et = pickFresh(function () { return Characters.voiceOf(p.charId, 'win'); });
            quotes.push({ name: p.name, txt: et });
            UI.showEmote(p.idx, et);
            if (MP && MP.hosting()) MP.fxEmote(p.idx, et);
          } else if (!p.folded && res.pots.some(function (pr) { return !pr.foldWin; }) &&
                     (bigLoss || Math.random() < 0.6)) {
            var et2 = bigLoss && Math.random() < 0.4
              ? pick(function () { return Characters.COMFORT[Math.floor(Math.random() * Characters.COMFORT.length)]; })
              : pickFresh(function () { return Characters.voiceOf(p.charId, 'lose'); });
            quotes.push({ name: p.name, txt: et2 });
            UI.showEmote(p.idx, et2);
            if (MP && MP.hosting()) MP.fxEmote(p.idx, et2);
          }
        });
        UI.render();
        await sleep(350);
      } else {
        await sleep(600);
      }
      /* P2-2+：弃牌进摊牌时，用 vsHand 复盘「若跟注到底」的结果 */
      if (!handBroken && me.folded && res.board.length === 5) {
        var widx = null;
        res.pots.forEach(function (pr) {
          if (!pr.foldWin) pr.winners.forEach(function (i) { if (widx === null && !table.players[i].folded) widx = i; });
        });
        if (widx !== null) {
          var eq = Equity.vsHand(me.hole, res.board, table.players[widx].hole, 500);
          extraNote = '复盘：若跟注到底，你的手牌胜率 <b>' + Math.round(eq * 100) + '%</b>——会' +
            (eq > 0.5 ? '<b style="color:#7ee2a8">赢</b>' : '<b style="color:#ff9d9d">输</b>');
        }
      }
      /* 好友房：摊牌消息（结果 + 揭牌 + 最终快照）先于弹窗广播。
       * 异常中断的手没有结算结果（res=null），直接进下一手，不弹结算窗。 */
      if (!handBroken) {
        if (MP && MP.hosting()) MP.hostShowdown(table, res, extraNote, quotes);
        UI.showShowdown(res, extraNote, quotes);
        await UI.waitNextHand();
        UI.hideOverlay();
      }
      await sleep(200);
    }
  }

  /* P0-A-4：看门狗（回访审计重构版）
   * 15 秒无心跳 → 给 table 打 forceKill；活着的主循环在下一个 await 返回点
   * 抛出中断、弃手不计分并自动恢复。不重建 loop（旧实现每次误报叠加僵尸循环）。
   * 连续 3 次无自愈（循环确实已死的最后手段）才重建。 */
  function startWatchdog() {
    setInterval(function () {
      if (!table) return;
      var stale = loopRunning && Date.now() - lastTick > 15000;
      if (!stale) { staleStrikes = 0; return; }
      staleStrikes++;
      table.forceKill = true;
      heartbeat();                                       /* 防止连发 */
      if (staleStrikes >= 3 && Date.now() - lastRecoverWarn > 30000) {
        /* 循环真的死了（forceKill 无人消费）→ 最后手段重建 */
        lastRecoverWarn = Date.now();
        staleStrikes = 0;
        loopRunning = false;
        try { table.log('⚠ 循环失去响应，已强制恢复'); } catch (e) { /* ignore */ }
        if (window.UI && window.UI.appendError) window.UI.appendError('检测到循环失去响应，已自动恢复');
        loop();
      }
    }, 5000);
  }

  var gameStarted = false;

  /* 雀魂式大厅：角色舞台/服装/部员切换/顶栏统计（js/lobby.js） */
  if (window.Lobby && window.Lobby.init) window.Lobby.init();

  /* 进入牌局公共路径：初始化 UI + 等 PNG 资产扫描后重绘 */
  function enterGame() {
    UI.init(table);
    UI.render();
    if (window.Portraits && window.Portraits.scan) {
      window.Portraits.scan().then(function () { UI.render(); });
    }
  }

  /* 单机开局公共路径：角色/服装 = 大厅看板娘设置（localStorage gto-char/gto-costume-map），不再二次选择 */
  function startSoloGame(seats) {
    if (gameStarted) return;
    gameStarted = true;
    table = new Table({ seatCount: seats, sb: 10, bb: 20, startStack: 2000, runoutMode: true });
    Characters.assign(table, 0);  // 玩家用看板娘角色，机器人分配其余角色
    UI.setCoachAvailable(true);   // 单机对机器人：教练可用
    UI.hideStart();
    enterGame();
    loop();
  }
  document.getElementById('btn-start').addEventListener('click', function () {
    var seats = parseInt(document.querySelector('input[name="seats"]:checked').value, 10);
    startSoloGame(seats);
  });

  /* 好友房·房主开局（mp.js 大厅「开始牌局」回调）：
   * 权威引擎在本地跑，客人在远端渲染快照 + 回传动作 */
  function startHostGame() {
    if (gameStarted) return;
    gameStarted = true;
    table = new Table({ seatCount: MP.seatCount(), sb: 10, bb: 20, startStack: 2000, runoutMode: true });
    MP.hostSetup(table);          // 名单填座：真人客人 + GTO 部员补空位
    UI.setCoachAvailable(false);  // 多人局对真人禁用教练（公平性）
    MP.closeLobby();
    enterGame();
    loop();
  }
  window.MpGame = { startHost: startHostGame };

  /* 🏠 返回大厅：联机时先干净退房（对方立刻收到断线通知），再回主界面 */
  document.getElementById('btn-home').addEventListener('click', function () {
    try { if (window.MP && window.MP.leaveIfAny) window.MP.leaveIfAny(); } catch (e) { /* noop */ }
    location.reload();
  });

  /* P0-A-1：全局错误可见化 */
  window.addEventListener('error', function (e) {
    if (window.UI && window.UI.appendError) window.UI.appendError('运行时错误：' + (e.message || '未知'));
  });
  window.addEventListener('unhandledrejection', function (e) {
    if (window.UI && window.UI.appendError) window.UI.appendError('异步错误：' + (e.reason || '未知'));
  });

  /* 手机性能修复：小屏/触屏设备把机器人蒙特卡洛迭代降到 45%
   * （桌面一次 ~35ms，中端手机 ~200-300ms 且阻塞主线程——每个机器人行动卡一下） */
  (function () {
    try {
      var small = window.matchMedia && window.matchMedia('(max-width: 860px)').matches;
      var touch = (navigator.maxTouchPoints || 0) > 0 && 'ontouchstart' in window;
      if ((small || touch) && window.GTO && window.GTO.setPerf) window.GTO.setPerf(0.45);
    } catch (e) { /* noop */ }
  })();

  UI.setSessionStats(SESS);   /* P1-D：启动即恢复历史统计 */
  /* Step 2：用户活跃度追踪（pointerdown/keydown/wheel 任一即视为活跃） */
  ['pointerdown', 'keydown', 'wheel'].forEach(function (evt) {
    document.addEventListener(evt, function () { lastUserInputAt = Date.now(); }, { passive: true });
  });

  window.__waitHeartbeat = heartbeat;   /* Step 2：手间等待期心跳（ui.js waitNextHand 用） */

  /* 手游适配：首次手势解锁 AudioContext（移动端 WebView 初始挂起，不解锁=可能全程无声）；
   * 全局按钮点按音——行动区/表情条自带专属音效，排除防双响 */
  (function () {
    var unlocked = false;
    document.addEventListener('pointerdown', function (e) {
      if (!SFX) return;
      if (!unlocked) { SFX.unlock(); unlocked = true; }
      var t = e.target;
      if (!t || !t.closest) return;
      if (t.closest('#action-controls, #presets, #emote-strip, #emote-fab')) return;
      if (t.closest('button')) SFX.click();
    }, { passive: true, capture: true });
  })();

  (function () {   /* 版本标识: 截图判版本, 不再靠猜 */
    try {
      var foot = document.querySelector('#landing .landing-foot');
      if (foot) foot.insertAdjacentHTML('beforeend', ' <span class="ver">v' + APP_VERSION + '</span>');
      var brand = document.querySelector('#topbar .brand');
      if (brand) brand.insertAdjacentHTML('beforeend', ' <span class="ver">v' + APP_VERSION + '</span>');
    } catch (e) { /* noop */ }
  })();

  UI.wireTopbar();
  UI.wireCharSelect();
  startWatchdog();

  /* 大厅三板块 */
  document.getElementById('mc-train').addEventListener('click', function () {
    document.getElementById('landing').classList.add('hidden');
    /* 雀魂式：看板娘/服装已在大厅选定，直接开局（桌型在大厅选择，默认 6 人） */
    var seats = 6;
    try { seats = parseInt(window.localStorage.getItem('gto-seats') || '6', 10) || 6; } catch (e) { /* noop */ }
    startSoloGame(seats);
  });
  document.getElementById('mc-multi').addEventListener('click', function () {
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('multi-modal').classList.remove('hidden');
  });
  document.getElementById('mc-data').addEventListener('click', function () {
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('data-modal').classList.remove('hidden');
    document.body.classList.add('data-open');   /* R6：顶栏降权，重新开局不可误点 */
    if (window.DataPage && window.DataPage.render) window.DataPage.render();
    wireDataScrollHint();
  });
  /* 滚动提示：内容溢出才显示，距底 <80px 淡出（视觉评审发现：横屏玩家不知道下面还有统计卡） */
  function wireDataScrollHint() {
    var card = document.querySelector('#data-modal #start-card') || document.getElementById('data-modal');
    var body = document.getElementById('data-body');
    if (!card || !body || document.getElementById('data-scroll-hint')) return;
    var hint = document.createElement('div');
    hint.id = 'data-scroll-hint';
    hint.textContent = '下滑查看统计明细 ▾';
    if (card.style.position !== 'absolute' && card.style.position !== 'relative') card.style.position = 'relative';
    card.appendChild(hint);
    function toggle() {
      var over = body.scrollHeight > body.clientHeight + 20;
      var nearBottom = body.scrollTop + body.clientHeight >= body.scrollHeight - 80;
      hint.classList.toggle('gone', !over || nearBottom);
    }
    body.addEventListener('scroll', toggle, { passive: true });
    setTimeout(toggle, 200);
  }
  document.getElementById('btn-data-back').addEventListener('click', function () {
    document.getElementById('data-modal').classList.add('hidden');
    document.body.classList.remove('data-open');
    document.getElementById('landing').classList.remove('hidden');
  });
})();
