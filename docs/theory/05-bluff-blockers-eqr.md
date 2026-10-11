# 05 · 诈唬理论、阻断牌与胜率实现

> 来源：GTO Wizard（Equity Realization / Flop Overbet / Calling Down Over-Bluffed Lines）、Upswing、Red Chip Poker。文末附参考链接。

## 1. 诈唬候选牌三要素

好的诈唬牌 = **无摊牌价值 + 有再改善权益 + 好的 blocker**。

1. **无摊牌价值**：下注的替代方案是弃牌，诈唬的机会成本为零。
2. **有再改善权益**：翻牌超池的诈唬并非纯空气，而是 25–60% 权益的牌（卡顺、底对、后门同花、带阻断效应的同花 Ax）——即使被跟也有改善路径。
3. **好 blocker**：阻断对手的跟注范围（详见下文）。

还要兼顾**范围覆盖（coverage）**：诈唬牌的"改善牌"分布要均匀覆盖各转牌/河牌，保证每一张危险牌上仍有诈唬组合可继续。

## 2. 多街连续诈唬（multi-street bluff）

- **预先规划线路**：优先选带听牌、且阻断对方强跟注范围的牌，按「翻牌小注 → 转牌大注 → 河牌全推或放弃」的几何线路推进（与几何尺寸联动，见 [02-core-math.md](02-core-math.md)）。
- **何时继续/放弃**：直证听牌类诈唬在转牌继续下注（不阻断对手弃牌范围）；白板河牌（无改善）倾向放弃。同花带对/带 A 的牌转牌可小注保留摊牌价值。
- **早街诈唬频率 > 河牌标准**：因为半诈唬带权益 + 有弃牌权益 + 下注杠杆（详见 02 文件第 3 节注）。

## 3. 阻断牌（Blocker）理论

**原理**：持有某张牌会移除对手范围中的组合。36 张非公共牌中的任意一张，都会按对手范围中含该牌的密度"等比例削减"对手的组合数。

| 用途 | 选择逻辑 | 例子 |
|---|---|---|
| 诈唬用 blocker | 阻断对手的**跟注**范围 | 诈唬时持同花 A 高（阻断对手 AQ/AK 跟注）、河牌持顺子听牌的中间张 |
| 价值下注避自阻断 | 别用阻断对手弃牌的牌下大注价值 | KK/QQ 在转牌 Q♠ 改为过牌（自阻断顶对范围，对手两对+组合减少） |
| 薄价值 | 选不阻断对手支付牌的组合 | 河牌薄价值避免持 A 阻断对手的 Ax 支付牌 |
| 抓诈唬 | 阻断对方**诈唬**范围 → 偏跟注；阻断对方**价值**范围 → 偏弃牌 | 河牌持 K 阻断对手同花/两对价值时，bluff catcher 转向弃牌 |

## 4. 胜率实现（Equity Realization, EQR）

**EQR = EV ÷（权益 × 底池）**，衡量一手牌把原始胜率转化为实际赢池份额的能力，即**可玩性（playability）**。

- **位置是第一变量**：所有牌 OOP 实现率都更低。实例（J♥T♦9♥ 牌面，BB vs HJ）：HJ 的 A♦2♦ 实现近 100%，BB 同牌不足 2%——强范围靠弃牌权益"实现"权益，弱范围被挤出底池。
- **过实现（R > 1）**：强牌（价值下注 + 逼弃）与极弱牌（小诈唬 EV 即可超过零摊牌价值）。
- **欠实现最严重的是中等牌**：薄价值打不出、诈唬又太强——这是"范围中部是锚"的根源。
- 量化例子：AA vs 72o 拿 $88 权益，全推被弃可赢 $100（114% 实现），被跟赢 $164（186%）；BB OOP 的 98s（对子 + 两端顺听）实现不足 25%；3♥2♥ 同花 87%（怕更高同花）。
- **经验规律（R 值）**：位置好 + 可玩性好（连牌/同花听型）→ R > 1；OOP + 高 SPR + 差可玩性（如 A♠xo 类）→ R 可低至 ≈ 0.6。
- **推论**：65s 的 EV 常高于同权益的 A6o——**相同胜率，位置好、可玩性好的牌更赚钱**；这也是 BB 面对 33% 小注（4:1 赔率）仍会弃掉部分 20–44% 权益手牌的原因。

## 参考来源

- GTO Wizard — Equity Realization: https://blog.gtowizard.com/equity-realization/
- GTO Wizard — Calling Down the Over-Bluffed Lines: https://blog.gtowizard.com/calling-down-the-over-bluffed-lines-in-lower-limits/
- GTO Wizard — The Art of the Flop Overbet: https://blog.gtowizard.com/the_art_of_the_flop_overbet_and_why_youre_probably_doing_it_wrong/
- Upswing — Equity Realization Explained: https://upswingpoker.com/equity-realization-explained/
- Red Chip Poker — Equity Realization: https://redchippoker.com/equity-realization/
- Upswing — MDF vs Pot Odds: https://upswingpoker.com/minimum-defense-frequency-vs-pot-odds/
