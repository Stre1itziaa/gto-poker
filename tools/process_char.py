# process_char.py — 单角色资产生成管线编排（抠图 → 对齐 → 优化）
#
# 输入目录结构（ImageGen 顺序产出，每表情独立子目录，避免同名覆盖）：
#   assets/_raw/<charId>/<expr>/*.png     expr ∈ idle|think|happy|sad|blink
#
# 输出：
#   assets/characters/<charId>-<expr>-s.png   （900px 高，量化压缩）
#   assets/characters/<charId>-<expr>-s.webp
#
# 用法：
#   python process_char.py <charId> [--crop-bottom 88] [--threshold 90]
import sys
import os
import glob
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'assets', '_raw')
OUT = os.path.join(HERE, '..', 'assets', 'characters')
EXPRS = ['idle', 'think', 'happy', 'sad', 'blink']


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def first_png(d):
    fs = sorted(glob.glob(os.path.join(d, '*.png')))
    return fs[0] if fs else None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cid = sys.argv[1]
    crop = 88
    thresh = 90
    for i, a in enumerate(sys.argv):
        if a == '--crop-bottom' and i + 1 < len(sys.argv):
            crop = int(sys.argv[i + 1])
        elif a == '--threshold' and i + 1 < len(sys.argv):
            thresh = int(sys.argv[i + 1])

    cutout = load_module('cutout', os.path.join(HERE, 'cutout.py'))
    align = load_module('align', os.path.join(HERE, 'align.py'))
    optimize = load_module('optimize', os.path.join(HERE, 'optimize.py'))

    os.makedirs(OUT, exist_ok=True)
    # 中间产物：抠图后的平铺目录（<cid>-<expr>.png，供 align 消费）
    work = os.path.join(HERE, '..', 'assets', '_work', cid)
    os.makedirs(work, exist_ok=True)

    found = {}
    for e in EXPRS:
        src = first_png(os.path.join(RAW, cid, e))
        if not src:
            print('  [miss] %s 无源图，跳过' % e)
            continue
        found[e] = src

    if not found:
        print('错误：角色 %s 没有任何源图' % cid)
        sys.exit(1)

    print('== 角色 %s：抠图 ==' % cid)
    for e, src in found.items():
        dst = os.path.join(work, '%s-%s.png' % (cid, e))
        # 抠图（复用 cutout.py 的核心函数，避免子进程开销）
        from PIL import Image
        img = Image.open(src)
        if crop > 0:
            img = img.crop((0, 0, img.width, img.height - crop))
        out = cutout.remove_green(img, threshold=thresh, feather=0.6)
        out = cutout.trim_transparent(out, pad=8)
        out.save(dst, 'PNG', optimize=True)
        print('  %-6s -> %s' % (e, os.path.basename(dst)))

    print('== 角色 %s：对齐 ==' % cid)
    align_w = os.path.join(HERE, '..', 'assets', '_aligned')
    os.makedirs(align_w, exist_ok=True)
    # 直接复用 align 的核心，按内容高度填充对齐
    from PIL import Image as I2
    import numpy as np
    canvas = (760, 1160)
    ref = None
    imgs = {}
    for e in found:
        imgs[e] = I2.open(os.path.join(work, '%s-%s.png' % (cid, e))).convert('RGBA')
    ref_anchor = {'cx_ratio': 0.5, 'fill_ratio': 0.94}
    for e, img in imgs.items():
        x0, y0, x1, y1 = align.content_bbox(img)
        img = img.crop((x0, y0, x1, y1))
        scale = (canvas[1] * 0.94) / max(img.height, 1)
        nw = max(1, int(round(img.width * scale)))
        nh = max(1, int(round(img.height * scale)))
        img2 = img.resize((nw, nh), I2.LANCZOS)
        a = align.face_anchor(img2)
        cur_cx = a['cx'] if a else (align.content_bbox(img2)[0] + align.content_bbox(img2)[2]) / 2.0
        ox = int(round(canvas[0] * 0.5 - cur_cx))
        oy = canvas[1] - nh
        frame = I2.new('RGBA', canvas, (0, 0, 0, 0))
        frame.alpha_composite(img2, (ox, oy))
        dst = os.path.join(OUT, '%s-%s.png' % (cid, e))
        frame.save(dst, 'PNG', optimize=True)
        imgs[e] = frame
        print('  %-6s -> %s %dx%d' % (e, os.path.basename(dst), frame.width, frame.height))

    print('== 角色 %s：优化 ==' % cid)
    for e, img in imgs.items():
        img = optimize.shrink_alpha(img, 900)
        img = optimize.quantize_rgba(img)
        base = '%s-%s' % (cid, e)
        img.save(os.path.join(OUT, base + '-s.png'), 'PNG', optimize=True)
        img.save(os.path.join(OUT, base + '-s.webp'), 'WEBP', quality=88, method=6)
        print('  %-6s -> %s-s.png + .webp' % (e, base))

    # 清理中间目录
    import shutil
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(align_w, ignore_errors=True)
    print('完成：%s 全套差分已产出' % cid)


if __name__ == '__main__':
    main()
