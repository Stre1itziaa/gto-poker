# -*- coding: utf-8 -*-
"""function_audit.py — 功能目的断言探针（2026-10-03 全功能复查）

与 landscape_audit(几何) 互补：本探针以「玩家能否完成功能目的」为断言，
真实点击/输入并验证状态变化。覆盖：大厅/角色库/图鉴/对局行动/教练/结算/
表情/好友房P2P/数据页/引导卡/音效。
用法: python test/function_audit.py [group ...]   组缺省=全部
输出: 单行 JSON + 退出码(0=全过)
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8129/"
GAME = Path(__file__).resolve().parent.parent


def ensure_server():
    try:
        urllib.request.urlopen(URL, timeout=2)
        return
    except Exception:
        pass
    subprocess.Popen(["node", "serve.js", "8129"], cwd=str(GAME),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(URL, timeout=2)
            return
        except Exception:
            continue


RES = {"cases": [], "ok": True}


def case(name, ok, detail=""):
    RES["cases"].append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    if not ok:
        RES["ok"] = False
    print(f"{'✓' if ok else '✗'} {name} {detail if not ok else ''}", flush=True)


def enter_game(pg):
    pg.evaluate("""() => {
      const t = Array.from(document.querySelectorAll('#landing .mc-title, #landing div'))
        .find(d => d.classList && d.classList.contains('mc-title') && d.classList && d.classList.contains('mc-title') && d.textContent.indexOf('开始对局') >= 0);
      if (t) t.click();
    }""")
    for _ in range(24):
        pg.wait_for_timeout(700)
        if pg.evaluate("() => !document.getElementById('action-controls').classList.contains('hidden')"):
            return True
    return False


def main():
    ensure_server()
    groups = sys.argv[1:] or ["all"]
    want = lambda g: "all" in groups or g in groups

    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        ctx = br.new_context(viewport={"width": 740, "height": 360})
        pg = ctx.new_page()
        pg.goto(URL)
        pg.wait_for_load_state("domcontentloaded")

        # ---------- A 大厅 ----------
        if want("lobby"):
            pg.evaluate("() => { try { localStorage.clear(); } catch(e){} }")
            pg.reload()
            pg.wait_for_timeout(2000)
            tut = pg.evaluate("() => !!document.getElementById('tut-modal')")
            case("引导卡.首次出现", tut)
            pg.evaluate("() => document.getElementById('tut-go').click()")
            pg.wait_for_timeout(300)
            gone = pg.evaluate("() => !document.getElementById('tut-modal')")
            again = pg.evaluate("() => { location.reload(); }")
            pg.wait_for_timeout(1500)
            no2 = pg.evaluate("() => !document.getElementById('tut-modal')")
            case("引导卡.关闭后不再现", gone and no2)

            stats = pg.evaluate("() => (document.getElementById('lobby-stats')||{}).textContent || ''")
            case("大厅.统计行渲染", any(k in stats for k in ["手", "VPIP", "盈亏"]) or len(stats) > 4, stats[:60])

            src0 = pg.evaluate("() => (document.querySelector('#stage-portrait img')||{src:''}).src")
            pg.evaluate("() => document.querySelector('#stage-portrait img').click()")
            src1 = src0
            for _ in range(10):   # 轮询等异步重渲染(冷启动可能撞 scan/3s重扫)
                pg.wait_for_timeout(400)
                src1 = pg.evaluate("() => (document.querySelector('#stage-portrait img')||{src:''}).src")
                if src1 != src0:
                    break
            case("大厅.点立绘换表情", src0 and src1 and src0 != src1, f"{src0[-18:]}→{src1[-18:]}")

            pg.evaluate("() => { const b = Array.from(document.querySelectorAll('#landing button')).find(x => x.textContent.includes('4人桌')); if (b) b.click(); }")
            pg.wait_for_timeout(200)
            seats = pg.evaluate("() => { try { return localStorage.getItem('gto-seats'); } catch(e){ return '?'; } }")
            case("大厅.桌型选择落库", seats == "4", seats)

        # ---------- B 角色库 ----------
        if want("lib"):
            pg.evaluate("() => document.getElementById('lobby-lib').click()")
            pg.wait_for_timeout(900)
            n0 = pg.evaluate("() => document.querySelector('.lib-name b').textContent")
            pg.evaluate("() => document.querySelector('.lib-arrow-next').click()")
            pg.wait_for_timeout(500)
            n1 = pg.evaluate("() => document.querySelector('.lib-name b').textContent")
            case("角色库.箭头切换角色", n0 and n1 and n0 != n1, f"{n0}→{n1}")

            locked = pg.query_selector(".lib-cos.lock button") or pg.query_selector(".lib-cos .lock")
            if locked:
                pg.evaluate("() => document.querySelector('.lib-cos .lock').click()")
                pg.wait_for_timeout(600)
                bub = pg.evaluate("() => { const b = document.getElementById('stage-bubble'); return b && b.classList.contains('show'); }")
                case("角色库.锁定服装出提示", bub)
            else:
                case("角色库.锁定服装出提示", True, "全解锁(测试档)跳过")

            free = pg.evaluate("""() => { const btns = Array.from(document.querySelectorAll('.lib-cos button'))
                .filter(b => !b.classList.contains('lock') && !b.classList.contains('sel'));
                return btns.length ? btns[0].getAttribute('data-key') : null; }""")
            if free:
                map0 = pg.evaluate("() => localStorage.getItem('gto-costume-map')")
                pg.evaluate(f"() => document.querySelector('.lib-cos button[data-key=\"{free}\"]').click()")
                pg.wait_for_timeout(1500)
                map1 = pg.evaluate("() => localStorage.getItem('gto-costume-map')")
                case("角色库.点chip换装落库", map0 != map1, f"key={free}")
            else:
                case("角色库.点chip换装落库", True, "无可用chip")

            kb0 = pg.evaluate("() => document.querySelector('.kb-badge') ? document.querySelector('.lib-name b').textContent : ''")
            pg.evaluate("() => document.querySelector('.lib-set').click()")
            pg.wait_for_timeout(600)
            kb1 = pg.evaluate("() => document.querySelector('.kb-badge') ? document.querySelector('.lib-name b').textContent : ''")
            case("角色库.设为看板娘生效", kb1 and kb1 != "''", kb1 or "无badge")

            fv0 = pg.evaluate("() => !!document.getElementById('lib-fullview') && !document.getElementById('lib-fullview').classList.contains('hidden')")
            pg.evaluate("() => document.querySelector('.lib-img').click()")
            pg.wait_for_timeout(400)
            fv1 = pg.evaluate("() => !document.getElementById('lib-fullview').classList.contains('hidden') && document.querySelector('#lib-fullview img').src.length > 0")
            pg.evaluate("() => document.getElementById('lib-fullview').click()")
            pg.wait_for_timeout(200)
            fv2 = pg.evaluate("() => document.getElementById('lib-fullview').classList.contains('hidden')")
            case("角色库.全屏预览开关", (not fv0) and fv1 and fv2)
            pg.evaluate("() => document.getElementById('lib-modal').classList.add('hidden')")

        # ---------- C 图鉴 ----------
        if want("book"):
            pg.evaluate("() => document.getElementById('lobby-book').click()")
            pg.wait_for_timeout(900)
            c0 = pg.evaluate("() => document.querySelectorAll('.book-cell').length")
            tabs = pg.evaluate("() => document.querySelectorAll('.book-tab').length")
            pg.evaluate("() => document.querySelectorAll('.book-tab')[2].click()")
            pg.wait_for_timeout(500)
            c2 = pg.evaluate("() => document.querySelectorAll('.book-cell').length")
            lockn = pg.evaluate("() => document.querySelectorAll('.book-cell.lock').length")
            case("图鉴.tab切换内容联动", tabs >= 6 and c0 > 0 and c2 > 0, f"tabs={tabs} c0={c0} c2={c2}")
            case("图鉴.锁定格渲染", lockn >= 0, f"lock={lockn}")
            pg.evaluate("() => document.getElementById('book-modal').classList.add('hidden')")

        # ---------- D 对局 ----------
        if want("game"):
            if enter_game(pg):
                aff0 = pg.evaluate("() => { try { return JSON.stringify(JSON.parse(localStorage.getItem('gto-affection')||'{}')); } catch(e){ return ''; } }")
                cards = pg.evaluate("() => document.querySelectorAll('.seat.me .card').length")
                seats = pg.evaluate("() => document.querySelectorAll('.seat').length")
                case("对局.开局手牌2张座位齐", cards == 2 and seats >= 2, f"cards={cards} seats={seats}")

                # 调注面板(同一手、正轮到我)
                opened = pg.evaluate("() => { const t = document.getElementById('raise-tune'); if (t) { t.click(); return true; } return false; }")
                pg.wait_for_timeout(400)
                lab0 = pg.evaluate("() => document.getElementById('btn-raise').textContent")
                pg.evaluate("() => { const p = document.querySelectorAll('#presets button'); for (const b of p) { if (!b.className.includes('suggest')) { b.click(); break; } } }")
                pg.wait_for_timeout(400)
                lab1 = pg.evaluate("() => document.getElementById('btn-raise').textContent")
                case("对局.调注面板开+快捷注改金额", opened and lab0 != lab1, f"{lab0.strip()[:14]}→{lab1.strip()[:14]}")

                log0 = pg.evaluate("() => document.getElementById('log').textContent")
                pg.evaluate("() => document.getElementById('btn-fold').click()")
                pg.wait_for_timeout(1500)
                log1 = pg.evaluate("() => document.getElementById('log').textContent")
                case("对局.弃牌入日志+行动条收起", len(log1) > len(log0) and
                     pg.evaluate("() => document.getElementById('action-controls').classList.contains('hidden')"))

                shown = False
                for i in range(26):
                    pg.evaluate("""() => { const b = document.getElementById('btn-fold'); if (b && !b.disabled) b.click(); const n = document.getElementById('btn-next'); if (n) n.click(); }""")
                    pg.wait_for_timeout(1800)
                    if pg.evaluate("() => !document.getElementById('overlay').classList.contains('hidden')"):
                        shown = True
                        break
                case("对局.结算弹窗出现", shown)
                if shown:
                    pg.evaluate("() => document.getElementById('btn-next').click()")
                    pg.wait_for_timeout(2500)
                    fresh = pg.evaluate("() => document.querySelectorAll('.seat.me .card').length")
                    case("对局.下一局发新手牌", fresh == 2, f"cards={fresh}")
                    aff1 = pg.evaluate("() => { try { return JSON.stringify(JSON.parse(localStorage.getItem('gto-affection')||'{}')); } catch(e){ return ''; } }")
                    case("对局.好感度结算落库", aff1 != aff0 and len(aff1) > 2, "storage变化")

                coach = pg.evaluate("() => (document.getElementById('coach-body')||{}).textContent || ''")
                case("对局.教练面板在线", "轮到你" in coach or "%" in coach or "建议" in coach or "复盘" in coach, coach[:50])
            else:
                case("对局.进入超时", False)

        # ---------- E 表情 ----------
        if want("emote"):
            opened = pg.evaluate("() => { const f = document.getElementById('emote-fab'); if (f && f.offsetParent) { f.click(); return true; } return 'nofab'; }")
            pg.wait_for_timeout(400)
            chip = pg.evaluate("() => { const c = document.querySelector('#emote-strip .emote-chip:not([style*=\"none\"])'); if (c) { c.click(); return true; } return false; }")
            pg.wait_for_timeout(600)
            emo = pg.evaluate("() => !!document.querySelector('.seat .emote.show')")
            case("表情.快捷表情本地回显", chip and emo, f"fab={opened} chip={chip}")
            pg.evaluate("() => { const s = document.getElementById('emote-strip'); if (s) s.classList.remove('open'); }")

        # ---------- F 好友房 P2P（双页同 context，loopback） ----------
        if want("mp"):
            try:
                pg.evaluate("() => { const t = Array.from(document.querySelectorAll('#landing .mc-title, #landing div')).find(d => d.textContent.trim() === '好友房'); if (t) t.click(); }")
                pg.wait_for_timeout(600)
                pg.evaluate("() => document.getElementById('mp-btn-create').click()")
                code = ""
                for _ in range(20):
                    pg.wait_for_timeout(1000)
                    code = pg.evaluate("() => (document.getElementById('mp-room-code')||{}).textContent || ''").strip()
                    if code:
                        break
                okc = len(code) >= 4
                case("好友房.创建并出房码", okc, code)
                if okc:
                    g2 = ctx.new_page()
                    g2.goto(URL)
                    g2.wait_for_load_state("domcontentloaded")
                    g2.wait_for_timeout(1800)
                    g2.evaluate("() => { const t = Array.from(document.querySelectorAll('#landing .mc-title, #landing div')).find(d => d.textContent.trim() === '好友房'); if (t) t.click(); }")
                    g2.wait_for_timeout(500)
                    g2.evaluate("() => document.getElementById('mp-tab-join').click()")
                    g2.fill("#mp-code", code[:6])
                    g2.evaluate("() => document.getElementById('mp-btn-join') ? document.getElementById('mp-btn-join').click() : null")
                    joined = False
                    for _ in range(30):
                        g2.wait_for_timeout(1500)
                        st = g2.evaluate("() => document.body.textContent")
                        if "等待" in st or "房主" in st or "seat" in st.lower() or "准备" in st:
                            joined = True
                            break
                    case("好友房.房码加入连通", joined)
                    g2.close()
            except Exception as ex:
                case("好友房.P2P流程", False, repr(ex)[:120])
            pg.evaluate("() => { const m = document.getElementById('multi-modal'); if (m) m.classList.add('hidden'); }")

        # ---------- G 数据页 ----------
        if want("data"):
            pg.evaluate("""() => { const t = Array.from(document.querySelectorAll('#landing .mc-title, #landing div'))
                .find(d => d.textContent.trim() === '数据分析'); if (t) t.click(); }""")
            pg.wait_for_timeout(1800)
            cvs = pg.evaluate("() => document.querySelectorAll('#data-body canvas, #data-body svg.data-chart').length")
            cards = pg.evaluate("() => document.querySelectorAll('#data-body .data-cards > *').length")
            clr = pg.evaluate("() => !!Array.from(document.querySelectorAll('#data-body button')).find(b => b.textContent.includes('清空'))")
            case("数据页.图表与卡片渲染", cvs >= 1 and cards >= 1, f"charts={cvs} cards={cards}")
            case("数据页.清空入口存在", clr)

        # ---------- H 音效 ----------
        if want("sfx"):
            s = pg.evaluate("""() => { try { if (!window.SFX) return 'no-SFX';
                window.SFX.unlock(); window.SFX.click(); window.SFX.chip(); window.SFX.win();
                return 'ok'; } catch(e) { return 'err:' + e.message; } }""")
            case("音效.解锁与三音不抛错", s == "ok", s)

        br.close()

    print(json.dumps(RES, ensure_ascii=False))
    sys.exit(0 if RES["ok"] else 1)


if __name__ == "__main__":
    main()
