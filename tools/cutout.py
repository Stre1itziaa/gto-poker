# cutout.py — 绿幕抠图 / 去水印 / 边缘去绿溢色
#
# 用途：把 ImageGen 产出的绿幕立绘转成带 alpha 的透明 PNG，
#       同时裁掉右下角水印条带、修去边缘绿色反光（spill）。
#
# 用法：
#   python cutout.py <输入图> <输出图> [--crop-bottom 90] [--threshold 200]
#
# 依赖：pillow, numpy （安装在 C:/Users/Tabby/.workbuddy/binaries/python/pkgs）
import sys
import os
import numpy as np
from PIL import Image

def parse_args(argv):
    if len(argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, dst = argv[1], argv[2]
    crop_bottom = 0
    threshold = 90
    feather = 1.5
    lo = 20.0
    wipe = None
    for i, a in enumerate(argv):
        if a == '--crop-bottom' and i + 1 < len(argv):
            crop_bottom = int(float(argv[i + 1]))
        elif a == '--threshold' and i + 1 < len(argv):
            threshold = float(argv[i + 1])
        elif a == '--feather' and i + 1 < len(argv):
            feather = float(argv[i + 1])
        elif a == '--lo' and i + 1 < len(argv):
            lo = float(argv[i + 1])
        elif a == '--wipe' and i + 1 < len(argv):
            # 比例坐标矩形 x0,y0,x1,y1 (0-1)，抠图前整块刷成纯绿幕。
            # 用途：擦右下角水印字（全身图不能像胸像那样裁底部）。
            wipe = tuple(float(v) for v in argv[i + 1].split(','))
    return src, dst, crop_bottom, threshold, feather, lo, wipe


def _dilate(mask, iters):
    """4-邻域膨胀，numpy 向量化。"""
    out = mask.copy()
    for _ in range(iters):
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def _vec_hsv_stats(px):
    """向量化计算一组 RGB 像素的 (中位色相, 中位饱和度, 中位主导度)。px: float32 (N,3)。"""
    import numpy as np
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    mx = px.max(axis=1)
    mn = px.min(axis=1)
    delta = mx - mn
    sat = delta / np.maximum(mx, 1.0)
    hue = np.zeros(len(px), dtype=np.float32)
    m = delta > 1e-6
    rr, gg, bb, dd = r[m], g[m], b[m], delta[m]
    h = np.zeros(len(rr), dtype=np.float32)
    i1 = (mx[m] == rr)
    i2 = (~i1) & (mx[m] == gg)
    i3 = ~(i1 | i2)
    h[i1] = ((gg[i1] - bb[i1]) / dd[i1]) % 6.0
    h[i2] = (bb[i2] - rr[i2]) / dd[i2] + 2.0
    h[i3] = (rr[i3] - gg[i3]) / dd[i3] + 4.0
    hue[m] = h * 60.0
    dom = g - np.maximum(r, b)
    return float(np.median(hue)), float(np.median(sat)), float(np.median(dom))


def _bg_mask(greenish, rgb, min_hole_area=800):
    """背景掩码 = 与边缘连通的绿域 + 特征匹配绿幕的封闭绿袋。
    封闭袋判据（中位数）：色相 115-143° 且饱和度>=0.45 且 dominance>=55；
    角色绿色元素（如薄荷发 hue~150 / sat~0.31 / dom~38）三项全不满足，安全保留。
    边缘连通区用金字塔洪泛（向量化），剩余绿域小规模 BFS 逐域判定。"""
    from collections import deque
    h, w = greenish.shape
    s = 4
    H4, W4 = h // s, w // s
    g4 = greenish[:H4 * s, :W4 * s].reshape(H4, s, W4, s).any(axis=(1, 3))

    seed = np.zeros_like(g4)
    seed[0, :] |= g4[0, :]
    seed[-1, :] |= g4[-1, :]
    seed[:, 0] |= g4[:, 0]
    seed[:, -1] |= g4[:, -1]
    bg4 = seed & g4
    while True:
        grown = bg4.copy()
        grown[1:, :] |= bg4[:-1, :]
        grown[:-1, :] |= bg4[1:, :]
        grown[:, 1:] |= bg4[:, :-1]
        grown[:, :-1] |= bg4[:, 1:]
        grown &= g4
        if (grown == bg4).all():
            break
        bg4 = grown

    up = np.kron(bg4, np.ones((s, s), dtype=bool))
    approx = np.zeros((h, w), dtype=bool)
    approx[:up.shape[0], :up.shape[1]] = up
    approx &= greenish
    # 精修：把金字塔损失的边缘细节补回（限制在 greenish 内）
    approx = _dilate(approx, 8) & greenish

    bg = approx.copy()
    hole = np.zeros((h, w), dtype=bool)
    rest = greenish & ~bg
    if not rest.any():
        return bg

    visited = rest.copy()
    ys, xs = np.where(visited)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if not visited[y0, x0]:
            continue
        comp = []
        dq = deque([(y0, x0)])
        visited[y0, x0] = False
        while dq:
            y, x = dq.popleft()
            comp.append((y, x))
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and visited[ny, nx]:
                    visited[ny, nx] = False
                    dq.append((ny, nx))
        if len(comp) < min_hole_area:
            continue  # 小绿域 = 角色元素，保留
        idx = np.array(comp)
        if len(idx) > 5000:
            idx = idx[np.random.RandomState(7).choice(len(idx), 5000, replace=False)]
        px = rgb[idx[:, 0], idx[:, 1]]
        hue, sat, dom = _vec_hsv_stats(px)
        if 115.0 <= hue <= 143.0 and sat >= 0.45 and dom >= 55.0:
            for y, x in comp:
                bg[y, x] = True
                hole[y, x] = True
    if hole.any():  # 封闭袋的阴影边（低主导度绿）向外扩 2px 一并清除
        rr, gg, bb = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        dom_map = gg - np.maximum(rr, bb)
        bg |= _dilate(hole, 2) & (dom_map > 20)
    return bg


def remove_green(img, threshold=90.0, feather=1.5, lo=20.0):
    """洪泛式绿幕抠图：只移除与画面边缘连通的绿色区域，并做去绿溢色。
    threshold: dominance >= threshold 完全透明；lo: dominance <= lo 完全不透明。"""
    arr = np.asarray(img.convert('RGB')).astype(np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # 绿色主导度：绿越高于红蓝，越可能是背景
    dominance = g - np.maximum(r, b)

    greenish = dominance > max(lo + 25, 45.0)   # 洪泛候选（背景实测 >=85，角色绿发 <=40）
    bg = _bg_mask(greenish, arr)

    # 背景核心（离角色轮廓 6px 以外）直接全透明，消除远景绿雾；
    # 轮廓邻接带用双点软过渡保留抗锯齿边缘。
    interior = ~bg
    near_band = _dilate(interior, 6) & bg
    bg_core = bg & ~near_band

    span = max(threshold - lo, 1.0)
    soft = 1.0 - np.clip((dominance - lo) / span, 0.0, 1.0)  # 1=透明倾向
    alpha = np.where(bg_core, 0.0, np.where(near_band, soft, 1.0))

    if feather > 0:
        k = np.ones((3, 3), dtype=np.float32) / 9.0
        pad = np.pad(alpha, 1, mode='edge')
        acc = np.zeros_like(alpha)
        for dy in range(3):
            for dx in range(3):
                acc += pad[dy:dy + alpha.shape[0], dx:dx + alpha.shape[1]] * k[dy, dx]
        alpha = np.clip(alpha * (1 - 0.35 * feather) + acc * (0.35 * feather), 0.0, 1.0)

    # 去绿溢色：背景邻接带（含半透明边缘）把绿压到红蓝最大值
    near = bg.copy()
    for _ in range(3):
        grown = near.copy()
        grown[1:, :] |= near[:-1, :]
        grown[:-1, :] |= near[1:, :]
        grown[:, 1:] |= near[:, :-1]
        grown[:, :-1] |= near[:, 1:]
        near = grown
    spill = near & (alpha > 0.02)
    g_fixed = np.where(spill, np.minimum(g, np.maximum(r, b)), g)
    # 完全不透明的像素也轻微去绿（防止轮廓内圈泛绿）
    solid_mask = alpha >= 0.98
    g_fixed = np.where(solid_mask, np.minimum(g_fixed, np.maximum(r, b) + 6), g_fixed)

    out = np.dstack([r, g_fixed, b, alpha * 255.0]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def trim_transparent(img, pad=8):
    """按 alpha 包围盒裁紧，四周留 pad 透明边。"""
    a = np.asarray(img)[:, :, 3]
    ys, xs = np.where(a > 4)
    if len(ys) == 0:
        return img
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    y0 = max(0, y0 - pad); x0 = max(0, x0 - pad)
    y1 = min(img.height - 1, y1 + pad); x1 = min(img.width - 1, x1 + pad)
    return img.crop((int(x0), int(y0), int(x1 + 1), int(y1 + 1)))


def main():
    src, dst, crop_bottom, threshold, feather, lo, wipe = parse_args(sys.argv)
    img = Image.open(src)
    print('输入: %s  %dx%d  %s' % (src, img.width, img.height, img.mode))

    if crop_bottom > 0:
        img = img.crop((0, 0, img.width, img.height - crop_bottom))
        print('  裁掉底部水印条带: %dpx -> %dx%d' % (crop_bottom, img.width, img.height))

    if wipe:
        from PIL import ImageDraw
        w, h = img.width, img.height
        rect = (int(wipe[0] * w), int(wipe[1] * h), int(wipe[2] * w) + 1, int(wipe[3] * h) + 1)
        d = ImageDraw.Draw(img)
        d.rectangle(rect, fill=(16, 185, 40))   # 典型绿幕色，dominance 远超阈值
        print('  擦除水印区(比例坐标): %s -> 刷绿 %s' % (wipe, rect))

    out = remove_green(img, threshold=threshold, feather=feather, lo=lo)
    out = trim_transparent(out, pad=8)

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    out.save(dst, 'PNG', optimize=True)

    a = np.asarray(out)[:, :, 3]
    opaque = float((a > 250).sum()) / a.size * 100.0
    clear = float((a < 5).sum()) / a.size * 100.0
    print('输出: %s  %dx%d' % (dst, out.width, out.height))
    print('  实心像素 %.1f%%  透明像素 %.1f%%  半透明过渡 %.1f%%' %
          (opaque, clear, 100.0 - opaque - clear))


if __name__ == '__main__':
    main()
