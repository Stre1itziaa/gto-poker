# insp_r5b_next.py — R5 修复③ 严格版（里宝牌之光）：房主无响应场景下的 5s 恢复
# 与 insp_r5_next 的区别：房主即使关掉自动续局，收到客人 {t:'next'} 仍会「代点」自己的按钮立即开局，
# 导致采样窗口被污染。本脚本在房主页面用 document 捕获级拦截 #btn-next 点击（stopPropagation），
# 等价于「房主掉线/挂起不处理请求」；验证 5s 恢复与恢复后可重发，再解除拦截让房主正常推进打满 3 手。
# 判据：
#   a) 点击后 ≤0.5s 按钮禁用且文案「已请求，等待房主开下一手…」
#   b) 2s / 4s 时仍禁用（不会提前恢复）
#   c) 4.5s~6.5s 之间恢复可点且弹层全程未关（房主 __swallowed 计数证明请求已送达但被吞）
#   d) 恢复后再次点击 → 再次禁用「已请求」（可重发）
#   e) 解除拦截后再点 → 房主代点生效、弹层收起（链路仍通，无回归）
# 附带：① MP 牌谱翻前「加注到 N」实例（真实多人局）+ ④ chips sel 高亮 + ② 尾部几何
# 输出: data5/ribaora_next2/ + next_result.json
import sys, time, json, os, random

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data5", "ribaora_next2")
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

def gbtn(page):
    return page.evaluate("""() => {
      const b = document.getElementById('btn-next');
      const ov = document.getElementById('overlay');
      return b ? { text: b.textContent.trim(), disabled: b.disabled,
                   overlayOpen: ov && !ov.classList.contains('hidden') } : null;
    }""")

def block_host(ph):
    return ph.evaluate("""() => {
      if (window.__eat) return window.__swallowed || 0;
      window.__eat = function (e) {
        if (e.target && e.target.id === 'btn-next') {
          e.stopPropagation();
          window.__swallowed = (window.__swallowed || 0) + 1;
        }
      };
      document.addEventListener('click', window.__eat, true);
      window.__swallowed = 0;
      return 0;
    }""")

def unblock_host(ph):
    return ph.evaluate("""() => {
      if (window.__eat) { document.removeEventListener('click', window.__eat, true); window.__eat = null; }
      return window.__swallowed || 0;
    }""")

def swallowed(ph):
    return ph.evaluate("() => window.__swallowed || 0")

def play(page, max_hands, deadline_s, on_first_overlay=None):
    """能加注就加注；返回 (见到的弹层数, 第一次弹层时 on_first_overlay() 的返回)"""
    hands = 0
    turns = 0
    first_ret = None
    t0 = time.time()
    while time.time() - t0 < deadline_s and hands < max_hands:
        if visible(page, "#overlay:not(.hidden)"):
            hands += 1
            log("MP 第 %d 手结算" % hands)
            if hands == 1 and on_first_overlay is not None:
                first_ret = on_first_overlay()
                if first_ret.get("stop"):
                    return hands, first_ret
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
            if random.random() < 0.55 and visible(page, "#btn-raise"):
                try:
                    presets = page.locator("#presets button")
                    n = presets.count()
                    presets.nth(min(1, n - 1)).click()
                    page.wait_for_timeout(150)
                    page.locator("#btn-raise").click(timeout=2500)
                    log("行动#%d: 加注" % turns)
                    page.wait_for_timeout(700)
                    continue
                except Exception:
                    pass
            try:
                call_btn = page.locator("#btn-checkcall").text_content() or ""
                if "过牌" in call_btn:
                    page.locator("#btn-checkcall").click(timeout=2500)
                    log("行动#%d: 过牌" % turns)
                else:
                    amt = "".join(ch for ch in call_btn if ch.isdigit())
                    if amt and int(amt) <= 160:
                        page.locator("#btn-checkcall").click(timeout=2500)
                        log("行动#%d: 跟注 %s" % (turns, amt))
                    else:
                        try:
                            page.locator("#btn-fold").click(timeout=2500)
                            log("行动#%d: 弃牌(要跟%s)" % (turns, amt))
                        except Exception:
                            log("行动#%d: 点击落空（手牌已切换），跳过" % turns)
            except Exception:
                log("行动#%d: 控件消失（手牌已切换），跳过" % turns)
            page.wait_for_timeout(600)
        page.wait_for_timeout(500)
    return hands, first_ret

def main():
    from playwright.sync_api import sync_playwright
    result = {"ok": False}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        errsH, errsG = [], []

        # ---- 房主页（独立 context，避免与客人共 localStorage） ----
        ctxH = browser.new_context(viewport={"width": 1280, "height": 800})
        ph = ctxH.new_page()
        ph.on("pageerror", lambda e: errsH.append(str(e)))
        ph.goto(URL); ph.wait_for_timeout(1500)
        ph.locator("#mc-multi").click(); ph.wait_for_timeout(500)
        try:
            ph.locator("#mp-name").fill("R5b无自动房主")
        except Exception:
            pass
        ph.locator("#mp-btn-create").click(); ph.wait_for_timeout(800)
        try:
            ph.locator("#auto-next").uncheck(timeout=2000)
            log("房主 AUTO_NEXT=off")
        except Exception as e:
            log("AUTO_NEXT_WARN=%s" % e)
        code = ""
        for _ in range(30):
            code = (ph.locator("#mp-room-code").text_content() or "").strip()
            if code and "-" not in code:
                break
            ph.wait_for_timeout(500)
        log("隔离房 code=%s" % code)

        # ---- 客人页 ----
        ctxG = browser.new_context(viewport={"width": 1600, "height": 900})
        pg = ctxG.new_page()
        pg.on("pageerror", lambda e: errsG.append(str(e)))
        pg.on("console", lambda m: errsG.append(m.text) if m.type == "error" else None)
        pg.goto(URL); pg.wait_for_timeout(1200)
        pg.locator("#mc-multi").click(); pg.wait_for_timeout(500)
        pg.locator("#mp-name").fill("里宝牌之光R5b")

        joined = False
        for attempt in range(1, 4):
            pg.locator("#mp-tab-join").click()
            pg.locator("#mp-code").fill(code)
            pg.locator("#mp-btn-join").click()
            log("第 %d 次点击加入 %s" % (attempt, code))
            for i in range(10):
                if visible(pg, "#mp-lobby") and not pg.locator("#mp-lobby").is_hidden():
                    joined = True; break
                pg.wait_for_timeout(1000)
            if joined: break
            pg.wait_for_timeout(20000)
        if not joined:
            result.update({"ok": False, "reason": "join failed", "log": log_lines})
            json.dump(result, open(os.path.join(OUT, "next_result.json"), "w", encoding="utf-8"), ensure_ascii=False)
            browser.close()
            return

        pg.locator("#mp-btn-ready").click()
        log("已准备，等房主开局…")
        for i in range(120):
            if pg.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                break
            pg.wait_for_timeout(1000)
        pg.wait_for_timeout(1500)
        log("已进牌桌")

        # ===== 第 1 手：加注打到结算 → 拦截房主 → ③ 全时序 =====
        def first_overlay_seq():
            pg.wait_for_timeout(2500)   # 静置：房主不自动续
            still = visible(pg, "#overlay:not(.hidden)")
            log("静置 2.5s 弹层仍在: %s" % still)
            shot(pg, "20_overlay_waiting")
            block_host(ph)
            log("已拦截房主 #btn-next（模拟房主无响应）")

            pre = gbtn(pg)
            t0 = time.time()
            pg.locator("#btn-next").click()
            samples = []
            recovered_at = None
            while time.time() - t0 < 8.0:
                st = gbtn(pg) or {"gone": True}
                samples.append({"t": round(time.time() - t0, 2), **st})
                if recovered_at is None and st.get("disabled") is False and \
                   "已请求" not in st.get("text", "") and st.get("overlayOpen"):
                    recovered_at = round(time.time() - t0, 2)
                    shot(pg, "22_btn_recovered")
                    break
                pg.wait_for_timeout(150)
            shot(pg, "21_btn_requested")
            sw = swallowed(ph)
            log("房主吞掉请求数: %s" % sw)

            disabled_seen = [s for s in samples if s.get("disabled") and "已请求" in s.get("text", "")]
            still_disabled_2s = any(s["t"] >= 1.8 and s["t"] <= 2.6 and s.get("disabled") for s in samples)
            still_disabled_4s = any(s["t"] >= 3.8 and s["t"] <= 4.6 and s.get("disabled") for s in samples)
            overlay_kept = all(s.get("overlayOpen", False) for s in samples if "overlayOpen" in s)
            rerequest = None
            if recovered_at is not None:
                pg.locator("#btn-next").click()
                pg.wait_for_timeout(250)
                rerequest = gbtn(pg)
                shot(pg, "23_btn_rerequested")
                log("恢复后再次点击: %s" % json.dumps(rerequest, ensure_ascii=False))
            sw2 = swallowed(ph)

            seq = {
                "overlayStays": still, "pre": pre,
                "firstDisabled": disabled_seen[0] if disabled_seen else None,
                "stillDisabledAt2s": still_disabled_2s, "stillDisabledAt4s": still_disabled_4s,
                "recoveredAt": recovered_at, "overlayKeptOpen": overlay_kept,
                "hostSwallowed": [sw, sw2], "reRequest": rerequest,
                "samples": samples[:70],
            }
            seq["ok"] = bool(disabled_seen and disabled_seen[0]["t"] <= 0.6 and
                             still_disabled_2s and still_disabled_4s and
                             recovered_at and 4.5 <= recovered_at <= 6.5 and
                             overlay_kept and rerequest and rerequest.get("disabled") and
                             sw2 >= 2)
            log("③ 判定: %s" % json.dumps({k: v for k, v in seq.items() if k != "samples"}, ensure_ascii=False))
            # 等第二次请求的 5s 恢复定时器把按钮复活，再解除拦截并点击（确保点击真能发出）
            t2 = time.time()
            while time.time() - t2 < 8:
                st2 = gbtn(pg)
                if st2 and not st2.get("disabled"):
                    break
                pg.wait_for_timeout(200)
            log("第二次请求恢复耗时: %.1fs" % (time.time() - t2))
            unblock_host(ph)
            time.sleep(0.3)
            try:
                pg.locator("#btn-next").click(timeout=2000)
                log("解除拦截后再点「下一局」…")
            except Exception as e:
                log("解除后点击失败: %s" % e)
            t1 = time.time()
            advanced = False
            while time.time() - t1 < 8:
                if not visible(pg, "#overlay:not(.hidden)"):
                    advanced = True
                    break
                pg.wait_for_timeout(400)
            log("解除拦截后弹层收起（房主代点链路仍通）: %s" % advanced)
            seq["advancedAfterUnblock"] = advanced
            seq["ok"] = seq["ok"] and advanced
            if advanced:
                # 等新手牌真的发出来再回主循环，避免把同一弹层重复计数
                pg.wait_for_timeout(2500)
            return {"stop": False, "seq": seq}

        hands, first_ret = play(pg, 3, 60 * 10, on_first_overlay=first_overlay_seq)
        seq = (first_ret or {}).get("seq")
        result["requestCycle"] = seq
        log("MP 完成 %d 手" % hands)

        # ===== 回大厅 → 数据页：①④② =====
        try:
            pg.locator("#btn-home").click(timeout=4000)
            pg.wait_for_timeout(2500)
            pg.locator("#mc-data").click(timeout=4000)
            pg.wait_for_timeout(1200)
            shot(pg, "24_data_open")

            audit = pg.evaluate("""() => {
              const D = window.DataPage;
              const recs = D.all();
              const details = Array.from(document.querySelectorAll('#data-body details.data-hand'));
              const issues = [], preflopRaise = [], postflopBet = [];
              details.forEach(function (d, i) {
                const r = recs[i]; if (!r) return;
                d.querySelectorAll('.data-acts').forEach(function (ln) {
                  const head = (ln.querySelector('b') || {}).textContent || '';
                  const tokens = ln.textContent.replace(head, '').split('·').map(s => s.trim()).filter(Boolean);
                  let firstRaiseSeen = false;
                  tokens.forEach(function (tk) {
                    if (/下注 \\d+$/.test(tk)) {
                      if (head === '翻前') issues.push({ hand: r.handNo, street: head, token: tk, why: 'preflop-bet' });
                      else if (firstRaiseSeen) issues.push({ hand: r.handNo, street: head, token: tk, why: 'second-bet' });
                      else postflopBet.push({ hand: r.handNo, street: head, token: tk });
                      firstRaiseSeen = true;
                    } else if (/加注到 \\d+$/.test(tk)) {
                      if (head === '翻前') preflopRaise.push({ hand: r.handNo, token: tk });
                      else if (!firstRaiseSeen) issues.push({ hand: r.handNo, street: head, token: tk, why: 'flop-first-not-bet' });
                      firstRaiseSeen = true;
                    }
                  });
                });
              });
              return { records: recs.length, details: details.length, issues, preflopRaise, postflopBet };
            }""")
            log("① MP 审计: %s" % json.dumps(audit, ensure_ascii=False))
            result["audit1"] = audit

            pg.evaluate("() => document.querySelectorAll('#data-body details.data-hand').forEach(d => { d.open = true; })")
            pg.wait_for_timeout(500)
            shot(pg, "25_details_all_open")
            n = pg.evaluate("() => document.querySelectorAll('#data-body details.data-hand').length")
            for i in range(min(n, 6)):
                try:
                    pg.locator("#data-body details.data-hand").nth(i).screenshot(
                        path=os.path.join(OUT, "hand_detail_%d.png" % (i + 1)))
                except Exception as e:
                    log("逐手截图失败 %d: %s" % (i + 1, e))

            # ④ chips
            chips0 = pg.evaluate("""() => {
              const sel = document.querySelector('#data-body .data-mode-chip.sel');
              const all = Array.from(document.querySelectorAll('#data-body .data-mode-chip'))
                .map(b => ({ t: b.textContent.trim(), sel: b.classList.contains('sel') }));
              if (!sel) return { sel: null, all };
              const cs = getComputedStyle(sel);
              return { sel: sel.textContent.trim(), color: cs.color, borderColor: cs.borderColor, bg: cs.backgroundColor, all };
            }""")
            log("④ 默认 chips: %s" % json.dumps(chips0, ensure_ascii=False))
            result["chipsDefault"] = chips0
            shot(pg, "26_chips_default")
            pg.evaluate("""() => { const b = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).find(x => x.getAttribute('data-mode') === 'mp'); if (b) b.click(); }""")
            pg.wait_for_timeout(500)
            chips_mp = pg.evaluate("""() => { const sel = document.querySelector('#data-body .data-mode-chip.sel');
              const cs = sel ? getComputedStyle(sel) : null;
              return { sel: sel && sel.textContent.trim(), color: cs && cs.color, borderColor: cs && cs.borderColor,
                       rows: document.querySelectorAll('#data-body details.data-hand').length }; }""")
            log("④ 点「多人」: %s" % json.dumps(chips_mp, ensure_ascii=False))
            result["chipsMp"] = chips_mp
            shot(pg, "27_chips_mp")
            pg.evaluate("""() => { const b = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).find(x => x.getAttribute('data-mode') === ''); if (b) b.click(); }""")
            pg.wait_for_timeout(400)

            # ② 尾部
            tail = pg.evaluate("""() => {
              const body = document.getElementById('data-body');
              const ds = body.querySelectorAll('details.data-hand');
              if (!ds.length) return { none: true };
              Array.from(ds).forEach(d => { if (d.open) d.open = false; });
              const d = ds[ds.length - 1];
              body.scrollTop = body.scrollHeight;
              d.open = true;
              return new Promise(res => setTimeout(() => {
                const r = d.getBoundingClientRect();
                const c = body.getBoundingClientRect();
                const bar = body.querySelector(':scope > .mp-row:last-child');
                const br = bar ? bar.getBoundingClientRect() : null;
                res({ count: ds.length, detBottom: Math.round(r.bottom * 10) / 10,
                      contBottom: Math.round(c.bottom * 10) / 10,
                      barTop: br ? Math.round(br.top * 10) / 10 : null,
                      barHeight: br ? Math.round(br.height * 10) / 10 : null,
                      tailAboveBar: br ? r.bottom <= br.top + 1 : null,
                      tailVisible: r.bottom <= c.bottom + 1,
                      scrollMarginBottom: getComputedStyle(d).scrollMarginBottom,
                      scrollTop: Math.round(body.scrollTop) });
              }, 700));
            }""")
            log("② 尾部量测: %s" % json.dumps(tail, ensure_ascii=False))
            result["tailCheck"] = tail
            shot(pg, "28_expanded_tail")

            try:
                json.dump({"records": pg.evaluate("() => window.DataPage.all()")},
                          open(os.path.join(OUT, "handlog_dump.json"), "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
            except Exception as e:
                log("dump 失败: %s" % e)
        except Exception:
            import traceback
            result["dataErr"] = traceback.format_exc()[-500:]

        ok_flags = []
        if seq: ok_flags.append(seq.get("ok"))
        if "audit1" in result:
            ok_flags.append(result["audit1"]["records"] > 0 and not result["audit1"]["issues"] and bool(result["audit1"]["preflopRaise"]))
        if "chipsDefault" in result:
            ok_flags.append(chips0.get("borderColor") == "rgb(255, 158, 199)" and chips_mp.get("sel") == "多人")
        if "tailCheck" in result and not result["tailCheck"].get("none"):
            ok_flags.append(result["tailCheck"].get("tailAboveBar") is True and result["tailCheck"].get("scrollMarginBottom") == "96px")
        result["okFlags"] = ok_flags
        result["ok"] = bool(ok_flags) and all(bool(x) for x in ok_flags)
        result["js_errors"] = (errsG[:6] + ["HOST: " + e for e in errsH[:3]])
        result["log"] = log_lines
        json.dump(result, open(os.path.join(OUT, "next_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        browser.close()

if __name__ == "__main__":
    main()
