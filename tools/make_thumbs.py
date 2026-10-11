# make_thumbs.py — 从 *-s.webp 生成 300px 高缩略档 *-t.webp（立绘显示多为 46-210px，900px 原档过重）
# 运行：python tools/make_thumbs.py
import glob, os
from PIL import Image

os.chdir(os.path.join(os.path.dirname(__file__), '..', 'assets', 'characters'))
n = 0
for f in glob.glob('*-s.webp'):
    out = f.replace('-s.webp', '-t.webp')
    if os.path.exists(out):
        continue
    im = Image.open(f)
    h = 300
    w = round(im.width * h / im.height)
    im.resize((w, h), Image.LANCZOS).save(out, 'WEBP', quality=80, method=6)
    n += 1
print('generated', n, 'thumbs')
