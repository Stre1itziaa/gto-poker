# insp_wupa.py — R2 牌谱详情巡检（呜帕呜帕 专用）
# 优先加入好友房 452S7B 打 2 手；失败则退回单机训练模式打 2 手。
# 核心：回大厅 → 打开数据页 → 展开**每一手**牌谱详情 → innerText 全文 Dump + 逐手截图 + 结构断言。
# 输出: data2/wupa/insp_result.json + handlog_dump.json + 10/11/hand_*.png
import sys, time, json, os, random, traceback

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data2", "wupa")
URL = "http://localhost:8787/"
CODE = "452S7B"
NAME = "呜帕呜帕"
MAX_HANDS = 2

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

def play_hands(page, mode):
    """mode: 'mp' or 'solo' —— 同一套简单策略打 MAX_HANDS 手"""
    turns = 0
    hands = 0
    deadline = time.time() + (60 * 8 if mode == "mp" else 60 * 4)
    while time.time() < deadline and hands < MAX_HANDS:
        if visible(page, "#overlay:not(.hidden)"):
            ov = ""
            try:
                ov = page.locator("#overlay-body").text_content() or ""
            except Exception:
                pass
            log("[%s] 结算弹层: %s" % (mode, ov[:200]))
            hands += 1
            if hands >= MAX_HANDS:
                break
            try:
                page.locator("#btn-next").click(timeout=1500)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            continue
        if visible(page, "#action-controls"):
            turns += 1
            if turns == 1 or turns % 4 == 1:
                shot(page, "06_turn_%s_%d" % (mode, turns))
            call_btn = page.locator("#btn-checkcall").text_content() or ""
            r = random.random()
            if r < 0.15 and visible(page, "#btn-raise"):
                try:
                    presets = page.locator("#presets button")
                    n = presets.count()
                    if n > 0:
                        presets.nth(min(1, n - 1)).click()
                        page.wait_for_timeout(200)
                        page.locator("#btn-raise").click()
                        log("行动#%d: 加注" % turns)
                        page.wait_for_timeout(900)
                        continue
                except Exception:
                    pass
            if "过牌" in call_btn:
                page.locator("#btn-checkcall").click()
                log("行动#%d: 过牌" % turns)
            else:
                amt = "".join(ch for ch in call_btn if ch.isdigit())
                if amt and int(amt) <= 120:
                    page.locator("#btn-checkcall").click()
                    log("行动#%d: 跟注 %s" % (turns, amt))
                elif random.random() < 0.35:
                    page.locator("#btn-checkcall").click()
                    log("行动#%d: 跟大注 %s" % (turns, amt))
                else:
                    try:
                        page.locator("#btn-fold").click(timeout=2000)
                        log("行动#%d: 弃牌 (要跟 %s)" % (turns, amt))
                    except Exception:
                        page.locator("#btn-checkcall").click()
                        log("行动#%d: 弃牌失败改跟注" % turns)
            page.wait_for_timeout(900)
        page.wait_for_timeout(1200)
    return hands, turns

def audit_data_page(page):
    """展开每一手牌谱详情，Dump 全文 + 结构断言 + 逐手截图"""
    page.locator("#btn-home").click(timeout=5000)
    page.wait_for_timeout(2000)
    shot(page, "08_back_landing")
    page.locator("#mc-data").click(timeout=5000)
    page.wait_for_timeout(1500)

    audit = page.evaluate("""() => {
      const out = {};
      out.dataOpenClass = document.body.classList.contains('data-open');
      const tb = document.getElementById('topbar');
      const cs = tb ? getComputedStyle(tb) : null;
      out.topbarFilter = cs ? cs.filter : null;
      out.topbarPointer = cs ? cs.pointerEvents : null;
      out.sessionStats = (document.getElementById('session-stats') || {}).textContent || '';
      const D = window.DataPage; if (!D) { out.module = false; return out; }
      out.module = true;
      const recs = D.all(), st = D.stats(recs);
      out.stats = { hands: st.hands, netBB: st.netBB, vpip: st.vpip, pfr: st.pfr, totalHands: st.totalHands };
      out.records = recs;
      // 展开全部 details
      document.querySelectorAll('#data-body details.data-hand').forEach(function (d) { d.open = true; });
      out.handCount = document.querySelectorAll('#data-body details.data-hand').length;
      out.hands = [];
      document.querySelectorAll('#data-body details.data-hand').forEach(function (d, i) {
        const t = d.innerText || '';
        out.hands.push({
          i: i,
          summary: (d.querySelector('summary') || {}).textContent || '',
          text: t,
          starLines: (t.match(/★/g) || []).length,
          hasStreetGroup: { preflop: /翻前/.test(t), flop: /翻牌/.test(t), turn: /转牌/.test(t), river: /河牌/.test(t) },
          hasShowdownHoleLine: /摊牌 /.test(t),
          engTokens: (t.match(/\\b(check|call|bet|raise|fold)\\b/g) || []).length,
          hasPcode: /\\bP[1-6]\\b/.test(t),
          questionHand: /「？」/.test(t)
        });
      });
      return out;
    }""")
    shot(page, "10_data_collapsed")
    page.wait_for_timeout(400)
    # 展开态整页与逐手截图（JS 里已 open，重新截图）
    try:
        page.locator("#data-body").screenshot(path=os.path.join(OUT, "11_data_expanded.png"))
        log("截图 11_data_expanded(元素)")
    except Exception as e:
        log("元素截图失败: %s" % e)
        shot(page, "11_data_expanded")
    for i in range(audit.get("handCount", 0)):
        try:
            page.locator("#data-body details.data-hand").nth(i).screenshot(
                path=os.path.join(OUT, "hand_detail_%d.png" % (i + 1)))
        except Exception as e:
            log("逐手截图失败 %d: %s" % (i + 1, e))
    # 导出记录落盘
    try:
        json.dump(audit.get("records", []), open(os.path.join(OUT, "handlog_dump.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    except Exception:
        pass
    audit.pop("records", None)
    return audit

def main():
    from playwright.sync_api import sync_playwright
    result = {"ok": False, "mode": None}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(URL)
        page.wait_for_timeout(1200)
        shot(page, "01_landing")
        page.locator("#mc-multi").click(timeout=5000)
        page.wait_for_timeout(500)
        page.locator("#mp-name").fill(NAME)
        try:
            page.locator("#mp-chars .mp-ch:nth-child(5)").click()
        except Exception:
            pass

        joined = False
        for attempt in range(1, 4):
            try:
                page.locator("#mp-tab-join").click()
                page.locator("#mp-code").fill(CODE)
                page.locator("#mp-btn-join").click()
                log("第 %d 次点击加入房间 %s" % (attempt, CODE))
            except Exception as e:
                log("点击加入异常: %s" % e)
            for i in range(10):
                if visible(page, "#mp-lobby") and not page.locator("#mp-lobby").is_hidden():
                    joined = True
                    break
                page.wait_for_timeout(1000)
            if joined:
                break
            status = ""
            try:
                status = page.locator("#mp-status").text_content() or ""
            except Exception:
                pass
            log("加入未成功 status=%s，等 20 秒重试" % status.strip())
            page.wait_for_timeout(20000)

        started = False
        if joined:
            result["mode"] = "mp"
            shot(page, "03_lobby")
            try:
                log("大厅名单: %s" % page.locator("#mp-players").text_content())
            except Exception:
                pass
            page.locator("#mp-btn-ready").click()
            log("已点准备，等开局…")
            for i in range(150):
                if page.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                    started = True
                    break
                page.wait_for_timeout(1000)
            if started:
                page.wait_for_timeout(1800)
                shot(page, "04_table_first")
                h, t = play_hands(page, "mp")
                result["hands"] = h
                result["turns"] = t
        if not started:
            log("好友房未开局（joined=%s）→ 单机训练模式兜底" % joined)
            result["mode"] = "solo"
            page.goto(URL)
            page.wait_for_timeout(1200)
            page.locator("#mc-train").click(timeout=5000)
            page.wait_for_timeout(600)
            page.locator("#btn-start").click(timeout=5000)
            page.wait_for_timeout(1800)
            shot(page, "04_table_first")
            h, t = play_hands(page, "solo")
            result["hands"] = h
            result["turns"] = t

        audit = audit_data_page(page)
        result["audit"] = audit
        result["js_errors"] = errors[:10]
        result["ok"] = audit.get("module", False) and audit.get("handCount", 0) > 0
        json.dump(result, open(os.path.join(OUT, "insp_result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("INSP_DONE mode=%s hands=%s" % (result["mode"], result.get("hands")))
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            json.dump({"ok": False, "error": traceback.format_exc(), "log": log_lines},
                      open(os.path.join(OUT, "insp_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass
