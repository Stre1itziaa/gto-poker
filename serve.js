/* serve.js — 零依赖本地静态服务器（可选）
 * 用法：node serve.js [端口]   默认 8787，然后浏览器打开 http://localhost:8787/
 * 说明：直接双击 index.html 也能玩（脚本为经典加载，file:// 可用）；
 *       若浏览器安全策略拦截 file://，用本服务器。 */
'use strict';
var http = require('http');
var fs = require('fs');
var path = require('path');
var zlib = require('zlib');
var crypto = require('crypto');

var root = __dirname;
var port = parseInt(process.argv[2], 10) || 8787;
var MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.md': 'text/plain; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.webp': 'image/webp', '.ico': 'image/x-icon'
};

http.createServer(function (req, res) {
  var urlPath = decodeURIComponent(req.url.split('?')[0]);
  if (urlPath === '/') urlPath = '/index.html';
  var file = path.normalize(path.join(root, urlPath));
  if (!file.startsWith(root)) { res.writeHead(403); res.end('Forbidden'); return; }
  /* Step 1：留档审计端点——GET /api/handlog?room=XXX 返回该房全部留档 */
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
  if (req.method === 'POST' && urlPath === '/api/handlog') {
    var chunks = [];
    req.on('data', function (c) {
      chunks.push(c);
      if (Buffer.concat(chunks).length > 1000000) req.destroy();   // 单手上限 1MB
    });
    req.on('end', function () {
      try {
        var body = Buffer.concat(chunks).toString('utf8');
        var rec = JSON.parse(body);
        var room = String(rec.room || 'local').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 16) || 'local';
        var dir = path.join(root, 'test', 'hand-logs', room);
        var dirExists = fs.existsSync(dir);
        var existing = dirExists ? fs.readdirSync(dir).length : 0;
        if (existing > 500) {   /* S4：单房留档上限——滚动删除最旧，避免客户端 429 误报 */
          fs.readdirSync(dir).filter(function (f) { return f.slice(-5) === '.json'; })
            .map(function (f) { return { f: f, m: fs.statSync(path.join(dir, f)).mtimeMs }; })
            .sort(function (a, b) { return a.m - b.m; })
            .slice(0, existing - 480)
            .forEach(function (o) { try { fs.unlinkSync(path.join(dir, o.f)); } catch (e) { /* noop */ } });
        }
        fs.mkdirSync(dir, { recursive: true });
        var aid = String(rec.aid || Date.now()).replace(/[^A-Za-z0-9_-]/g, '').slice(0, 48) || String(Date.now());
        var name = 'hand_' + String(rec.handNo || 0).padStart(4, '0') + '_' + aid + '.json';   /* 重发按 aid 覆盖，不产生重复 */
        fs.writeFileSync(path.join(dir, name), body);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end('{"ok":true}');
      } catch (e) {
        res.writeHead(400); res.end('{"ok":false}');
      }
    });
    return;
  }
  fs.readFile(file, function (err, data) {
    if (err) { res.writeHead(404); res.end('Not Found'); return; }
    var ext = path.extname(file);
    var isAsset = urlPath.indexOf('/assets/') === 0;
    /* 手机性能：立绘等资源内容不变 → 长缓存 + ETag 304（重复访问零下载）；
     * html/js/css 仍走协商缓存（版本参数变更即失效） */
    var stat = fs.statSync(file);
    var etag = '"' + crypto.createHash('md5').update(stat.mtimeMs + ':' + data.length).digest('hex').slice(0, 16) + '"';
    if (req.headers['if-none-match'] === etag) {
      res.writeHead(304, { ETag: etag });
      res.end();
      return;
    }
    var headers = {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'ETag': etag,
      'Cache-Control': isAsset
        ? 'public, max-age=2592000, immutable'
        : 'no-cache, must-revalidate'
    };
    var gzippable = /\.(js|css|html|json|md)$/.test(urlPath) &&
      (req.headers['accept-encoding'] || '').indexOf('gzip') >= 0;
    if (gzippable) {
      zlib.gzip(data, function (e2, buf) {
        if (e2) { headers['Content-Length'] = data.length; res.writeHead(200, headers); res.end(data); return; }
        headers['Content-Encoding'] = 'gzip';
        headers['Content-Length'] = buf.length;
        res.writeHead(200, headers);
        res.end(buf);
      });
    } else {
      headers['Content-Length'] = data.length;
      res.writeHead(200, headers);
      res.end(data);
    }
  });
}).listen(port, '0.0.0.0', function () {
  console.log('GTO 德州扑克已就绪！');
  console.log('  本机游玩:   http://localhost:' + port + '/');
  // 打印所有局域网地址（手机连同一 Wi-Fi 用）
  var os = require('os');
  var ifaces = os.networkInterfaces();
  Object.keys(ifaces).forEach(function (name) {
    ifaces[name].forEach(function (iface) {
      if (iface.family === 'IPv4' && !iface.internal) {
        console.log('  手机/局域网: http://' + iface.address + ':' + port + '/   (' + name + ')');
      }
    });
  });
});
