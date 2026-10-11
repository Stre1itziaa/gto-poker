# patch_perf2.py — 二轮手机性能：立绘分档加载 + serve.js 长缓存/gzip
# 运行：python tools/patch_perf2.py （在 game/ 目录）
import io

# ============ portraits.js：tier 分档 ============
p = 'js/portraits.js'
s = io.open(p, encoding='utf-8').read()

old = """  /* 手机性能修复：90 张 .webp（≈90KB）与 .png（≈260KB）并存，webp 优先；
   * 探测记录每个 (角色,表情) 实际可用的扩展名，srcOf 按记录出 URL。 */
  var extUsed = {};   // id:expr -> 'webp' | 'png'

  function srcOfExt(id, expr, ext) {
    var cid = activeCostume ? id + '-' + activeCostume : id;
    return BASE + cid + '-' + expr + SUFFIX + '.' + ext;
  }
  function srcOf(id, expr) {
    return srcOfExt(id, expr, extUsed[id + ':' + expr] || 'png');
  }"""
new = """  /* 手机性能修复：90 张 .webp（≈90KB）与 .png（≈260KB）并存，webp 优先；
   * 探测记录每个 (角色,表情) 实际可用的扩展名，srcOf 按记录出 URL。 */
  var extUsed = {};   // id:expr:tier -> 'webp' | 'png'

  /* 二档资产：-t（300px 高，≈16KB）给座位/头像/横带等 ≤210px 的展示位，
   * -s（900px 高）只给选人大预览（330px）。探测按 t → s.webp → s.png 兜底。 */
  function tierOf(px) { return px >= 300 ? 's' : 't'; }
  function srcOfExt(id, expr, tier, ext) {
    var cid = activeCostume ? id + '-' + activeCostume : id;
    return BASE + cid + '-' + expr + (tier === 's' ? SUFFIX : '-t') + '.' + ext;
  }
  function srcOf(id, expr, px) {
    var tier = tierOf(px || 0);
    return srcOfExt(id, expr, tier, extUsed[id + ':' + expr + ':' + tier] || 'webp');
  }
  /* <img> 加载失败兜底：-t.webp → -s.webp → -s.png（资产不全的极端情况） */
  root.__ptFallback = function (img) {
    img.onerror = null;
    var src = img.getAttribute('src') || '';
    if (src.indexOf('-t.webp') >= 0) img.src = src.replace('-t.webp', '-s.webp');
    else if (src.indexOf('.webp') >= 0) img.src = src.replace('.webp', '.png');
  };"""
assert s.count(old) == 1, 'srcOf block'
s = s.replace(old, new)

old = """  function probe(id, expr) {
    if (available[id] && available[id][expr] !== undefined) return Promise.resolve(available[id][expr]);
    return tryExt(id, expr, ['webp', 'png']);
  }
  function tryExt(id, expr, exts) {
    if (!exts.length) { setAvail(id, expr, false); return Promise.resolve(false); }
    var ext = exts[0];
    return new Promise(function (res) {
      var im = new Image();
      im.onload = function () { setAvail(id, expr, true, ext); res(true); };
      im.onerror = function () { tryExt(id, expr, exts.slice(1)).then(res); };
      im.src = srcOfExt(id, expr, ext);
    });
  }"""
new = """  function probe(id, expr) {
    if (available[id] && available[id][expr] !== undefined) return Promise.resolve(available[id][expr]);
    return tryTier(id, expr, [
      { tier: 't', ext: 'webp' }, { tier: 's', ext: 'webp' }, { tier: 's', ext: 'png' }
    ]);
  }
  function tryTier(id, expr, chain) {
    if (!chain.length) { setAvail(id, expr, false); return Promise.resolve(false); }
    var step = chain[0];
    return new Promise(function (res) {
      var im = new Image();
      im.onload = function () { setAvail(id, expr, true, step.ext, step.tier); res(true); };
      im.onerror = function () { tryTier(id, expr, chain.slice(1)).then(res); };
      im.src = srcOfExt(id, expr, step.tier, step.ext);
    });
  }"""
assert s.count(old) == 1, 'probe block'
s = s.replace(old, new)

old = """  function setAvail(id, expr, ok, ext) {
    if (!available[id]) available[id] = {};
    available[id][expr] = ok;
    if (ok && ext) extUsed[id + ':' + expr] = ext;
  }"""
new = """  function setAvail(id, expr, ok, ext, tier) {
    if (!available[id]) available[id] = {};
    available[id][expr] = ok;
    if (ok && ext) extUsed[id + ':' + expr + ':' + (tier || 't')] = ext;
  }"""
assert s.count(old) == 1, 'setAvail block'
s = s.replace(old, new)

old = """    scanning = Promise.all(CHARS.map(function (c) {
      return probe(c.id, 'idle').then(function (ok) {
        if (!ok) return null;
        FALLBACK_ORDER.push(c.id);
        return null;
      });
    })).then(function () {
      FALLBACK_ORDER.forEach(function (id) { probeAll(id); });   // fire-and-forget
      return FALLBACK_ORDER.slice();
    });
    return scanning;"""
new = """    scanning = Promise.all(CHARS.map(function (c) {
      return probe(c.id, 'idle').then(function (ok) {
        if (!ok) return null;
        FALLBACK_ORDER.push(c.id);
        return null;
      });
    })).then(function () {
      setTimeout(function () {                    // 延迟补差分：不与首屏抢带宽
        FALLBACK_ORDER.forEach(function (id) { probeAll(id); });
      }, 2500);
      return FALLBACK_ORDER.slice();
    });
    return scanning;"""
assert s.count(old) == 1, 'scan block'
s = s.replace(old, new)

old = """    var idleSrc = srcOf(useId, expr);
    var blinkSrc = srcOf(useId, 'blink');"""
new = """    var idleSrc = srcOf(useId, expr, h);
    var blinkSrc = srcOf(useId, 'blink', h);"""
assert s.count(old) == 1, 'portraitHTML src block'
s = s.replace(old, new)

old = """    html += '<span class="pt-breath">';
    html += '<span class="pt-sway">';
    html += '<img class="pt-layer" src="' + idleSrc + '" alt="' + c.name + '" draggable="false">';
    if (canBlink) {
      html += '<img class="pt-eye" src="' + blinkSrc + '" alt="" draggable="false">';
    }"""
new = """    var fb = ' onerror="__ptFallback(this)"';
    html += '<span class="pt-breath">';
    html += '<span class="pt-sway">';
    html += '<img class="pt-layer" src="' + idleSrc + '" alt="' + c.name + '" draggable="false"' + fb + '>';
    if (canBlink) {
      html += '<img class="pt-eye" src="' + blinkSrc + '" alt="" draggable="false"' + fb + '>';
    }"""
assert s.count(old) == 1, 'img tag block'
s = s.replace(old, new)

old = """    return '<img class="pt-plain" src="' + srcOf(useId, expr) + '" ' +
      'alt="' + c.name + '" draggable="false" style="height:' + (px || 210) + 'px">';"""
new = """    return '<img class="pt-plain" src="' + srcOf(useId, expr, px || 210) + '" ' +
      'alt="' + c.name + '" draggable="false" onerror="__ptFallback(this)" style="height:' + (px || 210) + 'px">';"""
assert s.count(old) == 1, 'portraitImg block'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('portraits.js tiered')

# ============ main.js：首页横带走 t 档 ============
p = 'js/main.js'
s = io.open(p, encoding='utf-8').read()
old = """      d.innerHTML = '<img src="' + Portraits.srcOf(c.id, 'idle') + '" alt="' + c.name + '" draggable="false">' +"""
new = """      d.innerHTML = '<img src="' + Portraits.srcOf(c.id, 'idle', 118) + '" alt="' + c.name + '" draggable="false" onerror="__ptFallback(this)">' +"""
assert s.count(old) == 1, 'landing chars block'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('main.js patched')

# ============ serve.js：长缓存 + ETag 304 + gzip ============
p = 'serve.js'
s = io.open(p, encoding='utf-8').read()
old = """'use strict';
var http = require('http');
var fs = require('fs');
var path = require('path');"""
new = """'use strict';
var http = require('http');
var fs = require('fs');
var path = require('path');
var zlib = require('zlib');
var crypto = require('crypto');"""
assert s.count(old) == 1, 'serve requires block'
s = s.replace(old, new)

old = """  fs.readFile(file, function (err, data) {
    if (err) { res.writeHead(404); res.end('Not Found'); return; }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file)] || 'application/octet-stream',
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache'
    });
    res.end(data);
  });"""
new = """  fs.readFile(file, function (err, data) {
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
    var gzippable = /\\.(js|css|html|json|md)$/.test(urlPath) &&
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
  });"""
assert s.count(old) == 1, 'serve readFile block'
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('serve.js cached+gzip')

# ============ index.html：版本 ============
p = 'index.html'
s = io.open(p, encoding='utf-8').read()
s = s.replace('js/portraits.js?v=20260918h', 'js/portraits.js?v=20260918i')
s = s.replace('js/main.js?v=20260918h', 'js/main.js?v=20260918i')
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('versions bumped')
