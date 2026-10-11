/* patch-6.js — 大厅三板块接线 + 启动统计恢复 */
const fs = require('fs');
let s = fs.readFileSync('js/main.js', 'utf8');

function rep(oldS, newS, tag) {
  if (!s.includes(oldS)) { console.log('NOT FOUND: ' + tag); process.exit(1); }
  s = s.replace(oldS, newS);
}

/* 1. 大厅三板块接线 */
rep(
`  UI.setSessionStats(SESS);   /* P1-D：刷新后立即显示历史统计 */
  UI.wireTopbar();
  UI.wireCharSelect();
  startWatchdog();`,

`  UI.setSessionStats(SESS);   /* P1-D：启动即恢复历史统计 */
  UI.wireTopbar();
  UI.wireCharSelect();
  startWatchdog();

  /* 大厅三板块 */
  document.getElementById('mc-train').addEventListener('click', function () {
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('start-modal').classList.remove('hidden');
  });
  document.getElementById('mc-multi').addEventListener('click', function () {
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('multi-modal').classList.remove('hidden');
  });
  document.getElementById('mc-data').addEventListener('click', function () {
    document.getElementById('landing').classList.add('hidden');
    document.getElementById('data-modal').classList.remove('hidden');
  });
  document.getElementById('btn-multi-back').addEventListener('click', function () {
    document.getElementById('multi-modal').classList.add('hidden');
    document.getElementById('landing').classList.remove('hidden');
  });
  document.getElementById('btn-data-back').addEventListener('click', function () {
    document.getElementById('data-modal').classList.add('hidden');
    document.getElementById('landing').classList.remove('hidden');
  });`,
'大厅三板块'
);

/* 2. btn-start 只绑一次（避免重复绑定） */
rep(
`  document.getElementById('btn-start').addEventListener('click', function () {`,
`  var gameStarted = false;
  document.getElementById('btn-start').addEventListener('click', function () {
    if (gameStarted) return;
    gameStarted = true;`,
'btn-start 去重'
);

fs.writeFileSync('js/main.js', s);
console.log('OK main.js 大厅三板块 + 启动去重');
