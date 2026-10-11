# host_r4_noauto.py — 无头房主（不勾自动续局）：用于隔离验证客人「下一局」请求链路
# 与 host_room.py 唯一区别：显式取消 #auto-next，房主绝不自动开下一手。
# 用法: python host_r4_noauto.py <输出code文件> [保活秒数=600]
import sys, time, os
from playwright.sync_api import sync_playwright

OUT_FILE = sys.argv[1]
ALIVE = int(sys.argv[2]) if len(sys.argv) > 2 else 600
URL = "http://localhost:8787/"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_context(viewport={"width": 1280, "height": 800}).new_page()
    pg.goto(URL); pg.wait_for_timeout(1500)
    pg.locator("#mc-multi").click(); pg.wait_for_timeout(500)
    try:
        pg.locator("#mp-name").fill("R4无自动房主")
    except Exception:
        pass
    pg.locator("#mp-btn-create").click(); pg.wait_for_timeout(800)
    try:
        pg.locator("#auto-next").uncheck(timeout=2000)   # 关键：关闭自动续局
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
    t0 = time.time()
    while time.time() - t0 < ALIVE:
        pg.wait_for_timeout(5000)
    b.close()
