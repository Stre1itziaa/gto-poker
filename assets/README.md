# assets/characters — PNG 立绘资产管线

角色从 SVG 参数化插画（已废弃 `characters.js`）迁移为 **PNG 差分立绘 + CSS 骨骼动效**。

## 目录约定

```
assets/
├── _raw/<charId>/       ImageGen 原始输出（绿幕、带水印），只作存档
└── characters/
    ├── <charId>-<expr>-s.png     正式资产（900px 高，量化压缩，约 280KB）
    └── <charId>-<expr>-s.webp    同内容的 webp（备选，当前用 png）
```

`expr ∈ idle | think | happy | sad | blink`

## 产出管线（tools/）

按顺序执行，全部是零依赖 Python（Pillow + numpy）：

1. **ImageGen 出图** — 提示词里固定：绿幕 `#00FF00` 背景、`background: transparent` 会退化成棋盘格像素（不可用）、赛璐璐上色、同角色跨表情共用同一段基准描述。
2. **`cutout.py`** — 绿幕抠图：按「绿主导度」算 alpha + 去绿溢色，`--crop-bottom 88` 裁水印。阈值实测 `--threshold 90`（绿幕实际 dominance ≈ 125）。
3. **`align.py`** — 多差分归一化到统一画布 `760x1160`，按「内容高度填充」缩放 + 皮肤质心横向对齐，避免换表情时尺寸跳动。
4. **`optimize.py`** — 降到 900px 高 + FASTOCTREE 256 色调色板量化（保留 alpha），体积降 70%。

## 运行时（js/ + css/）

- `js/portraits.js` — 对外命名空间 `window.Portraits`，接口与旧 `Characters` 同名（`charSVG/byId/ALL/assign`），调用方无感。
- `css/portraits.css` — 呼吸/发丝摆动/眨眼/视线漂移，全走 `transform/opacity` 合成器路径。

### 关键坑（务必记住）

1. **`transform` 里不能写 `calc(数字 * 百分比)`** —— Chromium 会静默丢弃整条 transform，导致元素位置全错。bust 头像定位必须用纯 px。
2. **动画优先级高于普通声明** —— `pt-look` 动画的 transform 会覆盖 bust 的定位 transform，bust 模式需 `animation: none`。
3. **未产出的角色会自动回退**到首个有资产的角色（`Portraits.scan()` 探测），不会渲染裂图；5 个 404 是每角色一次 idle 探测的必要成本。

## 合规说明

角色人设年龄已统一上调为成年（20+ 岁），避免未成年角色编码。
