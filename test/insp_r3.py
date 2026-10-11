# insp_r3.py — R3 回归巡检（呜帕呜帕 · 房码 D2JBMA）
# 验证: ①数据页牌谱行动流中文化（真手牌 + 合成边界样本）
#       ②同赢家多池合并文案「主池+边池1（共 N）」/ 平分池
#       ③多人局右栏教练占位可见性（panel display / body 文案 / 顶栏开关）
# 流程: 加入 D2JBMA（失败等 20s 重试 ×3；仍失败退回单机）→ 打 1 手 → 探针右栏 →
#       塞合成牌谱 → 回大厅 → 数据分析 → 展开 details → innerText 全量 dump
# 输出: data3/wupa/r3_result.json + r3_dump.txt + r3_*.png
import sys, time, json, os, random, re, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data3", "wupa")
URL = "http://localhost:8787/"
CODE = "D2JBMA"
NAME = "呜帕呜帕"

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

COACH_PROBE = """() => {
  const g = id => document.getElementById(id);
  const panel = g('coach'), body = g('coach-body'), lbl = g('coach-toggle-label');
  return {
    coachPanelDisplay: panel ? getComputedStyle(panel).display : 'missing',
    coachBodyText: body ? (body.textContent || '').trim() : 'missing',
    coachToggleDisplay: lbl ? getComputedStyle(lbl).display : 'missing',
    topbarCoachToggle: (function(){ const t = g('coach-toggle');
      return t ? (getComputedStyle(t.closest('label') || t).display) : 'missing'; })()
  };
}"""

SYNTH_JS = """() => {
  const mk = (name, hole) => ({ name: name, charId: '', isBot: false, stackEnd: 2000,
    committed: 0, won: 0, refund: 0, rebuys: 0, hole: hole });
  // 9001: check/fold 无尾巴 + call 本街增量 + raise →to + 同赢家双池合并 + 平分池
  const r1 = {
    room: 'SYNTH-TEST', handNo: 9001, ts: new Date().toISOString(), sb: 10, bb: 20,
    players: [mk('呜帕呜帕', ['Ah', 'Kd']), mk('测试甲', ['2c', '2h']), mk('测试乙', ['Qs', 'Jd'])],
    board: ['As', 'Kc', '7h', '7d', '2s'],
    actions: [
      { idx: 1, street: 'preflop', type: 'raise', to: 60, added: 40 },
      { idx: 0, street: 'preflop', type: 'call', to: 60, added: 40 },
      { idx: 2, street: 'preflop', type: 'fold', to: 0, added: 0 },
      { idx: 0, street: 'flop', type: 'check', to: 0, added: 0 },
      { idx: 1, street: 'flop', type: 'raise', to: 300, added: 300 },
      { idx: 0, street: 'flop', type: 'call', to: 300, added: 300 },
      { idx: 1, street: 'turn', type: 'raise', to: 450, added: 150 },
      { idx: 0, street: 'turn', type: 'fold', to: 0, added: 0 }
    ],
    pots: [
      { amount: 240, winners: [1], label: '主池', handName: '两对', foldWin: false, uncalled: false, split: false },
      { amount: 180, winners: [1], label: '边池1', handName: '两对', foldWin: false, uncalled: false, split: false },
      { amount: 60, winners: [0, 1], label: '边池2', handName: '一对', foldWin: false, uncalled: false, split: true }
    ]
  };
  r1.assert = { sumPaid: 480, sumPut: 480, ok: true };
  r1.hero = '呜帕呜帕'; r1.mode = 'mp';
  window.DataPage.record(r1);
  return (window.DataPage.all() || []).length;
}"""

def try_join(page):
    page.goto(URL)
    page.wait_for_timeout(1500)
    page.locator("#mc-multi").click(timeout=5000)
    page.wait_for_timeout(500)
    page.locator("#mp-name").fill(NAME)
    page.locator("#mp-tab-join").click()
    page.locator("#mp-code").fill(CODE)
    page.locator("#mp-btn-join").click()
    log("尝试加入房间 %s" % CODE)
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

def play_one_hand(page, deadline):
    """等待并打完 1 手（简单策略），返回结算文本"""
    acted = 0
    while time.time() < deadline:
        if visible(page, "#overlay:not(.hidden)"):
            ov = ""
            try:
                ov = page.locator("#overlay-body").text_content() or ""
            except Exception:
                pass
            log("结算弹层: %s" % ov[:180])
            return ov
        if visible(page, "#action-controls"):
            acted += 1
            if acted == 1:
                shot(page, "r3_03_my_turn")
            call_btn = page.locator("#btn-checkcall").text_content() or ""
            if "过牌" in call_btn:
                page.locator("#btn-checkcall").click()
                log("行动#%d: 过牌" % acted)
            else:
                amt = "".join(ch for ch in call_btn if ch.isdigit())
                if amt and int(amt) <= 120:
                    page.locator("#btn-checkcall").click()
                    log("行动#%d: 跟注 %s" % (acted, amt))
                else:
                    page.locator("#btn-fold").click(timeout=2000)
                    log("行动#%d: 弃牌 (要跟 %s)" % (acted, amt))
            page.wait_for_timeout(800)
        page.wait_for_timeout(1000)
    return ""

def main():
    from playwright.sync_api import sync_playwright
    result = {"ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # ---- 入座（20s 重试 ×3）----
        mode = "mp"
        joined = False
        for attempt in range(1, 4):
            if try_join(page):
                joined = True
                log("第 %d 次尝试入座成功" % attempt)
                break
            if attempt < 3:
                log("等 20 秒后重试…")
                page.wait_for_timeout(20000)
        if joined:
            page.wait_for_timeout(800)
            shot(page, "r3_01_lobby")
            page.locator("#mp-btn-ready").click()
            log("已点准备，等开局…")
            for i in range(120):
                if page.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                    break
                page.wait_for_timeout(1000)
            page.wait_for_timeout(1500)
            probe1 = page.evaluate(COACH_PROBE)
            log("右栏探针(进桌): %s" % json.dumps(probe1, ensure_ascii=False))
            shot(page, "r3_02_table")
            ov = play_one_hand(page, time.time() + 60 * 6)
            probe2 = page.evaluate(COACH_PROBE)
            log("右栏探针(1手后): %s" % json.dumps(probe2, ensure_ascii=False))
            shot(page, "r3_04_after_hand")
            result["coach_probe_entry"] = probe1
            result["coach_probe_after_hand"] = probe2
            result["showdown_text"] = ov[:400]
        else:
            mode = "solo-fallback"
            log("多人入座失败 ×3，退回单机模式验证数据页")
            page.goto(URL)
            page.wait_for_timeout(1200)
            try:
                page.locator("#mc-solo").click(timeout=4000)
                play_one_hand(page, time.time() + 60 * 4)
            except Exception:
                log("单机入口异常: %s" % traceback.format_exc()[-200:])

        # ---- 塞合成牌谱（独立于对局，验证渲染边界）----
        synth_n = -1
        try:
            page.goto(URL)
            page.wait_for_timeout(1200)
            synth_n = page.evaluate(SYNTH_JS)
            log("合成牌谱已塞入，当前记录数=%s" % synth_n)
        except Exception:
            log("塞合成牌谱失败: %s" % traceback.format_exc()[-300:])
        result["synth_records"] = synth_n

        # ---- 数据分析页：展开全部牌谱 → dump ----
        dump_text = ""
        try:
            page.locator("#mc-data").click(timeout=5000)
            page.wait_for_timeout(1200)
            page.evaluate(
                "document.querySelectorAll('#data-body .data-hand').forEach(function(d){d.open=true})")
            page.wait_for_timeout(400)
            shot(page, "r3_05_data_expanded")
            dump_text = page.evaluate(
                "Array.from(document.querySelectorAll('#data-body .data-hand'))" +
                ".map(function(d){return d.innerText}).join('\\n==========\\n')")
            stats = page.evaluate(
                "JSON.stringify((function(){const D=window.DataPage;return D.stats(D.all())})())")
            log("数据页 stats: %s" % stats)
            result["data_stats"] = json.loads(stats)
        except Exception:
            log("数据页展开失败: %s" % traceback.format_exc()[-300:])
        result["dump"] = dump_text
        with open(os.path.join(OUT, "r3_dump.txt"), "w", encoding="utf-8") as f:
            f.write(dump_text or "(empty)")

        # ---- 自动断言 ----
        acts_joined = "\n".join(re.findall(r"(?:翻前|翻牌|转牌|河牌|摊牌)[^\n]*", dump_text or ""))
        checks = {
            "no_latin_action_tokens": not re.search(r"\b(fold|check|call|raise)\b", acts_joined),
            "has_call_increment": bool(re.search(r"跟注 \d+", acts_joined)),
            "has_raise_to": bool(re.search(r"加注到 \d+", acts_joined)),
            "has_check_plain": bool(re.search(r"过牌(?![ \d])", acts_joined)),
            "real_merge_710": "主池+边池1（共 710）" in (dump_text or ""),
            "synth_merge_420": "主池+边池1（共 420）" in (dump_text or ""),
            "has_split_mark": "（平分）" in (dump_text or ""),
            "hero_name_clean": "呜帕呜帕（你）" not in (dump_text or ""),
        }
        result["checks"] = checks
        result["mode"] = mode
        result["js_errors"] = errors[:10]
        result["ok"] = joined or mode == "solo-fallback"
        log("断言: %s" % json.dumps(checks, ensure_ascii=False))

        json.dump(result, open(os.path.join(OUT, "r3_result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        browser.close()

if __name__ == "__main__":
    main()
