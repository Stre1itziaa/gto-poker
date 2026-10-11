# insp_r5a.py — R5 修复③ 终验 v2：房主真掉线（关房主页）后客人「下一局」5s 自动恢复
# 背景：v2 前版房主在线时 requestNext 被秒响应（R4 链路），轮不到 5s 定时器。
# 场景：隔离房 → 客人打到摊牌 → 直接关闭房主 context（PeerJS 房主即房间本体，掉线不转世）
#       → 客人点「下一局」→ 应显「已请求」→ 约 5s 无响应自动恢复可点，弹层保持不动
# 用法: python insp_r5a.py <输出目录=data5/wupa>
# 输出: <OUT>/r5a_result.json + r5a_*.png
import sys, time, json, os, random, traceback

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data5", "wupa")
URL = "http://localhost:8787/"

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

def btn_state(page):
    return page.evaluate("""() => { const b = document.getElementById('btn-next');
      return b ? { text: b.textContent.trim(), disabled: b.disabled } : null; }""")

def main():
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        hostctx = browser.new_context(viewport={"width": 1280, "height": 800})
        host = hostctx.new_page()
        guest = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
        errs = []
        guest.on("pageerror", lambda e: errs.append(str(e)))

        # 房主：建房 + 关自动续局（之后在线但只挂机打牌，不主动点任何按钮）
        host.goto(URL); host.wait_for_timeout(1500)
        host.locator("#mc-multi").click(); host.wait_for_timeout(500)
        host.locator("#mp-name").fill("R5A掉线房主")
        host.locator("#mp-btn-create").click(); host.wait_for_timeout(800)
        try:
            host.locator("#auto-next").uncheck(timeout=2000)
            log("A2: 房主自动续局已关")
        except Exception as e:
            log("A2: 关自动续局异常: %s" % e)
        code = ""
        for _ in range(30):
            code = (host.locator("#mp-room-code").text_content() or "").strip()
            if code and "-" not in code:
                break
            host.wait_for_timeout(500)
        res["room"] = code
        log("A2: 隔离房房码 %s" % code)

        # 客人：加入 + 准备
        guest.goto(URL); guest.wait_for_timeout(1200)
        guest.locator("#mc-multi").click(); guest.wait_for_timeout(500)
        guest.locator("#mp-name").fill("呜帕·验掉线")
        guest.locator("#mp-tab-join").click()
        guest.locator("#mp-code").fill(code)
        guest.locator("#mp-btn-join").click()
        joined = False
        for _ in range(15):
            if visible(guest, "#mp-lobby") and not guest.locator("#mp-lobby").is_hidden():
                joined = True; break
            guest.wait_for_timeout(1000)
        if not joined:
            res.update({"ok": False, "reason": "guest join failed"})
            json.dump(res, open(os.path.join(OUT, "r5a_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            browser.close(); return
        guest.locator("#mp-btn-ready").click()
        log("A2: 客人已准备，等开局…")
        started = False
        for _ in range(90):
            if guest.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                started = True; break
            guest.wait_for_timeout(1000)
        if not started:
            res.update({"ok": False, "reason": "room never started"})
            json.dump(res, open(os.path.join(OUT, "r5a_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            browser.close(); return
        guest.wait_for_timeout(1800)
        log("A2: 已进牌桌，等第 1 手摊牌…")

        # 打到摊牌（与主脚本同款简单策略）
        turns = 0
        deadline = time.time() + 300
        while time.time() < deadline:
            if visible(guest, "#overlay:not(.hidden)"):
                break
            if visible(guest, "#action-controls"):
                turns += 1
                call_btn = guest.locator("#btn-checkcall").text_content() or ""
                if random.random() < 0.15 and visible(guest, "#btn-raise"):
                    try:
                        presets = guest.locator("#presets button")
                        n = presets.count()
                        if n > 0:
                            presets.nth(min(1, n - 1)).click()
                            guest.wait_for_timeout(200)
                            guest.locator("#btn-raise").click()
                            log("A2: 行动#%d: 加注" % turns)
                            guest.wait_for_timeout(900)
                            continue
                    except Exception:
                        pass
                if "过牌" in call_btn:
                    guest.locator("#btn-checkcall").click()
                else:
                    amt = "".join(ch for ch in call_btn if ch.isdigit())
                    if amt and int(amt) <= 120:
                        guest.locator("#btn-checkcall").click()
                    elif random.random() < 0.35:
                        guest.locator("#btn-checkcall").click()
                    else:
                        try:
                            guest.locator("#btn-fold").click(timeout=2000)
                        except Exception:
                            guest.locator("#btn-checkcall").click()
                guest.wait_for_timeout(900)
            guest.wait_for_timeout(1100)
        if not visible(guest, "#overlay:not(.hidden)"):
            res.update({"ok": False, "reason": "no showdown overlay"})
            json.dump(res, open(os.path.join(OUT, "r5a_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            browser.close(); return
        log("A2: 摊牌弹层出现，静置 2.6s 验证房主不自动续…")
        guest.wait_for_timeout(2600)
        stays = visible(guest, "#overlay:not(.hidden)")
        res["overlayStaysBeforeDrop"] = bool(stays)
        log("A2: 弹层仍在: %s" % stays)

        # ★ 房主真掉线：直接关闭房主 context（PeerJS 房主即房间本体）
        hostctx.close()
        log("A2: 房主页已关闭（模拟掉线）")
        guest.wait_for_timeout(2000)   # 等 WS 拆链
        res["overlayAfterHostDrop"] = bool(visible(guest, "#overlay:not(.hidden)"))
        log("A2: 掉线后客人弹层保持: %s" % res["overlayAfterHostDrop"])
        shot(guest, "r5a_0_after_drop")

        # 点「下一局」→ 已请求
        guest.locator("#btn-next").click(timeout=4000)
        guest.wait_for_timeout(150)
        st1 = btn_state(guest)
        res["afterClick"] = st1
        log("A2: 点击后按钮 %s" % json.dumps(st1, ensure_ascii=False))
        shot(guest, "r5a_1_requested")

        # 5s 无响应自动恢复：200ms 轮询，最长 8s
        t0 = time.time()
        recovered = None
        while time.time() - t0 < 8.0:
            s = btn_state(guest)
            if s and not s["disabled"] and ("下一局" in s["text"]):
                recovered = time.time() - t0
                break
            guest.wait_for_timeout(200)
        res["recoveredAfterS"] = round(recovered, 2) if recovered is not None else None
        res["afterRecover"] = btn_state(guest)
        res["overlayStillAfterRecover"] = bool(visible(guest, "#overlay:not(.hidden)"))
        log("A2: 恢复耗时 %s s，按钮 %s，弹层仍在: %s" % (
            res["recoveredAfterS"], json.dumps(res["afterRecover"], ensure_ascii=False),
            res["overlayStillAfterRecover"]))
        shot(guest, "r5a_2_recovered")

        # 恢复后可再次点击（幂等重发）
        reclick_ok = False
        st3 = None
        try:
            guest.locator("#btn-next").click(timeout=4000)
            guest.wait_for_timeout(150)
            st3 = btn_state(guest)
            res["reRequest"] = st3
            reclick_ok = bool(st3 and st3["disabled"] and ("已请求" in st3["text"]))
            log("A2: 再次点击后按钮 %s" % json.dumps(st3, ensure_ascii=False))
            shot(guest, "r5a_3_rerequested")
        except Exception as e:
            res["reRequestError"] = str(e)[:200]
            log("A2: 再次点击异常 %s" % e)

        res["ok"] = bool(stays and res["overlayAfterHostDrop"]
                         and st1 and st1["disabled"] and ("已请求" in st1["text"])
                         and recovered is not None and 4.5 <= recovered <= 6.5
                         and res["overlayStillAfterRecover"]
                         and reclick_ok)
        res["js_errors"] = errs[:5]
        res["log"] = log_lines
        json.dump(res, open(os.path.join(OUT, "r5a_result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("R5A_DONE ok=%s recover=%s" % (res["ok"], res["recoveredAfterS"]))
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            json.dump({"ok": False, "fatal": traceback.format_exc(), "log": log_lines},
                      open(os.path.join(OUT, "r5a_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass
