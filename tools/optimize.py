# optimize.py — 立绘资产体积优化
#
# 立绘是「带 alpha 的大图」，PNG 体积很大（单张约 1MB）。
# 处理策略：
#   1. 降采样到目标高度（默认 900px，网页立绘足够）
#   2. 调色板量化（256 色 + 保留 alpha），赛璐璐上色只有少量层次，量化几乎无损
#   3. 输出 PNG（保持 alpha）与 webp（体积更小，现代浏览器全支持）
#
# 用法：
#   python optimize.py <输入目录> [--height 900] [--webp] [--suffix -s]
import sys
import os
import glob
import numpy as np
from PIL import Image


def parse_args(argv):
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = argv[1]
    height = 900
    webp = False
    suffix = '-s'
    for i, a in enumerate(argv):
        if a == '--height' and i + 1 < len(argv):
            height = int(argv[i + 1])
        elif a == '--webp':
            webp = True
        elif a == '--suffix' and i + 1 < len(argv):
            suffix = argv[i + 1]
    return src, height, webp, suffix


def shrink_alpha(img, height):
    """等比降采样，用 LANCZOS 保边。"""
    if img.height <= height:
        return img
    w = max(1, round(img.width * height / img.height))
    return img.resize((w, height), Image.LANCZOS)


def quantize_rgba(img, colors=256):
    """保留 alpha 的调色板量化。
    做法：把 alpha 也作为一个通道参与量化，
    量化后回写 alpha（避免 PIL 的 convert('P') 丢 alpha 问题）。"""
    img = img.convert('RGBA')
    alpha = img.getchannel('A')
    # 用 FASTOCTREE —— 天然支持 RGBA，比 median cut 更适合带透明的图
    q = img.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.NONE)
    out = q.convert('RGBA')
    # 强制恢复原始 alpha，保证边缘不被量化破坏
    out.putalpha(alpha)
    return out


def main():
    src, height, webp, suffix = parse_args(sys.argv)
    files = sorted(glob.glob(os.path.join(src, '*.png')))
    if not files:
        print('未找到 PNG：%s' % src)
        sys.exit(1)

    total_before = total_after = 0
    print('%-22s %10s %10s %8s' % ('文件', '原始', '优化后', '降幅'))
    print('-' * 54)

    for f in files:
        name = os.path.basename(f)
        # 跳过已是优化产物的文件
        if suffix and ('%s.png' % suffix) in name or name.endswith('%s.webp' % suffix):
            continue
        before = os.path.getsize(f)
        img = Image.open(f).convert('RGBA')
        img = shrink_alpha(img, height)
        img = quantize_rgba(img)

        base = name[:-4]
        outp = os.path.join(src, '%s%s.png' % (base, suffix))
        img.save(outp, 'PNG', optimize=True)
        after = os.path.getsize(outp)

        if webp:
            outw = os.path.join(src, '%s%s.webp' % (base, suffix))
            img.save(outw, 'WEBP', quality=88, method=6)

        total_before += before
        total_after += after
        print('%-22s %9.0fK %9.0fK %7.0f%%' %
              (name, before / 1024, after / 1024, (1 - after / before) * 100))

    print('-' * 54)
    print('合计 %.1fMB -> %.1fMB  （降低 %.0f%%）' %
          (total_before / 1048576, total_after / 1048576,
           (1 - total_after / max(total_before, 1)) * 100))


if __name__ == '__main__':
    main()
