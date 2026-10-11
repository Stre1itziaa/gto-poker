# mp_guest.py — 好友房客人端自动玩家（Playwright 无头）
# 用法: python mp_guest.py <房码> <昵称> <截图输出目录> [最大手数=3] [角色序号1-6]
# 流程: 打开游戏 → 多人游戏 → 加入房间 → 准备 → 等房主开局 → 循环等自己行动 → 简单策略出牌
# 截图: 01_landing / 02_mp_modal / 03_lobby / 04_table_first / 06_turn_first / 05_showdown / 07_final
# 结果: OUT/result.json + stdout 全程日志
import sys, time, json, os, random, traceback

CODE = sys.argv[1]
NAME = sys.argv[2]
OUT = sys.argv[3]
MAX_HANDS = int(sys.argv[4]) if len(sys.argv) > 4 else 3
CHAR_IDX = int(sys.argv[5]) if len(sys.argv) > 5 else 0
URL = "http://localhost:8787/"
# AR18 审计: 设 GTO_LOBBY_COSTUME=p0/p1（新手未锁包）时，先在大厅点服装页签再进房，
# 验证 v2 每角色服装 (gto-costume-map) 与牌桌座位立绘同步
LOBBY_COSTUME = os.environ.get("GTO_LOBBY_COSTUME", "")
CHAR_IDS = ["suzu", "shiori", "natsu", "rin", "yuki", "ume"]  # 与 Portraits.ALL 同序

os.makedirs(OUT, exist_ok=True)
log_lines = []
def log(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    log_lines.append(line)
    print(line, flush=True)

def shot(page, tag):
    try:
        page.screenshot(path=os.path.join(OUT, f"{tag}.png"))
        log(f"截图 {tag}")
    except Exception as e:
        log(f"截图失败 {tag}: {e}")

def visible(page, sel):
    return page.locator(sel).is_visible()

def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900})
        # AR18: 先定角色，让大厅舞台即本命——服装切换才会作用到要进局的 charId
        # （mp.js v2：好友房角色=大厅看板娘 localStorage 'gto-char'，mp 弹窗内已无二次选择 UI）
        if CHAR_IDX:
            my_char = CHAR_IDS[CHAR_IDX - 1] if 1 <= CHAR_IDX <= 6 else "suzu"
            ctx.add_init_script("""
              try {
                localStorage.setItem('gto-char', '%s');
                localStorage.setItem('gto-name', '%s');
              } catch (e) {}
            """ % (my_char, NAME))
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(URL)
        page.wait_for_timeout(1200)
        # 全新 profile 下 #tut-modal 首次引导遮罩会拦截 #mc-multi 等点击，先关掉（已引导过则无操作）
        page.evaluate("() => { const g = document.getElementById('tut-go'); if (g) g.click(); }")
        shot(page, "01_landing")

        # AR18: 新大厅切服装（图鉴弹窗分页签：仅 p0/p1 新手可用；p2+ 好感锁）→ 进局核对座位立绘
        # #stage-costumes 页签已撤除（图鉴弹窗化）；改驱动 Lobby 图鉴弹窗的 .book-tab/.book-cell
        if LOBBY_COSTUME:
            my_char = CHAR_IDS[CHAR_IDX - 1] if (CHAR_IDX and 1 <= CHAR_IDX <= 6) else "suzu"
            try:
                page.evaluate("() => { const b = document.getElementById('lobby-book'); if (b) b.click(); }")
                page.wait_for_selector(f"#book-body .book-cell[data-char='{my_char}'][data-key='{LOBBY_COSTUME}']", timeout=10000)
                cell = page.locator(f"#book-body .book-cell[data-char='{my_char}'][data-key='{LOBBY_COSTUME}']")
                lock_cls = cell.get_attribute("class") or ""
                cell.click()
                if "lock" in lock_cls:
                    log(f"服装 {LOBBY_COSTUME} 处于好感锁（点击被拒绝，符合预期）")
                else:
                    page.wait_for_function(
                        "() => { const i = document.querySelector('#stage-portrait img, #stage-portrait .pt img');"
                        " return i && i.src.indexOf('-%s-') >= 0 && i.src.indexOf('%s-') >= 0; }" % (LOBBY_COSTUME, my_char), timeout=10000)
                    log(f"大厅切服装 {LOBBY_COSTUME} 成功（{my_char}）: 舞台 src 已更新")
            except Exception as e:
                log(f"大厅切服装失败: {e}")
            # 图鉴页 UI 状态快照（角色分页签/服装格锁与穿戴）+ 好感度
            try:
                page.wait_for_selector("#book-body .book-cell", timeout=3000)
                row_state = page.evaluate("""() => ({
                  tabs: Array.from(document.querySelectorAll('.book-tab')).map(b => b.textContent.trim()),
                  activeTab: (document.querySelector('.book-tab.active span') || {}).textContent || null,
                  cells: Array.from(document.querySelectorAll('#book-body .book-cell')).map(c => ({
                    key: c.getAttribute('data-key'), lock: c.className.indexOf('lock') >= 0,
                    equipped: c.className.indexOf('equipped') >= 0 })) })""")
                log("图鉴页: " + json.dumps(row_state, ensure_ascii=False))
                aff = page.evaluate("() => { const e = document.querySelector('#stage-plate .aff'); return e ? e.textContent : null; }")
                log(f"好感度条: {aff}")
            except Exception:
                pass
            # 关闭图鉴弹窗再进多人流程（全屏遮罩会拦截 #mc-multi 点击）
            try:
                page.locator("#book-close").click(timeout=2000)
                page.wait_for_timeout(200)
            except Exception:
                page.evaluate("() => document.getElementById('book-modal').classList.add('hidden')")

        page.locator("#mc-multi").click(timeout=5000)
        page.wait_for_timeout(500)
        page.locator("#mp-name").fill(NAME)
        if CHAR_IDX:
            log(f"角色序号 {CHAR_IDX} → {CHAR_IDS[CHAR_IDX - 1] if 1 <= CHAR_IDX <= 6 else 'suzu'}（gto-char 已由 init script 预置）")
        page.wait_for_timeout(400)
        shot(page, "02_mp_modal")

        page.locator("#mp-tab-join").click()
        page.locator("#mp-code").fill(CODE)
        page.locator("#mp-btn-join").click()
        log(f"点击加入房间 {CODE}")
        for i in range(40):
            if visible(page, "#mp-lobby") and not page.locator("#mp-lobby").is_hidden():
                break
            page.wait_for_timeout(1000)
        else:
            status = page.locator("#mp-status").text_content()
            log(f"加入失败! status={status}")
            shot(page, "err_join_fail")
            json.dump({"ok": False, "reason": f"join failed: {status}", "log": log_lines},
                      open(os.path.join(OUT, "result.json"), "w", encoding="utf-8"), ensure_ascii=False)
            return
        page.wait_for_timeout(800)
        shot(page, "03_lobby")
        lobby_text = page.locator("#mp-players").text_content()
        log(f"大厅名单: {lobby_text}")

        page.locator("#mp-btn-ready").click()
        log("已点准备")
        page.wait_for_timeout(800)

        # 等房主开局（最多 8 分钟）
        log("等待房主开局…")
        for i in range(480):
            if page.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"):
                break
            page.wait_for_timeout(1000)
        page.wait_for_timeout(1800)
        shot(page, "04_table_first")
        log("已进牌桌")

        # AR18: 牌桌座位立绘 src 全量 dump（v2 每角色服装：本命应穿大厅切的包，队手各穿各的）
        if LOBBY_COSTUME:
            my_char = CHAR_IDS[CHAR_IDX - 1] if (CHAR_IDX and 1 <= CHAR_IDX <= 6) else "suzu"
            try:
                srcs = page.evaluate("""() => Array.from(document.querySelectorAll('.seat .portrait [data-char]')).map(el => ({
                  char: el.getAttribute('data-char'),
                  img: el.querySelector('img') ? el.querySelector('img').getAttribute('src') : null
                }))""")
                mine = [s for s in srcs if s["char"] == my_char]
                mine_ok = bool(mine) and all(s["img"] and ("-%s-" % LOBBY_COSTUME) in s["img"] for s in mine)
                log(f"牌桌立绘同步: 本命 {my_char} {len(mine)} 座穿 {LOBBY_COSTUME}: {'OK' if mine_ok else 'NG'}")
                for s in srcs:
                    tag = " <-我" if s["char"] == my_char else ""
                    log(f"  座位 char={s['char']} src={s['img']}{tag}")
            except Exception as e:
                log(f"牌桌立绘 dump 失败: {e}")

        hand_no = 0
        try:
            prev_records = page.evaluate("window.DataPage ? DataPage.all().length : 0")
        except Exception:
            prev_records = 0
        turns = 0
        deadline = time.time() + 60 * 14
        while time.time() < deadline and hand_no < MAX_HANDS:
            if visible(page, "#overlay:not(.hidden)"):
                shot(page, f"05_showdown_{hand_no + 1}")
                ov = ""
                try:
                    ov = page.locator("#overlay-body").text_content() or ""
                except Exception:
                    pass
                log(f"结算弹层: {ov[:150]}")
                # Step 13：以 DataPage 记录数差值兜底计数（弹层残留/点击失败不再重复计数）
                try:
                    cur_records = page.evaluate("window.DataPage ? DataPage.all().length : 0")
                    if cur_records > prev_records:
                        hand_no += 1
                        prev_records = cur_records
                except Exception:
                    hand_no += 1
                if hand_no >= MAX_HANDS:
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
                    shot(page, f"06_turn_{turns}")
                call_btn = page.locator("#btn-checkcall").text_content() or ""
                r = random.random()
                if r < 0.15 and visible(page, "#btn-raise"):
                    try:
                        # 行动条两态化：滑条/快捷注收在默认收起的 #raise-box 浮层里，
                        # 先点 ▾调注 展开再点预设；已开则不重复点（防二次点击把面板收回去）。
                        # 全部给有界超时，失败快速回退过牌/跟注，不再 30s 停滞
                        if not page.locator("#raise-box").is_visible():
                            page.locator("#raise-tune").click(timeout=2500)
                        presets = page.locator("#presets button")
                        n = presets.count()
                        if n > 0:
                            presets.nth(min(1, n - 1)).click(timeout=2500)
                            page.wait_for_timeout(200)
                            page.locator("#btn-raise").click(timeout=2500)
                            log(f"行动#{turns}: 加注")
                            page.wait_for_timeout(900)
                            continue
                    except Exception:
                        pass
                if "过牌" in call_btn:
                    page.locator("#btn-checkcall").click()
                    log(f"行动#{turns}: 过牌")
                else:
                    amt = "".join(ch for ch in call_btn if ch.isdigit())
                    if amt and int(amt) <= 120:
                        page.locator("#btn-checkcall").click()
                        log(f"行动#{turns}: 跟注 {amt}")
                    elif random.random() < 0.35:
                        page.locator("#btn-checkcall").click()
                        log(f"行动#{turns}: 跟大注 {amt}")
                    else:
                        try:
                            page.locator("#btn-fold").click(timeout=2000)
                            log(f"行动#{turns}: 弃牌 (要跟 {amt})")
                        except Exception:
                            page.locator("#btn-checkcall").click()
                            log(f"行动#{turns}: 弃牌失败改跟注")
                page.wait_for_timeout(900)
            page.wait_for_timeout(1200)

        page.wait_for_timeout(800)
        shot(page, "07_final")

        # ===== 数据板块审计：回大厅 → 打开数据分析 → 程序化核账 =====
        data_audit = {"module": False}
        try:
            page.locator("#btn-home").click(timeout=4000)
            page.wait_for_timeout(2500)
            shot(page, "08_back_landing")
            page.locator("#mc-data").click(timeout=4000)
            page.wait_for_timeout(1500)
            shot(page, "09_data_modal")
            data_audit = page.evaluate("""() => {
              const D = window.DataPage; if (!D) return {module: false};
              const recs = D.all(), st = D.stats(recs);
              let sumBB = 0, n = 0;
              document.querySelectorAll('#data-body .data-hand summary b').forEach(function (b) {
                const m = (b.textContent || '').match(/([+\\u2212-]?)([\\d.]+)bb/);
                if (m) { const v = parseFloat(m[2]) * ((m[1] === '+' || m[1] === '') ? 1 : -1); sumBB += v; n++; }
              });
              return { module: true, records: recs.length,
                badAssert: recs.filter(function (r) { return r.assert && r.assert.ok === false; }).length,
                noAssert: recs.filter(function (r) { return !r.assert; }).length,
                withHole: recs.filter(function (r) { return r.players && r.players[0] && r.players[0].hole && r.players[0].hole.length === 2; }).length,
                stats: { hands: st.hands, netBB: st.netBB, vpip: st.vpip, pfr: st.pfr },
                oppCount: Object.keys(st.opponents).length,
                hasChart: !!document.querySelector('#data-body canvas.data-chart, #data-body svg.data-chart'),
                handRows: document.querySelectorAll('#data-body .data-hand').length,
                summaryRows: n, summarySumBB: Math.round(sumBB * 10) / 10,
                bodyChars: (document.getElementById('data-body').textContent || '').length };
            }""")
            if data_audit.get("module"):
                diff = round(data_audit["summarySumBB"] - data_audit["stats"]["netBB"], 2)
                tol = 0.05 * data_audit["summaryRows"] + 0.1
                data_audit["sumDiff"] = diff
                data_audit["sumMatch"] = data_audit["summaryRows"] > 0 and abs(diff) <= tol
        except Exception:
            data_audit["error"] = traceback.format_exc()[-400:]
        log(f"数据审计: {json.dumps(data_audit, ensure_ascii=False)[:300]}")

        state = {"ok": True, "name": NAME, "turns": turns, "hands_seen": hand_no,
                 "js_errors": errors[:10], "log": log_lines, "data_audit": data_audit}
        json.dump(state, open(os.path.join(OUT, "result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("RESULT_JSON=" + json.dumps(state, ensure_ascii=False))
        browser.close()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        json.dump({"ok": False, "error": traceback.format_exc(), "log": log_lines},
                  open(os.path.join(OUT, "result.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print("RESULT_JSON=" + json.dumps({"ok": False, "error": traceback.format_exc(), "log": log_lines}, ensure_ascii=False))
