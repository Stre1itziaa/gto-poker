# insp_r5_next.py — R5 修复③ 主验证 + ①④② 多人侧旁证（里宝牌之光）
# ③「已请求，等待房主开下一手…」5s 无响应自动恢复可点：房主无自动续局（host_r5.py），
#   点「下一局」后逐 150ms 采样按钮态，应观察到 禁用(已请求) → ~5s 恢复可点 → 再点再次禁用（可重发）。
# ① MP 牌谱行动流：翻前首攻 =「加注到 N」（不是「下注 N」），翻后首攻 =「下注 N」。
# ④ 数据页 chips 选中态高亮（.sel 计算样式）。②展开尾部不被 sticky 条盖（几何量测）。
# 用法: python insp_r5_next.py <房码> <输出目录>
import sys, time, json, os, random

CODE = sys.argv[1]
OUT = sys.argv[2]
URL = "http://localhost:8787/"
NAME = "里宝牌之光R5"

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
    return page.evaluate("""() => {
      const b = document.getElementById('btn-next');
      return b ? { text: b.textContent.trim(), disabled: b.disabled } : null;
    }""")

def play_aggressive(page, t0, deadline_s, max_hands):
    """能加注就加注（保证翻前 raise 实例）；返回见到的弹层数"""
    hands = 0
    turns = 0
    first_overlay_done = [False]
    while time.time() - t0 < deadline_s and hands < max_hands:
        if visible(page, "#overlay:not(.hidden)"):
            hands += 1
            log("MP 第 %d 手结算" % hands)
            if hands == 1 and not first_overlay_done[0]:
                first_overlay_done[0] = True
                seq = verify_request_cycle(page)   # ★ 第一手结算做 ③ 全时序
                return hands, seq
            try:
                page.locator("#btn-next").click(timeout=1500)
                log("点「下一局」（请求房主）")
            except Exception:
                pass
            page.wait_for_timeout(1500)
            continue
        if visible(page, "#action-controls"):
            turns += 1
            if turns == 1 or turns % 4 == 1:
                shot(page, "30_turn_%d" % turns)
            if visible(page, "#btn-raise"):
                try:
                    presets = page.locator("#presets button")
                    n = presets.count()
                    presets.nth(min(1, n - 1)).click()
                    page.wait_for_timeout(150)
                    page.locator("#btn-raise").click()
                    log("行动#%d: 加注" % turns)
                    page.wait_for_timeout(700)
                    continue
                except Exception:
                    pass
            call_btn = page.locator("#btn-checkcall").text_content() or ""
            if "过牌" in call_btn:
                page.locator("#btn-checkcall").click()
                log("行动#%d: 过牌" % turns)
            else:
                amt = "".join(ch for ch in call_btn if ch.isdigit())
                if amt and int(amt) <= 200:
                    page.locator("#btn-checkcall").click()
                    log("行动#%d: 跟注 %s" % (turns, amt))
                else:
                    try:
                        page.locator("#btn-fold").click(timeout=1500)
                        log("行动#%d: 弃牌(要跟%s)" % (turns, amt))
                    except Exception:
                        page.locator("#btn-checkcall").click()
                        log("行动#%d: 跟大注 %s" % (turns, amt))
            page.wait_for_timeout(600)
        page.wait_for_timeout(500)
    return hands, None

def verify_request_cycle(page):
    """③ 全时序：点击 → 禁用(已请求) → ~5s 恢复可点 → 再点再次禁用。返回采样表与判定。"""
    page.wait_for_timeout(2500)   # 静置 2.5s：房主无自动续局，弹层应停着
    still = visible(page, "#overlay:not(.hidden)")
    log("静置 2.5s 弹层仍在（房主自动续局确已关）: %s" % still)
    pre = btn_state(page)
    log("点击前按钮: %s" % json.dumps(pre, ensure_ascii=False))
    shot(page, "20_overlay_waiting")

    t0 = time.time()
    page.locator("#btn-next").click()
    samples = []
    recovered_at = None
    rerequest = None
    while time.time() - t0 < 8.0:
        st = btn_state(page)
        if st is None:
            st = {"gone": True}
        samples.append({"t": round(time.time() - t0, 2), **st})
        if recovered_at is None and st.get("disabled") is False and "已请求" not in st.get("text", ""):
            recovered_at = round(time.time() - t0, 2)
            shot(page, "22_btn_recovered")
            break
        page.wait_for_timeout(150)
    shot(page, "21_btn_requested")

    if recovered_at is not None:
        page.locator("#btn-next").click()
        page.wait_for_timeout(200)
        rerequest = btn_state(page)
        shot(page, "23_btn_rerequested")
        log("恢复后再次点击: %s" % json.dumps(rerequest, ensure_ascii=False))

    disabled_seen = any(s.get("disabled") and "已请求" in s.get("text", "") for s in samples)
    still_disabled_1s = any(s["t"] <= 1.2 and s.get("disabled") for s in samples)
    ok = bool(disabled_seen and recovered_at and 4.5 <= recovered_at <= 6.5
              and still_disabled_1s and rerequest and rerequest.get("disabled"))
    seq = {"overlayStays": still, "pre": pre, "disabledSeen": disabled_seen,
           "stillDisabledAt1s": still_disabled_1s, "recoveredAt": recovered_at,
           "reRequest": rerequest, "samples": samples[:60], "ok": ok}
    log("③ 时序判定: %s" % json.dumps({k: v for k, v in seq.items() if k != "samples"}, ensure_ascii=False))
    return seq

def main():
    from playwright.sync_api import sync_playwright
    result = {"ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

        page.goto(URL); page.wait_for_timeout(1200)
        page.locator("#mc-multi").click(); page.wait_for_timeout(500)
        page.locator("#mp-name").fill(NAME)

        joined = False
        for attempt in range(1, 4):
            page.locator("#mp-tab-join").click()
            page.locator("#mp-code").fill(CODE)
            page.locator("#mp-btn-join").click()
            log("第 %d 次点击加入 %s" % (attempt, CODE))
            for i in range(10):
                if visible(page, "#mp-lobby") and not page.locator("#mp-lobby").is_hidden():
                    joined = True; break
                page.wait_for_timeout(1000)
            if joined: break
            page.wait_for_timeout(20000)   # 加入失败等 20 秒重试
        if not joined:
            result.update({"ok": False, "reason": "join failed", "log": log_lines})
            json.dump(result, open(os.path.join(OUT, "next_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
            return

        page.locator("#mp-btn-ready").click()
        log("已准备，等房主开局…")
        for i in range(120):
            if page.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                break
            page.wait_for_timeout(1000)
        page.wait_for_timeout(1500)
        log("已进牌桌")

        hands, seq = play_aggressive(page, time.time(), 60 * 10, 3)
        log("MP 完成 %d 手" % hands)
        result["requestCycle"] = seq

        # ===== 回大厅 → 数据页：①MP 行动流实例 + ④chips + ②尾部 =====
        try:
            page.locator("#btn-home").click(timeout=4000)
            page.wait_for_timeout(2200)
            page.locator("#mc-data").click(timeout=4000)
            page.wait_for_timeout(1200)
            shot(page, "24_data_open")

            audit = page.evaluate("""() => {
              const D = window.DataPage;
              const recs = D.all();
              const out = { records: recs.length };
              /* —— ① 逐街口径独立复核：翻前禁止「下注 N」，翻后首个 raise 必须「下注 N」，其余「加注到 N」 —— */
              const details = document.querySelectorAll('#data-body details.data-hand');
              const streetZh = { preflop: '翻前', flop: '翻牌', turn: '转牌', river: '河牌' };
              const issues = [], preflopRaiseHands = [], postflopBetHands = [];
              details.forEach(function (d, i) {
                const r = recs[i]; if (!r) return;
                const lines = d.querySelectorAll('.data-acts');
                lines.forEach(function (ln) {
                  const head = (ln.querySelector('b') || {}).textContent || '';
                  const txt = ln.textContent.replace(head, '');
                  const tokens = txt.split('·').map(s => s.trim()).filter(Boolean);
                  let firstRaiseSeen = false;
                  tokens.forEach(function (tk) {
                    if (/下注 \\d+$/.test(tk)) {
                      if (head === '翻前') issues.push({ hand: r.handNo, street: head, token: tk, why: 'preflop-bet' });
                      else if (firstRaiseSeen) issues.push({ hand: r.handNo, street: head, token: tk, why: 'second-bet' });
                      firstRaiseSeen = true;
                    } else if (/加注到 \\d+$/.test(tk)) {
                      if (head !== '翻前' && !firstRaiseSeen) issues.push({ hand: r.handNo, street: head, token: tk, why: 'flop-first-not-bet' });
                      firstRaiseSeen = true;
                      if (head === '翻前') preflopRaiseHands.push({ hand: r.handNo, token: tk });
                    }
                  });
                });
                if ((r.actions || []).some(a => a.street !== 'preflop' && a.type === 'raise')) postflopBetHands.push(r.handNo);
              });
              out.issues = issues;
              out.preflopRaiseInstance = preflopRaiseHands[0] || null;
              out.preflopRaiseCount = preflopRaiseHands.length;
              out.raiseToTokenSeen = d => d;
              out.anyRaiseTo = !!document.querySelector('#data-body .data-acts');
              return out;
            }""")
            # 展开含翻前加注实例的手并截图
            page.evaluate("""() => {
              const ds = document.querySelectorAll('#data-body details.data-hand');
              ds.forEach(function (d) {
                const b = d.querySelector('.data-acts b');
                const first = d.querySelector('.data-acts');
                d.open = true;
              });
            }""")
            page.wait_for_timeout(400)
            shot(page, "25_details_all_open")
            audit["preflopRaiseText"] = page.evaluate("""() => {
              const lines = Array.from(document.querySelectorAll('#data-body .data-acts'));
              const hit = lines.find(l => l.textContent.includes('翻前') && /加注到 \\d+/.test(l.textContent));
              return hit ? hit.textContent.trim() : null;
            }""")
            audit["postflopBetText"] = page.evaluate("""() => {
              const lines = Array.from(document.querySelectorAll('#data-body .data-acts'));
              const hit = lines.find(l => !l.textContent.includes('翻前') && /下注 \\d+/.test(l.textContent));
              return hit ? hit.textContent.trim() : null;
            }""")
            log("① 审计: %s" % json.dumps({k: audit[k] for k in ("records", "issues", "preflopRaiseInstance", "preflopRaiseCount", "preflopRaiseText", "postflopBetText")}, ensure_ascii=False))

            # ④ chips：默认 sel 计算样式
            chips = page.evaluate("""() => {
              const sel = document.querySelector('#data-body .data-mode-chip.sel');
              if (!sel) return { sel: null };
              const cs = getComputedStyle(sel);
              return { sel: sel.textContent.trim(), color: cs.color, borderColor: cs.borderColor,
                       bg: cs.backgroundColor, all: Array.from(document.querySelectorAll('#data-body .data-mode-chip'))
                         .map(b => ({ t: b.textContent.trim(), sel: b.classList.contains('sel') })) };
            }""")
            log("④ 默认 chips: %s" % json.dumps(chips, ensure_ascii=False))
            result["chipsDefault"] = chips
            shot(page, "26_chips_default")
            page.evaluate("""() => { const b = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).find(x => x.getAttribute('data-mode') === 'mp'); if (b) b.click(); }""")
            page.wait_for_timeout(400)
            chips_mp = page.evaluate("""() => { const sel = document.querySelector('#data-body .data-mode-chip.sel');
              return { sel: sel && sel.textContent.trim(), rows: document.querySelectorAll('#data-body details.data-hand').length }; }""")
            log("④ 点多人: %s" % json.dumps(chips_mp, ensure_ascii=False))
            shot(page, "27_chips_mp")

            # ② 展开最后一条 → 尾部不被 sticky 条盖
            tail = page.evaluate("""() => {
              const body = document.getElementById('data-body');
              const ds = body.querySelectorAll('details.data-hand');
              if (!ds.length) return { none: true };
              ds.forEach(d => { if (d.open) d.open = false; });
              const d = ds[ds.length - 1];
              body.scrollTop = body.scrollHeight;
              d.open = true;                       // 触发 toggle → scrollIntoView({block:'nearest'})
              return new Promise(res => setTimeout(() => {
                const r = d.getBoundingClientRect();
                const c = body.getBoundingClientRect();
                const bar = body.querySelector(':scope > .mp-row:last-child');
                const br = bar ? bar.getBoundingClientRect() : null;
                const ds2 = body.querySelectorAll('details.data-hand');
                res({ count: ds2.length, detBottom: Math.round(r.bottom * 10) / 10,
                      contBottom: Math.round(c.bottom * 10) / 10,
                      barTop: br ? Math.round(br.top * 10) / 10 : null,
                      tailAboveBar: br ? r.bottom <= br.top + 1 : null,
                      tailVisible: r.bottom <= c.bottom + 1,
                      scrollMarginBottom: getComputedStyle(d).scrollMarginBottom,
                      scrollTop: Math.round(body.scrollTop) });
              }, 700));
            }""")
            log("② 尾部量测: %s" % json.dumps(tail, ensure_ascii=False))
            result["tailCheck"] = tail
            shot(page, "28_expanded_tail")
            try:
                page.locator("#data-body").screenshot(path=os.path.join(OUT, "29_databody_full.png"))
            except Exception as e:
                log("data-body 截图失败: %s" % e)

            # 逐手详情截图（①截图证据）
            n = page.evaluate("() => document.querySelectorAll('#data-body details.data-hand').length")
            for i in range(min(n, 6)):
                try:
                    page.locator("#data-body details.data-hand").nth(i).screenshot(
                        path=os.path.join(OUT, "hand_detail_%d.png" % (i + 1)))
                except Exception as e:
                    log("逐手截图失败 %d: %s" % (i + 1, e))

            try:
                json.dump({"records": page.evaluate("() => window.DataPage.all()")},
                          open(os.path.join(OUT, "handlog_dump.json"), "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
            except Exception as e:
                log("dump 失败: %s" % e)

            result["audit1"] = {k: audit[k] for k in ("records", "issues", "preflopRaiseInstance", "preflopRaiseCount", "preflopRaiseText", "postflopBetText")}
        except Exception:
            import traceback
            result["dataErr"] = traceback.format_exc()[-500:]

        ok_flags = []
        if seq: ok_flags.append(seq.get("ok"))
        if "audit1" in result:
            ok_flags.append(result["audit1"]["records"] > 0 and not result["audit1"]["issues"])
        if "tailCheck" in result and not result["tailCheck"].get("none"):
            ok_flags.append(result["tailCheck"].get("tailAboveBar") is True)
        result["ok"] = all(bool(x) for x in ok_flags) and bool(ok_flags)
        result["js_errors"] = errs[:8]
        result["log"] = log_lines
        json.dump(result, open(os.path.join(OUT, "next_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        browser.close()

if __name__ == "__main__":
    main()
