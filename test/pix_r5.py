# pix_r5.py — R5 数据页像素级复验（只读截图，不碰游戏）
# 用法: python pix_r5.py <png路径> <输出前缀目录>
# 输出: 按钮排边框剖面 / chips 分色统计 / 8x 放大裁片 / 牌谱区可见性扫描
import sys, os, json
from PIL import Image

PNG = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(PNG)
os.makedirs(OUT, exist_ok=True)
im = Image.open(PNG).convert("RGB")
W, H = im.size
px = im.load()

def close(c, ref, tol=14):
    return all(abs(c[i] - ref[i]) <= tol for i in range(3))

LINE = (48, 60, 102)   # --line #303c66
PINK = (255, 158, 199) # 主题 --gold 樱粉

def merge_spans(spans, gap=8):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + gap: out[-1] = (out[-1][0], max(out[-1][1], b))
        else: out.append((a, b))
    return out

# ---- 1. 找水平 LINE 色线段 ----
segs = []
for y in range(60, H - 40):
    run = 0; start = 0
    for x in range(400, 1250):
        if close(px[x, y], LINE, 30):
            if run == 0: start = x
            run += 1
        else:
            if run >= 40: segs.append((y, start, start + run - 1))
            run = 0
    if run >= 40: segs.append((y, start, start + run - 1))

rows = []
for s in sorted(segs):
    placed = False
    for r in rows:
        if abs(r[-1][0] - s[0]) <= 2:
            r.append(s); placed = True; break
    if not placed: rows.append([s])

print("=== 水平边框线段分组 (y, x0-x1) ===")
for r in rows:
    ys = sorted(set(s[0] for s in r))
    merged = merge_spans([(s[1], s[2]) for s in r])
    print(f"y={ys[0]}-{ys[-1]}: " + ", ".join(f"x{a}-{b}(w{b-a+1})" for a, b in merged))

report = {}

# ---- 2. 按钮排：y>600、3 条 60-140 宽 ----
btn_row = None
for r in rows:
    if r[0][0] <= 600: continue
    merged = merge_spans([(s[1], s[2]) for s in r])
    widths = [b - a + 1 for a, b in merged]
    if len(merged) == 3 and all(55 <= w <= 145 for w in widths):
        btn_row = r; break

if btn_row:
    ytop = min(s[0] for s in btn_row)
    spans = merge_spans([(s[1], s[2]) for s in btn_row])
    # 底边 = 同 x 跨度、y 更大的下一组
    ybot = ytop + 38
    for r2 in rows:
        y2 = min(s[0] for s in r2)
        if ytop + 8 < y2 <= ytop + 70:
            m2 = merge_spans([(s[1], s[2]) for s in r2])
            if len(m2) == len(spans) and all(abs(a2[0] - a1[0]) <= 3 and abs(a2[1] - a1[1]) <= 3
                                             for a1, a2 in zip(spans, m2)):
                ybot = y2; break
    print(f"\n=== 按钮排: 顶边 y={ytop} 底边 y={ybot} ===")
    names = ["导出 JSON", "导入 JSON", "清空本机记录"]
    btns = []
    for i, (a, b) in enumerate(spans[:3]):
        h = ybot - ytop + 1
        ym = (ytop + ybot) // 2
        # 中线 tight-tol 找左右边框列（线段端点是圆角，不能用来测厚）
        def edge_run(x0, x1, step):
            best = (0, None)
            x = x0
            while (step > 0 and x <= x1) or (step < 0 and x >= x1):
                if close(px[x, ym], LINE, 20):
                    n = 0
                    while close(px[x + step * n, ym], LINE, 20) and n < 6: n += 1
                    if n > best[0]: best = (n, x)
                    x += step * max(n, 1)
                else:
                    x += step
            return best
        ln, lx = edge_run(a - 16, a + 6, 1)
        rn, rx = edge_run(b + 16, b - 6, -1)
        # 上下边框厚度：中线 x 垂直扫 tight tol
        xm = (a + b) // 2
        t = 0
        yy = ytop
        while not close(px[xm, yy], LINE, 24) and yy < ytop + 6: yy += 1
        while close(px[xm, yy], LINE, 24) and t < 6: t += 1; yy += 1
        bt = 0
        yy = ybot
        while not close(px[xm, yy], LINE, 24) and yy > ybot - 6: yy -= 1
        while close(px[xm, yy], LINE, 24) and bt < 6: bt += 1; yy -= 1
        c_border = px[lx + 1, ym] if lx and ln else None
        # 中线剖面（边框真实位置±10）
        lo = lx if (lx and ln) else a - 12
        hi = rx if (rx and rn) else b + 12
        prof = "".join("L" if close(px[x, ym], LINE, 20) else "." for x in range(lo - 4, hi + 5))
        info = {"name": names[i] if i < 3 else f"btn{i}", "x": f"{a}-{b}", "w": b - a + 1, "h": h,
                "borderL_px": ln, "borderL_x": lx, "borderR_px": rn, "borderR_x": rx,
                "borderT_px": t, "borderB_px": bt, "border_color_left_mid": c_border}
        btns.append(info)
        print(f"{info['name']}: x{a}-{b}(w{info['w']}) h={h} 左边框{ln}px@x{lx} 右边框{rn}px@x{rx} "
              f"上边框{t}px 下边框{bt}px 边框色(mid)={c_border}")
        print(f"    y={ym} 剖面 x{lo-4}-{hi+4}: {prof}")
    report["buttons"] = btns
    a0 = spans[0][0] - 8; b0 = spans[-1][1] + 8
    crop = im.crop((a0, ytop - 8, b0, ybot + 8))
    crop.resize((crop.width * 8, crop.height * 8), Image.NEAREST).save(os.path.join(OUT, "zoom_buttons_8x.png"))
    print("已保存 zoom_buttons_8x.png")

# ---- 3. chips 行：y 90-260、2-4 条 35-95 宽 ----
chip_row = None
for r in rows:
    y0 = min(s[0] for s in r)
    if not (90 <= y0 <= 260): continue
    merged = merge_spans([(s[1], s[2]) for s in r])
    widths = [b - a + 1 for a, b in merged]
    if 2 <= len(merged) <= 4 and all(35 <= w <= 95 for w in widths):
        chip_row = r; break

if chip_row:
    ytop = min(s[0] for s in chip_row)
    spans = merge_spans([(s[1], s[2]) for s in chip_row])
    ybot = ytop + 37
    for r2 in rows:
        y2 = min(s[0] for s in r2)
        if ytop + 8 < y2 <= ytop + 70:
            m2 = merge_spans([(s[1], s[2]) for s in r2])
            if len(m2) == len(spans) and all(abs(a2[0] - a1[0]) <= 4 for a1, a2 in zip(spans, m2)):
                ybot = y2; break
    print(f"\n=== chips 行: 顶边 y={ytop} 底边 y={ybot} ===")
    names = ["全部", "多人", "单机"]
    chips = []
    for i, (a, b) in enumerate(spans):
        xm = (a + b) // 2
        t = 0
        while t < 5 and close(px[xm, ytop + t], px[xm, ytop], 26): t += 1
        c_top = [px[xm, ytop + k] for k in range(t)]
        # 文字区统计：亮像素里的最粉色 + 粉色计数
        peak = (0, 0, 0); peak_rb = -999; pink_n = 0; white_n = 0; total = 0
        for y in range(ytop + 7, ybot - 6):
            for x in range(a + 5, b - 4):
                c = px[x, y]; s3 = sum(c)
                if s3 < 330: continue
                total += 1
                rb = c[0] - c[2]
                if rb > peak_rb: peak_rb = rb; peak = c
                if c[0] > 170 and rb >= 25: pink_n += 1
                if rb <= 10 and s3 > 560: white_n += 1
        inner = px[a + 7, ybot - 8]
        info = {"name": names[i] if i < len(names) else f"chip{i}", "x": f"{a}-{b}", "w": b - a + 1,
                "h": ybot - ytop + 1, "border_top_thickness": t, "border_top_colors": c_top,
                "text_peak_pinkish": peak, "peak_RB": peak_rb, "pink_px": pink_n, "white_px": white_n,
                "bright_px": total, "inner_bg": inner}
        chips.append(info)
        print(f"{info['name']}: x{a}-{b}(w{info['w']}) h={info['h']} 顶边框厚{t}px 色={c_top} "
              f"文字峰值R-B={peak_rb}({peak}) 粉px={pink_n} 白px={white_n} 亮px={total} 内部底={inner}")
    sel_n = sum(1 for c in chips if c["pink_px"] > 30)
    print(f"--> 判定: {sel_n} 个 chip 呈粉色高亮 (期望恰 1 个=当前范围「全部」)")
    report["chips"] = chips
    a0 = spans[0][0] - 45; b0 = spans[-1][1] + 12
    crop = im.crop((a0, ytop - 10, b0, ybot + 10))
    crop.resize((crop.width * 8, crop.height * 8), Image.NEAREST).save(os.path.join(OUT, "zoom_chips_8x.png"))
    print("已保存 zoom_chips_8x.png")
else:
    print("\n!!! 未定位到 chips 行")

# ---- 4. 牌谱区可见性扫描 ----
print("\n=== 牌谱区亮像素扫描 (x 480-1130, y 560-800, 步长4) ===")
bands = []
for y in range(560, 800, 4):
    n = sum(1 for x in range(480, 1130, 2) if sum(px[x, y]) > 180)
    bands.append((y, n))
print("; ".join(f"{y}:{n}" for y, n in bands))
json.dump(report, open(os.path.join(OUT, "pix_report.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print("\npix_report.json 已写出")
