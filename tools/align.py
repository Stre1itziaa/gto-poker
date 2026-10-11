# align.py — 多张差分图的画布归一化与锚点对齐
#
# 问题：ImageGen 每次产出的构图、缩放、位置都不同，
#       直接换表情会出现角色尺寸跳动、头部漂移。
# 解决：以 idle 为基准，检测每张图的脸部（肤色区域质心 + 宽度）
#       作为锚点，把后续差分缩放/平移对齐到基准帧。
#
# 用法：
#   python align.py <输入目录> <输出目录> <角色id> [--size 760x1160]
#
# 输出：<角色id>-<表情>.png，全部统一画布尺寸、统一头部位置
import sys
import os
import glob
import numpy as np
from PIL import Image

EXPR_ORDER = ['idle', 'think', 'happy', 'sad', 'blink']


def parse_args(argv):
    if len(argv) < 4:
        print(__doc__)
        sys.exit(1)
    src_dir, dst_dir, cid = argv[1], argv[2], argv[3]
    size = (760, 1160)
    fit = False
    for i, a in enumerate(argv):
        if a == '--size' and i + 1 < len(argv):
            w, h = argv[i + 1].lower().split('x')
            size = (int(w), int(h))
        elif a == '--fit':
            fit = True
    return src_dir, dst_dir, cid, size, fit


def skin_mask(img):
    """检测裸露皮肤的像素（脸部/肩颈/手），用于定位锚点。
    赛璐璐肤色：R 明显高于 G 和 B，且整体明亮。"""
    a = np.asarray(img.convert('RGBA')).astype(np.float32)
    r, g, b, al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    skin = (al > 200) & (r > 150) & (r > g + 14) & (g > b - 6) & (r > b + 22) & (r - g < 90)
    return skin


def face_anchor(img):
    """返回脸部锚点：取皮肤掩码最上方 38% 区域（排除手/胸），
    算质心 x 与左右边界中点的 x，以及皮肤顶部 y。"""
    m = skin_mask(img)
    ys, xs = np.where(m)
    if len(ys) < 50:
        return None
    y_top = ys.min()
    y_bot = ys.max()
    band = ys <= y_top + (y_bot - y_top) * 0.38
    bx, by = xs[band], ys[band]
    if len(bx) < 30:
        bx, by = xs, ys
    cx = float(bx.mean())
    left, right = float(bx.min()), float(bx.max())
    width = right - left
    return {'cx': cx, 'top': float(by.min()), 'width': width, 'n': len(bx)}


def content_bbox(img, thresh=8):
    """不透明内容的包围盒。"""
    a = np.asarray(img)[:, :, 3]
    ys, xs = np.where(a > thresh)
    if len(ys) == 0:
        return 0, 0, img.width, img.height
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def align_one(src_path, ref_anchor, canvas, cid, expr, fit=False):
    """统一按「内容高度填充画布」归一化 —— 不逐帧独立缩放脸部宽度，
    避免 AI 各帧构图差异把缩放系数带偏（happy/blink 构图差异大时会乱跳）。
    缩放由高度决定，横向只做居中微调，用皮肤质心修正偏移。"""
    img = Image.open(src_path).convert('RGBA')
    x0, y0, x1, y1 = content_bbox(img)
    img = img.crop((x0, y0, x1, y1))          # 先裁紧，消除各帧不同的空白边
    ch = img.height

    # 目标内容高度 = 画布高 × fill_ratio
    fill = ref_anchor.get('fill_ratio', 0.94)
    scale = (canvas[1] * fill) / max(ch, 1.0)
    if fit:
        # --fit：宽高双约束取小，内容完整入画（G0-5 根治）
        scale = min(scale, (canvas[0] * 0.96) / max(img.width, 1.0))
    nw = max(1, int(round(img.width * scale)))
    nh = max(1, int(round(img.height * scale)))
    img2 = img.resize((nw, nh), Image.LANCZOS)

    # 横向：优先用脸部质心对齐画布中轴；检出失败则用内容包围盒中点
    a = face_anchor(img2)
    if a is not None:
        cur_cx = a['cx']
    else:
        cb = content_bbox(img2)
        cur_cx = (cb[0] + cb[2]) / 2.0

    cx_t = canvas[0] * ref_anchor.get('cx_ratio', 0.5)
    ox = int(round(cx_t - cur_cx))
    ox = max(int(canvas[0] * 0.02) - 0, min(ox, canvas[0] - nw - int(canvas[0] * 0.02)))
    oy = int(round(canvas[1] - nh))            # 底部对齐（角色脚/裙摆贴画布底）

    frame = Image.new('RGBA', canvas, (0, 0, 0, 0))
    frame.alpha_composite(img2, (ox, oy))
    return frame


def main():
    src_dir, dst_dir, cid, canvas, fit = parse_args(sys.argv)
    os.makedirs(dst_dir, exist_ok=True)

    paths = {}
    for f in glob.glob(os.path.join(src_dir, '*.png')):
        for e in EXPR_ORDER:
            if os.path.basename(f).endswith('-%s.png' % e):
                paths[e] = f

    if 'idle' not in paths:
        print('错误：缺少 idle 基准帧')
        sys.exit(1)

    idle = Image.open(paths['idle']).convert('RGBA')
    ref = face_anchor(idle)
    if ref is None:
        print('错误：idle 未检出锚点')
        sys.exit(1)

    ref_norm = dict(ref)
    ref_norm['cx_ratio'] = 0.5
    ref_norm['fill_ratio'] = 0.94

    print('基准帧 idle: 脸宽 %.0f px -> 统一画布 %dx%d（内容高度填充 %.0f%%）'
          % (ref['width'], canvas[0], canvas[1], ref_norm['fill_ratio'] * 100))

    for e in EXPR_ORDER:
        if e not in paths:
            print('  [skip] %s 缺失' % e)
            continue
        out = align_one(paths[e], ref_norm, canvas, cid, e, fit)
        dst = os.path.join(dst_dir, '%s-%s.png' % (cid, e))
        out.save(dst, 'PNG', optimize=True)
        a = np.asarray(out)[:, :, 3]
        filled = float((a > 250).sum()) / a.size * 100.0
        print('  %-6s -> %s  %dx%d  实心 %.1f%%' % (e, os.path.basename(dst), out.width, out.height, filled))


if __name__ == '__main__':
    main()
