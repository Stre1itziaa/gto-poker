/* mp.js — 好友房联机（PeerJS P2P · 房主权威架构）
 *
 * 分工：
 *   房主  跑唯一一份权威引擎（main.js 的 loop），每步把「脱敏快照」发给每个客人
 *         ——快照旋转到收件人视角（收件人永远在 0 号位），只带收件人自己的底牌。
 *   客人  零引擎逻辑：收到快照 → 更新「影子桌」→ 复用现有 UI.render() 渲染；
 *         轮到自己时走原有按钮/滑条 → 把动作发回房主。
 *   空位  由 GTO 部员机器人补齐（房主端决策，客人端只是渲染）。
 *
 * 防作弊面：客人端从头到尾看不到别人的底牌（摊牌时才随 showdown 消息揭示）。
 *
 * 纯逻辑部分（snapFor / buildShadow / 旋转映射）可在 Node 无头测试：
 *   MP.__test.snapFor(table, youAbs) / MP.__test.buildShadow(meta)
 */
(function (root) {
  'use strict';
  var Net = root.Net, Portraits = root.Portraits;
  var CHARS = Portraits ? Portraits.ALL : [];

  /* 昵称等对端字符串进 innerHTML 前必须全量转义（只拦 `<` 挡不住属性上下文） */
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var PROTO_V = 1;
  var TURN_MS = 45000;          // 客人行动超时：自动过牌/弃牌
  var CODE_RE = /^[A-Z2-9]{4,8}$/;

  var ROLE = '';                // '' | 'host' | 'guest'
  var st = {
    phase: 'idle',              // idle | lobby | game
    seats: 6,
    myName: '', myChar: '',
    roomCode: '',
    roster: [],                 // 房主：权威名单；客人：镜像（仅 name/charId/isHost）
    youAbs: 0, n: 0,
    handId: 0,
    handStartStack: null,       // 本手开始时（盲注前）自己的筹码
    vpipDone: false, pfrDone: false,
    uiReady: false, deciding: false,
    boardLen: -1,
    sess: { hands: 0, bb: 0.0, vpip: 0, pfr: 0, rebuys: 0 }
  };
  var shadow = null;            // 客人端影子桌（字段被快照原地更新，DOM 座位不重建）
  var hostPending = null;       // 房主等待中的客人动作 {seat, table, resolve, timer}
  var earlyActs = {};           // peerId → 先于 hostPending 到达的动作（快照先发、等待后挂，竞态缓冲）
  var deadSeats = {};           // 房主：断线座位 → 自动过牌/弃牌代打
  var seatPeer = [];            // 房主：绝对座位 → 客人 peerId（null=房主/机器人）
  var lastLogSent = 0;          // 房主：日志已发长度（增量推送）
  var selChar = null;           // 大厅角色选择
  var joinTimer = null;         // 客人：加入超时兜底（8s 无响应必须给反馈）
  var autoStartTimer = null;    // 房主：全员就绪倒计时自动开局
  var autoStartLeft = 0;
  var lobbyTick = null;         // 大厅状态行秒级刷新（客人等待秒数/房主倒计时）
  var lobbyShownAt = 0;

  function sanitizeEmote(s) {
    s = String(s || '').replace(/[\u0000-\u001f<>]/g, '').trim().slice(0, 12);
    return s;
  }

  /* ---------- 小工具 ---------- */
  function $(id) { return root.document ? root.document.getElementById(id) : null; }
  function rotIdx(abs, you, n) { return (abs - you + n) % n; }
  function toast(text) {
    if (root.UI && root.UI.appendError) root.UI.appendError(text);
    else setMpStatus(text);
  }
  function sanitizeName(s) {
    s = String(s || '').replace(/[\u0000-\u001f<>]/g, '').trim().slice(0, 8);
    return s || '玩家';
  }

  /* ================================================================
   *  快照构建（房主端，纯函数可测试）
   * ================================================================ */
  function snapFor(table, youAbs, reveal) {
    var n = table.players.length;
    var actorAbs = (!table.handOver && !table.awaitingRunout && table.currentActor())
      ? table.actorIdx : -1;
    var players = [];
    for (var i = 0; i < n; i++) {
      var abs = (youAbs + i) % n;
      var p = table.players[abs];
      var showHole = (abs === youAbs) || (!!reveal && !p.folded && p.hole.length === 2);
      players.push({
        name: p.name, isBot: !!p.isBot, charId: p.charId || '',
        stack: p.stack, rebuys: p.rebuys || 0,
        hole: showHole ? p.hole.slice() : [],
        folded: !!p.folded, allIn: !!p.allIn, spoke: !!p.spoke,
        streetCommitted: p.streetCommitted, totalCommitted: p.totalCommitted,
        lastAction: p.lastAction || '', wonThisHand: p.wonThisHand || 0,
        refundThisHand: p.refundThisHand || 0,
        idle: !!deadSeats[abs],      /* Step 5：离席/代打座位标记 */
        score: showHole ? (p.score || 0) : 0
      });
    }
    var posNames = [];
    for (var j = 0; j < n; j++) posNames.push(table.positionName((youAbs + j) % n));
    return {
      t: 'snap', v: PROTO_V,
      handId: table.handNo,
      n: n, sb: table.sb, bb: table.bb,
      youAbs: youAbs,
      street: table.street,
      board: table.board.slice(),
      handOver: !!table.handOver, awaitingRunout: !!table.awaitingRunout,
      turnEndsAt: (function () {
        /* Step 2：按行动者真实钟广播——远端真人 45s / 房主真人（AFK 已降 8s）/ 机器人不显示倒计时 */
        if (actorAbs < 0) return 0;
        if (seatPeer[actorAbs]) return Date.now() + TURN_MS;
        if (actorAbs === 0 && table.humanTurnEndsAt) return Math.max(table.humanTurnEndsAt, Date.now());
        return 0;
      })(),
      buttonRot: rotIdx(table.buttonIdx, youAbs, n),
      actorRot: actorAbs < 0 ? -1 : rotIdx(actorAbs, youAbs, n),
      currentBet: table.currentBet || 0, minRaise: table.minRaiseSize || table.bb,
      la: (actorAbs === youAbs) ? table.legalActions(youAbs) : null,
      posNames: posNames,
      players: players,
      actionHistory: table.actionHistory.map(function (a) {
        return { playerIdx: rotIdx(a.playerIdx, youAbs, n), street: a.street,
          type: a.type, to: a.to, added: a.added, frac: a.frac, auto: !!a.auto };
      }),
      logFrom: lastLogSent,
      logTail: table.logLines.slice(lastLogSent)
    };
  }

  /* ================================================================
   *  影子桌（客人端）：纯字段 + 少量方法，兼容 UI / 教练的全部读取面
   * ================================================================ */
  function buildShadow(meta) {
    var sh = {
      sb: meta.sb, bb: meta.bb, startStack: 2000,
      players: [], board: meta.board.slice(), street: meta.street,
      handNo: meta.handId, handOver: meta.handOver, awaitingRunout: meta.awaitingRunout,
      buttonIdx: meta.buttonRot, actorIdx: meta.actorRot,
      currentBet: meta.currentBet, minRaiseSize: meta.minRaise,
      actionHistory: meta.actionHistory, logLines: [],
      resolved: null, _la: meta.la || null, _pos: meta.posNames,
      potTotal: function () {
        var s = 0;
        this.players.forEach(function (p) { s += p.totalCommitted; });
        return s;
      },
      currentActor: function () { return this.players[this.actorIdx]; },
      positionName: function (i) { return this._pos[i]; },
      legalActions: function (idx) {
        if (idx !== 0 || !this._la) {
          var p = this.players[idx] || this.players[0];
          var toCall = Math.max(0, this.currentBet - p.streetCommitted);
          var maxTo = p.streetCommitted + p.stack;
          var minTo = this.currentBet === 0
            ? Math.min(maxTo, this.bb)
            : Math.min(maxTo, this.currentBet + this.minRaiseSize);
          return { toCall: toCall, canCheck: toCall <= 0,
            canRaise: maxTo > this.currentBet, minTo: minTo, maxTo: maxTo };
        }
        return this._la;
      },
      log: function () { /* 客人端日志只来自房主推送 */ },
      spr: function (idx) {
        var p = this.players[idx];
        return (p.stack + p.streetCommitted) / Math.max(1, this.potTotal());
      }
    };
    meta.players.forEach(function (rp, i) {
      sh.players.push({
        idx: i, name: i === 0 ? rp.name + '（你）' : rp.name,
        isBot: rp.isBot, charId: rp.charId,
        stack: rp.stack, rebuys: rp.rebuys || 0,
        hole: (rp.hole || []).slice(),
        folded: rp.folded, allIn: rp.allIn, spoke: rp.spoke,
        streetCommitted: rp.streetCommitted, totalCommitted: rp.totalCommitted,
        lastAction: rp.lastAction, score: rp.score || 0,
        wonThisHand: rp.wonThisHand || 0, refundThisHand: rp.refundThisHand || 0,
        aggro: 1, bluff: 1
      });
    });
    return sh;
  }

  /* ================================================================
   *  房主端控制
   * ================================================================ */
  function hosting() { return ROLE === 'host' && st.phase === 'game'; }
  function seatByPeer(pid) {
    for (var i = 0; i < seatPeer.length; i++) if (seatPeer[i] === pid) return i;
    return -1;
  }
  function charTaken(cid) {
    return st.roster.some(function (r) { return r.charId === cid; });
  }
  function firstFreeChar() {
    for (var i = 0; i < CHARS.length; i++) if (!charTaken(CHARS[i].id)) return CHARS[i].id;
    return CHARS[0].id;
  }

  function startHostRoom() {
    ROLE = 'host';
    st.roster = [{ name: st.myName, charId: st.myChar, isHost: true, ready: true, peer: 'me' }];
    setMpStatus('正在创建房间…');
    Net.host('', {
      onReady: function (code) {
        st.roomCode = code;
        st.phase = 'lobby';
        setMpStatus('');
        showLobby(true);
        renderLobbyList();
      },
      onGuestJoin: function (pid, meta) {
        function reject(msg, extra) {
          var m = { t: msg };
          if (extra) for (var k in extra) m[k] = extra[k];
          Net.sendTo(pid, m);
          setTimeout(function () {
            var c = Net.connections()[pid];
            if (c) try { c.close(); } catch (e) { /* noop */ }
          }, 350);
        }
        if (st.phase === 'game') return reject('busy', { hand: st.hostHandNo || 0, seats: st.roster.length });
        /* P1-4：断线座位保留期内，同名昵称直接回到原座（角色与准备状态原样保留） */
        var nm = sanitizeName(meta && meta.name);
        var rejoin = -1;
        st.roster.forEach(function (r, k) { if (r.off && r.name === nm) rejoin = k; });
        if (rejoin > 0) {
          var r0 = st.roster[rejoin];
          r0.off = false; r0.offAt = 0; r0.peer = pid;
          renderLobbyList();
          broadcastLobby();
          return;
        }
        if (st.roster.length >= st.seats) return reject('full', { seats: st.seats });
        /* S1：charId 必须在内置角色白名单内，否则回退分配（堵属性注入 XSS） */
        var cid = meta && meta.charId;
        var cidOk = false;
        for (var ci = 0; ci < CHARS.length; ci++) if (CHARS[ci].id === cid) { cidOk = true; break; }
        if (!cidOk || charTaken(cid)) cid = firstFreeChar();
        st.roster.push({ peer: pid, name: nm, charId: cid, isHost: false, ready: false });
        renderLobbyList();
        broadcastLobby();
      },
      onGuestLeave: function (pid) {
        var i = -1;
        st.roster.forEach(function (r, k) { if (r.peer === pid) i = k; });
        if (i < 0) return;
        var nm = st.roster[i].name;
        if (st.phase === 'game') {
          st.roster.splice(i, 1);
          var seat = seatByPeer(pid);
          if (seat >= 0 && !deadSeats[seat]) {
            deadSeats[seat] = true;
            if (root.UI && root.UI.appendError) root.UI.appendError(nm + ' 断线，剩余手由代打接管');
            if (hostPending && hostPending.seat === seat) {
              var l = hostPending.table.legalActions(seat);
              hostPending.resolve({ type: l.toCall > 0 ? 'fold' : 'check' });
            }
          }
          /* 僵尸局提醒：真人全部走光就别无声空转了 */
          var liveGuests = st.roster.filter(function (r) { return !r.isHost; }).length;
          if (liveGuests === 0 && root.UI && root.UI.appendError) {
            root.UI.appendError('所有客人都离开了；可继续与部员对打，或点「🏠 大厅」结束牌局');
          }
        } else {
          /* P1-4：大厅断线不删人——保留座位 120s 等重连，期间该座位显示离线 */
          var entry = st.roster[i];
          entry.off = true;
          entry.offAt = Date.now();
          entry.peer = null;
          renderLobbyList();
          broadcastLobby();
        }
      },
      onData: hostOnData,
      onError: function (e) { setMpStatus('连接出错：' + (e && (e.type || e.message) || '未知')); }
    });
  }

  function shadowTable_ref() { return shadow; }

  function hostOnData(pid, raw) {
    var d;
    try { d = JSON.parse(raw); } catch (e) { return; }
    if (!d || typeof d !== 'object') return;
    if (d.t === 'act') {
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
    } else if (d.t === 'ready' && st.phase === 'lobby') {
      var i = -1;
      st.roster.forEach(function (r, k) { if (r.peer === pid) i = k; });
      if (i > 0) {
        st.roster[i].ready = !!d.v;
        renderLobbyList();
        broadcastLobby();
      }
    } else if (d.t === 'emote' && st.phase === 'game') {      var seat2 = seatByPeer(pid);
      var txt2 = sanitizeEmote(d.txt);
      if (seat2 >= 0 && txt2 && root.UI && root.UI.showEmote) {
        root.UI.showEmote(seat2, txt2);   // 房主本地也看得到
        fxEmote(seat2, txt2);             // 转播给所有客人（fx 内部自带 hosting 判断）
      }
    } else if (d.t === 'next' && st.phase === 'game') {
      /* R6-R3：客人点「下一局」→ 房主代点同一按钮（复用 host 的续局路径） */
      var bn3 = root.document.getElementById('btn-next');
      var ov3 = root.document.getElementById('overlay');
      if (bn3 && ov3 && !ov3.classList.contains('hidden')) bn3.click();
    }
  }

  /* main.js 在 startHand 前后调用：给每个在座客人发「本手开始」快照 */
  function hostHandStart(table) {
    if (!hosting()) return;
    lastLogSent = 0;                      // 新一手日志从头推（含「第 N 手」分隔线）
    earlyActs = {};                       // 新一手丢弃上一手的迟到动作（防串手）
    st.hostHandNo = table.handNo;         // 供「房间已开局（第 N 手）」拒绝文案
    syncSnapshots(table, false);
  }

  function hostSync(table) { if (hosting()) syncSnapshots(table, false); }

  function syncSnapshots(table, reveal) {
    var conns = Net.connections();
    for (var seat = 0; seat < seatPeer.length; seat++) {
      var pid = seatPeer[seat];
      if (!pid || deadSeats[seat]) continue;
      var c = conns[pid];
      if (!c || !c.open) continue;
      Net.sendTo(pid, snapFor(table, seat, reveal));
    }
    lastLogSent = table.logLines.length;
  }

  function hostThink(abs, on) {
    if (hosting()) Net.broadcast({ t: 'fx', k: 'think', abs: abs, on: !!on });
  }
  function fxFly(abs) { if (hosting()) Net.broadcast({ t: 'fx', k: 'fly', abs: abs }); }
  function fxBurst(abs) { if (hosting()) Net.broadcast({ t: 'fx', k: 'burst', abs: abs }); }
  function fxEmote(abs, txt) { if (hosting()) Net.broadcast({ t: 'fx', k: 'emote', abs: abs, txt: txt }); }
  function fxSfx(k) { if (hosting()) Net.broadcast({ t: 'fx', k: 'sfx', name: k }); }

  function isRemoteSeat(abs) { return hosting() && !!seatPeer[abs]; }

  /* 房主等客人动作（main.js loop 调用）；断线座位/超时自动代打。
   * 进等待前先消费竞态缓冲（客人秒点先到的动作）。 */
  function normalizeAct(table, seat, d) {
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
  }

  function nextRemoteAction(table, seat) {
    return new Promise(function (resolve) {
      var pid = seatPeer[seat];
      if (pid && earlyActs[pid]) {
        var buf = earlyActs[pid];
        delete earlyActs[pid];
        if (buf.hand === table.handNo) { resolve(normalizeAct(table, seat, buf)); return; }
        /* 手号不匹配 = 旧手迟到动作，丢弃后继续走正常等待 */
      }
      var la = table.legalActions(seat);
      if (deadSeats[seat]) { resolve({ type: la.toCall > 0 ? 'fold' : 'check' }); return; }
      var done = false;
      function finish(act) {
        if (done) return;
        done = true;
        if (hostPending && hostPending.seat === seat) {
          clearTimeout(hostPending.timer);
          hostPending = null;
        }
        resolve(act);
      }
      hostPending = {
        seat: seat, table: table, resolve: finish,
        timer: setTimeout(function () {
          /* 不另写 ⏱ 行：timeout 标记让 main.js 统一记一行「弃牌　↳ 超时代打」 */
          try {
            var pid2 = seatPeer[seat];
            if (pid2) Net.sendTo(pid2, { t: 'timedout' });   // 让超时的客人知道发生了什么
          } catch (e) { /* noop */ }
          finish({ type: table.legalActions(seat).toCall > 0 ? 'fold' : 'check', timeout: true });
        }, TURN_MS)
      };
    });
  }

  /* 摊牌：先推「派彩后」的最终快照（客人端净数/会话统计依赖终局筹码），
   * 再广播结果 + 揭牌。extraNote 是房主视角的复盘，只给房主本地弹窗用。 */
  function hostShowdown(table, res, extraNote, quotes) {
    if (!hosting()) return;
    /* 暗牌保护（muck）：无人跟注全弃收池时不亮牌——亮牌权是牌手的基本权利 */
    var anyShowdown = res.pots.some(function (pr) { return !pr.foldWin && !pr.uncalled; });
    var reveal = anyShowdown ? table.players.filter(function (p) { return !p.folded && p.hole.length === 2; })
      .map(function (p) { return { abs: p.idx, hole: p.hole.slice(), score: p.score }; }) : [];
    syncSnapshots(table, reveal.length > 0);
    Net.broadcast({
      t: 'showdown',
      res: { pots: res.pots, board: res.board.slice() },
      reveal: reveal,
      quotes: quotes || [],
      extraNote: ''
    });
  }

  /* 开局：把大厅名单填进权威桌面（房主=0 号位，其后按加入顺序，空位补机器人） */
  function hostSetup(table) {
    st.phase = 'game';
    seatPeer = []; deadSeats = {}; earlyActs = {}; lastLogSent = 0;
    var usedChars = {};
    st.roster.forEach(function (r) { usedChars[r.charId] = true; });
    var botPool = CHARS.filter(function (c) { return !usedChars[c.id]; });
    for (var i = 0; i < table.players.length; i++) {
      var p = table.players[i];
      if (i < st.roster.length) {
        var r = st.roster[i];
        p.isBot = false;
        p.name = r.name;
        p.charId = r.charId;
        p.aggro = 1; p.bluff = 1;
        seatPeer[i] = (i === 0) ? null : r.peer;   // 0 号位=房主本人
      } else {
        var c = botPool.length ? botPool[(i - st.roster.length) % botPool.length] : CHARS[i % CHARS.length];
        p.isBot = true;
        p.name = c.name;
        p.charId = c.id;
        p.aggro = c.aggro || 1;
        p.bluff = c.bluff || 1;
        seatPeer[i] = null;
      }
    }
  }

  /* ================================================================
   *  客人端控制
   * ================================================================ */
  function startJoinRoom(code) {
    if (Net.selfId()) { try { Net.destroy(); } catch (e) { /* noop */ } }  // 二次加入前清掉旧 peer
    ROLE = 'guest';
    setJoinBusy(true);
    setMpStatus('正在连接房间 ' + code + ' …');
    var settled = false;
    if (joinTimer) clearTimeout(joinTimer);
    joinTimer = setTimeout(function () {
      if (settled) return;
      settled = true;
      setJoinBusy(false);
      setMpStatus('连接超时——请双方刷新后重试；若反复失败，多半是两边网络类型冲突（如都在校园网/公司网），换个网络（手机热点）再试', true);
    }, 15000);
    Net.guest(code, {
      onConnected: function () {
        /* 防幻影大厅：连接成功≠入座成功，等到房主第一份名单广播再进大厅 */
        st.phase = 'lobby';
        st.roomCode = code;
        setMpStatus('已连接，等待房间信息…');
      },
      onData: function (_tag, raw) { guestOnData(raw); },
      onDisconnected: function () {
        if (st.phase === 'game') {
          toast('与房主的连接断开，即将返回大厅…');
          setTimeout(function () { root.location.reload(); }, 2500);
        } else {
          leaveRoom();
          setMpStatus('与房主的连接断开', true);
        }
      },
      onError: function (e) {
        var t = e && e.type || '';
        if (!settled) {
          settled = true;
          if (joinTimer) clearTimeout(joinTimer);
          setJoinBusy(false);
        }
        setMpStatus(t === 'peer-unavailable' ? '找不到房间 ' + code + '，请核对房码' : '连接出错：' + (t || '未知'), true);
      }
    }, { name: st.myName, charId: st.myChar });
  }

  function guestOnData(raw) {
    var d;
    try { d = JSON.parse(raw); } catch (e) { return; }
    if (!d || typeof d !== 'object') return;
    switch (d.t) {
      case 'lobby':
        st.roster = d.players || [];
        st.seats = d.seats || st.seats;
        st.autoLeft = d.auto || 0;
        if (!st.lobbyShown) {              // 第一份名单 = 真正入座
          st.lobbyShown = true;
          if (joinTimer) clearTimeout(joinTimer);
          setJoinBusy(false);
          setMpStatus('');
          showLobby(false);
        }
        renderLobbyList();
        break;
      case 'snap': applySnap(d); break;
      case 'showdown': applyShowdown(d); break;
      case 'fx': applyFx(d); break;
      case 'timedout':
        toast('⏱ 你超时了，本回合已自动代打');
        st.autoThisHand = true;   /* Step 5：本手含代打，留档打标 */
        if (st.deciding) {
          st.deciding = false;
          if (root.UI && root.UI.cancelDecision) root.UI.cancelDecision();
        }
        break;
      case 'busy':
        settledJoin();
        leaveRoom();
        setMpStatus(d.hand ? ('房间已开局并自动续局中（正打第 ' + d.hand + ' 手），暂无法加入；房主可回大厅重开新局') : '房间已开局，暂无法加入', true);
        break;
      case 'full':
        settledJoin();
        leaveRoom();
        setMpStatus('房间已满（' + (d.seats || 6) + '/' + (d.seats || 6) + '），下次早点来', true);
        break;
    }
  }

  function applyFx(d) {
    if (!st.uiReady) return;
    var loc = rotIdx(d.abs, st.youAbs, st.n);
    if (d.k === 'emote') root.UI.showEmote(loc, d.txt);
    else if (d.k === 'fly') root.UI.flyChips(loc);
    else if (d.k === 'burst') root.UI.winBurst(loc);
    else if (d.k === 'think') root.UI.setThinking(d.on ? loc : -1);
    else if (d.k === 'sfx' && d.name === 'allin' && root.SFX) root.SFX.allin();
  }

  function enterGameView(d) {
    st.uiReady = true;
    st.phase = 'game';
    shadow = buildShadow(d);
    if (root.UI.setCoachAvailable) root.UI.setCoachAvailable(false);  // 多人局禁教练
    var cb0 = root.document.getElementById('coach-body');
    if (cb0) cb0.innerHTML = '<div class="muted">多人局为公平起见不提供教练——结束后去「数据分析」页复盘。</div>';
    root.UI.init(shadow);
    var rb = root.document.getElementById('btn-restart');
    if (rb) rb.style.display = 'none';     // 客人没有「重新开局」（那是单机/房主动作）
    if (st.gameTick) clearInterval(st.gameTick);
    st.gameTick = setInterval(function () {
      if (!st.deciding) refreshActionHint();
      /* 批1-T1.8：读秒环由 ui.js 的 setTurnDeadline + 内部 tick 统一驱动，此处不再直写 */
    }, 1000);
    hideMpModals();
    if (root.Portraits && root.Portraits.scan) {
      root.Portraits.scan().then(function () { root.UI.render(); });
    }
  }

  /* 提示条：第 N 手 · 街名 · 等待谁行动 · 剩余秒数（区分长考与挂机） */
  function refreshActionHint() {
    if (!st.uiReady || !shadow) return;
    var ah = root.document.getElementById('action-hint');
    if (!ah) return;
    if (shadow.handOver) { ah.textContent = '本手结束，等待下一局…'; return; }
    if (shadow.awaitingRunout) { ah.textContent = '全下跑马中…'; return; }
    var left = st.turnEndsAt ? Math.max(0, Math.ceil((st.turnEndsAt - Date.now()) / 1000)) : 0;
    var suffix = st.turnEndsAt ? (' · 剩 ' + left + 's' + (left <= 10 ? ' ⏰' : '')) : '';
    var actorName = (shadow.actorIdx >= 0 && shadow.players[shadow.actorIdx]) ? shadow.players[shadow.actorIdx].name : '';
    var streetZh = { preflop: '翻前', flop: '翻牌', turn: '转牌', river: '河牌', showdown: '摊牌' }[shadow.street] || shadow.street;
    var me = shadow.actorIdx === 0;
    ah.textContent = '第 ' + shadow.handNo + ' 手 · ' + streetZh + ' · ' +
      (me ? '轮到你行动' : '等待 ' + actorName + ' 行动') + suffix;
    ah.classList.remove('hidden');
  }

  function applySnap(d) {
    st.youAbs = d.youAbs;
    st.n = d.n;
    if (!st.uiReady) enterGameView(d);
    /* 状态回收：上一手挂起的决策若已不再是「轮到我」，立即收回控件（防永久卡死） */
    if (st.deciding && !(d.actorRot === 0 && !d.handOver && !d.awaitingRunout)) {
      st.deciding = false;
      if (root.UI && root.UI.cancelDecision) root.UI.cancelDecision();
    }
    st.turnEndsAt = d.turnEndsAt || 0;
    if (d.handId !== st.handId) {
      st.handId = d.handId;
      root.UI.hideOverlay();
      root.document.body.classList.remove('runout');
      var cb = root.document.getElementById('coach-body');
      if (cb) {
        cb.innerHTML = ROLE === 'guest'
          ? '<div class="muted">多人局为公平起见已禁用教练——靠自己的范围打，骑士。</div>'
          : '<div class="muted">轮到你行动时，这里会给出基于范围与频率的建议。</div>';
      }
      /* 盲注前的起始筹码 = 快照筹码 + 本街已投入（盲注额） */
      st.handStartStack = d.players[0].stack + d.players[0].streetCommitted;
      st.vpipDone = false;
      st.pfrDone = false;
      st.autoThisHand = false;   /* Step 5：新一手重置代打标记 */
      st.boardLen = -1;
    }
    var i;
    for (i = 0; i < d.logTail.length; i++) shadow.logLines.push(d.logTail[i]);
    shadow.board = d.board.slice();
    shadow.street = d.street;
    shadow.handNo = d.handId;
    shadow.handOver = d.handOver;
    shadow.awaitingRunout = d.awaitingRunout;
    shadow.buttonIdx = d.buttonRot;
    shadow.actorIdx = d.actorRot;
    shadow.currentBet = d.currentBet;
    shadow.minRaiseSize = d.minRaise;
    shadow.actionHistory = d.actionHistory;
    shadow._la = d.la;
    shadow._pos = d.posNames;
    shadow.resolved = null;
    d.players.forEach(function (rp, k) {
      var p = shadow.players[k];
      p.name = k === 0 ? rp.name + '（你）' : rp.name;
      p.isBot = rp.isBot; p.charId = rp.charId;
      p.stack = rp.stack; p.rebuys = rp.rebuys || 0;
      p.hole = (rp.hole || []).slice();
      p.folded = rp.folded; p.allIn = rp.allIn; p.spoke = rp.spoke;
      p.streetCommitted = rp.streetCommitted; p.totalCommitted = rp.totalCommitted;
      p.lastAction = rp.lastAction; p.wonThisHand = rp.wonThisHand || 0;
      p.refundThisHand = rp.refundThisHand || 0;
      p.idle = !!rp.idle;   /* Step 5：离席座位标记透传给客人端 */
      p.score = rp.score || 0;
    });
    d.actionHistory.forEach(function (a) {
      if (a.street === 'preflop' && a.playerIdx === 0) {
        if (a.type === 'call' || a.type === 'raise') st.vpipDone = true;
        if (a.type === 'raise') st.pfrDone = true;
      }
    });
    var boardChanged = shadow.board.length !== st.boardLen;
    if (boardChanged) {
      st.boardLen = shadow.board.length;
      if (root.SFX) root.SFX.deal();
      if (shadow.players[0].folded && root.UI.updateCoach) root.UI.updateCoach();
    }
    root.document.body.classList.toggle('runout', !!d.awaitingRunout);
    root.UI.setThinking(-1);
    root.UI.render();
    /* 客人端行动提示条：随快照更新 + 每秒读秒（gameTick 驱动） */
    if (!st.deciding) refreshActionHint();
    if (!d.handOver && !d.awaitingRunout && d.actorRot === 0 && !st.deciding) {
      beginMyDecision();
    }
  }

  function beginMyDecision() {
    st.deciding = true;
    root.UI.beginDecision();
    root.UI.updateCoach();
    root.UI.render();
    if (root.UI.setTurnDeadline) root.UI.setTurnDeadline(st.turnEndsAt || (Date.now() + TURN_MS));
    root.UI.getHumanAction().then(function (act) {
      st.deciding = false;
      if (root.UI.setTurnDeadline) root.UI.setTurnDeadline(0);
      if (act.type === '__cancel') return;   // 被回收（超时/新手）——不发动作
      Net.sendTo('host', { t: 'act', hand: st.handId, type: act.type, to: act.to });   /* R1：带手号防串手 */
    });
  }

  function applyShowdown(d) {
    if (!st.uiReady) return;
    var you = st.youAbs, n = st.n;
    (d.reveal || []).forEach(function (rv) {
      var p = shadow.players[rotIdx(rv.abs, you, n)];
      p.hole = rv.hole.slice();
      p.score = rv.score;
    });
    var mapped = {
      pots: d.res.pots.map(function (pr) {
        var o = {};
        for (var k in pr) if (Object.prototype.hasOwnProperty.call(pr, k)) o[k] = pr[k];
        o.winners = pr.winners.map(function (w) { return rotIdx(w, you, n); });
        return o;
      }),
      board: d.res.board.slice()
    };
    shadow.resolved = mapped;
    shadow.handOver = true;
    shadow.street = 'showdown';
    shadow.awaitingRunout = false;
    root.document.body.classList.remove('runout');
    root.UI.setThinking(-1);
    root.UI.render();
    /* 本手结算：真实筹码转移口径（起始 = 盲注前） */
    var p0 = shadow.players[0];
    if (st.handStartStack !== null) {
      var net = p0.stack - st.handStartStack;
      st.sess.hands++;
      st.sess.bb += net / shadow.bb;
      if (st.vpipDone) st.sess.vpip++;
      if (st.pfrDone) st.sess.pfr++;
      root.UI.setSessionStats(st.sess);
      if (net <= -1000) root.UI.showEmote(0, pickEmote('playerLose'));
      else if (net >= 1000 && Math.random() < 0.8) root.UI.showEmote(0, pickEmote('playerWin'));
    }
    /* 数据板块：客人也留本手牌谱（自己视角，仅存本机） */
    try {
      var CS = root.Cards;
      var cstr = function (c) { return CS ? CS.cardStr(c) : String(c); };
      var rec = {
        room: st.roomCode || 'mp', handNo: st.handId, ts: new Date().toISOString(),
        sb: shadow.sb, bb: shadow.bb,
        players: shadow.players.map(function (p) {
          return { name: p.name, charId: p.charId || '', isBot: !!p.isBot,
            stackEnd: p.stack, committed: p.totalCommitted,
            won: p.wonThisHand || 0, refund: p.refundThisHand || 0, rebuys: p.rebuys || 0,
            idle: !!p.idle, hole: (p.hole || []).map(cstr) };
        }),
        board: shadow.board.map(cstr),
        actions: (shadow.actionHistory || []).map(function (a) {
          return { idx: a.playerIdx, street: a.street, type: a.type, to: a.to, added: a.added };
        }),
        pots: (mapped.pots || []).map(function (pr) {
          return { amount: pr.amount, winners: pr.winners, label: pr.label || '',
            handName: pr.handName || null, foldWin: !!pr.foldWin, uncalled: !!pr.uncalled, split: !!pr.split };
        })
      };
      /* R6 反馈 P0：客人端同口径账目断言 + hero 归属（剥 UI 的（你）后缀进纯数据） */
      var paidG = 0, putG = 0;
      rec.pots.forEach(function (pr) { paidG += pr.amount || 0; });
      rec.players.forEach(function (q) { putG += q.committed || 0; });
      rec.assert = { sumPaid: paidG, sumPut: putG, ok: paidG === putG };
      rec.hero = String(rec.players[0].name || '').replace(/（你）/g, '');
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
      else root.DataPage.record(rec);
      /* 客人端也计好感度与会话统计（此前只有 host 路径落账） */
      if (root.Affection && root.Affection.onHand) {
        var aff = root.Affection.onHand(rec);
        if (aff && aff.levelUp && root.UI && root.UI.appendError) {
          var pc = root.Portraits && root.Portraits.byId ? root.Portraits.byId(aff.charId) : null;
          root.UI.appendError('💗 ' + (pc ? pc.name : aff.charId) + ' 好感度达到 Lv.' + aff.level + '！');
        }
      }
      try {
        var meG = rec.players && rec.players[0];
        if (meG) {
          var netG = (meG.won || 0) + (meG.refund || 0) - (meG.committed || 0);
          var sessG = JSON.parse(root.localStorage.getItem('gto-sess') || '{}') || {};
          sessG.hands = sessG.hands || 0; sessG.vpip = sessG.vpip || 0; sessG.pfr = sessG.pfr || 0; sessG.bb = sessG.bb || 0;   /* 旧档缺字段兜底, 防 NaN% */
          sessG.hands = (sessG.hands || 0) + 1;
          sessG.bb = Math.round(((sessG.bb || 0) + netG / (rec.bb || 20)) * 10) / 10;
          var preG = (rec.actions || []).filter(function (a) { return a.street === 'preflop' && a.idx === 0; });
          if (preG.some(function (a) { return a.type === 'call' || a.type === 'raise'; })) sessG.vpip = (sessG.vpip || 0) + 1;
          if (preG.some(function (a) { return a.type === 'raise'; })) sessG.pfr = (sessG.pfr || 0) + 1;
          root.localStorage.setItem('gto-sess', JSON.stringify(sessG));
          if (root.UI && root.UI.setSessionStats) root.UI.setSessionStats(sessG);
        }
      } catch (eSess) { /* 统计失败不影响对局 */ }
    } catch (e) { /* 留档失败不影响对局 */ }
    /* 弹层延迟 600ms：先让桌面表情气泡露脸，再暗场出结算（R3 反馈：气泡总被遮罩吞掉） */
    var myHand = st.handId;
    setTimeout(function () {
      if (st.uiReady && st.handId === myHand) {
        root.UI.showShowdown(mapped, d.extraNote, d.quotes || []);
        /* Step 6：客人勾选自动续局 → 每手结算自动请求房主开下一局 */
        var an2 = root.document.getElementById('auto-next-2');
        if (an2 && an2.checked && root.MP.requestNext) root.MP.requestNext();
      }
    }, 600);
  }

  function pickEmote(pool) {
    var E = (root.Portraits && root.Portraits.EMOTES) || {};
    var arr = E[pool] || ['…'];
    return arr[Math.floor(Math.random() * arr.length)];
  }

  /* ================================================================
   *  大厅 UI
   * ================================================================ */
  function setMpStatus(t, isErr) {
    var e = $('mp-status');
    if (!e) return;
    e.textContent = t;
    e.style.color = isErr ? 'var(--red)' : '';
  }

  function setJoinBusy(busy) {
    var b = $('mp-btn-join');
    if (b) {
      b.disabled = !!busy;
      b.textContent = busy ? '连接中…' : '加入房间 ✈';
    }
  }

  function settledJoin() {
    if (joinTimer) clearTimeout(joinTimer);
    joinTimer = null;
    setJoinBusy(false);
  }

  function showLobby(isHost) {
    var setup = $('mp-setup'), lobby = $('mp-lobby');
    if (setup) setup.hidden = true;
    if (lobby) lobby.hidden = false;
    var codeEl = $('mp-room-code');
    if (codeEl) codeEl.textContent = st.roomCode;
    var startBtn = $('mp-btn-start');
    if (startBtn) startBtn.hidden = !isHost;
    var readyBtn = $('mp-btn-ready');
    if (readyBtn) readyBtn.hidden = isHost;
    var hint = $('mp-seat-hint');
    if (hint) hint.textContent = st.seats;
    var ah = $('action-hint');
    if (ah) ah.textContent = '等待房主开始牌局…';   // 别再冒充「正在准备牌局」
    lobbyShownAt = Date.now();
    if (lobbyTick) clearInterval(lobbyTick);
    lobbyTick = setInterval(renderLobbyStatus, 1000);
    renderLobbyList();
  }

  /* 大厅状态行：在等谁 / 等了多久 / 全员就绪没有——不再让客人干等黑箱 */
  function renderLobbyStatus() {
    var el = $('mp-lobby-status');
    if (!el || st.phase !== 'lobby') return;
    /* P1-4：房主侧清理超时未归的离线座位（客人靠广播同步） */
    if (sweepOfflineSeats()) { renderLobbyList(); broadcastLobby(); return; }
    var readyN = st.roster.filter(function (r) { return r.isHost || r.ready; }).length;
    var total = st.roster.length;
    var waited = Math.floor((Date.now() - lobbyShownAt) / 1000);
    var txt, cls = '';
    if (total < 2) {
      txt = '等待更多玩家加入…（' + readyN + '/' + total + ' 已准备 · 已等待 ' + waited + 's）';
    } else if (!allGuestsReady()) {
      txt = '等待玩家准备…（' + readyN + '/' + total + ' 已准备）';
    } else if (ROLE === 'host') {
      txt = autoStartTimer
        ? '全员已准备，' + autoStartLeft + ' 秒后自动开局（也可手动点「开始牌局」）'
        : '全员已准备，等待开局…';
      cls = 'allready';
    } else {
      var autoLeft = st.autoLeft || 0;
      txt = '全员已准备，等待房主开局…（已等待 ' + waited + 's）';
      if (autoLeft > 0) txt = '全员已准备，' + autoLeft + ' 秒后自动开局';
      cls = 'allready';
    }
    el.textContent = txt;
    el.className = cls;
  }

  /* 房主：全员就绪 → 10 秒倒计时自动开局（点开始按钮可立即开局） */
  function clearAutoStart() {
    if (autoStartTimer) { clearInterval(autoStartTimer); autoStartTimer = null; }
    autoStartLeft = 0;
    var b = $('mp-btn-start');
    if (b) b.classList.remove('attn');
  }
  function updateAutoStart() {
    var startBtn = $('mp-btn-start');
    var ok = ROLE === 'host' && st.phase === 'lobby' &&
             st.roster.length >= 2 && allGuestsReady();
    if (startBtn) startBtn.classList.toggle('attn', ok);
    if (!ok) { clearAutoStart(); return; }
    if (autoStartTimer) return;
    autoStartLeft = 10;
    autoStartTimer = setInterval(function () {
      if (ROLE !== 'host' || st.phase !== 'lobby') { clearAutoStart(); return; }
      if (st.roster.length < 2 || !allGuestsReady()) { clearAutoStart(); renderLobbyList(); return; }
      autoStartLeft--;
      broadcastLobby();   // 客人端同步倒计时数字
      if (autoStartLeft <= 0) {
        clearAutoStart();
        if (root.MpGame) root.MpGame.startHost();
        return;
      }
      renderLobbyStatus();
    }, 1000);
  }

  function myRosterEntry() {
    var self = Net.selfId();
    for (var i = 0; i < st.roster.length; i++) {
      if (st.roster[i].peer === self) return st.roster[i];
    }
    return null;
  }

  function allGuestsReady() {
    return st.roster.every(function (r) { return r.isHost || (r.ready && !r.off); });
  }

  var OFFLINE_KEEP_MS = 120000;   // P1-4：断线座位保留 120s，超时让位
  function sweepOfflineSeats() {
    if (ROLE !== 'host' || st.phase !== 'lobby') return false;
    var now = Date.now(), changed = false;
    for (var k = st.roster.length - 1; k >= 1; k--) {
      if (st.roster[k].off && now - st.roster[k].offAt > OFFLINE_KEEP_MS) {
        st.roster.splice(k, 1);
        changed = true;
      }
    }
    return changed;
  }

  function renderLobbyList() {
    var box = $('mp-players');
    if (!box) return;
    box.innerHTML = '';
    st.roster.forEach(function (r) {
      var d = root.document.createElement('div');
      d.className = 'mp-pl' + (!r.isHost && (!r.ready || r.off) ? ' notready' : '');
      var av = root.document.createElement('div');
      av.className = 'avatar';
      av.innerHTML = root.Portraits.charSVG(r.charId, 'idle', 46, 'bust');
      var readyTag = '';
      if (r.isHost) readyTag = ' <span class="mp-tag">房主</span>';
      else if (r.off) readyTag = ' <span class="mp-tag wait">离线 · 等待重连</span>';
      else readyTag = r.ready ? ' <span class="mp-tag ok">已准备 ✓</span>'
                              : ' <span class="mp-tag wait">未准备</span>';
      /* P2-11：字段间显式分隔，不再糊成一团 */
      var tx = root.document.createElement('div');
      tx.innerHTML = '<b>' + escHtml(r.name) + '</b>' + readyTag +
        '<div class="muted" style="font-size:11px;margin-top:2px">角色 · ' +
        (root.Portraits.byId(r.charId) || {}).name + '</div>';
      d.appendChild(av);
      d.appendChild(tx);
      box.appendChild(d);
    });
    for (var i = st.roster.length; i < st.seats; i++) {
      var e = root.document.createElement('div');
      e.className = 'mp-pl empty';
      e.textContent = '（空位 · GTO 部员代打）';
      box.appendChild(e);
    }
    /* 斗地主式准备制：所有真人都准备了，房主才能开始 */
    var startBtn = $('mp-btn-start');
    if (startBtn) {
      var ok = allGuestsReady();
      startBtn.disabled = !ok;
      startBtn.textContent = ok ? '开始牌局 ▶' : '等待所有人准备…';
    }
    var readyBtn = $('mp-btn-ready');
    if (readyBtn && !readyBtn.hidden) {
      var me = myRosterEntry();
      var ready = !!(me && me.ready);
      readyBtn.textContent = ready ? '取消准备 ✕' : '准备 ✔';
    }
    updateAutoStart();
    renderLobbyStatus();
  }

  function broadcastLobby() {
    Net.broadcast({
      t: 'lobby',
      seats: st.seats,
      auto: autoStartTimer ? autoStartLeft : 0,   // 客人也能看到自动开局倒计时
      players: st.roster.map(function (r) {
        return { peer: r.peer, name: r.name, charId: r.charId, isHost: !!r.isHost,
                 ready: !!r.ready && !r.off, off: !!r.off };
      })
    });
  }

  function leaveRoom() {
    Net.destroy();
    ROLE = ''; st.phase = 'idle'; st.roster = []; st.uiReady = false;
    st.deciding = false; st.handId = 0; shadow = null;
    st.lobbyShown = false; st.autoLeft = 0;
    earlyActs = {};
    hostPending = null; deadSeats = {}; seatPeer = []; lastLogSent = 0;
    if (joinTimer) { clearTimeout(joinTimer); joinTimer = null; }
    clearAutoStart();
    if (lobbyTick) { clearInterval(lobbyTick); lobbyTick = null; }
    if (st.gameTick) { clearInterval(st.gameTick); st.gameTick = null; }
    if (root.UI && root.UI.setTurnDeadline) root.UI.setTurnDeadline(0);
    var setup = $('mp-setup'), lobby = $('mp-lobby');
    if (setup) setup.hidden = false;
    if (lobby) lobby.hidden = true;
    setJoinBusy(false);
    setMpStatus('');
  }

  function hideMpModals() {
    var m = $('multi-modal');
    if (m) m.classList.add('hidden');
    clearAutoStart();
    if (lobbyTick) { clearInterval(lobbyTick); lobbyTick = null; }
  }

  function readName() {
    var e = $('mp-name');
    st.myName = sanitizeName(e ? e.value : '');
    try { localStorage.setItem('gto-name', st.myName); } catch (x) { /* noop */ }
    /* 每次实时读看板娘：lobby 改完即生效 */
    try { selChar = localStorage.getItem('gto-char') || selChar; } catch (x) { /* noop */ }
    if (!selChar) selChar = CHARS[0] ? CHARS[0].id : 'suzu';
    st.myChar = selChar;
  }

  function wire() {
    if (!root.document || !$('mp-setup')) return;

    /* 昵称回填 */
    var nameEl = $('mp-name');
    try { nameEl.value = localStorage.getItem('gto-name') || ''; } catch (x) { /* noop */ }

    /* 角色 = 大厅看板娘（localStorage gto-char），好友房内不再二次选择 */
    /* 页签切换 */
    function tab(which) {
      $('mp-tab-host').classList.toggle('sel', which === 'host');
      $('mp-tab-join').classList.toggle('sel', which === 'join');
      $('mp-pane-host').hidden = which !== 'host';
      $('mp-pane-join').hidden = which !== 'join';
    }
    $('mp-tab-host').addEventListener('click', function () { tab('host'); });
    $('mp-tab-join').addEventListener('click', function () { tab('join'); });

    /* 房码输入规范化 */
    var codeEl = $('mp-code');
    codeEl.addEventListener('input', function () {
      var v = codeEl.value.toUpperCase().replace(/[^A-Z2-9]/g, '');
      if (v !== codeEl.value) codeEl.value = v;
    });

    $('mp-btn-create').addEventListener('click', function () {
      readName();
      var r = root.document.querySelector('input[name="mp-seats"]:checked');
      st.seats = r ? parseInt(r.value, 10) : 6;
      startHostRoom();
    });
    $('mp-btn-join').addEventListener('click', function () {
      var code = (codeEl.value || '').toUpperCase();
      if (!CODE_RE.test(code)) { setMpStatus('请输入 6 位房码'); return; }
      readName();
      startJoinRoom(code);
    });
    $('mp-btn-leave').addEventListener('click', leaveRoom);
    $('mp-btn-start').addEventListener('click', function () {
      if (!allGuestsReady()) { setMpStatus('还有人没准备'); return; }
      if (root.MpGame) root.MpGame.startHost();
    });
    $('mp-btn-ready').addEventListener('click', function () {
      var me = myRosterEntry();
      var v = !(me && me.ready);
      /* 乐观更新，房主广播后校正 */
      if (me) me.ready = v;
      renderLobbyList();
      Net.sendTo('host', { t: 'ready', v: v });
    });
    $('mp-copy-code').addEventListener('click', function () {
      var t = st.roomCode;
      var btn = $('mp-copy-code');
      function copied() {
        if (!btn) return;
        btn.textContent = '已复制 ✓';
        setTimeout(function () { btn.textContent = '复制'; }, 2000);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(t).then(function () { copied(); },
          function () { setMpStatus('房码：' + t); });
      } else { setMpStatus('房码：' + t); copied(); }
    });
  }

  /* ================================================================
   *  导出
   * ================================================================ */
  var MP = {
    hosting: hosting,
    TURN_MS: TURN_MS,
    isRemoteSeat: isRemoteSeat,
    seatCount: function () { return st.seats; },
    hostSetup: hostSetup,
    hostHandStart: hostHandStart,
    hostSync: hostSync,
    hostThink: hostThink,
    hostShowdown: hostShowdown,
    fxFly: fxFly, fxBurst: fxBurst, fxEmote: fxEmote, fxSfx: fxSfx,
    nextRemoteAction: nextRemoteAction,
    closeLobby: hideMpModals,
    leaveIfAny: function () { if (ROLE) leaveRoom(); },
    allGuestsReady: allGuestsReady,
    guestCount: function () { return Math.max(0, st.roster.length - 1); },
    roomCode: function () { return st.roomCode; },
    sendEmote: function (txt) {
      txt = sanitizeEmote(txt);
      if (!txt || st.phase !== 'game') return false;   /* 非对局态：交回本地回显 */
      if (ROLE === 'guest') {
        Net.sendTo('host', { t: 'emote', txt: txt });   // 房主转播后回显
      } else {
        if (root.UI && root.UI.showEmote) root.UI.showEmote(0, txt);
        fxEmote(0, txt);
      }
      return true;
    },
    isGuest: function () { return ROLE === 'guest'; },
    requestNext: function () {
      /* R6-R3：客人请求下一手（房主收到后代点「下一局」） */
      if (ROLE === 'guest' && st.phase === 'game') Net.sendTo('host', { t: 'next' });
    },
    __test: { snapFor: snapFor, buildShadow: buildShadow, rotIdx: rotIdx, normalizeAct: normalizeAct, _st: st }
  };
  root.MP = MP;

  if (typeof root.document !== 'undefined') {
    if (root.document.readyState === 'loading') {
      root.document.addEventListener('DOMContentLoaded', wire);
    } else {
      wire();
    }
  }
})(typeof window !== 'undefined' ? window : globalThis);
