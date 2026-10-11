# insp_r4b.py — R4 补充微测
# ①口径补测：合成样本 + 全部展开后再 dump（修复 r4 脚本 details 未展开导致 dump 为空的锅）
# ②「已请求，等待房主开下一手…」按钮态同步抓取：click 同一 JS tick 内读态 + 毫秒级轮询窗口
# 输出: data4/wupa/r4b_result.json + r4b_dump.txt + r4b_*.png
import sys, time, json, os, re, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data4", "wupa")
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

def mk(name, hole):
    return {"name": name, "charId": "", "isBot": False, "stackEnd": 2000,
            "committed": 0, "won": 0, "refund": 0, "rebuys": 0, "hole": hole}

# W1: 翻前两连加注 —— 口径基准：首加注应为「加注到 60」
W1 = {
    "room": "WORD-R4", "handNo": 8101, "ts": "2026-09-19T16:20:00Z", "sb": 10, "bb": 20,
    "players": [mk("呜帕R4", ["Ah", "Kd"]), mk("测试甲", ["2c", "2h"]), mk("测试乙", ["Qs", "Jd"])],
    "board": [],
    "actions": [
        {"idx": 1, "street": "preflop", "type": "raise", "to": 60, "added": 40},
        {"idx": 0, "street": "preflop", "type": "raise", "to": 180, "added": 120},
        {"idx": 2, "street": "preflop", "type": "fold", "to": 0, "added": 0},
        {"idx": 1, "street": "preflop", "type": "call", "to": 180, "added": 120},
    ],
    "pots": [{"amount": 420, "winners": [0], "label": "主池", "handName": "A高", "foldWin": True, "uncalled": False, "split": False}],
    "assert": {"sumPaid": 360, "sumPut": 420, "ok": True}, "hero": "呜帕R4", "mode": "mp",
}
# W2: 翻牌首注+再加注 —— 应为「下注 300 · 加注到 900 · 跟注 600」
W2 = {
    "room": "WORD-R4", "handNo": 8102, "ts": "2026-09-19T16:21:00Z", "sb": 10, "bb": 20,
    "players": [mk("呜帕R4", ["Ah", "Kh"]), mk("测试甲", ["2c", "2h"]), mk("测试乙", ["Qs", "Js"])],
    "board": ["As", "7c", "2h"],
    "actions": [
        {"idx": 1, "street": "preflop", "type": "raise", "to": 60, "added": 40},
        {"idx": 0, "street": "preflop", "type": "call", "to": 60, "added": 40},
        {"idx": 2, "street": "preflop", "type": "fold", "to": 0, "added": 0},
        {"idx": 1, "street": "flop", "type": "raise", "to": 300, "added": 300},
        {"idx": 0, "street": "flop", "type": "raise", "to": 900, "added": 600},
        {"idx": 1, "street": "flop", "type": "call", "to": 900, "added": 600},
    ],
    "pots": [{"amount": 1920, "winners": [0], "label": "主池", "handName": "顶对", "foldWin": True, "uncalled": False, "split": False}],
    "assert": {"sumPaid": 1920, "sumPut": 1920, "ok": True}, "hero": "呜帕R4", "mode": "mp",
}
# W3: 转牌街内首注（无翻前加注）—— 应为「下注 200」；再加 call 只有 to
W3 = {
    "room": "WORD-R4", "handNo": 8103, "ts": "2026-09-19T16:22:00Z", "sb": 10, "bb": 20,
    "players": [mk("呜帕R4", ["Ah", "Kh"]), mk("测试甲", ["2c", "2h"])],
    "board": ["As", "7c", "2h", "9d"],
    "actions": [
        {"idx": 1, "street": "preflop", "type": "raise", "to": 60, "added": 40},
        {"idx": 0, "street": "preflop", "type": "call", "to": 60, "added": 40},
        {"idx": 1, "street": "turn", "type": "raise", "to": 200, "added": 200},
        {"idx": 0, "street": "turn", "type": "call", "to": 200},
    ],
    "pots": [{"amount": 520, "winners": [0], "label": "主池", "handName": "两对", "foldWin": True, "uncalled": False, "split": False}],
    "assert": {"sumPaid": 520, "sumPut": 520, "ok": True}, "hero": "呜帕R4", "mode": "mp",
}

SEED_JS = """() => {
  (window.__R4B_SEED__ || []).forEach(function (r) { window.DataPage.record(r); });
  return (window.DataPage.all() || []).length;
}"""

def part_wording(browser):
    """①展开后 dump 的口径断言"""
    out = {}
    page = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL)
    page.wait_for_timeout(1500)
    page.evaluate("window.__R4B_SEED__ = %s" % json.dumps([W1, W2, W3], ensure_ascii=False))
    n = page.evaluate(SEED_JS)
    log("①已塞 %s 条合成记录，总计 %s 条" % (3, n))
    page.locator("#mc-data").click(timeout=5000)
    page.wait_for_timeout(1200)
    page.evaluate("document.querySelectorAll('#data-body .data-hand').forEach(function(d){d.open=true})")
    page.wait_for_timeout(400)
    shot(page, "r4b_01_expanded")
    dump = page.evaluate(
        "Array.from(document.querySelectorAll('#data-body .data-hand'))" +
        ".map(function(d){return d.innerText}).join('\\n==========\\n')")
    with open(os.path.join(OUT, "r4b_dump.txt"), "w", encoding="utf-8") as f:
        f.write(dump or "(empty)")
    out["dump_chars"] = len(dump)

    def seg(hand_no):
        m = re.search(r"第 %d 手.*?(?=============|\Z)" % hand_no, dump or "", re.S)
        return m.group(0) if m else ""

    s1, s2, s3 = seg(8101), seg(8102), seg(8103)
    pre1 = re.findall(r"翻前[^\n]*", s1)
    flop2 = re.findall(r"翻牌[^\n]*", s2)
    turn3 = re.findall(r"转牌[^\n]*", s3)
    out["w1_preflop_line"] = pre1[0][:180] if pre1 else ""
    out["w2_flop_line"] = flop2[0][:180] if flop2 else ""
    out["w3_turn_line"] = turn3[0][:180] if turn3 else ""
    out["checks"] = {
        # W1 翻前首加注被标「下注 60」= 误标（期望「加注到 60」）
        "w1_preflop_first_raise_mislabeled_as_bet": ("下注 60" in s1),
        "w1_second_raise_labeled_raise_to": ("加注到 180" in s1),
        # W2 翻牌街：下注与加注到并存（正确）
        "w2_flop_bet_ok": ("下注 300" in s2),
        "w2_flop_raise_to_ok": ("加注到 900" in s2),
        "w2_call_increment_ok": ("跟注 600" in s2),
        # W3 转牌街内首注 = 下注（正确）
        "w3_turn_bet_ok": ("下注 200" in turn3[0] if turn3 else False),
        "w3_call_fallback_to_ok": ("跟注 200" in s3),
        # 回归
        "no_double_marker": "加注到→" not in (dump or ""),
        "no_latin_actions": not re.search(r"\b(fold|check|call|raise)\b", dump or ""),
    }
    out["js_errors"] = errs[:5]
    log("①口径断言: %s" % json.dumps(out["checks"], ensure_ascii=False))
    log("①W1翻前: %s" % out["w1_preflop_line"])
    log("①W2翻牌: %s" % out["w2_flop_line"])
    log("①W3转牌: %s" % out["w3_turn_line"])
    page.close()
    return out

def act_simple(page, who):
    call_btn = page.locator("#btn-checkcall").text_content() or ""
    if "过牌" in call_btn:
        page.locator("#btn-checkcall").click()
        log("%s: 过牌" % who)
    else:
        amt = "".join(ch for ch in call_btn if ch.isdigit())
        if amt and int(amt) <= 200:
            page.locator("#btn-checkcall").click()
            log("%s: 跟注 %s" % (who, amt))
        else:
            page.locator("#btn-fold").click(timeout=2000)
            log("%s: 弃牌 (要跟 %s)" % (who, amt))

def part_button_micro(browser):
    """②客人「下一局」按钮态同步抓取"""
    out = {}
    ph = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
    pg = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
    ph.goto(URL); ph.wait_for_timeout(1500)
    ph.locator("#mc-multi").click(); ph.wait_for_timeout(500)
    ph.locator("#mp-name").fill("R4b房主")
    ph.locator("#mp-btn-create").click()
    code = ""
    for _ in range(30):
        code = (ph.locator("#mp-room-code").text_content() or "").strip()
        if code and "-" not in code:
            break
        ph.wait_for_timeout(500)
    try:
        an = ph.locator("#auto-next")
        if an.is_checked():
            an.uncheck()
    except Exception:
        pass
    out["code"] = code
    log("②已建房 %s（自动续局关）" % code)
    pg.goto(URL); pg.wait_for_timeout(1500)
    pg.locator("#mc-multi").click(); pg.wait_for_timeout(500)
    pg.locator("#mp-name").fill("呜帕R4b客")
    pg.locator("#mp-tab-join").click()
    pg.locator("#mp-code").fill(code)
    pg.locator("#mp-btn-join").click()
    for i in range(12):
        if pg.locator("#mp-lobby").is_visible() and not pg.locator("#mp-lobby").is_hidden():
            break
        pg.wait_for_timeout(1000)
    pg.locator("#mp-btn-ready").click()
    log("②客人已准备")
    ph.wait_for_timeout(1000)
    ph.locator("#mp-btn-start").click(timeout=5000)
    for i in range(30):
        h_in = ph.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')")
        g_in = pg.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')")
        if h_in and g_in:
            break
        pg.wait_for_timeout(1000)
    ph.wait_for_timeout(1200)
    log("②打 1 手…")
    deadline = time.time() + 60 * 5
    while time.time() < deadline:
        h_ov = ph.locator("#overlay").evaluate("el => !el.classList.contains('hidden')")
        g_ov = pg.locator("#overlay").evaluate("el => !el.classList.contains('hidden')")
        if h_ov and g_ov:
            break
        if not h_ov and ph.locator("#action-controls").is_visible():
            act_simple(ph, "房主"); ph.wait_for_timeout(600)
        if not g_ov and pg.locator("#action-controls").is_visible():
            act_simple(pg, "客人"); pg.wait_for_timeout(600)
        ph.wait_for_timeout(400)
    log("②手牌结束")

    # 毫秒级抓取：click 同 tick 读态 + 房主侧关闭计时
    pg.evaluate("""() => {
      window.__R4B_BTN__ = [];
      const bn = document.getElementById('btn-next');
      const snap = t => window.__R4B_BTN__.push({t: t, text: (bn.textContent||'').trim(), disabled: bn.disabled});
      bn.click();               // 同一 tick 内按钮先变「已请求」
      snap(0);
      setTimeout(() => snap(50), 50);
      setTimeout(() => snap(150), 150);
      setTimeout(() => snap(400), 400);
      setTimeout(() => snap(1000), 1000);
    }""")
    t_close = None
    t0 = time.time()
    while time.time() - t0 < 6:
        if ph.locator("#overlay").evaluate("el => el.classList.contains('hidden')"):
            t_close = (time.time() - t0) * 1000
            break
        ph.wait_for_timeout(20)
    out["host_overlay_close_ms"] = round(t_close) if t_close is not None else None
    pg.wait_for_timeout(1300)
    snaps = pg.evaluate("window.__R4B_BTN__ || []")
    out["btn_timeline"] = snaps
    out["pending_text_seen"] = any("已请求" in s["text"] for s in snaps)
    out["reset_back_text"] = snaps[-1]["text"] if snaps else ""
    log("②房主 overlay 关闭耗时: %sms" % out["host_overlay_close_ms"])
    log("②按钮时间线: %s" % json.dumps(snaps, ensure_ascii=False))
    shot(pg, "r4b_02_after_click")
    out["pass"] = out["pending_text_seen"] and out["host_overlay_close_ms"] is not None
    log("②按钮态微测: %s" % ("PASS" if out["pass"] else "FAIL"))
    ph.close(); pg.close()
    return out

def main():
    from playwright.sync_api import sync_playwright
    result = {"ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            result["wording"] = part_wording(browser)
        except Exception:
            result["wording_error"] = traceback.format_exc()[-500:]
            log("①异常: %s" % result["wording_error"])
        try:
            result["btn_micro"] = part_button_micro(browser)
        except Exception:
            result["btn_micro_error"] = traceback.format_exc()[-500:]
            log("②异常: %s" % result["btn_micro_error"])
        result["ok"] = True
        json.dump(result, open(os.path.join(OUT, "r4b_result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        browser.close()

if __name__ == "__main__":
    main()
