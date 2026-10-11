# 十八回访回归审计 · 天证骑士（数据党主审）

- 房间：GBY7TC · 6 人桌 · 房主「数据迭代房主」（无头挂机，自动下一局）
- 客户端：mp_guest.py · 角色 #6 绿川小梅 · 3 手 14 次行动 · 0 JS 报错 · 加入即成功（未触发 20s 重试）
- 产物：`play_new/tenjou/`（01–09 截图 + result.json[data_audit] + `_crop_*.png` 取证放大图）
- 审计基线：所有盈亏均为手算复核，未采信任何单侧数据源。

---

## A. 硬核审计表

| # | 项 | 判定 | 证据 |
|---|----|------|------|
| ①a | noAssert | **PASS** | `noAssert=0`，3/3 条留档均带 `assert` 且 `ok=true`（Σ派彩=Σ投入 引擎级断言无红字） |
| ①b | badAssert | **PASS** | `badAssert=0`；三手账目独立复核全平：手1 3490=1735+1735+20、派彩 −1735−20+1755=0；手2 230=150+10+70、+80−10−70=0；手3 130=50+10+20+50、+15−10−20+15=0 |
| ①c | sumMatch | **PASS** | 牌谱 summary 求和 −82.0bb == stats.netBB −82.0，`sumDiff=0`；三节点顶栏滚动 −86.8 → −82.8 → −82.0 与手算 −86.75/+4.0/+0.75 逐一吻合（`_crop_top_sd2/fin` 放大实读） |
| ② | VPIP/PFR 手算 | **PASS** | 翻前动作：#1 跟40、#8 跟20、#11 跟50 → VPIP=3/3=**100%** ✓；零翻前加注（#5 加注到566 在转牌、#9 跟50 是手2翻前对 iso 的防守、#10 加注在手2翻后）→ PFR=**0%** ✓；对手表抽查全对：月见凛大盲弃（投入恰 20=BB）不计 VPIP 0% ✓、葵夏 33/33（仅手2 iso）✓、绵雪 67/67 ✓、诗织 0/0 ✓。口径标注「只看翻前主动投入」在 KPI 下方在案 |
| ③ | 大厅/弹窗角色同源 | **PASS**（附缺口） | 三处写同一 `localStorage['gto-char']`：lobby.js:26（派发 `gto-char` 事件）、ui.js:927（单机选人）、mp.js:1008（mp 弹窗）；mp.js:995/981、portraits.js:301 同读。实测 01→02→03→08 链路角色一致（夜樱铃→绿川小梅→入座→回厅）。缺口见 C-3：事件只出不进，mp 弹窗 `wire()` 仅启动读一次 |
| ④ | 服装全局切换同步 | **PASS** | 大厅选 部服v4(p1) → 08 舞台立绘与 04/05/06/07 牌桌右侧立绘同装（青羽织）；座位半身像/弹窗头像均走 `portraitHTML`→`srcOf`（costume-aware 单源）；`setCostume` 持久化+重扫（portraits.js:187-196），ui.js:981 监听 `gto-costume` 清 portraitCache/standingCache；单机弹窗服装 tabs 已收编隐藏（ui.js buildCostumeTabs `row.hidden=true`），双入口消除 |
| ⑤a | 翻前口径 | **PASS** | 盲注被动投入不计 VPIP（月见凛案）；SESS（main.js:44-45）与 DataPage 两套统计口径一致，未复发翻前 bet/raise 混计 |
| ⑤b | 负号双轨 | **FAIL** | 同屏三轨仍在：data.js:215 KPI 用 ASCII `-`（"-82bb"）、data.js:316 牌谱用 U+2212（"−1735（−86.8bb）"）、ui.js:1034 顶栏 `toFixed` ASCII、lobby.js:142 顶栏用 U+2212——同一数据弹窗内就两种字形；mp_guest 审计正则被迫写 `[+\u2212-]` 双兼容即基建自证 |
| ⑤c | 数据页对手表截断 | **PASS**（带保留） | 非 AR6 硬截断复发：`#data-body` `overflow-y:auto`（style.css:477）+ 末 26px 渐隐 mask（:492-495，AR6 后既定「滚动提示+末行渐隐」案）+ 按钮行 sticky 常驻（:478）。oppCount=5、第 5 行（数据迭代房主）静止时半行没入渐隐区，可滚动可达但无可视滚动提示，可发现性边缘化，见 C-4 |

### 附加核验（非清单内，顺手全对）

- **加注口径**：引擎为「街内累计」制——"加注到 566"=该街累计，绵雪响应"下注 348"=566−218 差额，双方最终各投入 1735、残码 265（3755=265+3490 ✓）。
- **边池分层**：手3 主池40（4×10）+边池1 30（3×10）+边池2 60（2×30）=130，逐层标注[平分] ✓。
- **位置环**：手1 按钮房主→手2 我→手3 诗织，6-max UTG/HJ/CO/BTN/SB/BB 徽章全程正确。
- **牌型判定**：手3 公共牌 5♠4♦6♥3♣2♠ 天成 6 高顺，6♣J♣ 与 K♥Q♣ 均只能打公共牌，平分判型正确（`_crop_board3` 放大实读）。
- **留档重发队列**：data.js:62-80 postQueue+`aid` 幂等去重+每手 `flushPosts()`（main.js:115），本次 3/3 落档 0 失败 0 告警。
- **PeerJS**：客户端库已自托管（index.html:224 vendor/peerjs.min.js，消除 unpkg 供应链），但信令仍走官方云，见 C-5。

## B. 新大厅架构评价（lobby.js）

**总评：抽模块的方向正确、边界干净，是一次合格的解耦；但「事件只出不进」和「顶栏读错数据源」两处说明它目前是半成品同步模型，靠 `location.reload()` 兜底。**

好的方面：
1. **模块边界干净**：182 行 IIFE、唯一依赖 `window.Portraits`、DOM 挂点全部由 index.html 预留 id（lobby-backdrop/lobby-stats/lobby-player/stage-*），加载顺序 portraits→lobby→ui→mp→main 无倒挂。
2. **职责收编做得对**：服装选择唯一入口收进大厅（单机弹窗 tabs 显式 `hidden` 并留注释），消除双 UI 双状态；选角三端共用 `gto-char` 单 key，配合 `gto-char`/`gto-costume` 事件广播是正确的松耦合方向。
3. **细节有活儿**：`ensureCostume` 旧档迁移（''/club/glam→p1）、PACK_KEYS 只列有资产的五包、表情轮播 2.6s 回 idle、`__ptFallback` 裂图兜底、隐私模式 try/catch 全覆盖。

工程债：
1. `renderTopbar()` 只在 `init()` 跑一次且读 `gto-sess`——数据源选错（多人客人端该 key 永不更新），顶栏成了假活数据。
2. 不监听自己发出的两类事件，跨模块选角/切装后大厅舞台依赖 `btn-home` 的整页 `location.reload()` 才正确——拿刷新当状态同步，P2P 场景还多付一次断线重连。
3. EXPRS/PACK_KEYS 是 portraits.js 数据的手抄副本（COSTUMES 已有 `full` 标记与 scan 探测结果，资产白名单应挂数据源）。
4. 命名债：`charSVG` 现在返回的是 PNG 立绘 DOM（portraitHTML 别名），mp.js:1006 调用点语义误导后来人。
5. `plate.innerHTML` 直接拼 `c.quote/c.title`——静态白名单风险低，但与 mp.js 的 `esc()` 习惯不一致。

## C. 改动清单（现状 → 问题 → 具体改法）

1. **负号双轨统一**（⑤b，FAIL 必修）
   现状：data.js:215 ASCII、data.js:316 U+2212、ui.js:1034 ASCII、lobby.js:142 U+2212。
   问题：同一弹窗 KPI 与牌谱两种负号；跨模块顶栏又不一样。
   改法：抽 `fmtSigned(v, unit)` 工具（统一 U+2212 印刷负号），四处换用；审计脚本正则保留双兼容一个版本后收敛。

2. **会话统计单源化**（本审计最大 FAIL）
   现状：`gto-sess` 只被 main.js `loop()` 的 `recordSession()` 更新；客人端 mp.js:695-702 只喂 `UI.setSessionStats(st.sess)`，回大厅顶栏 0/0/0%（08_back_landing 实证），与数据页 3 手/−82bb/100% 直接矛盾。
   改法（二选一，推荐 b）：a) mp.js 结算处按同口径读-改-写 `gto-sess`；b) lobby.js `renderTopbar()` 改读 `DataPage.stats()`，以牌谱记录为唯一事实源，单机/房主/客人三态自然统一。

3. **mp 弹窗补 `gto-char` 监听**（③缺口）
   现状：mp.js `wire()` 仅启动执行一次（:1120），:995 只读一次 `gto-char`；大厅改角后不开新页直接进弹窗，高亮与入座角色都是旧值。
   改法：`root.addEventListener('gto-char', function(){ selChar = localStorage.getItem('gto-char') || selChar; buildCharRow(); })`，与 ui.js:989 对齐。

4. **对手表滚动可发现性**（⑤c 保留项）
   现状：第 5 行静止半行没入渐隐 mask，无任何"下面还有"提示。
   改法：data.js 渲染对手表时追加计数徽标「共 N 人」；或 mask 渐隐区 26px→12px 并给 `.data-table` 配细滚动条样式，二选一即可。

5. **PeerJS 信令真自托管**
   现状：index.html:224 自托管的是客户端库；net.js:63/112 `new Peer(pid, {debug:0})` 无 `{host,port,path}`，信令仍依赖 0.peerjs.com，离线/云抖动即无法开局。
   改法：serve.js（或 9000 端口）挂 peerjs-server；net.js 按 `location.hostname` 判定本机/局域网走自建信令，公网环境回落云信令。

6. **start-all.bat 坏档修复**
   现状：原始字节 `cd /d "E:Workspaceprojectsgto-pokergame"`、`toolsincloudflared.exe`——路径反斜杠在生成时被转义吃掉，脚本必挂（本次服务是手动 `node serve.js` 起的，掩盖了问题）。
   改法：重写路径为完整反斜杠形式并以 `if not exist` 自校验；生成脚本改用 raw 字符串。

7. **lobby.js 生命周期补全**
   现状：`renderTopbar/renderStage` 仅 init 一次。
   改法：导出 `Lobby.refresh()`，main.js 在 landing 显示路径（含 `btn-data-back`）调用；同时把 renderTopbar 的数据源按第 2 条换掉。

8. **服装资产白名单挂回数据源**
   现状：lobby.js `PACK_KEYS=['p0'..'p4']` 手抄副本，portraits.js 再加包就会漏。
   改法：COSTUMES 条目增加 `hasAssets`（由 scan 探测结果填充），lobby 过滤 `cs.hasAssets`，删本地常量。

9. **charSVG 更名**
   现状：portraits.js:334 `charSVG: portraitHTML` 名实不符。
   改法：新导出名 `portraitHTML`，`charSVG` 保留一个版本号后删除；mp.js:1006、其余调用点同步改。

10. **审计自动化补盲**（工具侧）
    现状：mp_guest.py data_audit 未覆盖"对手表是否需要滚动"与顶栏/数据页一致性。
    改法：evaluate 里加 `scrollHeight>clientHeight` 探测与 `#lobby-stats` 文本回读，把 ⑤c 与改动 2 的回归纳入自动化断言。

—— 天证骑士 · 2026-09-25 · 第 18 次回访
