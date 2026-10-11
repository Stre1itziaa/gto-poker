# probe5_r4_fulu.py — R4 双端复检探针 v5（单线程版：host overlay 轮询并入主循环）
import sys, time, json, os, traceback, re

OUT = "data4/fulu"
URL = "http://localhost:8787/"
os.makedirs(OUT, exist_ok=True)
log_lines = []
def log(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    log_lines.append(line)
    print(line, flush=True)

def shot(page, tag):
    try:
        page.screenshot(path=os.path.join(OUT, f"{tag}.png"))
        log(f"截图 {tag}")
    except Exception as e:
        log(f"截图失败 {tag}: {e}")

def ov_open(page):
    try:
        return not page.locator("#overlay").evaluate("el => el.classList.contains('hidden')")
    except Exception:
        return False

def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        errors = []

        # ---------- 房主端：建房、确认自动续局关闭，之后全程 AFK ----------
        hctx = browser.new_context(viewport={"width": 1280, "height": 800})
        host = hctx.new_page()
        host.on("pageerror", lambda e: errors.append("HOST:" + str(e)))
        host.goto(URL); host.wait_for_timeout(1500)
        host.locator("#mc-multi").click(); host.wait_for_timeout(500)
        try: host.locator("#mp-name").fill("R4复检房主")
        except Exception: pass
        host.locator("#mp-btn-create").click(); host.wait_for_timeout(800)
        try:
            host.locator("#auto-next").uncheck(timeout=2000)
            log("房主：auto-next 已确认关闭")
        except Exception:
            log("房主：auto-next 操作失败（可能本来就关）")
        try:
            host.locator("#auto-next-2").uncheck(timeout=1500)
        except Exception:
            pass
        code = ""
        for _ in range(30):
            code = (host.locator("#mp-room-code").text_content() or "").strip()
            if code and "-" not in code:
                break
            host.wait_for_timeout(500)
        log(f"房主：房间 {code} 建立（auto-next=off，AFK）")
        host_states = []
        def host_poll(tag=""):
            try:
                st = "open" if not host.locator("#overlay").evaluate("el => el.classList.contains('hidden')") else "closed"
                if not host_states or host_states[-1]["s"] != st:
                    host_states.append({"t": time.strftime("%H:%M:%S"), "s": st})
                    log(f"房主端 overlay → {st} {tag}")
                    shot(host, f"40_host_{st}_{len(host_states)}")
                return st
            except Exception:
                return "err"
        host_poll()

        # ---------- 客人端 ----------
        gctx = browser.new_context(viewport={"width": 1600, "height": 900})
        g = gctx.new_page()
        g.on("pageerror", lambda e: errors.append("GUEST:" + str(e)))
        g.goto(URL); g.wait_for_timeout(1200)
        g.locator("#mc-multi").click(); g.wait_for_timeout(400)
        g.locator("#mp-name").fill("副露战神")
        try: g.locator("#mp-chars .mp-ch:nth-child(3)").click()
        except Exception: pass
        g.locator("#mp-tab-join").click()
        g.locator("#mp-code").fill(code)
        g.locator("#mp-btn-join").click()
        joined = False
        for _ in range(20):
            if g.locator("#mp-lobby").is_visible():
                joined = True; break
            g.wait_for_timeout(500)
        if not joined:
            log("客人加入失败: " + (g.locator("#mp-status").text_content() or ""))
            json.dump({"ok": False, "reason": "self-room join failed", "log": log_lines},
                      open(os.path.join(OUT, "probe5_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
            return
        log("客人：已进大厅")
        g.locator("#mp-btn-ready").click()
        log("客人：已准备")
        started = False
        for _ in range(60):
            try:
                txt = host.locator("#mp-players").text_content() or ""
                if host.locator("#mp-lobby").is_visible() and "未准备" not in txt:
                    host.locator("#mp-btn-start").click()
                    started = True
                    log("房主：点开始")
                    break
            except Exception:
                pass
            g.wait_for_timeout(500)
        if not started:
            log("房主：未点到开始（可能已自动开局）")
        for _ in range(60):
            if g.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                break
            g.wait_for_timeout(1000)
        g.wait_for_timeout(800)
        log("客人：已进牌桌")

        captured, reset_seen, btn_states = [], [], []
        acted = 0
        last_host_poll = 0
        deadline = time.time() + 60 * 8
        while time.time() < deadline and len(captured) < 2:
            if time.time() - last_host_poll > 0.5:
                host_poll()
                last_host_poll = time.time()
            hand_no = 0
            try:
                m = re.search(r"第\s*(\d+)\s*手", g.locator("#hand-info").text_content() or "")
                if m: hand_no = int(m.group(1))
            except Exception:
                pass
            if ov_open(g) and hand_no not in captured:
                bn = g.locator("#btn-next")
                pre = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                shot(g, f"20_btn_pre_h{hand_no}_{len(captured)+1}")
                bn.click()
                log(f"客人：手{hand_no} 点击「下一局」")
                g.wait_for_timeout(120)
                post = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                btn_states.append({"hand": hand_no, "pre": pre, "post": post})
                shot(g, f"21_btn_post_h{hand_no}_{len(captured)+1}")
                log(f"客人：手{hand_no} 点击前 {json.dumps(pre, ensure_ascii=False)} / 点击后 {json.dumps(post, ensure_ascii=False)}")
                captured.append(hand_no)
                t0 = time.time()
                while time.time() - t0 < 30 and ov_open(g):
                    host_poll()
                    g.wait_for_timeout(150)
                dt = time.time() - t0
                log(f"客人：手{hand_no} 点下一局后 {dt:.1f}s 弹层关闭")
                btn_states[-1]["advance_seconds"] = round(dt, 1)
                g.wait_for_timeout(300)
                continue
            if ov_open(g) and hand_no in captured and hand_no not in reset_seen:
                bn = g.locator("#btn-next")
                cur = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                if not cur["disabled"] and "下一局" in cur["text"]:
                    reset_seen.append(hand_no)
                    shot(g, f"22_btn_reset_h{hand_no}")
                    log(f"客人：手{hand_no} 按钮重置态 {json.dumps(cur, ensure_ascii=False)}")
            if g.locator("#action-controls").is_visible() and acted < 20:
                acted += 1
                call_btn = g.locator("#btn-checkcall").text_content() or ""
                amt = "".join(ch for ch in call_btn if ch.isdigit())
                if "过牌" in call_btn or (amt and int(amt) <= 120):
                    g.locator("#btn-checkcall").click()
                    log(f"客人行动#{acted}: {'过牌' if '过牌' in call_btn else '跟注 ' + amt}")
                else:
                    try:
                        g.locator("#btn-fold").click(timeout=1500)
                        log(f"客人行动#{acted}: 弃牌(要跟{amt})")
                    except Exception:
                        g.locator("#btn-checkcall").click()
                g.wait_for_timeout(300)
            g.wait_for_timeout(300)

        scope = {"tested": False}
        try:
            g.locator("#btn-home").click(timeout=4000)
            g.wait_for_timeout(2200)
            g.locator("#mc-data").click(timeout=4000)
            g.wait_for_timeout(1500)
            scope["tested"] = True
            scope["records"] = g.evaluate("() => (window.DataPage ? window.DataPage.all().length : -1)")
            for label, tag in [("全部", "30_scope_all"), ("多人", "31_scope_mp"), ("单机", "32_scope_sp")]:
                loc = g.locator("#data-body button.data-mode-chip", has_text=label)
                if loc.count() > 0:
                    loc.first.click()
                else:
                    g.get_by_role("button", name=label).first.click()
                g.wait_for_timeout(500)
                info = g.evaluate("""() => {
                  const act = Array.from(document.querySelectorAll('button.data-mode-chip'))
                    .map(b => ({t: b.textContent.trim(), on: b.classList.contains('sel')}));
                  const rows = document.querySelectorAll('#data-body .data-hand').length;
                  const statsCard = Array.from(document.querySelectorAll('.data-stat')).map(d => d.textContent.trim());
                  const heads = Array.from(document.querySelectorAll('#data-body .data-hand summary'))
                    .slice(0, 8).map(s => (s.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 70));
                  return {act: act, rows: rows, statsCard: statsCard, heads: heads};
                }""")
                log(f"范围={label}: {json.dumps(info, ensure_ascii=False)}")
                shot(g, tag)
                scope[label] = info
            try:
                g.locator("#data-body .data-hand summary").first.click()
                g.wait_for_timeout(400)
                flow = g.evaluate("""() => {
                  const acts = document.querySelectorAll('#data-body .data-hand .data-acts');
                  return Array.from(acts).map(a => (a.textContent || '').trim().replace(/\\s+/g, ' '));
                }""")
                log(f"牌谱行动流: {json.dumps(flow, ensure_ascii=False)[:600]}")
                scope["flow"] = flow
                g.locator("#data-body .data-hand").first.screenshot(path=os.path.join(OUT, "33_handbook_flow.png"))
                log("截图 33_handbook_flow")
            except Exception as e:
                log(f"牌谱展开失败: {e}")
        except Exception:
            scope["error"] = traceback.format_exc()[-400:]
            log("数据页测试异常: " + scope["error"])

        host_poll()
        state = {"ok": True, "captured": captured, "reset_seen": reset_seen,
                 "btn_states": btn_states, "scope": scope, "host_states": host_states,
                 "js_errors": errors[:10], "log": log_lines}
        json.dump(state, open(os.path.join(OUT, "probe5_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("PROBE5_JSON=" + json.dumps(state, ensure_ascii=False))
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        json.dump({"ok": False, "error": traceback.format_exc(), "log": log_lines},
                  open(os.path.join(OUT, "probe5_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print("PROBE5_JSON=" + json.dumps({"ok": False, "error": traceback.format_exc()}, ensure_ascii=False))
