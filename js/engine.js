/* engine.js — 德州扑克游戏引擎（状态机）
 * 负责：盲注/发牌、四条街下注轮、最小加注规则、全下、边池分层结算、位置轮转。
 * 纯逻辑、无 DOM，可在 Node 里无头测试（test/sim.js）。
 * 全局命名空间 root.Table。 */
(function (root) {
  'use strict';
  var Cards = root.Cards;

  var BOT_NAMES = ['纳什', '赛弗斯', '深栈', '天平', '普鲁'];

  function Table(opts) {
    opts = opts || {};
    this.sb = opts.sb || 10;
    this.bb = opts.bb || 20;
    this.startStack = opts.startStack || this.bb * 100; // 默认 100bb
    this.seatCount = opts.seatCount || 6;               // 2 / 4 / 6
    this.players = [];
    for (var i = 0; i < this.seatCount; i++) {
      this.players.push({
        idx: i,
        name: i === 0 ? '你' : BOT_NAMES[(i - 1) % BOT_NAMES.length],
        isBot: i !== 0,
        stack: this.startStack,
        hole: [], folded: true, allIn: false, spoke: false,
        streetCommitted: 0, totalCommitted: 0,
        lastAction: '', score: 0, wonThisHand: 0
      });
    }
    this.humanIdx = 0;
    this.buttonIdx = this.seatCount - 1;
    this.runoutMode = opts.runoutMode !== false; // UI 默认逐街揭晓全下跑牌；无头测试传 false
    this.deck = [];
    this.board = [];
    this.street = 'idle'; // preflop | flop | turn | river | showdown
    this.handNo = 0;
    this.actionHistory = [];
    this.logLines = [];
    this.handOver = true;
    this.foldWin = false;
    this.resolved = null;
  }

  /* ---------- 工具 ---------- */
  Table.prototype.log = function (s) { this.logLines.push(s); };
  Table.prototype.potTotal = function () {
    var s = 0;
    this.players.forEach(function (p) { s += p.totalCommitted; });
    return s;
  };
  Table.prototype.activeUnfolded = function () {
    return this.players.filter(function (p) { return !p.folded; });
  };
  Table.prototype.canActPlayers = function () {
    return this.players.filter(function (p) { return !p.folded && !p.allIn; });
  };
  Table.prototype.currentActor = function () { return this.players[this.actorIdx]; };
  Table.prototype.spr = function (idx) {
    var p = this.players[idx];
    return (p.stack + p.streetCommitted) / Math.max(1, this.potTotal());
  };
  Table.prototype.positionName = function (idx) {
    var n = this.players.length;
    var rel = (idx - this.buttonIdx + n) % n;
    if (n === 2) return rel === 0 ? 'BTN' : 'BB';
    var names = n >= 6 ? ['BTN', 'SB', 'BB', 'UTG', 'HJ', 'CO']
      : n === 5 ? ['BTN', 'SB', 'BB', 'UTG', 'CO']
      : n === 4 ? ['BTN', 'SB', 'BB', 'CO']
      : ['BTN', 'SB', 'BB'];
    return names[rel];
  };
  Table.prototype.legalActions = function (idx) {
    var p = this.players[idx];
    var toCall = Math.max(0, this.currentBet - p.streetCommitted);
    var maxTo = p.streetCommitted + p.stack;
    var minTo;
    if (this.currentBet === 0) minTo = Math.min(maxTo, this.bb);
    else minTo = Math.min(maxTo, this.currentBet + this.minRaiseSize);
    return { toCall: toCall, canCheck: toCall <= 0,
      canRaise: maxTo > this.currentBet && !(this._underRaiseOnly && p.spoke),
      minTo: minTo, maxTo: maxTo };
  };

  function commit(p, amt) {
    amt = Math.min(amt, p.stack);
    p.stack -= amt;
    p.streetCommitted += amt;
    p.totalCommitted += amt;
    if (p.stack === 0) p.allIn = true;
    return amt;
  }

  /* ---------- 开一手 ---------- */
  Table.prototype.startHand = function () {
    var self = this, n = this.players.length;
    this.handNo++;
    // 打光才重新买入（不做 <20bb 自动补码——避免筹码池通胀，短码 push/fold 逻辑得以触发）
    this.players.forEach(function (p) {
      if (p.stack <= 0) {
        p.stack = self.startStack;
        p.rebuys = (p.rebuys || 0) + 1;
        self.log('↺ ' + p.name + ' 重新买入 ' + self.startStack + '（第 ' + p.rebuys + ' 次）');
      }
    });
    this.players.forEach(function (p) {
      p.folded = false; p.allIn = false; p.spoke = false;
      p.hole = []; p.streetCommitted = 0; p.totalCommitted = 0;
      p.lastAction = ''; p.score = 0; p.wonThisHand = 0; p.refundThisHand = 0;
    });
    this.buttonIdx = (this.buttonIdx + 1) % n;
    this.deck = Cards.shuffle(Cards.makeDeck());
    this.board = [];
    this.actionHistory = [];
    this.handOver = false;
    this.foldWin = false;
    this.resolved = null;
    this.awaitingRunout = false;
    this._underRaiseOnly = false; // 不足额全下后，已行动者不可再加注
    this.street = 'preflop';
    this.log('════ 第 ' + this.handNo + ' 手 ════');

    // 盲注（单挑：按钮位 = 小盲）
    var sbIdx, bbIdx;
    if (n === 2) { sbIdx = this.buttonIdx; bbIdx = (sbIdx + 1) % n; }
    else { sbIdx = (this.buttonIdx + 1) % n; bbIdx = (sbIdx + 1) % n; }
    commit(this.players[sbIdx], this.sb);
    commit(this.players[bbIdx], this.bb);
    this.players[sbIdx].lastAction = '小盲';   /* P1-4: 动作文案不带金额,数值由位置徽章 title 承担 */
    this.players[bbIdx].lastAction = '大盲';

    // 发牌（从按钮下一位开始，每人两张）
    var order = [];
    for (var k = 1; k <= n; k++) order.push((this.buttonIdx + k) % n);
    for (var r = 0; r < 2; r++) order.forEach(function (idx) {
      self.players[idx].hole.push(self.deck.pop());
    });

    this.currentBet = this.bb;
    this.minRaiseSize = this.bb;
    this.actorIdx = (n === 2) ? sbIdx : (bbIdx + 1) % n;
  };

  /* ---------- 下注轮 ---------- */
  function bettingComplete(t) {
    var live = t.activeUnfolded();
    for (var i = 0; i < live.length; i++) {
      var p = live[i];
      if (p.allIn) continue;
      if (!p.spoke) return false;
      if (p.streetCommitted !== t.currentBet) return false;
    }
    return true;
  }

  Table.prototype.apply = function (action) {
    var t = this;
    var p = this.players[this.actorIdx];
    var la = this.legalActions(p.idx);
    /* P0-A-3：动作额度必须是有限数字（NaN 会让 Math.max/min 全链污染） */
    if (action && action.type === 'raise' && (typeof action.to !== 'number' || !isFinite(action.to))) {
      action.to = la.minTo;
    }
    var potBefore = this.potTotal();
    var type = action.type, added = 0, text = '';

    if (type === 'fold') {
      p.folded = true; text = '弃牌';
    } else if (type === 'check') {
      if (la.toCall > 0) {
        /* R4：无效过牌不再炸掉整手；R6-R3（呜帕）：actionHistory 也记 fold，牌谱与钱一致 */
        p.folded = true; type = 'fold'; text = '弃牌（无效过牌自动转弃）';
      } else {
        text = '过牌';
      }
    } else if (type === 'call') {
      added = commit(p, la.toCall);
      text = p.allIn ? '全下跟注 ' + added : '跟注 ' + added;
    } else if (type === 'raise') {
      var to = Math.max(la.minTo, Math.min(action.to, la.maxTo));
      var prevBet = this.currentBet;
      added = commit(p, to - p.streetCommitted);
      var fullRaise = (to - prevBet) >= this.minRaiseSize;
      if (fullRaise) this.minRaiseSize = to - prevBet;
      this.currentBet = Math.max(this.currentBet, p.streetCommitted);
      if (fullRaise) {
        /* 足额加注：重开所有人的行动权 */
        this._underRaiseOnly = false;
        this.players.forEach(function (o) {
          if (o.idx !== p.idx && !o.folded && !o.allIn) o.spoke = false;
        });
      } else {
        /* P2-4：不足最小加注的全下——不重开加注权，已行动者只能跟注/弃牌 */
        this._underRaiseOnly = true;
      }
      text = (prevBet === 0 ? '下注 ' : '加注到 ') + p.streetCommitted + (p.allIn ? '（全下）' : '');
    } else {
      throw new Error('未知动作 ' + type);
    }
    p.spoke = true;
    p.lastAction = text;
    this.actionHistory.push({
      playerIdx: p.idx, street: this.street, type: type,
      to: p.streetCommitted, added: added,
      frac: added / Math.max(1, potBefore + (type === 'raise' ? la.toCall : 0)),
      auto: !!action.auto   /* Step 5：代打/超时动作打标，供留档与统计 */
    });
    this.log(p.name + '：' + text);

    // 局面推进
    var n = this.players.length;
    if (this.activeUnfolded().length === 1) {
      this.handOver = true;
      this.foldWin = true;
      return;
    }
    if (bettingComplete(this)) {
      this._advancePhase();
    } else {
      // 同一街内把行动权交给下一位未弃牌、未全下的玩家
      for (var k = 1; k <= n; k++) {
        var q = this.players[(p.idx + k) % n];
        if (!q.folded && !q.allIn) { this.actorIdx = q.idx; break; }
      }
    }
  };

  Table.prototype._advancePhase = function () {
    var t = this;
    this.players.forEach(function (p) { p.streetCommitted = 0; });
    this.currentBet = 0;
    this.minRaiseSize = this.bb;
    this.players.forEach(function (p) { p.spoke = false; });

    function dealNext() {
      if (t.street === 'preflop') {
        t.street = 'flop';
        t.board.push(t.deck.pop(), t.deck.pop(), t.deck.pop());
        t.log('── 翻牌 ' + t.board.map(Cards.cardStr).join(' ') + ' ──');
      } else if (t.street === 'flop') {
        t.street = 'turn';
        t.board.push(t.deck.pop());
        t.log('── 转牌 ' + Cards.cardStr(t.board[3]) + ' ──');
      } else if (t.street === 'turn') {
        t.street = 'river';
        t.board.push(t.deck.pop());
        t.log('── 河牌 ' + Cards.cardStr(t.board[4]) + ' ──');
      } else {
        t.street = 'showdown';
      }
    }

    dealNext();
    if (this.street === 'showdown') {
      this.handOver = true;
      return;
    }
    // 无人还能行动（全下）→ 逐街跑牌（runoutMode）或立即发完（无头测试）
    if (this.canActPlayers().length < 2) {
      if (this.runoutMode) {
        this.awaitingRunout = true;
      } else {
        while (this.street !== 'showdown' && this.canActPlayers().length < 2) dealNext();
        if (this.street === 'showdown') this.handOver = true;
      }
      return;
    }
    var n = this.players.length;
    for (var k = 1; k <= n; k++) {
      var idx = (this.buttonIdx + k) % n;
      var p = this.players[idx];
      if (!p.folded && !p.allIn) { this.actorIdx = idx; break; }
    }
  };

  /* runoutMode 下由 UI 驱动：每次发下一条街 */
  Table.prototype.runoutStep = function () {
    var t = this;
    function dealNext() {
      if (t.street === 'preflop') {
        t.street = 'flop';
        t.board.push(t.deck.pop(), t.deck.pop(), t.deck.pop());
        t.log('── 翻牌 ' + t.board.map(Cards.cardStr).join(' ') + ' ──');
      } else if (t.street === 'flop') {
        t.street = 'turn';
        t.board.push(t.deck.pop());
        t.log('── 转牌 ' + Cards.cardStr(t.board[3]) + ' ──');
      } else if (t.street === 'turn') {
        t.street = 'river';
        t.board.push(t.deck.pop());
        t.log('── 河牌 ' + Cards.cardStr(t.board[4]) + ' ──');
      } else {
        t.street = 'showdown';
      }
    }
    dealNext();
    if (this.street === 'showdown') {
      this.handOver = true;
      this.awaitingRunout = false;
    } else {
      this.awaitingRunout = this.canActPlayers().length < 2;
      if (!this.awaitingRunout) this.handOver = false;
    }
  };

  /* ---------- 结算（含边池） ---------- */
  Table.prototype.resolve = function () {
    var t = this;
    var live = this.activeUnfolded();
    // 单挑剩一人：其余全弃，直接拿走全部底池
    if (live.length === 1) {
      var amt = this.potTotal();
      live[0].stack += amt;
      live[0].wonThisHand = amt;
      this.resolved = {
        pots: [{ amount: amt, winners: [live[0].idx], handName: null, foldWin: true, split: false, label: '底池' }],
        board: this.board.slice()
      };
      this.log('★ ' + live[0].name + ' 收下 ' + amt + '（其余全弃）');
      this.handOver = true;
      this.street = 'showdown';
      return this.resolved;
    }
    live.forEach(function (p) { p.score = Cards.eval7(p.hole.concat(t.board)); });
    // 分层边池：未弃牌玩家的 totalCommitted 形成层级；多出的无人认领部分自然退还
    var levels = [];
    this.players.forEach(function (p) {
      if (p.totalCommitted > 0 && levels.indexOf(p.totalCommitted) < 0) levels.push(p.totalCommitted);
    });
    levels.sort(function (a, b) { return a - b; });
    var prev = 0, pots = [];
    levels.forEach(function (L) {
      var amt = 0, contribs = {};
      t.players.forEach(function (p) {
        var c = Math.max(0, Math.min(p.totalCommitted, L) - prev);
        if (c > 0) { amt += c; contribs[p.idx] = (contribs[p.idx] || 0) + c; }
      });
      var elig = live.filter(function (p) { return p.totalCommitted >= L; });
      /* R5-施工 P1-1：elig 为空也要入队（旧版在这里直接丢弃 = 筹码蒸发），
       * 由下方结果循环按「各人拿回各人」退还 */
      if (amt > 0) pots.push({ amount: amt, elig: elig, contribs: contribs });
      prev = L;
    });
    var potResults = [];
    pots.forEach(function (pot) {
      var contribNames = Object.keys(pot.contribs);
      var refundTo = function (ownerIdx, amt) {
        var owner = t.players[ownerIdx];
        owner.stack += amt;
        owner.refundThisHand = (owner.refundThisHand || 0) + amt;
        potResults.push({
          amount: amt, winners: [owner.idx], handName: null,
          split: false, foldWin: false, uncalled: true
        });
      };
      /* R5-施工 P1-1：只有一名未弃牌玩家可赢的层不是对局——
       * 即使该层有多个出资人（弃牌者的死钱），也按「收回未被跟注」归因，
       * 不再生成带牌型的「赢得边池」行（字面像赢了对手的钱，实为拿回自己超出部分+死钱）。 */
      if (pot.elig.length === 1) {
        refundTo(pot.elig[0].idx, pot.amount);
        return;
      }
      if (pot.elig.length === 0) {
        /* 全员弃牌的层（理论罕见）：各人拿回自己那份，绝不漏筹码 */
        contribNames.forEach(function (k) { refundTo(parseInt(k, 10), pot.contribs[k]); });
        return;
      }
      // 该层只有一人投入 = 未被跟注的下注，直接退还
      if (contribNames.length === 1) {
        refundTo(parseInt(contribNames[0], 10), pot.amount);
        return;
      }
      var best = Math.max.apply(null, pot.elig.map(function (p) { return p.score; }));
      var winners = pot.elig.filter(function (p) { return p.score === best; });
      var share = Math.floor(pot.amount / winners.length);
      var rem = pot.amount - share * winners.length;
      winners.forEach(function (w, i) {
        var gain = share + (i < rem ? 1 : 0);
        w.stack += gain;
        w.wonThisHand += gain;
      });
      potResults.push({
        amount: pot.amount,
        winners: winners.map(function (w) { return w.idx; }),
        handName: Cards.handName(best),
        split: winners.length > 1,
        foldWin: false
      });
    });
    // 分层标签：第一个非退还层=主池，其后=边池1/2…；单人独占层=未跟注退还
    var sideIdx = 0;
    potResults.forEach(function (pr) {
      if (pr.uncalled) { pr.label = '退还'; return; }
      pr.label = (sideIdx === 0) ? '主池' : '边池' + sideIdx;
      sideIdx++;
    });
    potResults.forEach(function (pr) {
      var names = pr.winners.map(function (i) { return t.players[i].name; }).join('、');
      t.log('★ ' + names + (pr.uncalled ? ' 收回未被跟注的 ' + pr.amount : ' 赢得' + pr.label + ' ' + pr.amount + (pr.handName ? '（' + pr.handName + '）' : '') + (pr.split ? '［平分］' : '')));
    });
    this.resolved = { pots: potResults, board: this.board.slice() };
    this.handOver = true;
    this.street = 'showdown';
    return this.resolved;
  };

  /* GTO 建模辅助（透传给 gto.js 用） */
  Table.prototype.raiseCount = function (street) {
    var n = 0;
    this.actionHistory.forEach(function (a) { if (a.street === street && a.type === 'raise') n++; });
    return n;
  };

  root.Table = Table;
})(typeof window !== 'undefined' ? window : globalThis);
