# 06 · 求解器原理、工具生态与学习方法论

> 来源：PioSOLVER 官网、GTO Wizard、CMU News、Wikipedia、GitHub CFR-Explained、中文社区资源。文末附参考链接。

## 1. 求解器如何工作：CFR 通俗原理

求解器把一手牌建模成一棵巨大的**博弈树**，用 **CFR（Counterfactual Regret Minimization，反事实遗憾最小化）** 类迭代算法逼近纳什均衡：

1. **遗憾匹配（regret matching）**：在每个信息集（对玩家不可区分的所有局面，如"我持 AK 在 K72 面对下注"）上反复自对弈，记录每个动作的累积"遗憾值"（当初选另一个动作本可多赢多少）。
2. 下一次迭代中，各动作按**正遗憾值的比例**被采用——过去表现更好的动作出现更频繁。
3. **"反事实"**：计算某动作的遗憾时按对手到达该节点的概率加权。
4. 单次迭代的策略会波动，但**所有迭代的平均策略收敛到纳什均衡**。

变体：CFR+（Cepheus 使用）、MCCFR（蒙特卡洛采样，让超大博弈可计算）、Deep CFR（神经网络近似遗憾值）。

**输入**：双方范围、有效筹码与底池、盲注/抽水、下注树（允许的动作序列）、下注尺度集合、公共牌面。
**输出**：每个决策点每手具体牌的**混合策略频率**（如 AJo 60% 超池 / 40% 小注 / 0% 过牌）与各动作 **EV**；可 nodelocking 锁定对手策略求最大剥削解。

**为什么"求解器输出 ≠ 严格 GTO"**：
1. **近似解**——有限迭代截断，只收敛到某个容差内；
2. **下注树是人设的**——只给 3 种尺度，真实最优尺度可能在集合之外；
3. 大局面常使用抽象化/抽样。
严谨说法是"给定博弈树的近似纳什均衡解"，而非全局最优。

## 2. 主流工具对比（2025–2026）

| 工具 | 定位 | 价格 | 适合人群 |
|---|---|---|---|
| **PioSOLVER** | 本地"计算器型"求解器，行业标准，nodelocking/脚本完善 | Basic ≈ $249、Pro ≈ $499（买断+1年更新） | 严肃的中高阶 NLHE 玩家/教练 |
| **GTO+** | 本地求解器+权益计算器+翻前构建器一体 | ≈ $75 买断（最便宜全功能） | 预算有限想自己跑解 |
| **GTO Wizard** | 云端预解库（数百万局面）+AI 求解+训练器+报告，覆盖 NLHE/PLO 现金/MTT/ICM | 免费额度；订阅 ≈ $49–279/月 | 全水平，最适合"即查即练" |
| **MonkerSolver** | 本地求解器，PLO4/5/6、多路底池 | ≈ €499 | 奥马哈职业玩家（学习曲线陡） |
| **PioViewer / MonkerViewer** | 免费查看他人求解结果 | 免费 | 只看解不跑解 |
| **训练器类**（GTO Wizard Trainer、PokerCoaching 测验、Preflop+ App、HRC〔MTT ICM〕） | 刷题与图表记忆 | 免费–订阅 | 把理论变成桌面决策 |

## 3. 扑克 AI 里程碑

- **Cepheus（2015）**：CFR+ 使单挑限注德扑"本质弱解决"（完美玩家也只能赢 ≈ 0.986 mb/手）。
- **DeepStack（2017）**：持续重解 + 深度学习，单挑无限注达职业级。
- **Libratus（2017）**：CMU，12 万手击败 4 位顶级单挑职业，赢超 178 万美元记分牌。
- **Pluribus（2019）**：首个 6 人桌无限注击败职业选手的 AI，时赢约 $1000，仅用很低算力。

## 4. 学习方法论

**推荐练习路径**：
1. 背熟与自己格式/筹码深度匹配的**翻前图表**（RFI、3bet、防御表）——理解原则而非死记；
2. 用 GTO Wizard / PioSOLVER **复盘关键手**：每周导入手牌历史，按位置和牌面类型归类找系统性漏洞；
3. **训练器刷题**把决策内化；
4. **范围作业**：自己先画范围再对照求解器，记录偏差原因，每次只专攻一类牌面。

**常见误区清单**：
- 把 GTO 当圣经（它是无剥削基线，不是每手牌的标准答案）；
- 忽视对手类型（对手明显偏离时仍按均衡打 = 漏掉大量利润）；
- 无脑背解（混合频率是长期平均值，不必精确随机化）；
- **在小注照搬 solver 解**——低注玩家过度跟注/过少弃牌，solver 的诈唬频率是白送钱，应减诈唬、增薄价值。

**从 GTO 到剥削性调整**：先了解**玩家群体倾向（population tendencies）**——低注玩家河牌过少诈唬、翻牌 c-bet 过多、盲注防御不足——再用 nodelocking 模拟对手偏离求最大剥削解。简化抓手：**对手弃牌太多就加诈唬；跟注太多就减诈唬、加薄价值**。

## 5. 资源清单

**书籍**：
- 《Modern Poker Theory》Michael Acevedo——solver 时代理论圣经
- 《Applications of No-Limit Hold'em》Matt Janda——范围与平衡经典
- 《Play Optimal Poker》1/2，Andrew Brokos——面向普通玩家
- 《Excelling at No-Limit Hold'em》Jonathan Little 主编文集

**课程/网站**：Upswing Lab（≈ $99/月）、PokerCoaching（≈ $49/月起）、Run It Once（Essential $24.99/月）、GTO Wizard（免费文章 + 学习计划 + 每日测验）。

**免费资源**：GTO Wizard 免费额度与博客、PioViewer/MonkerViewer、开源 Desktop Postflop、GitHub「CFR-Explained」图文教程。

**中文资源**：知乎专栏《德州扑克 GTO 学习指南——翻前范围》、B站 GTO Wizard 官方中文字幕视频、台湾 Rounders 中文介绍、PocketSolver 中文网页求解器、FreeBetRange 中文翻前范围工具、Preflop+ 中文纳什图表 App。

## 参考来源

- PioSOLVER: https://piosolver.com/ ｜ GTO Wizard: https://gtowizard.com/ ｜ MonkerSolver: https://monkerware.com/solver.html
- GTO+ 评测: https://www.vip-grinders.com/poker-tools/gto-review/
- CFR-Explained（GitHub）: https://github.com/brianberns/CFR-Explained
- Wikipedia — Pluribus: https://en.wikipedia.org/wiki/Pluribus_(poker_bot) ｜ Cepheus: http://poker.srv.ualberta.ca/
- CMU News — Libratus: https://www.cmu.edu/news/stories/archives/2017/december/ai-inner-workings.html ｜ Pluribus: https://www.cmu.edu/news/stories/archives/2019/july/cmu-facebook-ai-beats-poker-pros.html
- PokerFuse — Poker Solvers 入门: https://pokerfuse.com/learn-poker/tools/poker-solvers/
- 知乎 GTO 学习指南: https://zhuanlan.zhihu.com/p/1888763658970068322 ｜ B站: https://www.bilibili.com/video/BV1ACxQzKEyz/
- PocketSolver 中文: https://www.pocketsolver.com/zh ｜ FreeBetRange: https://freebetrange.com/zh-Hans
