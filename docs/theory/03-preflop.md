# 03 · 翻前（Preflop）GTO 策略

> 来源：GTO Wizard《Preflop Range Morphology》、FreeBetRange 6-max 图表、Upswing（极化 vs 线性、push/fold）、bbzpoker ICM 指南。数值为多来源求解器基线的常见区间（±2% 内随抽水/前注浮动）。本文件也是 `game/js/ranges.js` 机器人翻前图表的数据来源。

## 1. 范围思维：13×13 矩阵与组合计数

- **169 种手牌类型**：对角线 13 个口袋对（AA→22）；对角线上方三角 = 同花（AKs），下方 = 杂色（AKo）。记号 `TT+`、`ATs+`、`A2s+`、`KQo`。
- **组合数**：口袋对 6、同花 4、杂色 12，合计 **1326**。某手牌占比 = 组合数 ÷ 1326（AK ≈ 1.2%）。
- 结构占比：杂色 ~70.6%、同花 ~23.5%、口袋对 ~5.9%——同花与对子"稀缺而珍贵"的数学根源。

## 2. 6-max 现金桌 100bb RFI（首次加注）范围

开门尺度：UTG 2.0–2.5bb → 中位 2.3–2.5bb → BTN 2.5bb → SB 3bb（位置越靠后开得越大）。

| 位置 | RFI 占比 | 代表性手牌 |
|---|---|---|
| UTG | ~15–17% | 22+, A2s+, K9s+, Q9s+, J9s+, T9s, 98s, ATo+, KJo+ |
| HJ/LJ | ~18–21% | 上 + K8s, 76s, KTo+, QJo |
| CO | ~26–30% | 上 + A5o/A7o 弱 A、Q8s+, J8s+, 65s |
| BTN | ~42–48%（MTT+ante 可达 ~53%） | 几乎全部同花、22+、K2o+/Q6o+/J7o+ 级宽杂色 |
| SB | ~40–50%（低置信，求解器混入 limp） | 宽同花 + 强杂色；简化策略"3bb 加注或弃牌" |

规律：UTG→BTN 宽度单调递增；**SB 是唯一例外**（位置靠后但永久 OOP），远窄于 BTN。

## 3. 3-bet / 冷跟 / 4-bet 结构

- **极化 3-bet（polarized）**：价值手（AA-QQ、AK）+ 纯诈唬手（A2s–A5s、低同花连牌），中间牌极少。诈唬手靠 blocker 逻辑：持 A 降低对手 AA/AK 概率。
- **合并/线性 3-bet（merged/linear）**：价值 + 半价值 + 投机手连续排列。
- **适用规律**：**IP 3-bet 偏极化**（约 8–9%，如 BTN vs CO），**OOP 偏线性**（约 5–6%）。**著名例外：BB vs SB 用极化 3-bet**（BB 有位置且 SB 范围 capped）。
- 尺寸：IP 3-bet ~2.5–3x；OOP ~4x。范围内价值：诈唬 ≈ 3:2 到 2:1。
- **面对 3-bet**：4-bet 价值 QQ+/AK（部分）+ A2s–A5s 诈唬；**QQ、JJ、AK、AQs 在 100bb 常被跟而非 4-bet**（保留对 TT-99 的 domination、留住 A blocker）。总 4-bet 率 OOP ~2–3%、IP ~3–4%。
- **冷跟**：IP 比 OOP 宽（~19–27% vs ~14–20%，对 2.3bb 开门）；BB 凭赔率防守最宽（总防守 ~45–50% vs BTN）。

## 4. 单挑锅与位置

- **BTN vs BB**：BTN RFI ~42–45%，BB 宽防（3-bet ~9–11% + 跟注）；BTN 几乎总是翻后主动方，是全桌盈利最大的对局。
- **SB vs BB**：全扑克最宽对抗、SB 永久 OOP；BB 反而用极化 3-bet 压制 SB 的 capped 范围；翻牌常见双方 check。

## 5. 筹码深度与前注

- **深码（200bb+）**：范围变宽，隐含赔率手（小对子、同花连牌）升值，premium 相对贬值。
- **浅码（40bb MTT）**：隐含赔率消失，小对子/弱同花 A 贬值；**4-bet 全下常态化**（4-bet 更合并）；开局缩至 ~2.2–2.3x；按"可全下性"筛牌。
- **前注（ante）**：底池 1.5bb → ~2.3bb，防守赔率变好 → **所有位置 RFI 显著变宽**（BTN 现金 ~42% vs MTT ~53%）。

## 6. MTT 与现金桌差异

- MTT 无抽水更宽更便宜；盲注增长 → 需备 100/40/25/20/15/10bb 多套图表。
- **ICM**：筹码边际价值递减，筹码 EV ≠ 奖金 EV；泡沫期出现**风险溢价**（call 全下所需胜率 > 底池赔率）；大码可近全范围施压，中短码（被覆盖时）收缩。ICM 在剩 ~37–50% 选手时开始显著（中置信）。
- **Push/Fold**：有效筹码 <10bb 时策略坍缩为**纳什均衡 push/fold**（BTN/SB ~8–10bb 推 40–60%）；ICM 下实际 call 范围应比 Nash 更紧。

## 参考来源

- GTO Wizard — Preflop Range Morphology: https://blog.gtowizard.com/preflop-range-morphology/
- FreeBetRange — 6-max RFI 图表: https://blog.freebetrange.com/article/preflop-charts-open-raise-in-6-max-poker-cash-games
- GTO Wizard — Tournaments vs Cash: https://blog.gtowizard.com/poker-strategies-tournaments-vs-cash-games/
- Upswing — Polarized vs Linear: https://upswingpoker.com/polarized-vs-linear-ranges/
- GTO Wizard — Combinatorics 入门: https://blog.gtowizard.com/a-beginners-guide-to-poker-combinatorics/
- Upswing — Push/Fold 图表: https://upswingpoker.com/push-fold-tournament-strategy-charts/
- bbzpoker — ICM 完全指南: https://bbzpoker.com/the-complete-guide-to-independent-chip-model-icm/
- Red Chip — Preflop Charts: https://redchippoker.com/preflop-poker-charts/
- Upswing — 6-max 策略总览: https://upswingpoker.com/6-handed-max-poker-strategy/
