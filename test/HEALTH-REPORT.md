# 夜樱扑克部 · 代码健壮性 / 安全性 / 稳定性 全面评估报告
**日期**：2026-09-19　**范围**：game/ 全部运行时代码（js 12 文件 + index.html + serve.js + css）+ Cloudflare Pages 生产部署 + PeerJS P2P 链路
**方法**：全文件通读 + 关键路径证据核验（grep 取证）+ 结合本会话全部 E2E/测试记录。**只评估未改动。**

---

## 一、总体结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 健壮性 | **B+（良好）** | 主循环三重防护、竞态有缓冲、资金账目有断言；残余为低概率边缘态 |
| 安全性 | **B-（有一个必修项）** | 防作弊面设计优秀；但 charId 未白名单构成属性注入 XSS |
| 稳定性 | **B+（生产链路稳）** | 静态托管+CDN 无服务器面；联机链路有 4 个已知单点（均有降级或说明） |

**总评**：以「朋友间免费开黑」的产品定位衡量，整体工程质量高于业余项目平均线。存在 1 个应尽快修复的安全项（修复成本 1 行）和 3 个低成本健壮性补丁。

---

## 二、安全性

### 发现的问题（按严重度）

**S1 · [中高] 客人 charId 未白名单 → 属性注入 XSS**（修复成本：1 行）
- 链路：客人入房 metadata.charId → mp.js L222 `if (!cid || charTaken(cid)) cid = firstFreeChar()`——只要不与内置 6 个 id 重名，**任意字符串原样入库** → broadcastLobby 广播给全体客人 → renderLobbyList/portraits.charSVG 内嵌 → portraitHTML 的 `data-char="' + id + '"` 属性拼接点
- 复现：恶意客人发送 `charId: '"><img src=x onerror=alert(1)>'` → 提前闭合 div 标签注入 `<img onerror>` → **房主与所有客人的大厅/牌桌执行任意 JS**（innerHTML 注入的 img onerror 会触发）
- 影响：房间内全体客户端；受害者数据仅 localStorage（游戏进度），无敏感信息外泄面，但可破坏对局/冒名发消息
- 修复：入库前加白名单 `if (!cid || !CHARS.some(c => c.id === cid) || charTaken(cid)) cid = firstFreeChar();`

**S2 · [中] 会话存档 JSON.parse 无保护 → 存档损坏 = 页面瘫痪**（修复成本：3 行）
- main.js L27-28 顶层裸调 `JSON.parse(localStorage.getItem('gto-sess') || '{}')`，无 try/catch
- 复现：gto-sess 写入被截断/损坏（写盘瞬间断电、浏览器配额清理半途）→ 下次打开脚本顶层抛异常 → **wireTopbar/wireCharSelect 全部不执行 → 首页按钮全死**，且因存档损坏持续复现（自锁）
- 修复：try/catch 包裹，异常时回退 `{}` 并清掉坏 key

**S3 · [低] 客人动作 type 未白名单 → 可致整手中断**（修复成本：1 行）
- hostOnData/normalizeAct 只矫正 raise 的数值与 check 的合法性，未校验 type ∈ {fold,check,call,raise}；`{type:'zzz'}` 会被 apply 抛「未知动作」→ 主循环 catch → **本手异常中断不计分**
- 影响：恶意/坏客户端可随意打断房主牌局（朋友间威胁低，但健壮性缺口明确）
- 修复：normalizeAct 末尾 `if (!/^(fold|check|call|raise)$/.test(act.type)) act.type = la.toCall > 0 ? 'fold' : 'check';`

**S4 · [低] serve.js /api/handlog 无鉴权、文件数无上限**（仅本地/LAN）
- 0.0.0.0 绑定下局域网任意设备可无限 POST JSON 落盘（单文件限 1MB，但文件数无限）→ 磁盘慢慢填满
- 缓解因素：仅开发用服务器，生产站（静态托管）无此端点
- 修复建议：限制单房目录文件数（>500 拒绝）或加启动参数开关

**S5 · [低] unpkg CDN 依赖 = 供应链 + 可用性双风险**
- peerjs 1.5.4 从 unpkg 热加载：① unpkg 被挂/版本被替换 = 全客户端执行第三方代码（供应链）；② unpkg 国内偶发不可达 = **多人模式静默瘫痪**（Net 未定义，建房点击报错，单机不受影响）
- 修复：自托管 peerjs.min.js（约 80KB 入部署包，与立绘一起走 CF CDN）

**S6 · [信息/设计边界，非漏洞]**
- 房码即密码：31^6 ≈ 8.9 亿组合，暴力不可行；但知晓房码者即可入房（无房间密码）——朋友房定位下可接受
- 房主即权威：房主客户端理论上可作弊（自改引擎）——朋友房信任模型下可接受，已在设计文档声明
- PeerJS 免费公共信令服务器：可见房码与连接元数据（不见牌局数据，牌局走 P2P DataChannel）

### 已做对的部分（防作弊面）
- 客人端全程拿不到他人底牌（快照脱敏 + 摊牌才揭示，mp-shadow 20 手测试验证）✓
- 表情文本 12 字截断 + 控制字符/<> 过滤，textContent 渲染 ✓
- 昵称 8 字截断 + <> 过滤 + innerHTML 转义 ✓
- 动作经房主合法化校验（clamp 到 minTo/maxTo、check 非法转弃牌）✓
- 无账号无个人数据收集，隐私面极小 ✓

---

## 三、健壮性

### 强项（本会话与历史审计沉淀的防护网）
- 主循环：全程 try/catch + 15s 看门狗 + 心跳贯穿（长考/客人等待期每秒续约）+ forceKill 自愈 + 3 strikes 重建
- 竞态：earlyActs 缓冲（快照先发/等待后挂的时序差）+ 每手清空防串手
- 引擎：NaN 钳制、不足额全下不重开加注权、无效过牌降级弃牌、结算守恒断言（每手 Σ派彩=Σ投入）
- 客人端：决策状态回收（防控件永久卡死）、超时单发 timedout、幻影大厅防护（名单广播才进厅）
- 断线：房主代打、客人自动回厅、座位保留 120s、同名重连回座
- 测试网：4 套无头测试 + 遮挡审计 + 立绘报警，每批回归

### 弱项 / 建议（R 系列）
- **R1 [低] earlyActs 可被预存动作跨回合消费**：恶意客人一次连发两个动作，第二个会在下一回合被当作「秒回」消费。影响=自己坑自己为主，但严谨做法是动作带 handId+seq 校验。建议随 S3 一并加消息序号
- **R2 [低] localStorage 裸调用 6 处**（portraits.js L292、ui.js L876/897/794 等）：隐私模式（Safari 严格反追踪）下 getItem/setItem 会抛异常 → 角色选择/统计功能失效。建议统一包 try/catch（项目内已有此惯例，这 6 处是漏网）
- **R3 [低] UI.init 的 window resize 监听不注销**：当前每页只 init 一次无实害；若未来支持「返回大厅再开局」会产生重复监听。备忘即可
- **R4 [中] 联机协议无自动化测试**：earlyActs/timedout/断线代打目前靠人工 E2E。建议把 hostOnData/normalizeAct/nextRemoteAction 提为纯函数加 node 测试（mp-shadow 模式已具备条件）
- **R5 [信息] 老浏览器兼容**：代码主体 ES5，兼容面广；但 WebRTC 本身要求现代浏览器，无需额外处理

---

## 四、稳定性

### 生产链路（pages.dev）
- Cloudflare Pages：静态托管、全球 CDN、TLS、DDoS 防护由 CF 托底——**无服务器攻击面、无宕机自运维负担** ✓
- HTML 走协商缓存（发版即时生效）、assets immutable 长缓存 ✓
- 单点：Cloudflare 可用性本身（业界 99.99%+，可接受）

### 联机链路单点清单（每个都有既定行为）
| 单点 | 触发 | 现状行为 | 评级 |
|---|---|---|---|
| PeerJS 免费信令云 | 服务抖动 | peer.reconnect 自动重连；重连失败=新建房间 | 可接受 |
| 房主设备 | 关页/断网 | 客人收到断线通知自动回大厅 | 已知边界 |
| 客人 NAT（对称型） | 打洞失败 | 连不上，约 10-15% 概率，提示重试 | 已知边界 |
| unpkg CDN | 不可达 | 多人模式瘫痪（单机无感） | **建议自托管消除**（同 S5） |
| 微信/QQ 内置浏览器 | 用户误入 | WebRTC 缺失，联机不可用——需引导用系统浏览器 | 文档化 |

### 已知功能边界（非缺陷，设计取舍）
- 不支持对局中途加入/观战；客人视角不旋转；重连回局只到「下一手」（对局中断线由代打接管）

---

## 五、修复优先级建议

| 优先级 | 项 | 工作量 |
|---|---|---|
| **P0 立即** | S1 charId 白名单（1 行）+ S2 SESS try/catch（3 行）+ S3 动作 type 白名单（1 行） | 合计 <0.5h，建议随批 1.5 热修上线 |
| P1 短期 | S5 自托管 peerjs（复制 1 文件+改 1 行 script）+ R2 localStorage 包裹（6 处） | ~1h |
| P2 排期 | R4 协议纯函数测试、S4 handlog 上限、R1 消息序号 | 各 0.5-1 天 |

---

## 六、修复记录（2026-09-19 · 用户批示「必须全都修」后全部落地并上线）

| 项 | 状态 | 实施 |
|---|---|---|
| S1 | ✅ 已修 | mp.js 入口白名单（charId 必须命中内置 id）+ portraits.js portraitHTML 对 id 做字符消毒（深防） |
| S2 | ✅ 已修 | SESS 解析 try/catch + 坏档自动 removeItem 自清 |
| S3 | ✅ 已修 | normalizeAct 末尾动作类型白名单（非法 → 能过则过/不能则弃）；hostOnData 去重改走 normalizeAct |
| S4 | ✅ 已修 | 单房留档 >500 文件返回 429 |
| S5 | ✅ 已修 | peerjs 1.5.4 自托管 `js/vendor/peerjs.min.js`（92KB），unpkg 引用移除 |
| R1 | ✅ 已修 | 客人动作携带 hand 手号；hostOnData/earlyActs 消费端双端校验，旧手动作丢弃 |
| R2 | ✅ 已修 | 6 处裸 localStorage 调用全部 try/catch |
| R4 | ✅ 已修 | 新增 `test/mp-protocol.js`（normalizeAct 白名单/钳制/降级用例） |

**回归记录**：五套件全绿（sim / mp-shadow / resolve-attribution / mp-protocol / audit）；双端联机 E2E 一手 11 秒（客人 4 动作全消费、零超时零异常——act 消息新增 hand 字段后链路验证）；生产站验证 peerjs 自托管生效、unpkg 移除、版本 20260919b。

**遗留（低优先，未修）**：R3 resize 监听备忘（现无实害）。
