# host_r5.py — R5 隔离房房主：不勾「自动下一局」，摊牌弹层滞留 14s 后手动代开下一手。
# 14s 的留白给客人侧足够窗口验证「已请求 → 5s 无响应自动恢复可点 → 再点仍能重发请求」。
# 用法: python host_r5.py <输出code文件> [保活秒数=480] [手动推进阈值秒=14]
import sys, time, os
from playwright.sync_api import sync_playwright

OUT_FILE = sys.argv[1]
ALIVE = int(sys.argv[2]) if len(sys.argv) > 2 else 480
THRESH = float(sys.argv[3]) if len(sys.argv) > 3 else 14.0
URL = "http://localhost:8787/"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_context(viewport={"width": 1280, "height": 800}).new_page()
    pg.goto(URL); pg.wait_for_timeout(1500)
    pg.locator("#mc-multi").click(); pg.wait_for_timeout(500)
    try:
        pg.locator("#mp-name").fill("R5无自动房主")
    except Exception:
        pass
    pg.locator("#mp-btn-create").click(); pg.wait_for_timeout(800)
    try:
        pg.locator("#auto-next").uncheck(timeout=2000)
        print("AUTO_NEXT=off", flush=True)
    except Exception as e:
        print("AUTO_NEXT_WARN=" + str(e), flush=True)
    code = ""
    for _ in range(30):
        code = (pg.locator("#mp-room-code").text_content() or "").strip()
        if code and "-" not in code:
            break
        pg.wait_for_timeout(500)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(code)
    print("ROOM=" + code, flush=True)

    last_open = None
    advanced = 0
    t0 = time.time()
    while time.time() - t0 < ALIVE:
        try:
            ov = pg.locator("#overlay")
            if ov.count() and not ov.evaluate("el => el.classList.contains('hidden')"):
                if last_open is None:
                    last_open = time.time()
                elif time.time() - last_open >= THRESH:
                    bn = pg.locator("#btn-next")
                    if bn.count() and bn.is_enabled():
                        bn.click(timeout=2000)
                        advanced += 1
                        print("[%s] 手动推进 #%d（弹层滞留 >=%.0fs）" % (time.strftime("%H:%M:%S"), advanced, THRESH), flush=True)
                        last_open = None
            else:
                last_open = None
        except Exception as e:
            print("WARN " + str(e), flush=True)
        pg.wait_for_timeout(500)
    print("ADVANCED=" + str(advanced), flush=True)
    b.close()
