# insp_r4_next.py — R4 修复① 实测：客人点「下一局」= 向房主发请求（房主无自动续局）
# 判定：房主关掉自动续局后，摊牌弹层会一直停着——客人点「下一局」后若下一手能开，
#       只能是 requestNext→房主代点 这条链路起效。同时抓按钮「已请求」态截图。
# 用法: python insp_r4_next.py <房码> <输出目录>
import sys, time, json, os, random

CODE = sys.argv[1]
OUT = sys.argv[2]
URL = "http://localhost:8787/"
NAME = "里宝牌之光·验一"

os.makedirs(OUT, exist_ok=True)
log_lines = []
def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    log_lines.append(line)
    print(line, flush=True)

def shot(page, tag):
    try:
        page.screenshot(path=os.path.join(OUT, tag + ".png"))
        log("截图 " + tag)
    except Exception as e:
        log("截图失败 %s: %s" % (tag, e))

def visible(page, sel):
    try:
        return page.locator(sel).is_visible()
    except Exception:
        return False

def main():
    from playwright.sync_api import sync_playwright
    result = {"ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))

        page.goto(URL); page.wait_for_timeout(1200)
        page.locator("#mc-multi").click(); page.wait_for_timeout(500)
        page.locator("#mp-name").fill(NAME)

        joined = False
        for attempt in range(1, 4):
            page.locator("#mp-tab-join").click()
            page.locator("#mp-code").fill(CODE)
            page.locator("#mp-btn-join").click()
            log("第 %d 次点击加入 %s" % (attempt, CODE))
            for i in range(10):
                if visible(page, "#mp-lobby") and not page.locator("#mp-lobby").is_hidden():
                    joined = True; break
                page.wait_for_timeout(1000)
            if joined: break
            page.wait_for_timeout(20000)   # 加入失败等 20 秒重试
        if not joined:
            result.update({"ok": False, "reason": "join failed", "log": log_lines})
            json.dump(result, open(os.path.join(OUT, "next_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
            return

        page.locator("#mp-btn-ready").click()
        log("已准备，等房主开局…")
        for i in range(120):
            if page.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                break
            page.wait_for_timeout(1000)
        page.wait_for_timeout(1500)
        log("已进牌桌，等第一手结束（摊牌弹层）…")

        # 等摊牌弹层（房主无自动续局，弹层会一直停着）
        t0 = time.time()
        while time.time() - t0 < 300:
            if visible(page, "#overlay:not(.hidden)"):
                break
            page.wait_for_timeout(500)
        if not visible(page, "#overlay:not(.hidden)"):
            log("超时未见摊牌弹层")
            shot(page, "20_no_overlay")
            result.update({"ok": False, "reason": "no overlay", "log": log_lines})
            json.dump(result, open(os.path.join(OUT, "next_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
            return

        page.wait_for_timeout(2500)   # 多停 2.5s：证明房主不会自动续
        still = visible(page, "#overlay:not(.hidden)")
        log("静置 2.5s 后弹层仍在（房主自动续局确已关闭）: %s" % still)
        shot(page, "20_overlay_waiting")

        # ★ 核心动作：点「下一局」→ 立即抓按钮态
        btn_before = page.locator("#btn-next").text_content()
        page.locator("#btn-next").click()
        page.wait_for_timeout(120)
        btn_state = page.evaluate("""() => {
          const b = document.getElementById('btn-next');
          return { text: b.textContent.trim(), disabled: b.disabled };
        }""")
        log("点击前按钮: %r" % btn_before)
        log("点击后按钮: %s" % json.dumps(btn_state, ensure_ascii=False))
        shot(page, "21_btn_requested")

        # 等下一手真正开出来（弹层收起 + 再见到行动面板或新的手）
        t0 = time.time()
        advanced = False
        while time.time() - t0 < 60:
            if not visible(page, "#overlay:not(.hidden)"):
                advanced = True
                break
            page.wait_for_timeout(500)
        page.wait_for_timeout(2500)
        shot(page, "22_after_next")
        # 弹层收起后按钮应被重置回「下一局」
        btn_after = page.evaluate("""() => {
          const b = document.getElementById('btn-next');
          return { text: b.textContent.trim(), disabled: b.disabled };
        }""")
        log("下一手开出来: %s，按钮复位态: %s" % (advanced, json.dumps(btn_after, ensure_ascii=False)))

        ok = btn_state["disabled"] and ("已请求" in btn_state["text"]) and advanced \
             and btn_after["disabled"] is False and ("下一局" in btn_after["text"])
        result.update({"ok": bool(ok), "btnRequested": btn_state, "advanced": advanced,
                       "btnReset": btn_after, "hostNoAutoOverlayStays": still,
                       "js_errors": errs[:5], "log": log_lines})
        json.dump(result, open(os.path.join(OUT, "next_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        browser.close()

if __name__ == "__main__":
    main()
