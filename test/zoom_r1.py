# zoom_r1.py — 截图放大查看辅助（外观党审图用）
# 用法: python zoom_r1.py <png路径> <out路径> <x0> <y0> <x1> <y1> [倍数=2]
import sys
from PIL import Image
src, out = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(int, sys.argv[3:7])
k = float(sys.argv[7]) if len(sys.argv) > 7 else 2.0
im = Image.open(src).crop((x0, y0, x1, y1))
w, h = int(im.width * k), int(im.height * k)
im = im.resize((w, h), Image.LANCZOS)
im.save(out)
print(f"saved {out} {w}x{k and h}")
