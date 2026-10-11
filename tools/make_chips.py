# -*- coding: utf-8 -*-
"""筹码资产生成 · 5 面值程序化筹码（与 make_cards.py 同产线铁律：矢量程序化，禁 AI 生图）

产出: game/assets/chips/chip_<面值>.png × 5 + chips_preview.png
设计: 外盘 + 6 段 rim 短纹 + 内环 + 面值字 (Constantia Bold, 4x 超采样)
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
OUT = HERE.parent / "assets" / "chips"
OUT.mkdir(parents=True, exist_ok=True)
FONT = "C:/Windows/Fonts/constanb.ttf"

DENOMS = [
    (10,   "#e6ddc4", "#4a4334"),   # (面值, 盘色, 字色)
    (50,   "#c8405a", "#ffe9ee"),
    (100,  "#2c3a5e", "#d8e2ff"),
    (500,  "#7a4fa0", "#f0e6ff"),
    (1000, "#c9a86a", "#241d10"),
]
PX = 96
SS = 4


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def make_chip(value, base, txt_color):
    s = PX * SS
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = cy = s / 2
    r = s / 2 - 2 * SS
    b = hexc(base)
    t = hexc(txt_color)
    # 外盘
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*b, 255))
    # 6 段 rim 短纹（经典筹码边纹）
    dash_r_out, dash_r_in = r, r * 0.80
    for k in range(6):
        a0 = math.radians(k * 60 - 105 + 8)
        a1 = math.radians(k * 60 - 105 + 52)
        p0 = (cx + dash_r_out * math.cos(a0), cy + dash_r_out * math.sin(a0))
        p1 = (cx + dash_r_out * math.cos(a1), cy + dash_r_out * math.sin(a1))
        p2 = (cx + dash_r_in * math.cos(a1), cy + dash_r_in * math.sin(a1))
        p3 = (cx + dash_r_in * math.cos(a0), cy + dash_r_in * math.sin(a0))
        light = tuple(min(255, v + 60) for v in b)
        d.polygon([p0, p1, p2, p3], fill=(*light, 255))
    # 内环
    ir = r * 0.62
    d.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], outline=(*t, 200), width=2 * SS)
    # 面值字
    fpx = int(s * (0.34 if value < 1000 else 0.28))
    f = ImageFont.truetype(FONT, fpx)
    txt = str(value)
    tw = d.textlength(txt, font=f)
    bb = f.getbbox(txt)
    d.text((cx - tw / 2, cy - (bb[3] + bb[1]) / 2), txt, font=f, fill=(*t, 255))
    return im.resize((PX, PX), Image.LANCZOS)


def main():
    for value, base, txt in DENOMS:
        make_chip(value, base, txt).save(OUT / f"chip_{value}.png")
        print(f"chip_{value}.png", flush=True)
    # 预览条
    sheet = Image.new("RGBA", (len(DENOMS) * (PX + 8) + 8, PX + 16), (40, 32, 52, 255))
    for i, (value, _, _) in enumerate(DENOMS):
        c = Image.open(OUT / f"chip_{value}.png")
        sheet.alpha_composite(c, (8 + i * (PX + 8), 8))
    sheet.convert("RGB").save(OUT / "chips_preview.png")
    print(f"预览: {OUT / 'chips_preview.png'}", flush=True)


if __name__ == "__main__":
    main()
