# 雀魂客群对标 · 20 画像迭代研究

> 长周期美术/体验研究任务：研究雀魂玩家生态 → 构建 20 画像 → 逐画像迭代评价 → 客群研究报告。
> 评价对象：当前真实版本（PNG 立绘角色系统 + 夜樱主题 + 教练 Worker + 会话统计）。
> 诚实声明：画像为构建的模拟用户；所有硬证据来自 ① 真实引擎按画像参数跑的真实牌局（可复现脚本 `game/test/persona.js`）② 真实浏览器实机走查（DOM 取证 + 截图）。

## 文件索引

| 文件 | 内容 |
|---|---|
| [01-mahjongsoul-research.md](01-mahjongsoul-research.md) | 第一步：雀魂玩家偏好与行为研究 |
| [02-personas.md](02-personas.md) | 第二步：20 画像定义 + 模拟参数 + 置信度声明 |
| [rounds-R1-competitive.md](rounds-R1-competitive.md) | 第三步·竞技群 7 轮（P01/05/06/08/12/17/18） |
| [rounds-R2-emotional.md](rounds-R2-emotional.md) | 第三步·情感群 4 轮（P02/03/07/13） |
| [rounds-R3-casual.md](rounds-R3-casual.md) | 第三步·休闲群 5 轮（P04/10/11/14/19） |
| [rounds-R4-social-experience.md](rounds-R4-social-experience.md) | 第三步·社交/体验群 4 轮（P09/15/16/20） |
| [03-report.md](03-report.md) | 第四步：系统性客群研究报告 |

## 复现方式

```bash
cd gto-poker/game
node test/persona.js 150   # 跑 20 画像模拟（产出 test/persona-results.json）
```
浏览器走查：任意画像的操作路径可直接在游戏里重放（选人界面点击、移动端 390px 视口、教练面板观察）。
