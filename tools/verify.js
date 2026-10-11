// verify.js — 用 Playwright 驱动真实浏览器验证立绘系统接入游戏后的表现
// 玩法：打开游戏 → 点开始 → 等牌局进入 → 截图；同时做 DOM 断言。
'use strict';
const path = require('path');
const { chromium } = require(path.join(
  'C:/Users/Tabby/.workbuddy/binaries/node/workspace/node_modules', 'playwright-core'));

const URL = process.argv[2] || 'http://127.0.0.1:8791/index.html';
const OUT = process.argv[3] || '_shots';

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:/Users/Tabby/AppData/Local/ms-playwright/chromium-1124/chrome-win/chrome.exe',
    args: ['--no-sandbox', '--disable-gpu'],
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  await page.goto(URL, { waitUntil: 'load' });
  await page.waitForTimeout(1200);

  // 选人弹窗截图
  await page.screenshot({ path: path.join(OUT, 'game-1-select.png') });

  // DOM 断言：角色卡片里应当是 <img>（PNG）而不是 <svg>
  const stats = await page.evaluate(() => {
    const cards = document.querySelectorAll('#char-grid .char-card');
    let img = 0, svg = 0;
    cards.forEach(c => {
      img += c.querySelectorAll('img').length;
      svg += c.querySelectorAll('svg').length;
    });
    const prev = document.getElementById('char-preview');
    return {
      cardCount: cards.length,
      cardImg: img,
      cardSvg: svg,
      previewImg: prev ? prev.querySelectorAll('img').length : -1,
      previewSvg: prev ? prev.querySelectorAll('svg').length : -1,
      hasPortraits: typeof window.Portraits !== 'undefined',
      availability: window.Portraits ? JSON.stringify(window.Portraits.available) : 'n/a'
    };
  });
  console.log('选人界面断言:', JSON.stringify(stats, null, 2));

  // 开局
  await page.click('#btn-start');
  await page.waitForTimeout(2500);

  const seatStats = await page.evaluate(() => {
    const seats = document.querySelectorAll('#seats .seat');
    let pt = 0, img = 0, svg = 0;
    seats.forEach(s => {
      pt += s.querySelectorAll('.pt').length;
      img += s.querySelectorAll('.portrait img').length;
      svg += s.querySelectorAll('.portrait svg').length;
    });
    const panel = document.getElementById('portrait-panel');
    return {
      seats: seats.length,
      seatPortrait_pt: pt,
      seatPortrait_img: img,
      seatPortrait_svg: svg,
      panelImg: panel ? panel.querySelectorAll('img').length : -1,
      panelSvg: panel ? panel.querySelectorAll('svg').length : -1,
      panelH: panel && panel.querySelector('.pt') ?
        getComputedStyle(panel.querySelector('.pt')).height : 'n/a'
    };
  });
  console.log('牌桌断言:', JSON.stringify(seatStats, null, 2));

  await page.screenshot({ path: path.join(OUT, 'game-2-table.png') });

  console.log('\nJS 错误数:', errors.length);
  errors.slice(0, 10).forEach(e => console.log('  ' + e));

  await browser.close();
  process.exit(errors.length ? 1 : 0);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
