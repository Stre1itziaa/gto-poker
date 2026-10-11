# -*- coding: utf-8 -*-
"""牌面合成器 v2 · 52 张牌面 + 程序化牌背

学习自 Monarch/Artisan 级参考 (tools/ref/): 大而敢的 pip、剪影+金色内雕双色、
贝塞尔曲线轮廓、纹章式宫廷牌、克制的 4 色盘、象牙纸面。
数据: cards_layout.json    产出: game/assets/cards/ + cards_preview.png
铁律: 牌面含字母/数字/pip 一律程序化, 禁止 AI 生图 (06-ui-steam-plan.md)
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
CFG = json.loads((HERE / "cards_layout.json").read_text(encoding="utf-8"))
OUT = HERE.parent / "assets" / "cards"
OUT.mkdir(parents=True, exist_ok=True)

C = CFG["colors"]
W, H = CFG["canvas"]["w"], CFG["canvas"]["h"]
SS = CFG["canvas"]["supersample"]


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _font(px):
    try:
        return ImageFont.truetype(CFG["font_rank"], px)
    except OSError:
        return ImageFont.truetype(CFG["font_rank_fallback"], px)


# ---------- 贝塞尔轮廓 ----------

def _sample(segs, s, n=30):
    """闭/开三次贝塞尔链 (0..1 归一坐标) -> 按 s 缩放的多边形点列"""
    pts = []
    for p0, c1, c2, p1 in segs:
        for i in range(n + 1):
            t = i / n
            u = 1 - t
            pts.append((u * u * u * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p1[0],
                        u * u * u * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p1[1]))
    return [(x * s, y * s) for x, y in pts]


def _poly(d, segs, s, color):
    d.polygon(_sample(segs, s), fill=color)


def _heart_body(d, s, color, flip=False):
    """正/倒心形主体 (flip=黑桃上半部, 顶部收尖)"""
    m = lambda y: 1 - y if flip else y
    if flip:
        t1, t2 = (0.42, m(0.02)), (0.58, m(0.02))
    else:
        t1, t2 = (0.34, m(0.00)), (0.66, m(0.00))
    segs = [
        ((0.50, m(0.90)), (0.20, m(0.66)), (0.04, m(0.52)), (0.055, m(0.32))),
        ((0.055, m(0.32)), (0.07, m(0.10)), t1, (0.50, m(0.19))),
        ((0.50, m(0.19)), t2, (0.93, m(0.10)), (0.945, m(0.32))),
        ((0.945, m(0.32)), (0.96, m(0.52)), (0.80, m(0.66)), (0.50, m(0.90))),
    ]
    _poly(d, segs, s, color)


def _stem(d, s, color):
    segs = [
        ((0.425, 0.56), (0.455, 0.74), (0.38, 0.86), (0.295, 0.96)),
        ((0.295, 0.96), (0.44, 0.96), (0.56, 0.96), (0.705, 0.96)),
        ((0.705, 0.96), (0.62, 0.86), (0.545, 0.74), (0.575, 0.56)),
    ]
    _poly(d, segs, s, color)


def draw_spade(d, s):
    c = C["black_suit"]
    _heart_body(d, s, c, flip=True)
    _stem(d, s, c)


def draw_heart(d, s):
    _heart_body(d, s, C["red_suit"])


def draw_diamond(d, s):
    c = C["red_suit"]
    _poly(d, [
        ((0.50, 0.03), (0.68, 0.24), (0.82, 0.38), (0.955, 0.50)),
        ((0.955, 0.50), (0.82, 0.62), (0.68, 0.76), (0.50, 0.97)),
        ((0.50, 0.97), (0.32, 0.76), (0.18, 0.62), (0.045, 0.50)),
        ((0.045, 0.50), (0.18, 0.38), (0.32, 0.24), (0.50, 0.03)),
    ], s, c)


def draw_club(d, s):
    c = C["black_suit"]
    r = 0.165 * s
    for ox, oy in [(0.50, 0.235), (0.29, 0.46), (0.71, 0.46)]:
        d.ellipse([ox * s - r, oy * s - r, ox * s + r, oy * s + r], fill=c)
    d.ellipse([0.50 * s - 0.135 * s, 0.40 * s - 0.135 * s, 0.50 * s + 0.135 * s, 0.40 * s + 0.135 * s], fill=c)
    _stem(d, s, c)


GLYPHS = {"spade": draw_spade, "heart": draw_heart, "diamond": draw_diamond, "club": draw_club}


def glyph(name, px):
    s = px * 4
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    GLYPHS[name](ImageDraw.Draw(tile), s)
    return tile.resize((px, px), Image.LANCZOS)


def sakura(size, color, alpha, outline=False):
    """五瓣樱花 (分离花瓣 + 中心蕊)"""
    s = size * 4
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    col = (*_hex(color), alpha)
    cx = cy = s / 2
    pr, ring = s * 0.15, s * 0.27
    for k in range(5):
        th = math.radians(90 + k * 72)
        px_, py_ = cx + ring * math.cos(th), cy + ring * math.sin(th)
        box = [px_ - pr, py_ - pr * 0.72, px_ + pr, py_ + pr * 0.72]
        if outline:
            d.ellipse(box, outline=col, width=max(2, s // 90))
        else:
            d.ellipse(box, fill=col)
    d.ellipse([cx - s * 0.065, cy - s * 0.065, cx + s * 0.065, cy + s * 0.065], fill=col)
    return tile.resize((size, size), Image.LANCZOS)


def sakura_detailed(size, color, tint):
    """纹章级樱花: 花瓣描边 + 淡色填充 + 蕊"""
    s = size * 4
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    fill = (*_hex(color), 46)
    line = (*_hex(color), 255)
    cx = cy = s / 2
    pr, ring = s * 0.15, s * 0.27
    lw = max(3, s // 100)
    for k in range(5):
        th = math.radians(90 + k * 72)
        px_, py_ = cx + ring * math.cos(th), cy + ring * math.sin(th)
        box = [px_ - pr, py_ - pr * 0.72, px_ + pr, py_ + pr * 0.72]
        d.ellipse(box, fill=fill, outline=line, width=lw)
    rr = s * 0.062
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=line, width=lw)
    d.ellipse([cx - rr * 0.4, cy - rr * 0.4, cx + rr * 0.4, cy + rr * 0.4], fill=line)
    return tile.resize((size, size), Image.LANCZOS)


# ---------- 牌面 ----------

def _paper():
    w, h = W, H
    m = SS
    im = Image.new("RGBA", (w * m, h * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = CFG["canvas"]["corner_radius"] * m
    d.rounded_rectangle([0, 0, w * m - 1, h * m - 1], r, fill=(*_hex(C["paper"]), 255))
    sheen = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sheen)
    ds.polygon([(0, 0), (w * m, 0), (0, h * m * 0.55)], fill=(*_hex(C["sheen"]), 14))
    im = Image.alpha_composite(im, sheen)
    return im.resize((w, h), Image.LANCZOS)


def _pip_with_detail(name, px, color, accent):
    """剪影 + 中心樱花内雕 (Monarch 式双色)"""
    t = glyph(name, px)
    if px >= 90:
        det = sakura(int(px * 0.30), accent, 235)
        t.alpha_composite(det, (int((t.width - det.width) / 2), int((t.height - det.height) / 2)))
    return t


def _corner(img, rank, g, x, y, rot):
    cpx = CFG["corner"]
    rank_px = cpx["rank_px_10"] if rank == "10" else cpx["rank_px"]
    bw, bh = int(rank_px * 1.7), rank_px + cpx["suit_px"] + 4
    block = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bd = ImageDraw.Draw(block)
    f = _font(rank_px)
    tw = bd.textlength(rank, font=f)
    bb = f.getbbox(rank)
    bd.text(((bw - tw) / 2, -bb[1] * 0.15), rank, font=f, fill=g["color"])
    sg = g["tile"]
    block.alpha_composite(sg, (int((bw - sg.width) / 2), rank_px + 4))
    if rot:
        block = block.rotate(180)
    img.alpha_composite(block, (x, y))


def _ornament_rule(d, cx, y, w, color):
    """水平饰线: 线—菱—线"""
    half, dd = w // 2, 5
    d.line([cx - half, y, cx - dd * 2, y], fill=color, width=2)
    d.line([cx + dd * 2, y, cx + half, y], fill=color, width=2)
    d.polygon([(cx, y - dd), (cx + dd, y), (cx, y + dd), (cx - dd, y)], outline=color, width=2)


def render_face(rank, suit):
    face = _paper()
    color = C["red_suit"] if suit["red"] else C["black_suit"]
    accent = C["paper"] if suit["red"] else C["gold"]
    g = {"color": color, "tile": glyph(suit["name"], CFG["corner"]["suit_px"])}

    cpx = CFG["corner"]
    _corner(face, rank, g, cpx["x"], cpx["y"], rot=False)
    _corner(face, rank, g, W - cpx["x"] - int(cpx["rank_px"] * 1.7),
            H - cpx["y"] - cpx["rank_px"] - cpx["suit_px"] - 4, rot=True)

    pa = CFG["pip_area"]
    ax, ay = pa["x1"] - pa["x0"], pa["y1"] - pa["y0"]
    layout = CFG["layouts"][rank]

    if layout == "ace":
        px = pa["ace_spade_px"] if suit["name"] == "spade" else pa["ace_px"]
        t = _pip_with_detail(suit["name"], px, color, accent)
        cy = H / 2 - 14
        face.alpha_composite(t, (int(W / 2 - px / 2), int(cy - px / 2)))
        if suit["name"] == "spade":
            for k, dx in enumerate((-64, 0, 64)):
                b = sakura(40, color, 200)
                face.alpha_composite(b, (int(W / 2 + dx - 20), int(cy + px / 2 + 16)))
    elif layout == "court":
        d = ImageDraw.Draw(face)
        cx, cy, rr = W / 2, H / 2, CFG["court"]["ring_r"]
        col = (*_hex(color), 130)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=col, width=3)
        d.ellipse([cx - rr + 10, cy - rr + 10, cx + rr - 10, cy + rr - 10], outline=(*_hex(color), 70), width=1)
        med = sakura_detailed(CFG["court"]["medallion_px"], color, C["paper"])
        face.alpha_composite(med, (int(cx - med.width / 2), int(cy - med.height / 2)))
        f = _font(CFG["court"]["letter_px"])
        tw = d.textlength(rank, font=f)
        bb = f.getbbox(rank)
        th = bb[3] - bb[1]
        d.text((cx - tw / 2, cy - th / 2 - bb[1]), rank, font=f, fill=color)
        rw = CFG["court"]["rule_w"]
        _ornament_rule(d, cx, cy - rr - 26, rw, (*_hex(color), 200))
        _ornament_rule(d, cx, cy + rr + 26, rw, (*_hex(color), 200))
    else:
        px = pa["pip_px"]
        t = _pip_with_detail(suit["name"], px, color, accent)
        for nx, ny in layout:
            x = pa["x0"] + ax * nx - px / 2
            y = pa["y0"] + ay * ny - px / 2
            tt = t.rotate(180) if ny > 0.5 else t
            face.alpha_composite(tt, (int(x), int(y)))
    return face


def render_back():
    face = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(face)
    d.rounded_rectangle([0, 0, W - 1, H - 1], CFG["canvas"]["corner_radius"], fill=(*_hex(C["back_base"]), 255))
    gold = (*_hex(C["back_gold"]), 255)
    gold_dim = (*_hex(C["back_gold"]), 90)
    d.rounded_rectangle([10, 10, W - 11, H - 11], CFG["canvas"]["corner_radius"] - 8, outline=gold, width=3)
    d.rounded_rectangle([20, 20, W - 21, H - 21], CFG["canvas"]["corner_radius"] - 14, outline=gold_dim, width=1)
    # 斜向格纹 (裁剪在内框内)
    lattice = Image.new("RGBA", (W - 48, H - 48), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lattice)
    for i in range(-(H // 36 + 2), (W // 36) + 40):
        dl.line([i * 36, 0, i * 36 + lattice.height, lattice.height], fill=gold_dim, width=1)
    for i in range(-(H // 36 + 2), (W // 36) + 40):
        dl.line([i * 36, lattice.height, i * 36 + lattice.height, 0], fill=gold_dim, width=1)
    mask = Image.new("L", lattice.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([14, 14, lattice.width - 15, lattice.height - 15], 16, fill=110)
    face.paste(lattice, (24, 24), Image.composite(mask, Image.new("L", lattice.size, 0), mask))
    # 四角小花 + 中央纹章
    for ox, oy in [(52, 52), (W - 92, 52), (52, H - 92), (W - 92, H - 92)]:
        face.alpha_composite(sakura(40, C["back_gold"], 220), (ox, oy))
    d.ellipse([W / 2 - 96, H / 2 - 96, W / 2 + 96, H / 2 + 96], outline=gold, width=3)
    med = sakura_detailed(150, C["back_gold"], C["back_base"])
    face.alpha_composite(med, (int(W / 2 - 75), int(H / 2 - 75)))
    return face


def main():
    made = []
    for suit in CFG["suits"]:
        for rank in CFG["ranks"]:
            render_face(rank, suit).save(OUT / f"face_{rank}{suit['key']}.png")
            made.append(f"face_{rank}{suit['key']}")
    render_back().save(OUT / "back_classic.png")
    made.append("back_classic")
    print(f"产出 {len(made)} 张 -> {OUT}")

    tw, th, pad = 128, 179, 6
    sheet = Image.new("RGBA", (13 * (tw + pad) + pad, 4 * (th + pad) + pad + th + pad * 2), (58, 42, 66, 255))
    for r, suit in enumerate(CFG["suits"]):
        for c, rank in enumerate(CFG["ranks"]):
            im = Image.open(OUT / f"face_{rank}{suit['key']}.png").resize((tw, th), Image.LANCZOS)
            sheet.alpha_composite(im, (pad + c * (tw + pad), pad + r * (th + pad)))
    y = 4 * (th + pad) + pad
    for c, name in enumerate(["face_As", "face_10h", "face_7d", "face_Kc", "back_classic"]):
        im = Image.open(OUT / f"{name}.png").resize((46, 64), Image.LANCZOS)
        sheet.alpha_composite(im, (pad + c * 56, y))
    sheet.convert("RGB").save(HERE.parent / "assets" / "cards_preview.png")
    print(f"预览: {HERE.parent / 'assets' / 'cards_preview.png'}")


if __name__ == "__main__":
    main()
