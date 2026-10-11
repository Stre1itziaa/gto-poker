# insp_r5.py — R5（呜帕呜帕 第10轮·终验）三修复黑盒复检
# A. 客人点「下一局」→「已请求」态 5s 无响应自动恢复（隔离房：房主关自动续局 + 全程装死）
# B. 牌谱口径：翻前所有加注 = 「加注到 N」且翻前无「下注」；翻后街内首攻 = 「下注 N」、后续 = 「加注到 N」
#    —— 用 DataPage.all() 结构化 actions 按渲染规则复算期望文案，与 DOM innerText 逐条比对
# C. 展开牌谱 scrollIntoView({block:'nearest'}) + scroll-margin-bottom:96px：
#    真实点击 summary 展开，量测展开块尾部矩形 vs sticky 按钮条顶部矩形
# 用法: python insp_r5.py <输出目录=data5/wupa>
# 输出: <OUT>/r5_result.json + r5_*.png
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

def play_until(page, n_hands, deadline_s, tag_prefix):
    """简单策略打满 n_hands 手（与 mp_guest 同款），返回 (hands, turns)"""
    turns, hands = 0, 0
    deadline = time.time() + deadline_s
    while time.time() < deadline and hands < n_hands:
        if visible(page, "#overlay:not(.hidden)"):
            ov = ""
            try:
                ov = page.locator("#overlay-body").text_content() or ""
            except Exception:
                pass
            log("[%s] 结算弹层: %s" % (tag_prefix, ov[:120]))
            hands += 1
            if hands >= n_hands:
                break
            try:
                page.locator("#btn-next").click(timeout=1500)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            continue
        if visible(page, "#action-controls"):
            turns += 1
            call_btn = page.locator("#btn-checkcall").text_content() or ""
            if random.random() < 0.15 and visible(page, "#btn-raise"):
                try:
                    presets = page.locator("#presets button")
                    n = presets.count()
                    if n > 0:
                        presets.nth(min(1, n - 1)).click()
                        page.wait_for_timeout(200)
                        page.locator("#btn-raise").click()
                        log("[%s] 行动#%d: 加注" % (tag_prefix, turns))
                        page.wait_for_timeout(900)
                        continue
                except Exception:
                    pass
            if "过牌" in call_btn:
                page.locator("#btn-checkcall").click()
                log("[%s] 行动#%d: 过牌" % (tag_prefix, turns))
            else:
                amt = "".join(ch for ch in call_btn if ch.isdigit())
                if amt and int(amt) <= 120:
                    page.locator("#btn-checkcall").click()
                    log("[%s] 行动#%d: 跟注 %s" % (tag_prefix, turns, amt))
                elif random.random() < 0.35:
                    page.locator("#btn-checkcall").click()
                    log("[%s] 行动#%d: 跟大注 %s" % (tag_prefix, turns, amt))
                else:
                    try:
                        page.locator("#btn-fold").click(timeout=2000)
                        log("[%s] 行动#%d: 弃牌 (要跟 %s)" % (tag_prefix, turns, amt))
                    except Exception:
                        page.locator("#btn-checkcall").click()
                        log("[%s] 行动#%d: 弃牌失败改跟注" % (tag_prefix, turns))
            page.wait_for_timeout(900)
        page.wait_for_timeout(1100)
    return hands, turns


def phase_a_request_recovery(p):
    """A. 隔离房：房主关自动续局且装死 → 客人点「下一局」→ 已请求 → 5s 自动恢复"""
    res = {}
    browser = p.chromium.launch(headless=True)
    host = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
    guest = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()

    # 房主页：建房 + 显式关自动续局，之后全程不碰
    host.goto(URL); host.wait_for_timeout(1500)
    host.locator("#mc-multi").click(); host.wait_for_timeout(500)
    host.locator("#mp-name").fill("R5无自动房主")
    host.locator("#mp-btn-create").click(); host.wait_for_timeout(800)
    try:
        host.locator("#auto-next").uncheck(timeout=2000)
        log("A: 房主自动续局已关")
    except Exception as e:
        log("A: 关自动续局异常: %s" % e)
    code = ""
    for _ in range(30):
        code = (host.locator("#mp-room-code").text_content() or "").strip()
        if code and "-" not in code:
            break
        host.wait_for_timeout(500)
    res["room"] = code
    log("A: 隔离房房码 %s" % code)

    # 客人页：加入 + 准备
    guest.goto(URL); guest.wait_for_timeout(1200)
    guest.locator("#mc-multi").click(); guest.wait_for_timeout(500)
    guest.locator("#mp-name").fill("呜帕·验恢复")
    guest.locator("#mp-tab-join").click()
    guest.locator("#mp-code").fill(code)
    guest.locator("#mp-btn-join").click()
    joined = False
    for _ in range(15):
        if visible(guest, "#mp-lobby") and not guest.locator("#mp-lobby").is_hidden():
            joined = True; break
        guest.wait_for_timeout(1000)
    if not joined:
        res.update({"okA": False, "reasonA": "guest join failed"})
        browser.close()
        return res
    guest.locator("#mp-btn-ready").click()
    log("A: 客人已准备，等自动开局…")

    started = False
    for _ in range(90):
        if guest.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
            started = True; break
        guest.wait_for_timeout(1000)
    if not started:
        res.update({"okA": False, "reasonA": "room never started"})
        browser.close()
        return res
    guest.wait_for_timeout(1800)
    log("A: 已进牌桌，打满 1 手到摊牌…")
    shot(guest, "r5_A0_table")
    h, t = play_until(guest, 1, 300, "A")
    res["handsPlayed"] = h
    if not visible(guest, "#overlay:not(.hidden)"):
        res.update({"okA": False, "reasonA": "no showdown overlay"})
        browser.close()
        return res

    guest.wait_for_timeout(2600)   # 静置 2.6s：房主装死，弹层应一直停着
    stays = visible(guest, "#overlay:not(.hidden)")
    res["overlayStaysNoAuto"] = bool(stays)
    log("A: 静置 2.6s 弹层仍在（房主确实不自动续）: %s" % stays)
    shot(guest, "r5_A1_overlay_waiting")

    # 核心：点「下一局」→ 已请求态
    guest.locator("#btn-next").click()
    guest.wait_for_timeout(150)
    st1 = guest.evaluate("""() => { const b = document.getElementById('btn-next');
      return { text: b.textContent.trim(), disabled: b.disabled }; }""")
    res["afterClick"] = st1
    log("A: 点击后按钮 %s" % json.dumps(st1, ensure_ascii=False))
    shot(guest, "r5_A2_requested")

    # 5s 无响应自动恢复：200ms 轮询，最长 7.5s
    t0 = time.time()
    recovered = None
    while time.time() - t0 < 7.5:
        s = guest.evaluate("""() => { const b = document.getElementById('btn-next');
          return { text: b.textContent.trim(), disabled: b.disabled }; }""")
        if not s["disabled"] and ("下一局" in s["text"]):
            recovered = time.time() - t0
            break
        guest.wait_for_timeout(200)
    res["recoveredAfterS"] = round(recovered, 2) if recovered is not None else None
    st2 = guest.evaluate("""() => { const b = document.getElementById('btn-next');
      return { text: b.textContent.trim(), disabled: b.disabled }; }""")
    res["afterRecover"] = st2
    log("A: 恢复耗时 %s s，按钮 %s" % (res["recoveredAfterS"], json.dumps(st2, ensure_ascii=False)))
    shot(guest, "r5_A3_recovered")

    # 恢复后可再次点击（幂等重发）
    guest.locator("#btn-next").click()
    guest.wait_for_timeout(150)
    st3 = guest.evaluate("""() => { const b = document.getElementById('btn-next');
      return { text: b.textContent.trim(), disabled: b.disabled }; }""")
    res["reRequest"] = st3
    log("A: 再次点击后按钮 %s" % json.dumps(st3, ensure_ascii=False))
    shot(guest, "r5_A4_rerequested")

    okA = bool(stays and st1["disabled"] and ("已请求" in st1["text"])
               and recovered is not None and 4.5 <= recovered <= 6.5
               and ("下一局" in st2["text"])
               and st3["disabled"] and ("已请求" in st3["text"]))
    res["okA"] = okA
    browser.close()
    return res


def phase_b_wording_occlusion(page):
    """B+C：单机补打 2 手 → 数据页口径双核对 + 尾部让位量测（在传入 page 上操作）"""
    res = {}
    # 单机训练补打 2 手（同一 localStorage 牌谱库）
    page.goto(URL); page.wait_for_timeout(1200)
    page.locator("#mc-train").click(timeout=5000)
    page.wait_for_timeout(600)
    page.locator("#btn-start").click(timeout=5000)
    page.wait_for_timeout(1800)
    h, t = play_until(page, 2, 300, "B")
    res["soloHands"] = h
    log("B: 单机补打 %d 手" % h)

    page.locator("#btn-home").click(timeout=5000)
    page.wait_for_timeout(2000)
    page.locator("#mc-data").click(timeout=5000)
    page.wait_for_timeout(1500)

    audit = page.evaluate("""() => {
      const D = window.DataPage; if (!D) return { module: false };
      const recs = D.all();
      const out = { module: true, recordCount: recs.length, hands: [] };
      const details = document.querySelectorAll('#data-body details.data-hand');
      out.detailCount = details.length;
      // 渲染规则复算（与 data.js R6-R4 口径一致）：翻前 betSeen=true；翻后街内首攻=下注，后续=加注到
      const expected = recs.map(function (r) {
        const streets = ['preflop', 'flop', 'turn', 'river'];
        const segs = {};
        streets.forEach(function (sName) {
          const seg = (r.actions || []).filter(function (a) { return a.street === sName; });
          if (!seg.length) return;
          let betSeen = (sName === 'preflop');
          segs[sName] = seg.map(function (a) {
            const nm = (r.players && r.players[a.idx] && r.players[a.idx].name) || ('P' + (a.idx + 1));
            let zh = ({fold:'弃牌', check:'过牌', call:'跟注', raise:'加注到'})[a.type] || a.type;
            let suffix = '';
            if (a.type === 'raise') {
              if (!betSeen) { zh = '下注'; betSeen = true; }
              suffix = ' ' + (a.to || '');
            } else if (a.type === 'call' && (a.added || a.to)) { suffix = ' ' + (a.added || a.to); }
            return nm + ' ' + zh + suffix;
          });
        });
        return segs;
      });
      // DOM 文本抽取
      details.forEach(function (d, i) {
        const t = d.innerText || '';
        const lines = {};
        Array.prototype.forEach.call(d.querySelectorAll('.data-acts'), function (ln) {
          const head = (ln.querySelector('b') || {}).textContent || '';
          lines[head] = (ln.textContent || '').replace(head, '');
        });
        out.hands.push({ i: i, summary: (d.querySelector('summary') || {}).textContent || '',
          text: t, streetLines: lines, expected: expected[i] || null });
      });
      return out;
    }""")
    log("B: 记录 %s 条 / 详情 %s 个" % (audit.get("recordCount"), audit.get("detailCount")))

    # 逐条口径核对
    nPreRaise = nPreBet = nPostBet = nPostRaise = violations = 0
    for hd in audit.get("hands", []):
        exp = hd.get("expected") or {}
        for street, acts in exp.items():
            domline = (hd.get("streetLines") or {}).get(
                {"preflop": "翻前", "flop": "翻牌", "turn": "转牌", "river": "河牌"}.get(street, street), "")
            for token in acts:
                is_raise = ("加注到" in token) or ("下注" in token)
                if is_raise:
                    if street == "preflop":
                        nPreRaise += 1
                        if "下注" in token:
                            violations += 1; hd.setdefault("viol", []).append("preflop下注: " + token)
                        elif token not in domline:
                            violations += 1; hd.setdefault("viol", []).append("preflop加注到缺失: " + token + " / 行=" + domline)
                    else:
                        if "下注" in token:
                            nPostBet += 1
                            if token not in domline:
                                violations += 1; hd.setdefault("viol", []).append("翻后下注缺失: " + token)
                        else:
                            nPostRaise += 1
                            if token not in domline:
                                violations += 1; hd.setdefault("viol", []).append("翻后加注到缺失: " + token)
        # 硬规则：翻前行里不允许出现「下注」
        pre = (hd.get("streetLines") or {}).get("翻前", "")
        if "下注" in pre:
            violations += 1; hd.setdefault("viol", []).append("翻前行含「下注」字样: " + pre)
    audit["counts"] = {"preflopRaise": nPreRaise, "postflopFirstBet": nPostBet,
                       "postflopLaterRaise": nPostRaise, "violations": violations}
    res["wording"] = {"counts": audit["counts"],
                      "viol": [v for hd in audit.get("hands", []) for v in hd.get("viol", [])]}
    log("B: 口径计数 %s" % json.dumps(audit["counts"], ensure_ascii=False))

    shot(page, "r5_B1_data")
    try:
        page.locator("#data-body").screenshot(path=os.path.join(OUT, "r5_B2_expanded.png"))
    except Exception:
        pass

    # C. 逐个展开（真实点击 summary → toggle → scrollIntoView），量测尾部 vs sticky 条
    n = audit.get("detailCount", 0)
    occ = []
    for i in range(n - 1, -1, -1):   # 从最底部手开始（最容易被盖）
        try:
            page.evaluate("() => { document.getElementById('data-body').scrollTop = 0; }")
            page.wait_for_timeout(200)
            page.locator("#data-body details.data-hand").nth(i).locator("summary").click()
            page.wait_for_timeout(800)
            m = page.evaluate("""(i) => {
              const body = document.getElementById('data-body');
              const d = document.querySelectorAll('#data-body details.data-hand')[i];
              const sticky = body.querySelector(':scope > .mp-row:last-child');
              const dr = d.getBoundingClientRect();
              const sr = sticky ? sticky.getBoundingClientRect() : null;
              const lastEl = d.lastElementChild;
              const lr = lastEl ? lastEl.getBoundingClientRect() : null;
              return { scrollMarginBottom: getComputedStyle(d).scrollMarginBottom,
                detailBottom: Math.round(dr.bottom), stickyTop: sr ? Math.round(sr.top) : null,
                lastLineBottom: lr ? Math.round(lr.bottom) : null,
                scrollTop: Math.round(body.scrollTop),
                bodyScrollHeight: body.scrollHeight, bodyClientHeight: body.clientHeight,
                open: d.open };
            }""", i)
            m["index"] = i
            m["overflow"] = m["bodyScrollHeight"] > m["bodyClientHeight"] + 2
            m["tailNotCovered"] = (m["stickyTop"] is None) or (m["detailBottom"] <= m["stickyTop"] + 2)
            m["lastLineNotCovered"] = (m["stickyTop"] is None) or (m["lastLineBottom"] is None) or (m["lastLineBottom"] <= m["stickyTop"] + 2)
            m["msb96"] = (m["scrollMarginBottom"] or "").strip() == "96px"
            occ.append(m)
            log("C: 手#%d 展开量测 %s" % (i + 1, json.dumps(m, ensure_ascii=False)))
            page.locator("#data-body details.data-hand").nth(i).screenshot(
                path=os.path.join(OUT, "r5_C_hand%d.png" % (i + 1)))
            page.locator("#data-body details.data-hand").nth(i).evaluate("el => el.open = false")
        except Exception as e:
            occ.append({"index": i, "error": str(e)[:200]})
            log("C: 手#%d 量测异常 %s" % (i + 1, e))
    res["occlusion"] = occ
    res["occlPass"] = bool(occ) and all(o.get("tailNotCovered") and o.get("lastLineNotCovered") and o.get("msb96")
                                        for o in occ if "error" not in o) and any("error" not in o for o in occ)
    shot(page, "r5_C_final_data")
    res["audit"] = {k: v for k, v in audit.items() if k != "hands"}
    res["handsText"] = [{"i": hd["i"], "summary": hd["summary"], "streetLines": hd["streetLines"],
                         "viol": hd.get("viol", [])} for hd in audit.get("hands", [])]
    return res


def main():
    from playwright.sync_api import sync_playwright
    result = {"ok": False}
    with sync_playwright() as p:
        try:
            result["phaseA"] = phase_a_request_recovery(p)
            log("A 结论: %s" % result["phaseA"].get("okA"))
        except Exception:
            result["phaseA"] = {"okA": False, "error": traceback.format_exc()[-600:]}
            log("A 异常: %s" % result["phaseA"]["error"])
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
            result["phaseB"] = phase_b_wording_occlusion(page)
            log("B/C 结论: wording violations=%s occlPass=%s" % (
                result["phaseB"]["wording"]["counts"]["violations"], result["phaseB"].get("occlPass")))
            browser.close()
        except Exception:
            result["phaseB"] = {"error": traceback.format_exc()[-600:]}
            log("B/C 异常: %s" % result["phaseB"]["error"])
    okA = result.get("phaseA", {}).get("okA", False)
    okB = result.get("phaseB", {}).get("wording", {}).get("counts", {}).get("violations") == 0 \
        and result.get("phaseB", {}).get("wording", {}).get("counts", {}).get("preflopRaise", 0) > 0
    okC = result.get("phaseB", {}).get("occlPass", False)
    result["ok"] = bool(okA and okB and okC)
    result["verdict"] = {"A_requestRecover": okA, "B_wording": okB, "C_occlusion": okC}
    json.dump(result, open(os.path.join(OUT, "r5_result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("R5_DONE verdict=%s" % json.dumps(result["verdict"]))
    return result


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            json.dump({"ok": False, "fatal": traceback.format_exc(), "log": log_lines},
                      open(os.path.join(OUT, "r5_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass
