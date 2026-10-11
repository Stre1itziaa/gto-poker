# insp_r4_solo.py — R4 单机侧巡检（里宝牌之光）：②③④⑤⑥
# ② 单机牌谱人名剥「（你）」（gto-name 未设 → 回退角色名剥后缀；设置后优先昵称）
# ③ 牌谱行动流口径：街内首个进攻=「下注 N」、其余=「加注到 N」、无「到→」、fold/check 无尾巴、call=本街增量
# ④ 数据页顶部「范围：全部/多人/单机」chips 按 mode 过滤
# ⑤ 无效过牌转弃：引擎级探针（独立 Table 实例，不碰在打的局）
# ⑥ 牌谱详情展开 scrollIntoView 到位（sticky 按钮条不再盖尾）
# 输出: data4/ribaora_insp/ + solo_result.json
import sys, time, json, os, random

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data4", "ribaora_insp")
URL = "http://localhost:8787/"
MAX_HANDS = 3

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

def play(page, max_hands, deadline_s, nickname_at_end=None):
    """加注偏高的简单策略；最后一手结算后若给 nickname 则先写 gto-name 再继续"""
    turns = 0
    hands = 0
    t0 = time.time()
    while time.time() - t0 < deadline_s and hands < max_hands:
        if visible(page, "#overlay:not(.hidden)"):
            hands += 1
            log("单机第 %d 手结算" % hands)
            if hands == max_hands - 1 and nickname_at_end:
                page.evaluate("n => localStorage.setItem('gto-name', n)", nickname_at_end)
                log("已写入 gto-name=%s（第 3 手验证昵称优先）" % nickname_at_end)
            try:
                page.locator("#btn-next").click(timeout=1500)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            continue
        if visible(page, "#action-controls"):
            turns += 1
            if turns == 1 or turns % 4 == 1:
                shot(page, "10_turn_%d" % turns)
            r = random.random()
            if r < 0.55 and visible(page, "#btn-raise"):
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
                if amt and int(amt) <= 160:
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
        page.wait_for_timeout(800)
    return hands, turns

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
        # 确保 gto-name 未设：验证「回退角色名仍剥（你）」路径
        page.evaluate("localStorage.removeItem('gto-name')")
        shot(page, "01_landing")
        page.locator("#mc-train").click(timeout=5000)
        page.wait_for_timeout(600)
        page.locator("#btn-start").click()
        log("单机开局（训练模式，默认桌位）")
        page.wait_for_timeout(2500)

        hands, turns = play(page, MAX_HANDS, 60 * 9, nickname_at_end="里宝牌之光R4")
        log("单机完成 %d 手 / %d 次行动" % (hands, turns))
        shot(page, "11_after_solo")

        # ===== ⑤ 引擎级探针：独立 Table，不碰在打的局 =====
        probe = page.evaluate("""() => {
          const out = {};
          try {
            const t = new window.Table({ seatCount: 2, sb: 10, bb: 20, startStack: 2000, runoutMode: true });
            t.startHand();
            const a = t.players[t.actorIdx];
            const la = t.legalActions(a.idx);
            out.preToCall = la.toCall;
            t.apply({ type: 'check' });              // 面对未跟平的注硬过牌 → 应自动转弃
            const last = t.actionHistory[t.actionHistory.length - 1];
            out.invalidCheck = { text: a.lastAction, histType: last.type,
                                 folded: a.folded, pot: t.potTotal(),
                                 stack: a.stack, committed: a.totalCommitted };
            // 合法过牌不应误伤
            const t2 = new window.Table({ seatCount: 2, sb: 10, bb: 20, startStack: 2000, runoutMode: true });
            t2.startHand();
            t2.apply({ type: 'call' });
            const bb2 = t2.players[t2.actorIdx];
            t2.apply({ type: 'check' });
            out.validCheckText = bb2.lastAction;
            // 街内首攻/再加注的现场文本（flop currentBet=0）
            const acts = t2.actionHistory.length;
            const t3 = new window.Table({ seatCount: 2, sb: 10, bb: 20, startStack: 2000, runoutMode: true });
            t3.startHand();
            t3.apply({ type: 'raise', to: 40 });
            const b3 = t3.players[t3.actorIdx];
            b3.spoke = false;
            t3.apply({ type: 'call' });
            t3._advancePhase();                       // 到翻牌
            const first = t3.players[t3.actorIdx];
            t3.apply({ type: 'raise', to: 60 });
            out.flopBetText = first.lastAction;
            const other = t3.players[t3.actorIdx];
            t3.apply({ type: 'raise', to: 180 });
            out.flopReraiseText = other.lastAction;
            out.preflopRaiseText = t3.actionHistory.filter(x => x.street === 'preflop').map(x => x.type);
          } catch (e) { out.error = String(e); }
          return out;
        }""")
        log("引擎探针: %s" % json.dumps(probe, ensure_ascii=False))
        result["probe"] = probe

        # ===== 回大厅 → 数据页 =====
        page.locator("#btn-home").click(timeout=4000)
        page.wait_for_timeout(2200)
        page.locator("#mc-data").click(timeout=4000)
        page.wait_for_timeout(1200)
        shot(page, "12_data_open")

        # ===== 注入一条多人样例（走 DataPage.record 公开接口，仅本机一次性浏览器）——验证 chips 的 mode 消费 =====
        page.evaluate("""() => {
          window.DataPage.record({
            room: 'VGFQYT', handNo: 1, ts: new Date().toISOString(), sb: 10, bb: 20, mode: 'mp',
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
        log("已注入 1 条多人样例记录（验证 chips mode 消费）")

        # ===== chips + 牌谱全文审计 =====
        audit = page.evaluate("""() => {
          const D = window.DataPage;
          const out = { chips: [] };
          document.querySelectorAll('#data-body .data-mode-chip').forEach(b => out.chips.push({
            label: b.textContent.trim(), mode: b.getAttribute('data-mode'), sel: b.classList.contains('sel') }));
          function rows() { return document.querySelectorAll('#data-body details.data-hand').length; }
          function statsLine() {
            const els = document.querySelectorAll('#data-body .data-stat b');
            return Array.from(els).map(e => e.textContent);
          }
          out.countAll = rows(); out.statsAll = statsLine();
          const texts = [];
          document.querySelectorAll('#data-body details.data-hand').forEach(d => { d.open = true; texts.push(d.innerText); });
          out.handTexts = texts;
          const mp = D.all().filter(r => r.mode === 'mp').length;
          const sp = D.all().filter(r => r.mode === 'sp').length;
          out.modeSplit = { mp: mp, sp: sp };
          return out;
        }""")
        log("chips: %s" % json.dumps(audit["chips"], ensure_ascii=False))
        log("全部=%s modeSplit=%s stats=%s" % (audit["countAll"], json.dumps(audit["modeSplit"]), json.dumps(audit["statsAll"])))

        # 点「多人」chip
        page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).find(x => x.getAttribute('data-mode') === 'mp');
          b.click();
        }""")
        page.wait_for_timeout(400)
        cnt_mp = page.evaluate("() => ({ rows: document.querySelectorAll('#data-body details.data-hand').length, sel: (document.querySelector('#data-body .data-mode-chip.sel')||{}).textContent, stats: Array.from(document.querySelectorAll('#data-body .data-stat b')).map(e=>e.textContent) })")
        log("多人筛选: %s" % json.dumps(cnt_mp, ensure_ascii=False))
        shot(page, "13_chip_mp")
        # 点「单机」chip
        page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).find(x => x.getAttribute('data-mode') === 'sp');
          b.click();
        }""")
        page.wait_for_timeout(400)
        cnt_sp = page.evaluate("() => ({ rows: document.querySelectorAll('#data-body details.data-hand').length, sel: (document.querySelector('#data-body .data-mode-chip.sel')||{}).textContent })")
        log("单机筛选: %s" % json.dumps(cnt_sp, ensure_ascii=False))
        shot(page, "14_chip_sp")
        # 回「全部」
        page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('#data-body .data-mode-chip')).find(x => x.getAttribute('data-mode') === '');
          b.click();
        }""")
        page.wait_for_timeout(400)
        result["chips"] = {"def": audit["chips"], "all": audit["countAll"], "mp": cnt_mp, "sp": cnt_sp,
                           "modeSplit": audit["modeSplit"], "statsAll": audit["statsAll"]}

        # ===== ③ 文本口径断言 =====
        texts = audit["handTexts"]
        joined = "\n".join(texts)
        checks = {
            "noYouSuffix": "（你）" not in joined,
            "hasBetN": "下注 " in joined,
            "hasRaiseToN": "加注到 " in joined,
            "noArrowArtifact": ("到→" not in joined) and ("→" not in joined),
            "hasCallN": "跟注 " in joined,
            "hasCheck": "过牌" in joined,
            "hasFold": "弃牌" in joined,
            "invalidCheckMarked": "无效过牌自动转弃" in joined,
        }
        log("文本口径断言: %s" % json.dumps(checks, ensure_ascii=False))
        result["textChecks"] = checks

        # ===== ⑥ 展开最后一条详情 → 量尾部可见性 =====
        tail = page.evaluate("""() => {
          const body = document.getElementById('data-body');
          const ds = body.querySelectorAll('details.data-hand');
          if (!ds.length) return { none: true };
          const d = ds[ds.length - 1];
          d.scrollIntoView({ block: 'start' });       // 先把它推到最底，制造「展开尾被盖」的最坏情形
          body.scrollTop = body.scrollHeight;         // 滚到容器底
          if (!d.open) d.open = true;                  // 触发 toggle → scrollIntoView({block:'nearest'})
          return new Promise(res => setTimeout(() => {
            const r = d.getBoundingClientRect();
            const c = body.getBoundingClientRect();
            res({ count: ds.length, detBottom: r.bottom, contBottom: c.bottom,
                  tailVisible: r.bottom <= c.bottom + 1, scrollTop: body.scrollTop });
          }, 600));
        }""")
        log("⑥ 展开尾部: %s" % json.dumps(tail, ensure_ascii=False))
        result["tailCheck"] = tail
        shot(page, "15_expanded_tail")
        try:
            page.locator("#data-body").screenshot(path=os.path.join(OUT, "16_databody_full.png"))
        except Exception as e:
            log("data-body 截图失败: %s" % e)
        # 逐手详情截图
        n = page.evaluate("() => document.querySelectorAll('#data-body details.data-hand').length")
        for i in range(min(n, 6)):
            try:
                page.locator("#data-body details.data-hand").nth(i).screenshot(
                    path=os.path.join(OUT, "hand_detail_%d.png" % (i + 1)))
            except Exception as e:
                log("逐手截图失败 %d: %s" % (i + 1, e))

        # 落盘全文 dump
        try:
            json.dump({"texts": texts, "records": page.evaluate("() => window.DataPage.all()")},
                      open(os.path.join(OUT, "handlog_dump.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        except Exception as e:
            log("dump 失败: %s" % e)

        result["ok"] = all([checks["noYouSuffix"], checks["noArrowArtifact"],
                            probe.get("invalidCheck", {}).get("histType") == "fold",
                            tail.get("tailVisible")])
        result["js_errors"] = errs[:8]
        result["log"] = log_lines
        json.dump(result, open(os.path.join(OUT, "solo_result.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        browser.close()

if __name__ == "__main__":
    main()
