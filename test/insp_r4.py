# insp_r4.py — R4 回归巡检（呜帕呜帕 · 第 9 次试玩）
# 验证: ①客人点「下一局」请求链路归因（自开房、房主关自动续局，房主被代点才算 PASS）
#       ②牌谱行动流「下注/加注到」口径（真实手 + 合成边界样本，重点：翻前首加注被标「下注」?）
#       ③牌谱展开自动滚动到位性：展开后尾行与 sticky 按钮条的重叠像素测量
# 输出: data4/wupa/r4_result.json + r4_*.png + r4_dump.txt
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

def visible(page, sel):
    try:
        return page.locator(sel).is_visible()
    except Exception:
        return False

def act_simple(page, who):
    """简单策略行动一次：能过就过，小额跟，大额弃"""
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
            try:
                page.locator("#btn-fold").click(timeout=2000)
                log("%s: 弃牌 (要跟 %s)" % (who, amt))
            except Exception:
                page.locator("#btn-checkcall").click()
                log("%s: 弃牌失败改跟注" % who)

# ---------- 合成牌谱 ----------
def mk(name, hole):
    return {"name": name, "charId": "", "isBot": False, "stackEnd": 2000,
            "committed": 0, "won": 0, "refund": 0, "rebuys": 0, "hole": hole}

# S1: 翻前两连加注 —— 正确口径应为「加注到 60 · 加注到 180」，若出现「下注 60」即翻前误标
SYNTH_S1 = {
    "room": "SYNTH-R4", "handNo": 8001, "ts": "2026-09-19T16:00:00Z", "sb": 10, "bb": 20,
    "players": [mk("呜帕R4", ["Ah", "Kd"]), mk("测试甲", ["2c", "2h"]), mk("测试乙", ["Qs", "Jd"])],
    "board": [],
    "actions": [
        {"idx": 1, "street": "preflop", "type": "raise", "to": 60, "added": 40},
        {"idx": 0, "street": "preflop", "type": "raise", "to": 180, "added": 120},
        {"idx": 2, "street": "preflop", "type": "fold", "to": 0, "added": 0},
        {"idx": 1, "street": "preflop", "type": "call", "to": 180, "added": 120},
    ],
    "pots": [{"amount": 420, "winners": [0], "label": "主池", "handName": "A高", "foldWin": True, "uncalled": False, "split": False}],
}
SYNTH_S1["assert"] = {"sumPaid": 360, "sumPut": 420, "ok": True}
SYNTH_S1["hero"] = "呜帕R4"; SYNTH_S1["mode"] = "mp"

# S2: 翻牌街内首注+再加注 —— 应为「下注 300 · 加注到 900 · 跟注 600」
SYNTH_S2 = {
    "room": "SYNTH-R4", "handNo": 8002, "ts": "2026-09-19T16:01:00Z", "sb": 10, "bb": 20,
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
}
SYNTH_S2["assert"] = {"sumPaid": 1920, "sumPut": 1920, "ok": True}
SYNTH_S2["hero"] = "呜帕R4"; SYNTH_S2["mode"] = "mp"

# S3: 转牌 call 只有 to 没有 added（回退口径）
SYNTH_S3 = {
    "room": "SYNTH-R4", "handNo": 8003, "ts": "2026-09-19T16:02:00Z", "sb": 10, "bb": 20,
    "players": [mk("呜帕R4", ["Ah", "Kh"]), mk("测试甲", ["2c", "2h"])],
    "board": ["As", "7c", "2h", "9d"],
    "actions": [
        {"idx": 1, "street": "preflop", "type": "raise", "to": 60, "added": 40},
        {"idx": 0, "street": "preflop", "type": "call", "to": 60, "added": 40},
        {"idx": 1, "street": "flop", "type": "raise", "to": 100, "added": 100},
        {"idx": 0, "street": "flop", "type": "call", "to": 100, "added": 100},
        {"idx": 1, "street": "turn", "type": "raise", "to": 300, "added": 200},
        {"idx": 0, "street": "turn", "type": "call", "to": 300},
    ],
    "pots": [{"amount": 920, "winners": [0], "label": "主池", "handName": "两对", "foldWin": True, "uncalled": False, "split": False}],
}
SYNTH_S3["assert"] = {"sumPaid": 920, "sumPut": 920, "ok": True}
SYNTH_S3["hero"] = "呜帕R4"; SYNTH_S3["mode"] = "mp"

# S4×10: 长牌谱（撑高滚动容器，测量展开滚动）
def mk_scroll_rec(n):
    acts = []
    for st_, base in (("preflop", 40), ("flop", 120), ("turn", 260), ("river", 420)):
        acts.append({"idx": 1, "street": st_, "type": "raise", "to": base, "added": base})
        acts.append({"idx": 0, "street": st_, "type": "raise", "to": base * 3, "added": base * 2})
        acts.append({"idx": 1, "street": st_, "type": "call", "to": base * 3, "added": base * 2})
    return {
        "room": "SCROLL-R4", "handNo": 9000 + n, "ts": "2026-09-19T16:03:00Z", "sb": 10, "bb": 20,
        "players": [mk("呜帕R4", ["Ah", "Kd"]), mk("滚动填充甲%d号" % n, ["2c", "2h"]),
                    mk("滚动填充乙%d号" % n, ["7s", "7d"])],
        "board": ["As", "Kc", "7h", "7d", "2s"],
        "actions": acts,
        "pots": [{"amount": 3000, "winners": [0], "label": "主池", "handName": "两对",
                  "foldWin": True, "uncalled": False, "split": False}],
        "assert": {"sumPaid": 3000, "sumPut": 3000, "ok": True},
        "hero": "呜帕R4", "mode": "mp",
    }

SEED_JS = """() => {
  const recs = window.__R4_SEED__ || [];
  recs.forEach(function (r) { window.DataPage.record(r); });
  return (window.DataPage.all() || []).length;
}"""

# ---------- 滚动测量 ----------
MEASURE_HEAD = """() => {
  const body = document.getElementById('data-body');
  const bar = body.querySelector(':scope > .mp-row:last-child');
  const items = Array.from(body.querySelectorAll('details.data-hand'));
  return {count: items.length, bodyClientH: body.clientHeight, bodyScrollH: body.scrollHeight,
          barH: bar ? Math.round(bar.getBoundingClientRect().height * 10) / 10 : null};
}"""

MEASURE_OPEN = """(i) => {
  const body = document.getElementById('data-body');
  const bar = body.querySelector(':scope > .mp-row:last-child');
  const d = body.querySelectorAll('details.data-hand')[i];
  if (!d) return {i: i, missing: true};
  const before = body.scrollTop;
  d.open = true;
  return new Promise(function (res) { setTimeout(function () {
    const dRect = d.getBoundingClientRect();
    const bRect = bar.getBoundingClientRect();
    const nodes = d.querySelectorAll('*');
    const last = nodes[nodes.length - 1];
    const lRect = last.getBoundingClientRect();
    const overlap = Math.max(0, Math.min(lRect.bottom, bRect.bottom) - Math.max(lRect.top, bRect.top));
    res({i: i, scrollTopBefore: before, scrollTopAfter: body.scrollTop,
         scrolled: Math.round((body.scrollTop - before) * 10) / 10,
         dBottomInViewport: Math.round(dRect.bottom * 10) / 10,
         barTopInViewport: Math.round(bRect.top * 10) / 10,
         tailOverlapPx: Math.round(overlap * 10) / 10,
         tailCovered: overlap > 1});
  }, 350); });
}"""

def try_create_room(page):
    page.goto(URL)
    page.wait_for_timeout(1500)
    page.locator("#mc-multi").click(timeout=5000)
    page.wait_for_timeout(500)
    page.locator("#mp-name").fill("R4归因房主")
    page.locator("#mp-btn-create").click()
    code = ""
    for _ in range(30):
        code = (page.locator("#mp-room-code").text_content() or "").strip()
        if code and "-" not in code:
            break
        page.wait_for_timeout(500)
    if not code or "-" in code:
        return ""
    # 强制关掉自动下一局（归因关键：房主不自走）
    try:
        an = page.locator("#auto-next")
        if an.is_checked():
            an.uncheck()
            log("房主自动下一局：已由开→关")
        else:
            log("房主自动下一局：默认已关")
    except Exception as e:
        log("auto-next 操作异常: %s" % e)
    log("已建房，房码 %s" % code)
    return code

def try_join(page, code):
    page.goto(URL)
    page.wait_for_timeout(1500)
    page.locator("#mc-multi").click(timeout=5000)
    page.wait_for_timeout(500)
    page.locator("#mp-name").fill("呜帕R4客")
    page.locator("#mp-tab-join").click()
    page.locator("#mp-code").fill(code)
    page.locator("#mp-btn-join").click()
    log("尝试加入房间 %s" % code)
    for i in range(12):
        if visible(page, "#mp-lobby") and not page.locator("#mp-lobby").is_hidden():
            return True
        page.wait_for_timeout(1000)
    status = ""
    try:
        status = page.locator("#mp-status").text_content() or ""
    except Exception:
        pass
    log("加入未成功: %s" % status)
    return False

def main():
    from playwright.sync_api import sync_playwright
    result = {"ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        errors = []
        ctx_h = browser.new_context(viewport={"width": 1600, "height": 900})
        ctx_g = browser.new_context(viewport={"width": 1600, "height": 900})
        ph = ctx_h.new_page()
        pg = ctx_g.new_page()
        for page in (ph, pg):
            page.on("pageerror", lambda e: errors.append("pageerror: " + str(e)))
            page.on("console", lambda m: errors.append("console: " + m.text) if m.type == "error" else None)

        # ---- Part A: 自开房归因验证客人「下一局」请求 ----
        part_a = {"host_room": False}
        try:
            code = try_create_room(ph)
            part_a["code"] = code
            joined = False
            if code:
                for attempt in range(1, 4):
                    if try_join(pg, code):
                        joined = True
                        log("第 %d 次尝试入座成功" % attempt)
                        break
                    if attempt < 3:
                        log("等 20 秒后重试…")
                        pg.wait_for_timeout(20000)
            if code and joined:
                part_a["host_room"] = True
                pg.wait_for_timeout(600)
                pg.locator("#mp-btn-ready").click()
                log("客人已点准备")
                ph.wait_for_timeout(1200)
                ph.locator("#mp-btn-start").click(timeout=5000)
                log("房主点开始")
                for i in range(30):
                    h_in = ph.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')")
                    g_in = pg.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')")
                    if h_in and g_in:
                        break
                    pg.wait_for_timeout(1000)
                ph.wait_for_timeout(1500)
                log("已进牌桌，打 1 手…")
                shot(pg, "r4_01_table")

                # 双页轮流行动，直到双方都出现结算弹层
                deadline = time.time() + 60 * 5
                while time.time() < deadline:
                    h_ov = visible(ph, "#overlay:not(.hidden)")
                    g_ov = visible(pg, "#overlay:not(.hidden)")
                    if h_ov and g_ov:
                        break
                    if not h_ov and visible(ph, "#action-controls"):
                        act_simple(ph, "房主")
                        ph.wait_for_timeout(700)
                    if not g_ov and visible(pg, "#action-controls"):
                        act_simple(pg, "客人")
                        pg.wait_for_timeout(700)
                    ph.wait_for_timeout(500)
                log("手牌结束，进入归因阶段")
                shot(pg, "r4_02_guest_showdown")
                shot(ph, "r4_03_host_showdown")

                # 房主此刻 overlay 应该还开着（自动续局已关）
                host_overlay_before = ph.locator("#overlay").evaluate("el => !el.classList.contains('hidden')")
                part_a["host_overlay_before_request"] = host_overlay_before

                # 客人点「下一局」
                btn_before = pg.locator("#btn-next").text_content() or ""
                pg.locator("#btn-next").click()
                pg.wait_for_timeout(300)
                btn_after_text = pg.locator("#btn-next").text_content() or ""
                btn_after_disabled = pg.locator("#btn-next").is_disabled()
                part_a["guest_btn_before"] = btn_before.strip()
                part_a["guest_btn_after_text"] = btn_after_text.strip()
                part_a["guest_btn_after_disabled"] = btn_after_disabled
                log("客人按钮: 「%s」→「%s」 disabled=%s" % (btn_before.strip(), btn_after_text.strip(), btn_after_disabled))
                shot(pg, "r4_04_guest_requested")

                # 房主 5 秒内 overlay 关闭 = 被代点推进
                host_closed = False
                for i in range(50):
                    if ph.locator("#overlay").evaluate("el => el.classList.contains('hidden')"):
                        host_closed = True
                        break
                    ph.wait_for_timeout(100)
                part_a["host_overlay_closed_after_request"] = host_closed
                log("房主 overlay 被代点关闭: %s" % host_closed)
                shot(ph, "r4_05_host_after_request")

                # 等第 2 手在客人端开起来
                hand2 = False
                for i in range(20):
                    if visible(pg, "#action-controls"):
                        hand2 = True
                        break
                    pg.wait_for_timeout(1000)
                part_a["hand2_started_on_guest"] = hand2
                log("第 2 手在客人端开打: %s" % hand2)

                passed = (host_overlay_before and btn_after_disabled
                          and ("已请求" in btn_after_text) and host_closed and hand2)
                part_a["pass"] = bool(passed)
                log("Part A 归因验证: %s" % ("PASS" if passed else "FAIL"))
            else:
                part_a["pass"] = False
                log("Part A 跳过（建房或入座失败）")
        except Exception:
            part_a["error"] = traceback.format_exc()[-500:]
            log("Part A 异常: %s" % part_a["error"])
        result["part_a_guest_next_request"] = part_a

        # ---- Part B/C: 真实牌谱 + 合成边界样本（都在客人页做）----
        try:
            # 塞合成样本
            pg.evaluate("window.__R4_SEED__ = %s" % json.dumps(
                [SYNTH_S1, SYNTH_S2, SYNTH_S3] + [mk_scroll_rec(n) for n in range(1, 11)],
                ensure_ascii=False))
            n = pg.evaluate(SEED_JS)
            log("合成牌谱已塞入，当前记录数=%s" % n)

            pg.goto(URL)
            pg.wait_for_timeout(1500)
            pg.locator("#mc-data").click(timeout=5000)
            pg.wait_for_timeout(1200)

            dump_text = pg.evaluate(
                "Array.from(document.querySelectorAll('#data-body .data-hand'))" +
                ".map(function(d){return d.innerText}).join('\\n==========\\n')")
            with open(os.path.join(OUT, "r4_dump.txt"), "w", encoding="utf-8") as f:
                f.write(dump_text or "(empty)")
            result["dump_chars"] = len(dump_text)

            # 口径断言
            street_lines = re.findall(r"(?:翻前|翻牌|转牌|河牌|摊牌)[^\n]*", dump_text or "")
            pre_lines = [l for l in street_lines if l.startswith("翻前")]
            flop_lines = [l for l in street_lines if l.startswith("翻牌")]
            s1_seg = ""
            m = re.search(r"8001.*?(?=====|$)", dump_text or "", re.S)
            checks = {
                "has_bet_n": bool(re.search(r"下注 \d+", "\n".join(street_lines))),
                "has_raise_to_n": bool(re.search(r"加注到 \d+", "\n".join(street_lines))),
                "no_double_marker": "加注到→" not in (dump_text or ""),
                "no_latin_actions": not re.search(r"\b(fold|check|call|raise)\b", "\n".join(street_lines)),
                # 翻前是否出现「下注 N」（出现 = 翻前首加注被误标）
                "preflop_bet_mislabel": any(re.search(r"下注 \d+", l) for l in pre_lines),
                # 翻牌街「下注/加注到」并存（正确行为）
                "flop_bet_and_raise": any(re.search(r"下注 \d+", l) for l in flop_lines) and any(re.search(r"加注到 \d+", l) for l in flop_lines),
                "s1_first_pre_raise_label": "",
            }
            if m:
                seg = re.findall(r"翻前[^\n]*", m.group(0))
                checks["s1_first_pre_raise_label"] = " | ".join(seg)[:200]
            result["wording_checks"] = checks
            log("口径断言: %s" % json.dumps(checks, ensure_ascii=False))
        except Exception:
            result["part_bc_error"] = traceback.format_exc()[-500:]
            log("Part B/C 异常: %s" % result["part_bc_error"])

        # ---- Part D: 展开滚动定量测量 ----
        try:
            head = pg.evaluate(MEASURE_HEAD)
            result["scroll_head"] = head
            log("滚动容器: 条目=%s 容器高=%s 内容高=%s sticky条高=%s" % (
                head["count"], head["bodyClientH"], head["bodyScrollH"], head["barH"]))
            meas = []
            idxs = [0, head["count"] // 2, head["count"] - 1] if head["count"] else []
            for i in idxs:
                r = pg.evaluate(MEASURE_OPEN, i)
                meas.append(r)
                log("展开 #%d: 滚动=%spx 条目底=%s sticky顶=%s 尾行重叠=%spx 盖住=%s" % (
                    i, r.get("scrolled"), r.get("dBottomInViewport"), r.get("barTopInViewport"),
                    r.get("tailOverlapPx"), r.get("tailCovered")))
                shot(pg, "r4_06_expand_%d" % i)
                # 收起还原，避免影响下一条测量
                pg.evaluate("(i => { document.querySelectorAll('#data-body details.data-hand')[i].open = false; })(%d)" % i)
                pg.wait_for_timeout(150)
            result["scroll_measure"] = meas
            covered = [r for r in meas if r.get("tailCovered")]
            result["scroll_tail_covered_count"] = len(covered)
            log("尾行被 sticky 条盖住的条目数: %d / %d" % (len(covered), len(meas)))
        except Exception:
            result["part_d_error"] = traceback.format_exc()[-500:]
            log("Part D 异常: %s" % result["part_d_error"])

        result["js_errors"] = errors[:10]
        result["ok"] = True
        json.dump(result, open(os.path.join(OUT, "r4_result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        browser.close()

if __name__ == "__main__":
    main()
