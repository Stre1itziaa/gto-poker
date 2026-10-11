# insp_r5_sbm.py — R5 三倍满少女 补充微测（只调用页面 JS / 截图，不改游戏）
# ①牌谱行不可见诊断：#data-body 滚动几何 + .data-hand 的 rect/样式
# ②chips 过滤正确性：种子 4 多人 + 2 单机，点 多人/单机/全部，断言 hands/handRows/sel 迁移，各截图
# ③computed style 复核：导入 label 边框宽度/圆角、chip.sel 色、aria-pressed
# 输出: data5/sanbaiman/insp_sbm_result.json + insp_sbm_*.png
import sys, os, json, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data5", "sanbaiman")
URL = "http://localhost:8787/"

def mk(name, hole, mode="mp"):
    return {"name": name, "charId": "", "isBot": False, "stackEnd": 2000,
            "committed": 0, "won": 0, "refund": 0, "rebuys": 0, "hole": hole,
            "room": "INSP-R5", "handNo": 0, "ts": "2026-09-19T17:00:00Z",
            "sb": 10, "bb": 20, "board": [],
            "actions": [{"idx": 0, "street": "preflop", "type": "call", "to": 20, "added": 20},
                        {"idx": 1, "street": "preflop", "type": "check", "to": 0, "added": 0}],
            "pots": [{"amount": 40, "winners": [0], "label": "主池", "handName": "A高",
                      "foldWin": True, "uncalled": False, "split": False}],
            "assert": {"sumPaid": 40, "sumPut": 40, "ok": True},
            "hero": name, "mode": mode}

RECS = []
for i in range(4):
    r = mk("小梅MP%d" % (i + 1), ["Ah", "Kd"], "mp"); r["handNo"] = 9001 + i; RECS.append(r)
for i in range(2):
    r = mk("小梅单机%d" % (i + 1), ["Qs", "Jd"], "sp"); r["handNo"] = 9101 + i; RECS.append(r)

def main():
    from playwright.sync_api import sync_playwright
    result = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL)
        page.wait_for_timeout(1500)
        n = page.evaluate("window.__R5_SEED__ = %s; (window.__R5_SEED__||[]).forEach(function(r){window.DataPage.record(r)}); (window.DataPage.all()||[]).length" % json.dumps(RECS, ensure_ascii=False))
        result["seeded"] = n
        page.locator("#mc-data").click(timeout=5000)
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(OUT, "insp_sbm_1_all.png"))

        # ③ computed styles
        result["styles"] = page.evaluate("""() => {
          const gi = document.querySelector('.data-import-label');
          const gs = gi ? getComputedStyle(gi) : null;
          const chips = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).map(function(b){
            const cs = getComputedStyle(b);
            return {text: b.textContent, sel: b.classList.contains('sel'), aria: b.getAttribute('aria-pressed'),
                    color: cs.color, borderColor: cs.borderColor, bg: cs.backgroundColor};
          });
          const exp = document.querySelector('#data-body .mp-row button');
          const ecs = exp ? getComputedStyle(exp) : null;
          return {
            import_border: gs ? {width: gs.borderWidth, radius: gs.borderRadius, color: gs.borderColor, display: gs.display} : null,
            export_border: ecs ? {width: ecs.borderWidth, radius: ecs.borderRadius} : null,
            chips: chips
          };
        }""")

        # ① 牌谱行几何诊断
        result["handrows"] = page.evaluate("""() => {
          const body = document.getElementById('data-body');
          const br = body.getBoundingClientRect();
          const rows = Array.from(document.querySelectorAll('#data-body .data-hand')).map(function(d, i){
            const r = d.getBoundingClientRect(); const cs = getComputedStyle(d);
            return {i: i, open: d.open, h: Math.round(r.height), w: Math.round(r.width),
                    topInBody: Math.round(r.top - br.top), display: cs.display, visibility: cs.visibility,
                    parentClass: d.parentElement.className || d.parentElement.tagName};
          });
          const sticky = body.querySelector(':scope > .mp-row:last-child');
          const sr = sticky ? sticky.getBoundingClientRect() : null;
          return {scrollTop: body.scrollTop, clientH: body.clientHeight, scrollH: body.scrollHeight,
                  bodyTop: Math.round(br.top), bodyBottom: Math.round(br.bottom),
                  stickyTopInBody: sr ? Math.round(sr.top - br.top) : null, stickyH: sr ? Math.round(sr.height) : null,
                  rows: rows};
        }""")

        # ② chips 过滤交互
        def scope_state():
            return page.evaluate("""() => {
              const st = window.DataPage.stats ? window.DataPage.stats(window.DataPage.all()) : {};
              const sel = (document.querySelector('#data-body .data-mode-chip.sel') || {}).textContent || null;
              return {sel: sel, hands_card: document.querySelectorAll('#data-body .data-stat b')[0].textContent,
                      handRows: document.querySelectorAll('#data-body .data-hand').length,
                      stats_hands: st.hands};
            }""")
        states = {"全部(初始)": scope_state()}
        for label, tag in [("多人", "mp"), ("单机", "solo"), ("全部", "all2")]:
            page.locator("#data-body .data-mode-chip", has_text=label).first.click()
            page.wait_for_timeout(700)
            states["%s(点击后)" % label] = scope_state()
            page.screenshot(path=os.path.join(OUT, "insp_sbm_2_%s.png" % tag))
        result["scope_states"] = states
        result["js_errors"] = errs[:5]
        browser.close()
    json.dump(result, open(os.path.join(OUT, "insp_sbm_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False, indent=1)[:5000])

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
