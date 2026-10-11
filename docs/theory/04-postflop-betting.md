# 04 · 翻后策略与下注理论

> 来源：GTO Wizard 博客系列（C-Bet Sizing / Flop Heuristics / Turn Strategy / Overbetting）、PokerCoaching、GTO Gecko、Upswing。文末附参考链接。

## 1. 两大核心优势：范围优势 vs 坚果优势

GTO Wizard 核心框架：**范围优势决定下注频率，坚果优势（配合弃牌权益）决定下注尺度**。

- **范围优势（Range Advantage）**：整体范围的平均权益更强。优势越大，越能用"整个范围"高频下注。例：BTN 对 BB 几乎在任何牌面都保有优势——BB 未 3-bet 已让出范围顶端，且享受盲注折扣而范围偏宽。
- **坚果优势（Nut Advantage）**：范围顶部（坚果类强牌）的组合占比更多。坚果优势越大，越能用大注/超池极化下注。
- **两者可以分离**：配对牌面上 IP 常保有权益优势但丢失坚果优势（双方都能暗三）→ 高频小注，而不是大注。

**尺度选择法则**（GTO Wizard）：
- **下大注，当**——对手坚果牌少、对手范围中有大量"对你的顶级牌尚有权益"的牌、弃牌权益值钱、你自己的中等牌少。
- **下小注，当**——对手坚果牌多、你的中等牌多需要保护（"范围中部是锚，顶部必须为它护航"）。

## 2. 牌面纹理与 c-bet 频率（BTN vs BB 现金局主流结论）

| 牌面类型 | c-bet 频率 | 主尺寸 | 逻辑 |
|---|---|---|---|
| 高牌/断连/彩虹 | ≈ 70–100% | 33% pot | 范围优势大，全范围轻注剥夺权益 |
| 配对牌面 | 接近 100% | ≈ 33% pot | 双方都难有超强牌，轻注保护 |
| A 高牌面 | 略低于其他高牌面 | 33% pot | BB 范围 Ax 多、无超牌可保护、BB check-raise 增多 |
| 有顺/同花听牌 | 50–70% | 66% pot 为主 | 转向两极化 |
| 单调色（mono） | 断崖式下降 | — | BB 同花牌碾压 IP 强牌 |

**「湿度抛物线」**（Mechanics of C-Bet Sizing）：干牌小注 → 中等湿度（K♥J♥7♦ 类）大注甚至超池 → 极湿（Q♦J♦T♦ 类）尺度回缩。实例：QQ6r 上 BTN 高频 33% 池；K♥J♥7♦ 上主用 75% 与 125% 池（BB 对超池弃 62%）；Q♦J♦T♦ 上下注/过牌近 50/50 且以 33% 池为主。

**开局越紧，IP 优势越大**：面对 CO 开局，BB 防御更紧；BB 对抗 33% 小注以 check-call 中等牌为主，check-raise 中等频率且强调顶对好踢脚；配对与低牌面上 BB check-raise 显著增多。

## 3. 下注尺度理论

- **小尺寸（25–33% pot）**："全范围轻注"——轻量价值 + 剥夺权益（equity denial）+ 保护中等牌。适用于：范围优势大、坚果优势小、干燥牌面。
- **大尺寸（75%+）与超池（overbet，120%+）**：极化范围（坚果牌 + 弃牌型诈唬）。触发条件：① 坚果优势；② 中等牌下注无收益；③ "urgency"（强牌有被翻盘风险需尽快造池）；④ 对手范围窄/capped（阻断牌价值放大）。实例：AK6r 上求解器若限用单一尺寸会选择 **253% 池、约 1/3 范围下注**；T95r/J95r 类牌面超池占 c-bet 一半以上。
- **超池用量参考**（GTO Gecko）：河牌约占下注范围 15–25%，转牌 5–15%，翻牌最有选择性。
- **几何尺寸**：s = √(1+SPR) − 1（两街打光的每街比例，SPR=3 时约 100% 池），是转牌—河牌两极打光线路的标准构造。通用公式见 [02-core-math.md](02-core-math.md)。
- **河牌诈唬:价值比**：b 池下注时诈唬占下注范围 b/(1+2b)——半池 3:1、满池 2:1、2x 超池 1.5:1（价值:诈唬）。

## 4. 各街策略要点

### 翻牌
- IP 以高频小注为主（见第 2 节）。
- OOP check-raise 混合价值牌与半诈唬听牌（只 raise 坚果 + 好听牌会被剥削）。
- **Donk bet（反主动下注）翻牌很少正确**；但**转牌 donk** 的经典触发场景是"范围突然反转"：转牌使 preflop 跟注方范围晋级——低牌配对（配第二/第三张）、顺子完成（K75 翻牌来 6，填满 BB 的 98/76）、同花完成（BB 听牌更集中）。频率示例：UTG vs BB（40bb）J53r 各转牌合计约 18% donk，BTN vs BB 约 7%；特定牌（J53 的 3♥）BB donk 约 40% 范围；尺寸通常很小（约 20% 池）。

### 转牌
- 转牌"更诚实"：中等牌倾向过牌控池、强牌大注造池、弱牌要么大诈唬要么放弃。
- **攻守常在转牌反转**：翻牌全范围小注后，BB 跟注剔除垃圾牌，原加注者转为 check 为主；此时下注多为超池。实例（UTG vs BB K♠8♥4♦，转牌 Q♠）：只下约 40% 范围且**全部超池**（两对/暗三纯下注，KK/QQ 因自阻断而慢打）；转牌 8♠（恶牌）则改用半池。
- 浅码（20bb）用 50% 池替代超池，以便河牌几何全推。

### 河牌
- 价值最大化 + 薄价值 + 超池极化。
- **Bluff catcher 决策框架**：范围层面用 MDF（半池需防守 67%、满池 50%、2x 池 33%）；单手牌层面优先用底池赔率（满池下注需 33% 胜率）并结合**阻断牌**——阻断对方价值范围（持有对方价值下注想有的牌）偏弃牌；阻断对方诈唬范围（持有对方诈唬会用的牌）偏跟注。
- 对手范围"无自然诈唬牌"时，MDF 失效，可全弃。

## 参考来源

- GTO Wizard — The Mechanics of C-Bet Sizing: https://blog.gtowizard.com/the-mechanics-of-c-bet-sizing/
- GTO Wizard — Flop Heuristics: IP C-Betting in Cash Games: https://blog.gtowizard.com/flop-heuristics-ip-c-betting-in-cash-games/
- GTO Wizard — The Art of the Flop Overbet: https://blog.gtowizard.com/the_art_of_the_flop_overbet_and_why_youre_probably_doing_it_wrong/
- GTO Wizard — Principles of Turn Strategy: https://blog.gtowizard.com/principles-of-turn-strategy/
- GTO Wizard — Turn Donk Bets: https://blog.gtowizard.com/how-and-why-you-should-use-turn-donk-bets/
- GTO Wizard — Exploiting Excessive C-Betting by IP: https://blog.gtowizard.com/exploiting-excessive-c-betting-by-ip/
- GTO Wizard — Overbetting the Flop in Cash Games: https://blog.gtowizard.com/overbetting-the-flop-in-cash-games/
- GTO Gecko — Overbetting Strategy: https://gtogecko.com/blog/overbetting-strategy
- PokerCoaching — C-Betting on Paired Boards: https://pokercoaching.com/blog/c-betting-on-paired-boards/
- Upswing — Nut Range & Positional Advantage: https://upswingpoker.com/nut-range-positional-advantage/
