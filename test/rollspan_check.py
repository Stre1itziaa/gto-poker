# rollspan_check.py — R2 验证：结算金额「终值直出」无中间假数 + 数据弹窗布局
# 方法: 单机模式打到结算 → 弹层一露出就开始高频轮询 #overlay-body 数字，连续快照对比
import json, os, re, time, traceback
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__)) + "/data2/fulu"
URL = "http://localhost:8787/"
NUM = re.compile(r"-?−?\d+(?:\.\d+)?")

def nums(text):
    return NUM.findall(text or "")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1600, "height": 900})
    pg = ctx.new_page()
    pg.goto(URL); pg.wait_for_timeout(1200)
    pg.locator("#mc-train").click(); pg.wait_for_timeout(400)
    pg.locator("#btn-start").click()
    pg.wait_for_timeout(1500)

    # 简单策略打到第一次结算（最多 4 分钟）
    t0 = time.time()
    while time.time() - t0 < 240:
        if pg.locator("#overlay:not(.hidden)").count():
            break
        if pg.locator("#action-controls").is_visible():
            cb = pg.locator("#btn-checkcall").text_content() or ""
            if "过牌" in cb:
                pg.locator("#btn-checkcall").click()
            else:
                amt = "".join(ch for ch in cb if ch.isdigit())
                if amt and int(amt) <= 60:
                    pg.locator("#btn-checkcall").click()
                else:
                    try: pg.locator("#btn-fold").click(timeout=1500)
                    except Exception: pg.locator("#btn-checkcall").click()
            pg.wait_for_timeout(700)
        else:
            pg.wait_for_timeout(80)   # 高频轮询，弹层一露就读

    result = {"overlay_seen": bool(pg.locator("#overlay:not(.hidden)").count())}
    try:
        if result["overlay_seen"]:
            # 立即连拍: 9 次快照，间隔 ~120ms（旧动画窗口 750ms 必被覆盖）
            snaps = []
            for i in range(9):
                txt = pg.locator("#overlay-body").inner_text()
                el_count = pg.locator("#overlay-body .roll-num").count()
                pulse = pg.locator("#overlay-body .roll-num.roll-pulse").count()
                snaps.append({"t_ms": int((time.time() - t0) * 1000), "nums": nums(txt),
                              "rollNums": el_count, "rollPulse": pulse})
                pg.wait_for_timeout(120)
            result["snapshots"] = snaps
            all_same = all(s["nums"] == snaps[0]["nums"] for s in snaps)
            result["all_snapshots_equal"] = all_same
            result["final_nums"] = snaps[-1]["nums"]
            pg.screenshot(path=os.path.join(OUT, "10_rollspan_t0.png"))
            # 动画类核查: .roll-num 不应再带逐帧滚动（css 里只有 rollPulse 一次性脉冲）
            result["anim_css"] = pg.evaluate(
                "() => { const el = document.querySelector('#overlay-body .roll-num');"
                " if (!el) return null; const cs = getComputedStyle(el);"
                " return { animationName: cs.animationName, animationIterationCount: cs.animationIterationCount,"
                " animationDuration: cs.animationDuration }; }")

        # 数据弹窗布局核查（与对局无关，独立读计算样式）
        pg.locator("#btn-home").click(timeout=4000); pg.wait_for_timeout(1500)
        pg.locator("#mc-data").click(timeout=4000); pg.wait_for_timeout(800)
        result["data_modal"] = pg.evaluate("""() => {
          const card = document.querySelector('#data-modal #start-card');
          const body = document.getElementById('data-body');
          const row = body ? body.querySelector(':scope > .mp-row:last-child') : null;
          const cs = card ? getComputedStyle(card) : null;
          const bcs = body ? getComputedStyle(body) : null;
          return {
            cardMaxWidth: cs ? cs.maxWidth : null, cardWidth: card ? card.getBoundingClientRect().width : null,
            bodyOverflowY: bcs ? bcs.overflowY : null,
            lastRowSticky: row ? getComputedStyle(row).position : null,
            topbarFilterBefore: getComputedStyle(document.getElementById('topbar')).filter,
            bodyHasDataOpen: document.body.classList.contains('data-open')
          };
        }""")
        # 打开状态下的顶栏降权
        result["data_modal"]["topbarFilterOpen"] = pg.evaluate(
            "() => getComputedStyle(document.getElementById('topbar')).filter + ' / pe=' +"
            " getComputedStyle(document.getElementById('topbar')).pointerEvents")
    except Exception:
        result["error"] = traceback.format_exc()[-400:]
    b.close()

print("ROLLSPAN_JSON=" + json.dumps(result, ensure_ascii=False))
