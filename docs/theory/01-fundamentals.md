# 01 · GTO 理论基础

> 来源：GTO Wizard 博客、arXiv《A Survey on Game Theory Optimal Poker》、Wikipedia、Science（Libratus/Pluribus）。文末附参考链接。

## 1. GTO 的严格定义

**GTO（Game Theory Optimal，博弈论最优）** 指扑克博弈的**纳什均衡策略**：当双方都采用均衡策略时，任何一方都无法通过单方面改变自己的策略来提高 EV。

- **不可剥削性（unexploitability）**：利用度（exploitability，即对手用最优反制策略能从你身上多赚的 EV）在均衡处趋近于零。GTO 保证**长期不被打爆**——它为你的策略设定 EV 下限（博弈的游戏价值），无论对手多强、多怪，都只能逼近打平而无法系统性赢你的钱。
- **GTO ≠ 每手牌最优，而是"范围"最优**：均衡策略以整手牌的范围为单位达到平衡，单看某一手牌的行动常常反直觉（比如 KK 在某些转牌过牌）。
- **GTO 是近似解**：实战中说的"GTO 策略"其实是求解器在**人为设定的下注树**内算出的近似纳什均衡（见 06 文件）。

## 2. GTO vs 剥削策略（exploitative）

| | GTO（均衡） | 剥削策略 |
|---|---|---|
| 目标 | 不可被剥削，EV 下限最大化 | 针对对手漏洞，EV 期望最大化 |
| 假设 | 对手也是均衡的 | 对手会系统性犯错 |
| 风险 | 对手打得差时你"少赚" | 你被反剥削（对手反向针对） |
| 适用 | 强对手、不明对手、高额桌 | 弱对手、有明显倾向的玩家群 |

业界共识：**以均衡为骨架，以剥削为血肉**。对抗弱玩家以剥削为主；对抗强玩家或信息不明时回归均衡。GTO 的真正价值是提供"参照系"——知道均衡在哪，才能量化对手偏离了多远、该往哪个方向惩罚。

## 3. 混合策略与无差别原则（indifference principle）

**无差别原则**：均衡处，对手的边缘手牌（典型如 bluff catcher 听牌型跟注牌）在可选动作之间 **EV 相等**——跟注与弃牌一样好，因此无论怎么调整都无法占便宜。

这正是求解器输出「83% check / 17% bet」这类**混合策略（mixed strategy）**的内在逻辑，两个方向互为镜像：

1. **攻击方定诈唬频率**：下注范围中诈唬占比恰好使防守方 bluff catcher 的跟注 EV = 弃牌 EV。
   - 诈唬多一手 → 对手全跟注即剥削你；
   - 诈唬少一手 → 对手全弃牌即剥削你。
2. **防守方定弃牌频率**：弃牌频率恰好使攻击方的纯诈唬 EV = 0（放弃的 EV），即按 MDF 防守。

双方被"钉死"在精确频率上，任何单方面偏移都会被对方惩罚——这就是纳什均衡的微观机制。

> **实务注解**：求解器输出中的很多"混合"来自花色/移除效应造成的微小 EV 差异（同点数手牌因阻断牌不同而频率略异），并非都要求你"掷骰子"。人类执行混合策略的正确方式是"这一类牌整体上按频率分布"，而不是每手精确随机。

## 4. GTO 的局限与常见误解

1. **对弱玩家 GTO 不是 EV 最大化**：均衡假设对手也均衡；对手若系统性过度弃牌，剥削策略 EV 更高。在小注别把 solver 解照搬——见 06 文件误区清单。
2. **"每手牌都按固定表格打"是误解**：表格/图表是范围层面的近似表达，GTO 的本质是频率与无差别，不是死记硬背。
3. **混合频率 ≠ 随机乱混**：混合是长期平均值，且多数混合源于阻断牌差异。
4. **MDF/均衡频率在对手失衡时机械执行是错的**：对手永不诈唬时，你可以把 bluff catcher 全部弃掉。
5. **求解器输出 ≠ 严格 GTO**：受限于下注树设定与迭代次数（详见 06）。

## 5. 扑克 AI 里程碑（背景）

| 系统 | 年份 | 团队 | 成果 |
|---|---|---|---|
| Cepheus | 2015 | 阿尔伯塔大学（*Science*） | CFR+ 使单挑限注德扑"本质弱解决"，人类终身对打也难占优 |
| DeepStack | 2017 | 阿尔伯塔大学（*Science*） | 深度学习 + 持续重解，单挑无限注击败职业选手 |
| Libratus | 2017–18 | CMU（Brown & Sandholm，*Science*） | 12 万手击败 4 名顶级单挑无限注职业选手 |
| Pluribus | 2019 | CMU + Facebook AI（*Science*） | 首个在 6 人桌无限注击败精英职业玩家的 AI（仅 2 颗 CPU） |

## 参考来源

- GTO Wizard — What is GTO in Poker: https://blog.gtowizard.com/what-is-gto-in-poker/
- GTO Wizard Glossary — Indifference: https://gtowizard.com/en/glossary/indifference/
- arXiv — A Survey on Game Theory Optimal Poker: https://arxiv.org/html/2401.06168v1
- Science — Libratus beats top human professionals: https://www.science.org/doi/10.1126/science.aao1733
- Cepheus 项目主页: http://poker.srv.ualberta.ca/
- 相关文件：[02-core-math.md](02-core-math.md)（无差别原则的数学落地）、[06-solvers-training.md](06-solvers-training.md)（求解器如何逼近均衡）
