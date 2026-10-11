/* net.js — P2P 网络层（PeerJS WebRTC DataChannel）
 *
 * 房主模式：以 gto-poker-<房码> 为 peer ID，等朋友连接
 * 客人模式：连接到 gto-poker-<房码>
 * 消息格式：JSON 字符串
 * 架构：星型拓扑——房主为 hub，所有客人直连房主
 * 费用：PeerJS 免费信令 + Google 免费 STUN = ¥0
 */
(function (root) {
  'use strict';

  /* 轻量网络事件日志（控制台难取时的现场证据；环形保留最近 60 条） */
  var __netlog = [];
  function nlog(s) {
    __netlog.push(new Date().toISOString().slice(11, 23) + ' ' + s);
    if (__netlog.length > 60) __netlog.shift();
    try { console.info('[net]', s); } catch (e) { /* noop */ }
  }

  var peer = null;
  var conns = {};
  var mode = '';
  var roomCode = '';
  var guestCount = 0;

  /* P2P 打洞服务器：Cloudflare STUN 国内直连极快(实测 0.2s)，Google STUN 在国内蜂窝网
     基本不可达(实测 3.2s/常超时)——只用 Google 会造成跨网加入永久卡死，故双保险 */
  var ICE_SERVERS = [
    { urls: 'stun:stun.cloudflare.com:3478' },
    { urls: 'stun:stun.l.google.com:19302' }
  ];

  var CODE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';

  function genCode(len) {
    len = len || 6;
    var s = '';
    for (var i = 0; i < len; i++) {
      s += CODE_CHARS[Math.floor(Math.random() * CODE_CHARS.length)];
    }
    return s;
  }

  var handlers = {
    onReady: null,
    onGuestJoin: null,
    onGuestLeave: null,
    onConnected: null,
    onDisconnected: null,
    onData: null,
    onError: null
  };

  function mergeHandlers(cb) {
    if (cb.onReady) handlers.onReady = cb.onReady;
    if (cb.onGuestJoin) handlers.onGuestJoin = cb.onGuestJoin;
    if (cb.onGuestLeave) handlers.onGuestLeave = cb.onGuestLeave;
    if (cb.onConnected) handlers.onConnected = cb.onConnected;
    if (cb.onDisconnected) handlers.onDisconnected = cb.onDisconnected;
    if (cb.onData) handlers.onData = cb.onData;
    if (cb.onError) handlers.onError = cb.onError;
  }

  function host(code, cb) {
    mode = 'host';
    roomCode = code || genCode();
    if (cb) mergeHandlers(cb);
    var pid = 'gto-poker-' + roomCode;

    peer = new root.Peer(pid, { debug: 0, config: { iceServers: ICE_SERVERS } });

    peer.on('open', function () {
      if (handlers.onReady) handlers.onReady(roomCode);
    });

    peer.on('connection', function (conn) {
      nlog('host: incoming ' + conn.peer);
      conn.on('open', function () {
        conns[conn.peer] = conn;
        guestCount++;
        nlog('host: guest open ' + conn.peer);
        if (handlers.onGuestJoin) handlers.onGuestJoin(conn.peer, conn.metadata || {});
      });
      conn.on('data', function (data) {
        if (handlers.onData) handlers.onData(conn.peer, data);
      });
      conn.on('close', function () {
        delete conns[conn.peer];
        guestCount--;
        nlog('host: guest close ' + conn.peer);
        if (handlers.onGuestLeave) handlers.onGuestLeave(conn.peer);
      });
      conn.on('error', function (e) {
        nlog('host: guest error ' + conn.peer + ' ' + (e && e.type || e));
      });
    });

    peer.on('error', function (e) {
      if (e.type === 'unavailable-id') {
        peer.destroy();
        host(genCode(), cb);
      } else if (handlers.onError) {
        handlers.onError(e);
      }
    });

    peer.on('disconnected', function () {
      nlog('host: signaling lost, reconnecting');
      peer.reconnect();
    });
  }

  function guest(code, cb, meta) {
    mode = 'guest';
    roomCode = code;
    if (cb) mergeHandlers(cb);
    var hostId = 'gto-poker-' + code;

    peer = new root.Peer({ debug: 0, config: { iceServers: ICE_SERVERS } });

    peer.on('open', function () {
      var conn = peer.connect(hostId, { reliable: true, metadata: meta || {} });
      conn.on('open', function () {
        conns[hostId] = conn;
        conns['host'] = conn;   /* 别名：客人回传动作用 sendTo('host')，直连唯一房主 */
        nlog('guest: connected to ' + hostId);
        if (handlers.onConnected) handlers.onConnected();
      });
      conn.on('data', function (data) {
        if (handlers.onData) handlers.onData('host', data);
      });
      conn.on('close', function () {
        nlog('guest: conn closed');
        if (handlers.onDisconnected) handlers.onDisconnected();
      });
      conn.on('error', function (e) {
        nlog('guest: conn error ' + (e && e.type || e));
      });
    });

    peer.on('error', function (e) {
      nlog('guest: peer error ' + (e && e.type || e));
      if (handlers.onError) handlers.onError(e);
    });

    peer.on('disconnected', function () {
      nlog('guest: signaling lost, reconnecting');
      peer.reconnect();
    });
  }

  function broadcast(data) {
    var json = JSON.stringify(data);
    for (var k in conns) {
      if (conns[k] && conns[k].open) {
        try { conns[k].send(json); } catch (e) { /* ignore */ }
      }
    }
  }

  function sendTo(connId, data) {
    var c = conns[connId];
    if (c && c.open) {
      try { c.send(JSON.stringify(data)); } catch (e) { /* ignore */ }
    }
  }

  function destroy() {
    if (peer) { peer.destroy(); peer = null; }
    conns = {};
    mode = '';
    roomCode = '';
    guestCount = 0;
  }

  root.Net = {
    genCode: genCode,
    host: host,
    guest: guest,
    broadcast: broadcast,
    sendTo: sendTo,
    destroy: destroy,
    isHost: function () { return mode === 'host'; },
    isGuest: function () { return mode === 'guest'; },
    isLocal: function () { return mode === ''; },
    guestCount: function () { return guestCount; },
    roomCode: function () { return roomCode; },
    connections: function () { return conns; },
    selfId: function () { return peer && peer.id ? peer.id : ''; },
    log: function () { return __netlog.slice(); }
  };
})(typeof window !== 'undefined' ? window : globalThis);
