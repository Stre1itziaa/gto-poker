# face_check.py — 批1-T1.10 立绘一致性报警脚本 v2（跨表情比对口径）
#
# v1 教训：动漫脸级联对大幅立绘框取失真（框进整头），瞳距口径 100% 误报 → 废弃。
# v2 口径：不检测「脸」，直接比对「同一角色的各表情是否还是同一张脸」：
#   1. 对齐：各表情与 idle 做模板匹配取最优偏移（亚像素级构图锚定）
#   2. 脸部 diff：对齐后 absdiff，diff>25 的像素占比 >6% → 报警（表情只该动眼嘴，脸型阴影跑偏即超标）
#   3. 构图质心：亮区（皮肤/高光）质心偏移 >2% 画布 → 报警
# 输出：test/face-audit-report.md（按曝光度排序）
# 运行：python tools/face_check.py   （需 tools/.venv-faces 的 opencv 4.x）
import glob, os, sys
import cv2
import numpy as np

os.chdir(os.path.join(os.path.dirname(__file__), '..'))
ASSET_DIR = os.path.join('assets', 'characters')
DIFF_RATIO_LIMIT = 0.06     # 脸部 diff 像素占比上限
CENTROID_LIMIT = 0.02       # 构图质心偏移上限（画布比例）

def load_gray(path):
    img = cv2.imread(path)
    if img is None:
        return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return g

def bright_centroid(gray):
    """亮区质心（皮肤/高光）：HSV 高 V 低 S"""
    hsv = cv2.cvtColor(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 2] > 178) & (hsv[:, :, 1] < 70)).astype(np.uint8)
    n = int(mask.sum())
    if n < 50:
        return None
    ys, xs = np.nonzero(mask)
    return xs.mean() / gray.shape[1], ys.mean() / gray.shape[0], n

def align_diff(base, expr):
    """expr 相对 base 的最优平移 + 对齐后 diff 占比。返回 (dx, dy, diff_ratio)"""
    res = cv2.matchTemplate(base, expr, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(res)
    dx, dy = max_loc
    # base 与 expr 同尺寸：偏移后重叠区 diff
    h, w = base.shape
    x0, y0 = max(0, dx), max(0, dy)
    x1, y1 = min(w, dx + expr.shape[1]), min(h, dy + expr.shape[0])
    if x1 - x0 < w * 0.5 or y1 - y0 < h * 0.5:
        return dx, dy, 1.0
    b = base[y0:y1, x0:x1]
    e = expr[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    diff = cv2.absdiff(b, e)
    return dx, dy, float((diff > 25).mean())

def main():
    files = sorted(glob.glob(os.path.join(ASSET_DIR, '*.png')) + glob.glob(os.path.join(ASSET_DIR, '*.webp')))
    # 分组：(角色, 服装) → {表情: 路径}；优先原始大图，缺失用 -s.png
    groups = {}
    for f in files:
        b = os.path.basename(f)
        stem = b.rsplit('.', 1)[0]
        if stem.endswith('-t'):
            continue
        if '-s' in stem.split('-')[-1]:
            stem = stem[:-2]
        parts = stem.split('-')
        cid = parts[0]
        costume = parts[1] if len(parts) > 2 and parts[1] in ('club', 'glam', 'p0', 'p1', 'p2', 'p3', 'p4') else ''
        expr = parts[2] if costume else (parts[1] if len(parts) > 1 else 'idle')
        if expr not in ('idle', 'blink', 'happy', 'sad', 'think'):
            continue
        groups.setdefault((cid, costume), {})[expr] = f

    rows, alarms = [], []
    for (cid, costume), exprs in sorted(groups.items()):
        if 'idle' not in exprs:
            continue
        base = load_gray(exprs['idle'])
        if base is None:
            continue
        base_c = bright_centroid(base)
        tag = cid + ('-' + costume if costume else '')
        # 第一遍：算全组 diff → 组内中位数（v3 相对口径基准：表情为整张生成，绝对阈值无裁决意义）
        measured = {}
        for expr, path in exprs.items():
            if expr == 'idle':
                continue
            g = load_gray(path)
            if g is None:
                continue
            dx, dy, diff_ratio = align_diff(base, g)
            measured[expr] = (g, dx, dy, diff_ratio)
        diffs = [m[3] for m in measured.values()]
        median = sorted(diffs)[len(diffs) // 2] if diffs else 0
        # 第二遍：组内相对裁决——blink 应为最小（只动眼睛）；离群 = 中位数 1.6 倍
        for expr, (g, dx, dy, diff_ratio) in sorted(measured.items()):
            c = bright_centroid(g)
            notes = []
            if expr == 'blink' and diffs and diff_ratio > median:
                notes.append(f'blink diff={diff_ratio:.1%} 高于组内中位 {median:.1%}（blink 只该动眼睛，应为最小）')
            if diffs and diff_ratio > median * 1.6 + 0.02:
                notes.append(f'diff={diff_ratio:.1%} 是组内中位（{median:.1%}）的离群值')
            if base_c and c:
                off = ((c[0] - base_c[0]) ** 2 + (c[1] - base_c[1]) ** 2) ** 0.5
                if off > CENTROID_LIMIT:
                    notes.append(f'构图质心偏移 {off:.1%}')
            elif not c:
                notes.append('亮区质心未检出')
            level = 'WARN' if notes else 'OK'
            exp = 3 if expr == 'idle' else 1
            rows.append((exp, f'{tag}-{expr}', level,
                         f'diff={diff_ratio:.1%}（组中位 {median:.1%}） ' + ('；'.join(notes) if notes else '一致')))
            if notes:
                alarms.append((exp, f'{tag}-{expr}', level, '；'.join(notes)))

    rows.sort(key=lambda r: -r[0])
    alarms.sort(key=lambda r: -r[0])
    with open(os.path.join('test', 'face-audit-report.md'), 'w', encoding='utf-8') as f:
        f.write('# 立绘一致性报警报告 v3（批1-T1.10：组内相对口径）\n\n')
        f.write('口径 v3：表情为整张生成，全局 diff（实测 13-50%）是固有属性，绝对阈值无裁决意义——该数据本身坐实了方向 3「需要 inpaint 分区管线」的判断。\n')
        f.write('改用组内相对口径：blink 应为组内最小 diff（只动眼睛）；任意表情 >组内中位 1.6 倍 = 离群；构图质心偏移 >2% 绝对报警。\n\n')
        f.write(f'扫描 {len(rows)} 张表情差分，报警 {len(alarms)} 张。\n\n')
        f.write('## 报警清单（按曝光度排序，人工裁决）\n\n| 曝光 | 文件 | 级别 | 说明 |\n|---|---|---|---|\n')
        for exp, key, level, note in alarms:
            f.write(f'| {"★"*exp or "-"} | {key} | {level} | {note} |\n')
        f.write('\n## 全量明细\n\n| 曝光 | 文件 | 级别 | 说明 |\n|---|---|---|---|\n')
        for exp, key, level, note in rows:
            f.write(f'| {"★"*exp or "-"} | {key} | {level} | {note} |\n')
    print(f'扫描 {len(rows)} 张表情差分，报警 {len(alarms)} 张 → test/face-audit-report.md')

if __name__ == '__main__':
    main()
