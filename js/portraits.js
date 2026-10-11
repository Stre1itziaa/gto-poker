/* portraits.js — PNG 立绘系统（替代 characters.js 的 SVG 参数化方案）
 *
 * 设计目标
 *   1. 完全抛弃 SVG：角色资产为带 alpha 的 PNG 差分图。
 *   2. 零运行时依赖：纯 <img> + CSS transform，file:// 双击可玩。
 *   3. 动效靠 CSS 骨骼：呼吸 / 眨眼 / 发丝摆动 / 视线，各层独立延迟。
 *   4. 接口兼容：对外暴露与旧 Characters 相同的方法名，
 *      ui.js 只需把 root.Characters 换成 root.Portraits。
 *
 * 资产规范
 *   assets/characters/<charId>-<expr>.png
 *   expr ∈ idle | think | happy | sad | blink
 *   建议统一画布 760x1160（由 tools/align.py 归一化产出）
 *
 * 命名空间 window.Portraits
 */
(function (root) {
  'use strict';

  var BASE = 'assets/characters_v2/';
  var EXPRS = ['idle', 'think', 'happy', 'sad', 'blink'];
  /* 优化版后缀：assets/characters/<id>-<expr>-s.png（900px 高，约 280KB）
   * 由 tools/optimize.py 产出。开发时想看原图可改成 ''。 */
  var SUFFIX = '-s';
  var available = {};   // charId -> {expr: bool}

  /* ---------- 服装层（第二套立绘）----------
   * 资产命名：<id>-<服装key>-<expr>-s.png（如 suzu-club-idle-s.png）。
   * setCostume('club') 后 srcOf 全部改指部服文件；探测与回退缓存重建。
   * 服装是全局表现层：charId / 游戏逻辑完全不受影响。 */
  var COSTUMES = [
    { key: '', label: '默认服' },
    { key: 'club', label: '部服' },
    /* full: true 表示该套为「全身资产」——
     * 资产画布里头到脚完整入画（默认服/部服是胸上构图），
     * UI 层据此放大展示位并在容器上加 .pt-full 供 CSS 调整。 */
    { key: 'glam', label: '魅惑', full: true },
    /* v4 五包试点位（2026-09-20 裁决：五包制/全胸上构图；试点验收后转正命名） */
    { key: 'p0', label: '默认服v4' },
    { key: 'p1', label: '部服v4' },
    { key: 'p2', label: '特色装·壹' },
    { key: 'p3', label: '特色装·贰' },
    { key: 'p4', label: '特色装·叁' },
    { key: 'r1', label: '奖励·夏祭' },
    { key: 'r2', label: '奖励·盛夏' },
    { key: 'r3', label: '奖励·夜宴' }
  ];
  var activeCostume = '';
  try {
    var savedCostume = localStorage.getItem('gto-costume');
    if (savedCostume !== null && COSTUMES.some(function (c) { return c.key === savedCostume; })) {
      activeCostume = savedCostume;
    }
  } catch (e) { /* 非浏览器环境 */ }

  /* ---------- 角色名鉴（沿用原设定，人设年龄上调为成年） ---------- */
  /* voices：R5-施工 P1-7 每角色分声线的结算台词池（赢家 win / 输家 lose），
   * 大亏 ≥50bb 必出 lose 池安抚——替代全员共用一个池的同屏撞词。 */
  var CHARS = [
    { id: 'suzu', name: '夜樱铃', title: '夜樱部长', age: 23,
      quote: '别猜我什么时候诈唬——连我自己也不知道。',
      voices: {
        win: ['节奏在我这边♪', '你猜的第二次，还是错的。', '底池，收下了。', '这就是平衡的味道。'],
        lose: ['记下了，这一手。', '好牌运——先借你的。', '唔，让我重新建模。', '下一次，我的范围会更宽。']
      },
      accent: '#ff5f8f', aggro: 1.0, bluff: 1.0, sway: 5.2, breath: 3.8, blink: 4.6, look: 9.0 },
    { id: 'shiori', name: '白鹭诗织', title: '读牌魔女', age: 25,
      quote: '你手里的阻断牌，我都数过了。',
      voices: {
        win: ['都说了，我数过你的阻断牌。', '读完了，就这么简单。', '你的范围，漏风哦。', '计算完毕，谢谢底池。'],
        lose: ['……变量藏在我没看到的地方。', '记进笔记了。', '这一街的数据，归你。', '下一次，我不会算错。']
      },
      accent: '#7fa8e0', aggro: 0.9, bluff: 0.8, sway: 6.0, breath: 4.2, blink: 5.4, look: 11.0 },
    { id: 'natsu', name: '葵夏', title: '起手式狂人', age: 22,
      quote: '位置就是武器！BTN 我 48% 全开！',
      voices: {
        win: ['位置就是武器！', '全开——漂亮吧！', '这波节奏我带你飞♪', '起手式，完成！'],
        lose: ['可恶，被反超了！', '下一手我加倍开！', '运气而已，再来再来！', '唔……我的位置呢！']
      },
      accent: '#ffc258', aggro: 1.18, bluff: 1.3, sway: 4.2, breath: 3.2, blink: 3.8, look: 7.0 },
    { id: 'rin', name: '月见凛', title: '冰点计算者', age: 24,
      quote: '底池赔率不够。这是第二次说了。',
      voices: {
        win: ['底池赔率，足够了。', '计算无误。', '预期之内的结果。', '这就是 EV。'],
        lose: ['……方差，记下了。', '赔率不够也跟了吗。', '重算。下一次不会输。', '冷静，这只是波动。']
      },
      accent: '#a98fd8', aggro: 0.85, bluff: 0.7, sway: 6.6, breath: 4.6, blink: 6.2, look: 12.0 },
    { id: 'yuki', name: '绵雪', title: '温和的粘性', age: 21,
      quote: 'MDF 防守……我一次都没有迟到过哦。',
      voices: {
        win: ['嘿嘿，粘到你了♪', '慢慢来，底池不会跑。', '谢谢款待～', '守住了哦。'],
        lose: ['呜，被读掉了…', '下次我会守得更久一点。', '唔……再粘一次试试。', '没关系，下一手！']
      },
      accent: '#8ec2e0', aggro: 1.05, bluff: 0.85, sway: 5.6, breath: 3.6, blink: 5.0, look: 8.5 },
    { id: 'ume', name: '绿川小梅', title: '元气几何学', age: 22,
      quote: '几何下注！每条街等比例铺满！',
      voices: {
        win: ['几何下注，等比收割！', '每条街都铺满——赢啦！', '计算正确，奖励我♪', '比例完美！'],
        lose: ['呜，比例崩了…', '重新计算，下一手！', '可恶，被反几何了！', '分数会追回来的！']
      },
      accent: '#58b568', aggro: 1.12, bluff: 1.2, sway: 4.6, breath: 3.0, blink: 3.4, look: 6.5 }
  ];

  /* 全局安抚池：大亏（净 ≥50bb）时必出，盖过普通输家台词 */
  var COMFORT = [
    '深呼吸——扑克很长，这一手很短。',
    '输掉的是筹码，赢回的是范围。',
    '部长的安慰：河牌是大家的。',
    '记住这一手，但别记住疼。'
  ];

  function byId(id) {
    for (var i = 0; i < CHARS.length; i++) if (CHARS[i].id === id) return CHARS[i];
    return CHARS[0];
  }

  /* ---------- 资产探测与回退 ----------
   * 完整差分（6 角色 × 5 表情）是分批产出的，未产出的角色不能渲染
   * 一个必定 404 的 <img>（会显示裂图占位符、污染控制台）。
   * 策略：
   *   1. 一个角色只要有任意一张图可用，就整角色可用（缺失表情回退该图）；
   *   2. 一个角色完全没图，就整体回退到首个可用角色的图像；
   *   3. 全部没有图时，返回空字符串，调用方显示文字占位。 */

  var FALLBACK_ORDER = [];        // 已确认有资产的角色 id 列表
  var scanning = null;            // 探测中的 Promise，避免重复扫描

  function readyChar(id) {
    /* 把一个角色映射到「实际有图」的角色 id */
    if (available[id] && available[id].idle) return id;
    if (FALLBACK_ORDER.length) return FALLBACK_ORDER[0];
    return null;
  }

  /* 扫描：先探 idle（一张就够判断角色是否有资产），有则补齐其余差分 */
  function scan() {
    if (scanning) return scanning;
    /* 手机性能修复：首屏只探测 idle（6 张小图即出首帧），
     * 其余表情差分后台补齐——完成前用 idle 兜底，下次 render 自然拾取 */
    scanning = Promise.all(CHARS.map(function (c) {
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
    return scanning;
  }

  /* 手机性能修复：90 张 .webp（≈90KB）与 .png（≈260KB）并存，webp 优先；
   * 探测记录每个 (角色,表情) 实际可用的扩展名，srcOf 按记录出 URL。 */
  var extUsed = {};   // id:expr:tier -> 'webp' | 'png'

  /* 二档资产：-t（300px 高，≈16KB）给座位/头像/横带等 ≤210px 的展示位，
   * -s（900px 高）只给选人大预览（330px）。探测按 t → s.webp → s.png 兜底。 */
  function tierOf(px) { return px >= 300 ? 's' : 't'; }
  function srcOfExt(id, expr, tier, ext) {
    var ck = costumeFor(id);
    var cid = ck ? id + '-' + ck : id;
    return BASE + cid + '-' + expr + (tier === 's' ? SUFFIX : '-t') + '.' + ext;
  }
  function srcOf(id, expr, px) {
    var tier = tierOf(px || 0);
    return srcOfExt(id, expr, tier, extUsed[id + ':' + expr + ':' + tier] || 'webp');
  }
  /* <img> 加载失败兜底：-t.webp → -s.webp → -s.png（资产不全的极端情况） */
  root.__ptFallback = function (img) {
    /* 回退链: t.webp → s.webp → s.png → p1 同名(冷启动裸名在 v2 无资产时的一跳) */
    var src = img.getAttribute('src') || '';
    var step = img.dataset.fbStep || '';
    var next = null;
    if (step === '' && src.indexOf('-t.webp') >= 0) {
      next = src.replace('-t.webp', '-s.webp');
    } else if (step !== '2' && src.indexOf('.webp') >= 0) {
      next = src.replace('.webp', '.png');
    } else if (src.indexOf('/characters_v2/') >= 0 && !/-p\d-/.test(src)) {
      next = src.replace(/-(idle|think|happy|sad|blink)-/, '-p1-$1');
    }
    if (next && next !== src) {
      img.dataset.fbStep = step === '' ? '1' : '2';
      img.onerror = root.__ptFallback;
      img.src = next;
    } else {
      img.onerror = null;
    }
  };

  function getCostume() { return activeCostume; }

  /* ---------- 每角色独立服装（好感度解锁后分角色穿戴） ----------
   * costumeMap: charId -> 服装key，存 localStorage 'gto-costume-map'。
   * costumeFor(id) = map[id] || activeCostume（旧档兼容：未设置时回落全局）。 */
  var costumeMap = {};
  try { costumeMap = JSON.parse(root.localStorage.getItem('gto-costume-map') || '{}') || {}; } catch (e) { costumeMap = {}; }
  function saveCostumeMap() {
    try { root.localStorage.setItem('gto-costume-map', JSON.stringify(costumeMap)); } catch (e) { /* 隐私模式 */ }
  }
  function costumeFor(id) { return costumeMap[id] || activeCostume || 'p1'; }   /* 空档回落 p1: v2 仅存带前缀资产, 免冷启动 404 */
  function setCharCostume(id, key) {
    var ok = COSTUMES.some(function (c) { return c.key === key; });
    if (!ok || costumeMap[id] === key) return scan();
    costumeMap[id] = key;
    saveCostumeMap();
    delete available[id];
    for (var k in extUsed) { if (Object.prototype.hasOwnProperty.call(extUsed, k) && k.indexOf(id + ':') === 0) delete extUsed[k]; }
    scanning = null;
    return scan();
  }
  function getCharCostume(id) { return costumeFor(id); }
  /* 指定服装直出 URL（图鉴用，绕过全局/每角色状态） */
  function srcOfCostume(id, key, expr, px) {
    var tier = tierOf(px || 0);
    var cid = key ? id + '-' + key : id;
    return BASE + cid + '-' + expr + (tier === 's' ? SUFFIX : '-t') + '.webp';
  }

  /* 当前服装是否为全身资产（决定选人界面的展示尺寸） */
  function isFullbody() {
    for (var i = 0; i < COSTUMES.length; i++) {
      if (COSTUMES[i].key === activeCostume) return !!COSTUMES[i].full;
    }
    return false;
  }

  /* 切换服装：重置探测缓存并重新扫描（返回 scan Promise，便于调用方重绘）。
   * 注意 available 被导出为引用，这里只做原地清空，不做重新赋值。 */
  function setCostume(key) {
    var ok = COSTUMES.some(function (c) { return c.key === key; });
    if (!ok || key === activeCostume) return scan();
    activeCostume = key;
    try { localStorage.setItem('gto-costume', key); } catch (e) {}
    for (var k in available) { if (Object.prototype.hasOwnProperty.call(available, k)) delete available[k]; }
    for (var e in extUsed) { if (Object.prototype.hasOwnProperty.call(extUsed, e)) delete extUsed[e]; }
    FALLBACK_ORDER.length = 0;
    scanning = null;
    return scan();
  }

  function resolveExpr(id, expr) {
    var av = available[id];
    if (!av) return expr;
    if (av[expr]) return expr;
    if (av.idle) return 'idle';
    for (var i = 0; i < EXPRS.length; i++) if (av[EXPRS[i]]) return EXPRS[i];
    return expr;
  }

  function setAvail(id, expr, ok, ext, tier) {
    if (!available[id]) available[id] = {};
    available[id][expr] = ok;
    if (ok && ext) extUsed[id + ':' + expr + ':' + (tier || 't')] = ext;
  }
  function probe(id, expr) {
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
  }

  function probeAll(id, exprs) {
    var list = exprs || EXPRS;
    return Promise.all(list.map(function (e) { return probe(id, e); }));
  }

  /* ---------- 生成立绘 DOM ----------
   * 返回一段 HTML 字符串，结构与旧 charSVG 的调用点兼容。
   *
   * mode:
   *   'standing' 完整立绘（默认）
   *   'bust'     半身（下半裁切，用于座位头像）
   */
  var uidN = 0;

  function portraitHTML(id, expr, px, mode) {
    /* S1 深防：id 只允许安全字符进 HTML 拼接（入口已白名单，这里是最后防线） */
    id = String(id == null ? '' : id).replace(/[^A-Za-z0-9_-]/g, '');
    var c = byId(id);
    mode = mode || 'standing';
    var h = px || 210;
    var aspect = 590 / 900;                        // 资产画布宽高比
    var w = Math.round(h * aspect);

    /* 资产未就绪 / 该角色无图：给一个同尺寸空位，避免布局跳动与裂图 */
    var useId = readyChar(id);
    if (!useId) {
      return '<div class="pt pt-empty" style="width:' + w + 'px;height:' + h + 'px" ' +
        'data-char="' + id + '"></div>';
    }
    expr = resolveExpr(useId, expr || 'idle');
    var cc = byId(useId);
    var uid = useId + '_' + (uidN++);

    var cls = 'pt pt-' + uid + (mode === 'bust' ? ' pt-bust' : '') +
      (isFullbody() && mode !== 'bust' ? ' pt-full' : '') +
      (useId !== id ? ' pt-sub' : '');
    var style = '--pt-sway:' + cc.sway + 's;--pt-breath:' + cc.breath + 's;' +
      '--pt-blink:' + cc.blink + 's;--pt-look:' + cc.look + 's;' +
      'width:' + w + 'px;height:' + h + 'px;';

    var idleSrc = srcOf(useId, expr, h);
    var blinkSrc = srcOf(useId, 'blink', h);
    var canBlink = (expr === 'idle' && available[useId] && available[useId].blink);

    var html = '<div class="' + cls + '" style="' + style + '" data-char="' + id + '" data-expr="' + expr + '">';
    html += '<span class="pt-glow" style="background:radial-gradient(closest-side,' + cc.accent + '55,transparent)"></span>';
    var fb = ' onerror="__ptFallback(this)"';
    html += '<span class="pt-breath">';
    html += '<span class="pt-sway">';
    html += '<img class="pt-layer" src="' + idleSrc + '" alt="' + c.name + '" draggable="false"' + fb + '>';
    if (canBlink) {
      html += '<img class="pt-eye" src="' + blinkSrc + '" alt="" draggable="false"' + fb + '>';
    }
    html += '</span></span>';
    html += '</div>';
    return html;
  }

  /* 只取图片本身（无包裹层），用于需要极简 DOM 的地方 */
  function portraitImg(id, expr, px) {
    var c = byId(id);
    var useId = readyChar(id);
    if (!useId) return '<span class="pt-empty" style="display:inline-block;height:' + (px || 210) + 'px"></span>';
    expr = resolveExpr(useId, expr || 'idle');
    return '<img class="pt-plain" src="' + srcOf(useId, expr, px || 210) + '" ' +
      'alt="' + c.name + '" draggable="false" onerror="__ptFallback(this)" style="height:' + (px || 210) + 'px">';
  }

  /* ---------- 座位分配（与原 assign 行为一致） ---------- */
  function assign(table, playerId) {
    var selId = CHARS[0].id;
    try { selId = localStorage.getItem('gto-char') || selId; } catch (e) { /* 隐私模式 */ }
    var pool = CHARS.slice().sort(function () { return Math.random() - 0.5; });
    table.players.forEach(function (p) {
      var c;
      if (p.idx === playerId) c = byId(selId);
      else { do { c = pool.shift(); } while (c && c.id === selId); if (!c) c = CHARS[0]; }
      p.charId = c.id;
      p.aggro = c.aggro || 1;
      p.bluff = c.bluff || 1;
      p.name = p.idx === playerId ? c.name + '（你）' : c.name;
    });
  }

  /* 分声线台词：按角色取池；大亏时用全局安抚池（main.js 判定） */
  function voiceOf(charId, kind) {
    var c = byId(charId);
    var pool = (c && c.voices && c.voices[kind]) || (kind === 'win' ? EMOTES_FALLBACK.win : EMOTES_FALLBACK.lose);
    return pool[Math.floor(Math.random() * pool.length)];
  }
  var EMOTES_FALLBACK = {
    win: ['这局是我的节奏♪', '承让承让～'],
    lose: ['呜……记下了', '唔，下一局！']
  };

  root.Portraits = {
    ALL: CHARS,
    EXPRS: EXPRS,
    COSTUMES: COSTUMES,
    getCostume: getCostume,
    isFullbody: isFullbody,
    setCostume: setCostume, getCostume: getCostume, COSTUMES: COSTUMES,
    setCharCostume: setCharCostume, getCharCostume: getCharCostume, costumeFor: costumeFor, srcOfCostume: srcOfCostume,
    byId: byId,
    html: portraitHTML,
    charSVG: portraitHTML,
    img: portraitImg,
    assign: assign,
    probe: probe,
    probeAll: probeAll,
    scan: scan,
    readyChar: readyChar,
    available: available,
    srcOf: srcOf,
    voiceOf: voiceOf,
    COMFORT: COMFORT,
    EMOTES: {
      win: ['这局是我的节奏♪', '频率，学学？', '承让承让～', '计算完毕！', '就这？'],
      lose: ['呜……记下了', '可恶，被读心了', '唔，下一局！', '运气而已！'],
      playerWin: ['嘿嘿，到手了♪', '稳住，我们能赢', '这把打得漂亮'],
      playerLose: ['呜，被河杀了…', '可恶，下一手讨回来！']
    }
  };
})(typeof window !== 'undefined' ? window : globalThis);
