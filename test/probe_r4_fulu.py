# probe_r4_fulu.py — R4 复检探针（只测 UI，不改游戏代码）
# 目标：①客人点「下一局」按钮反馈态（已请求，等待房主开下一手…）+ 新一手后重置
#       ②数据页「范围：全部/多人/单机」chips 真实筛选交互
#       ③牌谱展开后的行动流「下注 N/加注到 N」口径截图
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

def visible(page, sel):
    return page.locator(sel).is_visible()

def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # 加入（失败等 20s 重试，最多 3 次）
        joined = False
        for attempt in range(1, 4):
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
            page.locator("#mp-btn-join").click()
            log(f"第 {attempt} 次尝试加入 {CODE}")
            for i in range(15):
                if visible(page, "#mp-lobby") and not page.locator("#mp-lobby").is_hidden():
                    joined = True
                    break
                page.wait_for_timeout(1000)
            if joined:
                break
            status = ""
            try: status = page.locator("#mp-status").text_content() or ""
            except Exception: pass
            log(f"加入未成功 status={status}，等 20s 重试")
            page.wait_for_timeout(20000)
        if not joined:
            json.dump({"ok": False, "reason": "join failed after retries", "log": log_lines},
                      open(os.path.join(OUT, "probe_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
            return
        page.wait_for_timeout(600)
        page.locator("#mp-btn-ready").click()
        log("已点准备，等开局")

        for i in range(480):
            if page.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                break
            page.wait_for_timeout(1000)
        page.wait_for_timeout(1200)
        log("已进牌桌")

        captured = []       # 已完成「点击反馈」采集的手序号
        reset_seen = []     # 已采集「按钮重置态」的手序号
        btn_post_state = None
        deadline = time.time() + 60 * 9
        while time.time() < deadline and len(captured) < 2:
            # 手序号：顶栏「第 N 手」
            hand_no = 0
            try:
                import re as _re
                m = _re.search(r"第\s*(\d+)\s*手", page.locator("#hand-info").text_content() or "") if visible(page, "#hand-info") else None
                if m: hand_no = int(m.group(1))
            except Exception:
                pass
            ov_open = visible(page, "#overlay") and not page.locator("#overlay").evaluate("el => el.classList.contains('hidden')")
            if ov_open and hand_no not in captured:
                bn = page.locator("#btn-next")
                pre = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                shot(page, f"20_btn_pre_h{hand_no}_{len(captured)+1}")
                bn.click()
                page.wait_for_timeout(150)
                post = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                btn_post_state = post
                shot(page, f"21_btn_post_h{hand_no}_{len(captured)+1}")
                log(f"手{hand_no} 按钮点击前: {json.dumps(pre, ensure_ascii=False)}")
                log(f"手{hand_no} 按钮点击后: {json.dumps(post, ensure_ascii=False)}")
                captured.append(hand_no)
                # 等新手开（快照到达 → 弹层隐藏）
                t0 = time.time()
                while time.time() - t0 < 12:
                    if not page.locator("#overlay").evaluate("el => el.classList.contains('hidden')") and \
                       not (visible(page, "#overlay") and not page.locator("#overlay").evaluate("el => el.classList.contains('hidden')")):
                        pass
                    try:
                        if page.locator("#overlay").evaluate("el => el.classList.contains('hidden')"):
                            log(f"手{hand_no} 点下一局后 {(time.time()-t0):.1f}s 弹层关闭（新手快照到达）")
                            break
                    except Exception:
                        pass
                    page.wait_for_timeout(200)
                page.wait_for_timeout(500)
                continue
            if ov_open and hand_no in captured and hand_no not in reset_seen and btn_post_state:
                bn = page.locator("#btn-next")
                cur = {"text": (bn.text_content() or "").strip(), "disabled": bn.is_disabled()}
                if not cur["disabled"] and "下一局" in cur["text"]:
                    reset_seen.append(hand_no)
                    shot(page, f"22_btn_reset_h{hand_no}")
                    log(f"手{hand_no} 按钮重置态: {json.dumps(cur, ensure_ascii=False)}")
            if visible(page, "#action-controls"):
                call_btn = page.locator("#btn-checkcall").text_content() or ""
                amt = "".join(ch for ch in call_btn if ch.isdigit())
                if "过牌" in call_btn:
                    page.locator("#btn-checkcall").click()
                elif amt and int(amt) <= 120:
                    page.locator("#btn-checkcall").click()
                else:
                    try:
                        page.locator("#btn-fold").click(timeout=1500)
                    except Exception:
                        page.locator("#btn-checkcall").click()
                page.wait_for_timeout(400)
            page.wait_for_timeout(400)

        # ===== 数据页范围筛选交互测试 =====
        scope = {"tested": False}
        try:
            page.locator("#btn-home").click(timeout=4000)
            page.wait_for_timeout(2200)
            page.locator("#mc-data").click(timeout=4000)
            page.wait_for_timeout(1500)
            scope["tested"] = True
            for label, tag in [("全部", "30_scope_all"), ("多人", "31_scope_mp"), ("单机", "32_scope_sp")]:
                chip = page.locator(f"#data-body button.chip", has_text=label).first
                if chip.count() == 0:
                    chip = page.get_by_role("button", name=label).first
                chip.click()
                page.wait_for_timeout(500)
                info = page.evaluate("""() => {
                  const act = Array.from(document.querySelectorAll('#data-body button'))
                    .filter(b => /全部|多人|单机/.test(b.textContent))
                    .map(b => ({t: b.textContent.trim(), on: b.className}));
                  const rows = document.querySelectorAll('#data-body .data-hand').length;
                  const empty = (document.getElementById('data-body').textContent || '').includes('还没有');
                  const heads = Array.from(document.querySelectorAll('#data-body .data-hand summary'))
                    .slice(0, 6).map(s => (s.textContent || '').trim().slice(0, 60));
                  return {act: act, rows: rows, empty: empty, heads: heads};
                }""")
                log(f"范围={label}: {json.dumps(info, ensure_ascii=False)}")
                shot(page, tag)
                scope[label] = info
            # 展开第一手牌谱看行动流口径
            try:
                page.locator("#data-body .data-hand summary").first.click()
                page.wait_for_timeout(500)
                flow = page.evaluate("""() => {
                  const d = document.querySelector('#data-body .data-hand');
                  return d ? (d.textContent || '').slice(0, 500) : '';
                }""")
                log(f"牌谱展开片段: {flow[:200]}")
                page.locator("#data-body .data-hand").first.screenshot(path=os.path.join(OUT, "33_handbook_flow.png"))
                log("截图 33_handbook_flow")
            except Exception as e:
                log(f"牌谱展开失败: {e}")
        except Exception:
            scope["error"] = traceback.format_exc()[-400:]
            log("数据页测试异常: " + scope["error"])

        state = {"ok": True, "captured": captured, "reset_seen": reset_seen,
                 "btn_post_state": btn_post_state, "scope": scope,
                 "js_errors": errors[:10], "log": log_lines}
        json.dump(state, open(os.path.join(OUT, "probe_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("PROBE_JSON=" + json.dumps(state, ensure_ascii=False))
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        json.dump({"ok": False, "error": traceback.format_exc(), "log": log_lines},
                  open(os.path.join(OUT, "probe_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print("PROBE_JSON=" + json.dumps({"ok": False, "error": traceback.format_exc()}, ensure_ascii=False))
