# 《夜樱扑克部》第 18 次回访 · 互动与演出审计报告

审计员：雀魂老玩家「呜帕呜帕」（表情包战神）  
时间：2026-09-25 01:05–01:45 · 版本：雀魂式大厅上线后  
方法：Playwright 无头 1600×900，真实点击走查 + 5 连手结算深探 + 代码走读互证。  
产物：`test/play_new/lobby/`（24 张状态截图 + audit.json + showdown_probe.json）、`test/play_new/wupa/`（联机尝试留档）、临时脚本 `test/wupa_lobby_audit.py` / `test/wupa_emote_probe.py` / `test/wupa_showdown_probe.py`。

---

## A. 新大厅互动审计（雀魂式大厅 · 首页重构）

测试路径：首页舞台立绘点击轮播 → 2.6s idle 回位 → 快速连点 → 部员切换 ×6 → 服装切换 ×5 → reload 持久化 → 与选人弹窗/牌局内一致性。全部截图存 `play_new/lobby/00~05_*.png`。

### ① 点击立绘轮播五表情：顺序 ✓ / 过渡 ✗
- 实测顺序：idle → **happy → think → sad → blink → idle**，5 连点全部命中（`01_expr1~5_*.png`），与 `lobby.js` `EXPRS=['idle','happy','think','sad','blink']` 一致；所有差分 `naturalWidth=590`，无破图。
- 2.6s 无操作回 idle ✓（点 happy 后静置 3.2s 复原）；快速连点 6 次轮播不错乱，revert 定时器 `clearTimeout` 处理正确。
- 差分质量高：happy（眯眼+星星+腮红）、think（抵唇凝视）、sad（泪眼揪衣角）、blink（安闭目），构图有真差异，呜帕满意。
- **问题 A1（过渡缺失）**：表情切换是 `img.src` 硬切，`#stage-portrait img` 无任何 transition/keyframe（只有常驻 `stageFloat` 浮动），雀魂式的小弹跳/淡入完全没有。另 `#lobby-backdrop` 声明的 `transition: background-image .4s ease` 在 Chrome 是 no-op（background-image 不可插值）——写了等于没写。
- **问题 A2（双头维护）**：`lobby.js` EXPRS 顺序为 `happy,think`，`portraits.js` 为 `think,happy`——同一列表两处维护且已经分叉，迟早出戏。
- 小项：`#stage-hint`「点击立绘换表情」首次点击后不淡出，常驻左下角。

### ② 部员切换 ✓
- 6 名部员（夜樱铃/白鹭诗织/葵夏/月见凛/绵雪/绿川小梅）逐个点击：铭牌姓名/称号/台词、背景模糊立绘、缩略图选中框三件套全部同步（`03_char0~5_*.png`）；`localStorage['gto-char']` 正确写入；切部员后表情位重置 idle ✓。
- 小项：`#stage-chars` 声明 `role=tablist`，但子项 `.sw-char` 无 `role=tab`/`aria-selected`，读屏与键盘状态不可知。

### ③ 服装切换 ✓
- 5 包全通：默认服v4 / 部服v4 / 特色·和趣 / 特色·职业 / 特色·主题，点击后 `Portraits.setCostume` 重扫并整套换装——大立绘、6 枚缩略图、背景全部跟随（`04_costume0~4_*.png`），无破图；`localStorage['gto-costume']` ✓。
- 持久化 ✓：选「绿川小梅 + 特色·主题」后 reload，角色/服装/选中态完整复原（`05_after_reload.png`）。`ensureCostume` 把旧档（''/club/glam）强制迁移 p1，新环境首屏即为部服v4 ✓。
- 一致性 ✓：大厅选的服装同步到选人弹窗大预览与牌局内站立立绘（`suzu-p1-*-t.webp`）。
- **问题 A3（折行）**：右栏「服装」opt-row 一行装不下 5 个 tab，「特色·主题」折到第二行且与「理论支撑」脚注贴得过近（见 `00_lobby_initial.png`）。

### ④ 大厅整体
- 结构对标雀魂成立：舞台+铭牌+台词+部员栏+服装行+模式卡+顶栏统计，氛围在线，本次重构方向呜帕认可。
- **问题 A4（自动化不友好）**：`stageFloat` 无限浮动使 Playwright `locator.click()` 稳定性检查永久超时（本审计被迫改用 JS 派发 click）；E2E 与未来自动化都会撞这堵墙。立绘 `img` 亦不可键盘聚焦（无 tabindex、无 Enter 触发）。

---

## B. 牌局演出回归（含旧账复查）

联机说明：房间 GBY7TC（00:55:02 建房，见 `test/pr_code.txt`）为挂机房主 + 自动续局，实测 3.7 手/分钟永不停歇；`mp.js` 中房主开局后对所有 join 一律回 `busy`（「房间已开局并自动续局中…房主可回大厅重开新局」）。本次按规程 **20 秒间隔重试 30 次全部 busy**（进房时第 28 手，弃权时第 104+ 手）。故牌局演出以 **GTO 训练（单机）5+2 手实测**取证——气泡/台词/差分均为 `ui.js`/`main.js` 共享代码，多人局仅经 `fx` 转发进同一 `UI.showEmote`（`mp.js` applyFx），结论对多人同样成立；`applySnap` 不重建座位 DOM，多人亦无清场。

### 旧账复查表

| # | 旧账 | 现状 | 证据 |
|---|------|------|------|
| B1 | 气泡跨手残留 | **❌ 未修，实测 5/5 手 100% 残留** | `08_next_hand_first_beat.png`、`23_residue_after_sd1.png`：点完「下一局」进新手翻前第一拍，上一手两条结算气泡（「起手式，完成！」「分数会追回来的！」）仍挂在座位上。根因：无 startHand 清场、`render()` 不重建 `.emote`、只靠 4.5s 定时器；结算出词→弹层延迟 600ms→下一局 ≤2s，残留是必然事件。多人局 `applySnap` 同样不清理 |
| B2 | 台词复读 | **⚠️ 半修** | `main.js` R5 `pickFresh` 的 `usedQuotes` 是 showdown 处理器**局部变量**，只防「同一次结算双赢家撞词」；跨手仍是裸随机（每角色 4 句池，连赢两手 25% 概率复读同一句）。注释宣称「连续两手…不再复读」与实现不符。本次 5 连手实测 0 复读纯属样本运气 |
| B3 | 数据页牌谱回看 | **✅ 正常** | `09/10_data_*.png`：双手谱全展开（逐街动作/摊牌亮牌/边池分账/筹码+bb 双口径），盈亏曲线、对手倾向表（VPIP/PFR/判定样本）、范围筛选 chips、导入/导出/清空、返回大厅 sticky 条全在位 |
| B4 | 结算弹层盖气泡 | ✅ 已修（R3） | 弹层延迟 600ms，`07_showdown_1.png` 可见气泡先露脸 |
| B5 | 同屏气泡上限 | ✅ 逻辑在 | `ui.js` `emoteOrder` 最多 3 个、挤掉最旧（静态确认） |
| B6 | 差分演出 | ✅ 正常 | 结算站立立绘 win→happy / lose→sad、新手回 idle（showdown_probe.json：suzu-p1-sad-t / suzu-p1-happy-t / suzu-p1-idle-t 三态轮转） |
| B7 | 分声线台词池 | ✅ 正常 | 每角色独立 win/lose 池 + 大亏安抚池逻辑在位（本次未触发大亏） |
| B8 | **新账：快捷表情条单机失灵** | **❌** | 实测点 4 个 chip（你好♪/打得漂亮！/呜…/就这？）全程 **0 气泡**（`20_emote_chip*.png`）。根因：`sendQuickEmote` 判 `root.MP && root.MP.sendEmote` 即走联机路径，但 MP 模块常驻加载；`MP.sendEmote` 内 `st.phase!=='game'` 在单机直接 return——静默丢弃，本地回显分支 `showEmote(0,txt)` 是死代码 |

### 新增连带发现

- **C1（服务端+客户端双重锅）**：牌局内常驻红字「⚠ 牌局留档服务不可达，已排队重发」。实测根因：`test/hand-logs/local/` 已 **501 个文件 > serve.js S4 单房 500 上限** → 每手 POST `/api/handlog` 一律 **429**，而 `data.js` 无 429 分支，把「房满」误报成「服务不可达」并永久入队、每手重发。实测 `curl` 与浏览器裸 POST 均 200 正常落盘（探针 TETS/TETS2），唯游戏记录 429。GBY7TC 现有 75 档（档名时间为 UTC，即本场）、房主 3.7 手/分钟，照此 **~2 小时后同样撞墙**。
- **C2（单机独有）**：新手翻前第一拍，GTO 教练面板仍显示上一手手牌/建议（`08` 图：面板 J♦T♥ vs 实际手牌 9♦6♠），与面板自述「轮到你行动时给出建议」矛盾；多人局 `applySnap` 新手时会清面板，单机没有。

### 「呜帕时刻」评分（新大厅加了多少分）

- **加分**：立绘五表情高差分（+2，嗑到了）；部员/服装/持久化全套在线的换装打卡体验（+2）；快捷表情条 4 固定短语+数字快捷键的雀魂形制（+1，形对了）；大厅台词铭牌氛围（+1）。
- **减分**：单机发表情零反应——「呜帕时刻」的主动表达直接归零（−3，最伤的一项）；台词池每角色仅 4+4 句，连打两手就呜帕复读机（−1）；结算气泡糊在新手脸上破坏结算仪式感（−1）。
- **净评：新大厅本身 +4/5，但「呜帕时刻」闭环缺最后一口气（主动表情失灵）。**

---

## C. 改动清单（现状 → 问题 → 具体改法）

1. **气泡跨手残留**（B1）
   现状：无任何清场，残留率 100%。问题：新手开场挂着上一手的台词，破坏手与手的边界感。
   改法：`ui.js` 暴露 `clearAllEmotes()`（遍历 `emoteTimers` clearTimeout + 移除 `.show` + `emoteOrder.length=0`），在 `main.js` `loop()` 的 `table.startHand()` 后与 `mp.js` `applySnap` 的 `d.handId!==st.handId` 分支各调一次。
2. **台词跨手复读**（B2）
   现状：`usedQuotes` 局部变量只管本手。问题：跨手裸随机，4 句池连赢必复读。
   改法：把 `usedQuotes` 提升为模块级并按角色分桶（`usedQuotes[charId]={}`），每手结束不重置、全会话去重；同时每角色 win/lose 池从 4 句扩到 ≥6 句。
3. **快捷表情单机失灵**（B8）
   现状：`sendQuickEmote` 以「方法存在」判联机，`MP.sendEmote` 以 `st.phase` 静默丢弃。
   改法：`sendQuickEmote` 改判真实会话（如 `MP.inRoom && MP.inRoom()`）；`MP.sendEmote` 在无 ROLE/未连接时回退 `UI.showEmote(0,txt)` 本地回显，不再 return。
4. **留档 429 误报「服务不可达」**（C1）
   现状：serve.js 满房回 429+reason，data.js 一律当网络故障。问题：单机留档永久失败+每手空重发，误导玩家。
   改法：`data.js` `sendBody` 成功分支解析 `res.json()`，`reason==='room log full'` 时提示「本房留档已满（500 上限），本机记录不受影响」且不入队；serve.js 改为落盘前滚动清理最旧档（保留 500）或按日期分目录。
5. **表情/部员/服装切换无过渡**（A1）
   现状：src 硬切 + 无效的 background-image transition。改法：`#stage-portrait img` 换 src 时 restart 一个 `fadePop` keyframes（0.18s，opacity 0→1 + scale .985→1）；背景改双层 img 交叉淡入；删掉 no-op 的 `transition: background-image`。
6. **EXPRS 双头维护**（A2）
   现状：lobby.js 与 portraits.js 各持一份顺序已分叉。改法：lobby.js 删除本地 `EXPRS`，直接 `P.EXPRS`（或 `P.EXPRS.slice(1)` 轮播用），单一事实来源。
7. **服装行折行**（A3）
   现状：5 个 tab 挤爆右栏一行。改法：`.opt-row#stage-costumes` 加 `flex-wrap:wrap; gap:6px`（声明式两行），或压缩 tab 字号/padding 使其单行；与脚注间补 `margin-bottom`。
8. **挂机房 + 自动续局 = 新客永久无法入座**（D）
   现状：房主开局后 join 一律 `busy`，挂机房主永不回大厅。问题：本次 30 次重试全部被拒，好友房对外是一扇焊死的门。
   改法：`mp.js` 房主侧允许「等待中 join 排队」——本手结算回大厅间隙自动接纳并下一手入座；或 `busy` 响应附预计空档，客户端出「本局结束后自动重试加入」开关。
9. **教练面板跨手残留（单机）**（C2）
   现状：多人 applySnap 清面板、单机不清。改法：`main.js` `startHand` 后将 `#coach-body` 置占位「本手行动时给建议…」，与多人行为对齐。
10. **大厅可访问性/自动化**（A4）
    现状：立绘 img 不可键盘触发、无 alt 语义；stageFloat 令自动化 click 超时。
    改法：立绘包一层 `button`（或 `tabindex=0` + Enter/Space 触发 `onPortraitClick`）并配 `aria-label="切换表情，当前 X"`；`.sw-char` 补 `role=tab` + `aria-selected`；E2E 脚本统一 `click(force=true)` 或项目内提供 `?static` 参数暂停浮动动画。
11. **stage-hint 收尾**：首次成功切换表情后给 `#stage-hint` 加淡出（`transition: opacity .4s` + `hidden`），别让教程文案常驻。

---

## D. 联机与留档原始记录

- **30 次加入尝试全程失败，房间到死没开过窗口**：第 1–25 次（01:08–01:35）一律 `busy`「已开局并自动续局中」（第 28→121 手，约 3 手/分钟）；01:36 起房主进程到期关闭，第 26–30 次变为「找不到房间 GBY7TC」。房间从 00:55 建房到 01:36 死亡共 41 分钟、121+ 手，**没有任何一个可加入的大厅空档**。终态留档：`test/play_new/wupa/result.json`（ok:false）+ `err_join_fail.png`。
- 房间出生证明：`test/pr_code.txt`（00:55:02 写入 GBY7TC）；挂机房主保活约 41 分钟后自然关闭。
- 留档 429 复现：`test/hand-logs/local/` 501 文件；探针 `TETS/`、`TETS2/` 为 200 落盘对照组。

呜帕结语：大厅这张脸整得漂亮，五表情差分我直接存当表情包；但请把「呜帕自己会说话」修好——现在我在自己部里发表情，就像对着空气比心。下回回访，我要在好友房里对真人打出一发「打得漂亮！」。
