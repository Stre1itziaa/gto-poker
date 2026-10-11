# host_room.py — 无头房主：建房并保活（行动超时由游戏内 45s 托管兜底）
# 用法: python host_room.py <输出code文件> [保活秒数=1500]
import sys, time, os
from playwright.sync_api import sync_playwright

OUT_FILE = sys.argv[1]
ALIVE = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
URL = "http://localhost:8787/"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_context(viewport={"width": 1280, "height": 800}).new_page()
    pg.goto(URL); pg.wait_for_timeout(1500)
    pg.locator("#mc-multi").click(); pg.wait_for_timeout(500)
    try:
        pg.locator("#mp-name").fill("数据迭代房主")
    except Exception:
        pass
    pg.locator("#mp-btn-create").click()
    try:
        pg.locator("#auto-next").check(timeout=2000)   # R6-R3：勾掉摊牌死锁（自动续局）
    except Exception:
        pass
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
        # 保活：页面别被回收
    b.close()
