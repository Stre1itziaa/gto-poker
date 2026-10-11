/* smoke_regression.js — 冒烟回归（无头，node test/smoke_regression.js）
 * 试玩报告 §四建议：热更前后各跑一遍，防「上版本好的这版本坏了」。
 * 四项断言：资产完整性 / 牌面映射 / 好感度经济 / 服装解锁与每角色穿着 */
'use strict';
global.window = global;
global.localStorage = {
  _s: {},
  getItem(k) { return this._s[k] ?? null; },
  setItem(k, v) { this._s[k] = String(v); },
  removeItem(k) { delete this._s[k]; }
};
global.localStorage._s['gto-char'] = 'suzu';
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..');

let pass = 0, fail = 0;
function ok(cond, label) {
  if (cond) { pass++; console.log('  ✓ ' + label); }
  else { fail++; console.log('  ✗ ' + label); }
}

/* 1) 资产完整性 */
console.log('[1] 资产完整性');
const v2 = path.join(ROOT, 'assets', 'characters_v2');
const v2files = fs.readdirSync(v2);
ok(v2files.length >= 720, `characters_v2 ≥ 720 文件 (实际 ${v2files.length})`);
const RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];
const SUITS = ['s', 'h', 'd', 'c'];
const KEYS = ['p0', 'p1', 'p2', 'p3', 'p4', 'r1', 'r2', 'r3'];
const CHARS = ['natsu', 'suzu', 'shiori', 'rin', 'yuki', 'ume'];
let missing = 0;
for (const c of CHARS) for (const k of KEYS) {
  if (!fs.existsSync(path.join(v2, `${c}-${k}-idle-s.webp`))) { missing++; console.log('    缺 ' + `${c}-${k}-idle-s.webp`); }
}
ok(missing === 0, `6人×8套 idle 主图齐全 (缺 ${missing})`);
const cardsDir = path.join(ROOT, 'assets', 'cards');
ok(fs.readdirSync(cardsDir).length >= 53, `牌面 ≥ 53 文件 (实际 ${fs.readdirSync(cardsDir).length})`);

/* 2) 牌面映射 */
console.log('[2] 牌面映射');
require('./../js/cards.js');
ok(global.Cards.cardStr(51) === 'A♣', 'cardStr(51) = A♣');
ok(global.Cards.rankDisplay(8) === '10', 'rankDisplay(8) = 10');
const cardFileOf = (c) => {
  const RF = ['2','3','4','5','6','7','8','9','10','J','Q','K','A'];
  const SF = ['s','h','d','c'];
  return `face_${RF[global.Cards.rankOf(c)]}${SF[global.Cards.suitOf(c)]}.png`;
};
let cardMissing = 0;
for (let c = 0; c < 52; c++) {
  if (!fs.existsSync(path.join(cardsDir, cardFileOf(c)))) cardMissing++;
}
ok(cardMissing === 0, `52 张牌面文件与 cardHTML 命名全对齐 (缺 ${cardMissing})`);

/* 3) 好感度经济 */
console.log('[3] 好感度经济');
require('./../js/portraits.js');
require('./../js/affection.js');
const A = global.Affection;
const wonHand = { bb: 20, pots: [{ handName: '一对', winners: [0] }], players: [{ won: 120, refund: 0, committed: 40 }] };
const r1 = A.onHand(wonHand);
ok(r1.gain === 18, `赢+摊牌+首胜 = 18 (实际 ${r1.gain})`);
const r2 = A.onHand({ bb: 20, pots: [], players: [{ won: 0, refund: 0, committed: 40 }] });
ok(r2.gain === 1, `输掉陪伴分 = 1 (实际 ${r2.gain})`);
const r3 = A.rankOnHand({ bb: 20, pots: [], players: [{ won: 300, refund: 0, committed: 40 }] });
ok(r3.delta === 13, `段位 +13bb (实际 ${r3.delta})`);
ok(A.rankOnHand({ bb: 20, pots: [], players: [{ won: 0, refund: 0, committed: 500 }] }).delta === -6, '大输保底 -6');

/* 4) 服装解锁与每角色穿着 */
console.log('[4] 服装解锁');
ok(A.isCostumeUnlocked('suzu', 'p1') === true, 'p1 初始解锁');
ok(A.isCostumeUnlocked('suzu', 'r3') === false, 'r3 满级前锁定 (当前 Lv1)');
const P = global.Portraits;
ok(typeof P.setCharCostume === 'function', '每角色服装 API 存在');
P.setCharCostume('suzu', 'p1');
ok(P.getCharCostume('suzu') === 'p1', 'setCharCostume 生效');
ok(P.srcOfCostume('rin', 'r3', 'idle', 118).indexOf('rin-r3-idle-t.webp') > 0, 'srcOfCostume 直出指定服装 URL');

/* 5) 接线源码断言（防热更回归） */
console.log('[5] 接线断言');
const uiSrc = fs.readFileSync(path.join(ROOT, 'js', 'ui.js'), 'utf8');
const lobbySrc = fs.readFileSync(path.join(ROOT, 'js', 'lobby.js'), 'utf8');
const mainSrc = fs.readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8');
ok(uiSrc.indexOf('cface') > 0, 'ui.js: cardHTML 输出图像牌面');
ok(uiSrc.indexOf("stage-portrait") >= 0 === false, 'ui.js 不含大厅舞台(归属 lobby.js)');
ok(lobbySrc.indexOf("addEventListener('click', onPortraitClick)") > 0, 'lobby.js: 舞台点击已绑定(表情轮播)');
ok(mainSrc.indexOf('Affection.onHand') > 0, 'main.js: 结算挂点接好感度');
const mpSrc = fs.readFileSync(path.join(ROOT, 'js', 'mp.js'), 'utf8');
ok(mpSrc.indexOf('Affection.onHand') > 0, 'mp.js: 客人结算接好感度');
const serveSrc = fs.readFileSync(path.join(ROOT, 'serve.js'), 'utf8');
ok(serveSrc.indexOf('writeHead(429') < 0, 'serve.js: 留档无 429 拒绝(滚动删最旧)');

console.log(`\n=== 冒烟回归: ${pass} 通过 / ${fail} 失败 ===`);
process.exit(fail ? 1 : 0);
