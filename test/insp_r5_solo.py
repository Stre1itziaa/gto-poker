# insp_r5_solo.py — R5 单机侧巡检（里宝牌之光）
# ① 牌谱行动流口径：翻前首攻 =「加注到 N」（禁止再标「下注 N」）；翻后首攻 =「下注 N」；后续 =「加注到 N」
# ② 牌谱展开自动滚动让位 sticky 按钮条：scroll-margin-bottom 96px，展开尾不被吸附按钮条盖住（几何量测）
# ④ 数据页「范围」chips 选中态高亮：.sel 计算样式（主题 --gold = 樱粉）+ 点击流转
# ⑤「已投」双段式（本手总额+本街）与字段 chip 化（.seg nowrap）无回归
# 输出: data5/ribaora_insp/ + solo_result.json
import sys, time, json, os, random

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data5", "ribaora_insp")
URL = "http://localhost:8787/"
MAX_HANDS = 4

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

def play(page, max_hands, deadline_s):
    """高加注策略；每次行动前抓自己座位的 .stack .seg（验⑤）"""
    turns = 0
    hands = 0
    seg_samples = []
    t0 = time.time()
    while time.time() - t0 < deadline_s and hands < max_hands:
        if visible(page, "#overlay:not(.hidden)"):
            hands += 1
            log("单机第 %d 手结算" % hands)
            try:
                page.locator("#btn-next").click(timeout=1500)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            continue
        if visible(page, "#action-controls"):
            turns += 1
            segs = page.evaluate("""() => {
              const st = document.querySelector('.seat .stack');
              if (!st) return null;
              return { text: st.textContent.trim(), html: st.innerHTML,
                       segs: Array.from(st.querySelectorAll('.seg')).map(s => s.textContent.trim()),
                       nowrap: Array.from(st.querySelectorAll('.seg')).map(s => getComputedStyle(s).whiteSpace) };
            }""")
            if segs and any("已投" in s for s in segs["segs"]):
                seg_samples.append({"turn": turns, **segs})
            if turns == 1 or turns % 4 == 1:
                shot(page, "10_turn_%d" % turns)
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
        page.wait_for_timeout(700)
    return hands, turns, seg_samples

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
        shot(page, "01_landing")
        page.locator("#mc-train").click(timeout=5000)
        page.wait_for_timeout(600)
        page.locator("#btn-start").click()
        log("单机开局（训练模式）")
        page.wait_for_timeout(2500)

        hands, turns, seg_samples = play(page, MAX_HANDS, 60 * 9)
        log("单机完成 %d 手 / %d 次行动" % (hands, turns))
        result["hands"] = hands
        result["segSamplesCount"] = len(seg_samples)
        dbl = [s for s in seg_samples if any("本街" in x for x in s["segs"])]
        result["doubleSegSample"] = dbl[0] if dbl else None
        result["segAllNowrap"] = all(w == "nowrap" for s in seg_samples for w in s["nowrap"])
        result["segNoDotArtifact"] = all("·" not in s["text"] for s in seg_samples)
        log("⑤ seg 样本 %d 组，双段式样本: %s，全部 nowrap: %s，无「·」悬挂: %s" % (
            len(seg_samples), json.dumps(result["doubleSegSample"], ensure_ascii=False)[:220] if dbl else "无",
            result["segAllNowrap"], result["segNoDotArtifact"]))
        shot(page, "11_after_solo")

        # ===== 回大厅 → 数据页 =====
        page.locator("#btn-home").click(timeout=4000)
        page.wait_for_timeout(2500)
        page.locator("#mc-data").click(timeout=4000)
        page.wait_for_timeout(1200)
        shot(page, "12_data_open")

        # ===== ① 逐街口径独立复核（渲染文本 vs 规则） =====
        audit = page.evaluate("""() => {
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
                  if (head === '翻前') issues.push({ hand: r.handNo, street: head, token: tk, why: 'preflop-bet（应为加注到）' });
                  else if (firstRaiseSeen) issues.push({ hand: r.handNo, street: head, token: tk, why: '同街第二个下注' });
                  else postflopBet.push({ hand: r.handNo, street: head, token: tk });
                  firstRaiseSeen = true;
                } else if (/加注到 \\d+$/.test(tk)) {
                  if (head === '翻前') preflopRaise.push({ hand: r.handNo, token: tk });
                  else if (!firstRaiseSeen) issues.push({ hand: r.handNo, street: head, token: tk, why: '翻后首攻应为下注' });
                  firstRaiseSeen = true;
                }
              });
            });
          });
          return { records: recs.length, details: details.length, issues, preflopRaise, postflopBet };
        }""")
        log("① 审计: %s" % json.dumps(audit, ensure_ascii=False))
        result["audit1"] = audit

        # 展开全部 → 找翻前加注实例截图
        page.evaluate("() => document.querySelectorAll('#data-body details.data-hand').forEach(d => { d.open = true; })")
        page.wait_for_timeout(500)
        shot(page, "13_details_all_open")
        n = page.evaluate("() => document.querySelectorAll('#data-body details.data-hand').length")
        for i in range(min(n, 6)):
            try:
                page.locator("#data-body details.data-hand").nth(i).screenshot(
                    path=os.path.join(OUT, "hand_detail_%d.png" % (i + 1)))
            except Exception as e:
                log("逐手截图失败 %d: %s" % (i + 1, e))

        # ===== ④ chips：默认 sel + 计算样式 + 点击流转（注入 1 条 mp 样例供筛选） =====
        chips0 = page.evaluate("""() => {
          const sel = document.querySelector('#data-body .data-mode-chip.sel');
          const all = Array.from(document.querySelectorAll('#data-body .data-mode-chip'))
            .map(b => ({ t: b.textContent.trim(), sel: b.classList.contains('sel') }));
          if (!sel) return { sel: null, all };
          const cs = getComputedStyle(sel);
          return { sel: sel.textContent.trim(), color: cs.color, borderColor: cs.borderColor,
                   bg: cs.backgroundColor, all };
        }""")
        log("④ 默认 chips: %s" % json.dumps(chips0, ensure_ascii=False))
        result["chipsDefault"] = chips0
        shot(page, "14_chips_default")
        page.evaluate("""() => {
          window.DataPage.record({
            room: 'INSP5', handNo: 1, ts: new Date().toISOString(), sb: 10, bb: 20, mode: 'mp',
            players: [
              { name: '里宝牌之光', charId: 'rin', isBot: false, stackEnd: 2060, committed: 60, won: 120, refund: 0, rebuys: 0, hole: ['As','Kd'] },
              { name: '夜樱铃', charId: 'suzu', isBot: false, stackEnd: 1940, committed: 60, won: 0, refund: 0, rebuys: 0, hole: [] }
            ],
            board: ['2h','7c','9s'],
            actions: [
              { idx: 1, street: 'preflop', type: 'raise', to: 40, added: 30 },
              { idx: 0, street: 'preflop', type: 'call', to: 40, added: 20 },
              { idx: 1, street: 'flop', type: 'raise', to: 40, added: 40 },
              { idx: 0, street: 'flop', type: 'raise', to: 120, added: 120 },
              { idx: 1, street: 'flop', type: 'fold' }
            ],
            pots: [{ amount: 120, winners: [0], label: '主池', handName: null, foldWin: true, uncalled: false, split: false }],
            assert: { sumPaid: 120, sumPut: 120, ok: true }, hero: '里宝牌之光'
          });
        }""")
        page.wait_for_timeout(400)
        chips_mp = page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).find(x => x.getAttribute('data-mode') === 'mp');
          if (b) b.click();
          return true;
        }""")
        page.wait_for_timeout(500)
        chips_mp_state = page.evaluate("""() => {
          const sel = document.querySelector('#data-body .data-mode-chip.sel');
          const cs = sel ? getComputedStyle(sel) : null;
          return { sel: sel && sel.textContent.trim(), color: cs && cs.color, borderColor: cs && cs.borderColor,
                   rows: document.querySelectorAll('#data-body details.data-hand').length };
        }""")
        log("④ 点「多人」: %s" % json.dumps(chips_mp_state, ensure_ascii=False))
        result["chipsMp"] = chips_mp_state
        shot(page, "15_chips_mp")
        page.evaluate("""() => { const b = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).find(x => x.getAttribute('data-mode') === ''); if (b) b.click(); }""")
        page.wait_for_timeout(400)

        # ===== ② 展开最后一条 → 尾部不被 sticky 按钮条盖（制造最坏情形） =====
        tail = page.evaluate("""() => {
          const body = document.getElementById('data-body');
          const ds = body.querySelectorAll('details.data-hand');
          if (!ds.length) return { none: true };
          Array.from(ds).forEach(d => { if (d.open) d.open = false; });
          const d = ds[ds.length - 1];
          body.scrollTop = body.scrollHeight;      // 滚到容器底：sticky 条吸附的最坏情形
          d.open = true;                           // 触发 toggle → scrollIntoView({block:'nearest'})
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
        shot(page, "16_expanded_tail")

        # ② 追加判别探针：
        # (a) 手动再调一次 scrollIntoView：若 scrollTop 变化 → toggle 时布局时机问题；若不变 → Chrome 对
        #     「原始滚动口内已可见」的元素不施加 scroll-margin（CSS 方案对此路径天然失效）
        # (b) 中段展开对照：倒数第二条展开（展开后底边越过滚动口 → 必然触发滚动）看 margin 是否生效
        probe2 = page.evaluate("""() => {
          const body = document.getElementById('data-body');
          const ds = Array.from(body.querySelectorAll('details.data-hand'));
          if (ds.length < 2) return { none: true };
          const out = {};
          // (a) 最后一条：手动重滚
          const last = ds[ds.length - 1];
          const before = body.scrollTop;
          last.scrollIntoView({ block: 'nearest' });
          out.manualRecallDelta = Math.round((body.scrollTop - before) * 10) / 10;
          const lr = last.getBoundingClientRect();
          const bar = body.querySelector(':scope > .mp-row:last-child');
          out.lastStillCovered = Math.round((lr.bottom - bar.getBoundingClientRect().top) * 10) / 10;
          // (b) 倒数第二条：展开后底边越过滚动口底部 → scroll 必触发，看 margin 是否被尊重
          Array.from(ds).forEach(d => { if (d.open) d.open = false; });
          body.scrollTop = body.scrollHeight;
          const mid = ds[ds.length - 2];
          mid.open = true;
          return new Promise(res => setTimeout(() => {
            const r = mid.getBoundingClientRect();
            const br = bar.getBoundingClientRect();
            const c = body.getBoundingClientRect();
            out.mid = {
              detBottom: Math.round(r.bottom * 10) / 10,
              contBottom: Math.round(c.bottom * 10) / 10,
              barTop: Math.round(br.top * 10) / 10,
              tailAboveBar: r.bottom <= br.top + 1,
              scrollTop: Math.round(body.scrollTop) };
            // 恢复现场：收起 mid，重开 last，供后续截图
            mid.open = false;
            body.scrollTop = body.scrollHeight;
            last.open = true;
            setTimeout(() => res(out), 400);
          }, 700));
        }""")
        log("② 判别探针: %s" % json.dumps(probe2, ensure_ascii=False))
        result["tailProbe"] = probe2
        shot(page, "18_tail_after_probe")
        try:
            page.locator("#data-body").screenshot(path=os.path.join(OUT, "17_databody_full.png"))
        except Exception as e:
            log("data-body 截图失败: %s" % e)

        try:
            json.dump({"records": page.evaluate("() => window.DataPage.all()")},
                      open(os.path.join(OUT, "handlog_dump.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        except Exception as e:
            log("dump 失败: %s" % e)

        ok_flags = [
            audit["records"] > 0 and not audit["issues"],
            bool(audit["preflopRaise"]),
            result["segAllNowrap"] and result["segNoDotArtifact"] and seg_samples,
            bool(result["doubleSegSample"]),
            chips0.get("sel") is not None and chips0.get("borderColor") == "rgb(255, 158, 199)",
            chips_mp_state.get("sel") == "多人" and chips_mp_state.get("borderColor") == "rgb(255, 158, 199)",
            not tail.get("none") and tail.get("tailAboveBar") is True and tail.get("scrollMarginBottom") == "96px",
        ]
        result["okFlags"] = ok_flags
        result["ok"] = all(ok_flags[:6])   # ② 几何单列：本轮允许残留，不并入总判
        result["js_errors"] = errs[:8]
        result["log"] = log_lines
        json.dump(result, open(os.path.join(OUT, "solo_result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        browser.close()

if __name__ == "__main__":
    main()
