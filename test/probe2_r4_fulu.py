# probe2_r4_fulu.py — R4 复检探针 v2：高频插窗加入（每 1.5s 重试，不刷页）
import sys, time, json, os, traceback

CODE = "VGFQYT"
NAME = "副露战神"
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
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(URL)
        page.wait_for_timeout(1200)
        page.locator("#mc-multi").click(timeout=5000)
        page.wait_for_timeout(400)
        page.locator("#mp-name").fill(NAME)
        try:
            page.locator("#mp-chars .mp-ch:nth-child(3)").click()
        except Exception:
            pass
        page.locator("#mp-tab-join").click()
        page.locator("#mp-code").fill(CODE)

        joined = False
        for attempt in range(1, 121):
            try:
                page.locator("#mp-btn-join").click()
            except Exception:
                pass
            page.wait_for_timeout(1500)
            try:
                if page.locator("#mp-lobby").is_visible() and not page.locator("#mp-lobby").is_hidden():
                    joined = True
                    break
            except Exception:
                pass
            if attempt % 10 == 0:
                status = ""
                try: status = page.locator("#mp-status").text_content() or ""
                except Exception: pass
                log(f"插窗重试 {attempt} 次… status={status.strip()[:40]}")
        if not joined:
            json.dump({"ok": False, "reason": "join failed after 120 rapid retries", "log": log_lines},
                      open(os.path.join(OUT, "probe2_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
            return
        log("插窗成功，进大厅")
        page.wait_for_timeout(200)
        try:
            page.locator("#mp-btn-ready").click(timeout=1500)
            log("已点准备")
        except Exception:
            log("准备按钮点击失败（可能已在局中）")
        for i in range(300):
            if page.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                break
            page.wait_for_timeout(1000)
        page.wait_for_timeout(1000)
        log("已进牌桌")

        captured, reset_seen = [], []
        btn_states = []
        deadline = time.time() + 60 * 8
        while time.time() < deadline and len(captured) < 2:
            hand_no = 0
            try:
                import re as _re
                m = _re.search(r"第\s*(\d+)\s*手", page.locator("#hand-info").text_content() or "")
                if m: hand_no = int(m.group(1))
            except Exception:
                pass
            if ov_open(page) and hand_no not in captured:
                bn = page.locator("#btn-next")
                pre = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                shot(page, f"20_btn_pre_h{hand_no}_{len(captured)+1}")
                bn.click()
                page.wait_for_timeout(120)
                post = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                btn_states.append({"hand": hand_no, "pre": pre, "post": post})
                shot(page, f"21_btn_post_h{hand_no}_{len(captured)+1}")
                log(f"手{hand_no} 点击前 {json.dumps(pre, ensure_ascii=False)} / 点击后 {json.dumps(post, ensure_ascii=False)}")
                captured.append(hand_no)
                t0 = time.time()
                while time.time() - t0 < 15 and ov_open(page):
                    page.wait_for_timeout(150)
                log(f"手{hand_no} 点下一局后 {(time.time()-t0):.1f}s 弹层关闭")
                page.wait_for_timeout(300)
                continue
            if ov_open(page) and hand_no in captured and hand_no not in reset_seen:
                bn = page.locator("#btn-next")
                cur = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                if not cur["disabled"] and "下一局" in cur["text"]:
                    reset_seen.append(hand_no)
                    shot(page, f"22_btn_reset_h{hand_no}")
                    log(f"手{hand_no} 按钮重置态: {json.dumps(cur, ensure_ascii=False)}")
            if page.locator("#action-controls").is_visible():
                call_btn = page.locator("#btn-checkcall").text_content() or ""
                amt = "".join(ch for ch in call_btn if ch.isdigit())
                if "过牌" in call_btn or (amt and int(amt) <= 120):
                    page.locator("#btn-checkcall").click()
                else:
                    try:
                        page.locator("#btn-fold").click(timeout=1500)
                    except Exception:
                        page.locator("#btn-checkcall").click()
                page.wait_for_timeout(300)
            page.wait_for_timeout(300)

        scope = {"tested": False}
        try:
            page.locator("#btn-home").click(timeout=4000)
            page.wait_for_timeout(2200)
            page.locator("#mc-data").click(timeout=4000)
            page.wait_for_timeout(1500)
            scope["tested"] = True
            for label, tag in [("全部", "30_scope_all"), ("多人", "31_scope_mp"), ("单机", "32_scope_sp")]:
                clicked = False
                for sel in ["#data-body button.data-mode-chip", "button.data-mode-chip"]:
                    loc = page.locator(sel, has_text=label)
                    if loc.count() > 0:
                        loc.first.click(); clicked = True; break
                if not clicked:
                    page.get_by_role("button", name=label).first.click()
                page.wait_for_timeout(500)
                info = page.evaluate("""() => {
                  const act = Array.from(document.querySelectorAll('button.data-mode-chip'))
                    .map(b => ({t: b.textContent.trim(), on: b.classList.contains('sel')}));
                  const rows = document.querySelectorAll('#data-body .data-hand').length;
                  const bodyTxt = (document.getElementById('data-body').textContent || '');
                  const empty = bodyTxt.includes('还没有') || rows === 0;
                  const statsCard = Array.from(document.querySelectorAll('.data-stat')).map(d => d.textContent.trim()).slice(0,4);
                  const heads = Array.from(document.querySelectorAll('#data-body .data-hand summary'))
                    .slice(0, 8).map(s => (s.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 70));
                  return {act: act, rows: rows, empty: empty, statsCard: statsCard, heads: heads};
                }""")
                log(f"范围={label}: {json.dumps(info, ensure_ascii=False)}")
                shot(page, tag)
                scope[label] = info
            try:
                page.locator("#data-body .data-hand summary").first.click()
                page.wait_for_timeout(400)
                flow = page.evaluate("""() => {
                  const d = document.querySelector('#data-body .data-hand');
                  const acts = d ? d.querySelectorAll('.data-acts') : [];
                  return Array.from(acts).map(a => (a.textContent || '').trim().replace(/\\s+/g, ' '));
                }""")
                log(f"牌谱行动流: {json.dumps(flow, ensure_ascii=False)[:400]}")
                scope["flow"] = flow
                page.locator("#data-body .data-hand").first.screenshot(path=os.path.join(OUT, "33_handbook_flow.png"))
                log("截图 33_handbook_flow")
            except Exception as e:
                log(f"牌谱展开失败: {e}")
        except Exception:
            scope["error"] = traceback.format_exc()[-400:]
            log("数据页测试异常: " + scope["error"])

        state = {"ok": True, "captured": captured, "reset_seen": reset_seen,
                 "btn_states": btn_states, "scope": scope,
                 "js_errors": errors[:10], "log": log_lines}
        json.dump(state, open(os.path.join(OUT, "probe2_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("PROBE2_JSON=" + json.dumps(state, ensure_ascii=False))
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        json.dump({"ok": False, "error": traceback.format_exc(), "log": log_lines},
                  open(os.path.join(OUT, "probe2_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print("PROBE2_JSON=" + json.dumps({"ok": False, "error": traceback.format_exc()}, ensure_ascii=False))
