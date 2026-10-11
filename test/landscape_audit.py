# -*- coding: utf-8 -*-
"""landscape_audit.py — 横屏 740x360 几何审计探针（美术布局重规划修复工作流的检查员标尺）

用法: python test/landscape_audit.py <screen>
  screen ∈ {action, lobby, lib, book, data, portrait, all}
输出: 单行 JSON + 退出码（0=全过 / 1=有 FAIL）
特性: 8129 未起时自动拉起 serve.js（自愈）；portrait 屏为 390x844 竖屏回归。
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8129/"
VW, VH = 740, 360
GAME = Path(__file__).resolve().parent.parent


def ensure_server():
    try:
        urllib.request.urlopen(URL, timeout=2)
        return
    except Exception:
        pass
    subprocess.Popen(
        ["node", "serve.js", "8129"], cwd=str(GAME),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(URL, timeout=2)
            return
        except Exception:
            continue


def run(pw, screen):
    res = {"screen": screen, "checks": [], "ok": True}
    br = pw.chromium.launch(headless=True)
    pg = br.new_context(viewport={"width": VW, "height": VH}).new_page()
    pg.goto(URL)
    pg.wait_for_load_state("domcontentloaded")
    pg.evaluate("() => { try { localStorage.setItem('gto-tutored','1'); } catch(e){} }")
    pg.reload()
    pg.wait_for_timeout(1800)

    def check(name, value, ok, target):
        res["checks"].append({"name": name, "value": value, "target": target, "ok": bool(ok)})
        if not ok:
            res["ok"] = False

    def enter_game():
        pg.evaluate("""() => {
          const t = Array.from(document.querySelectorAll('#landing .mc-title, #landing div'))
            .find(d => d.classList && d.classList.contains('mc-title') && d.classList && d.classList.contains('mc-title') && d.textContent.indexOf('开始对局') >= 0);
          if (t) t.click();
        }""")
        for _ in range(20):
            pg.wait_for_timeout(700)
            if pg.evaluate("() => !document.getElementById('action-controls').classList.contains('hidden')"):
                return True
        return False

    if screen in ("lobby", "all"):
        plate = pg.query_selector("#stage-plate")
        port = pg.query_selector("#stage-portrait img")
        check("大厅.名牌不出屏顶(top>=0)", px(plate, "top"), (px(plate, "top") or -1) >= 0, ">=0")
        check("大厅.立绘不出屏底(bottom<=362)", px(port, "bottom"), (px(port, "bottom") or 999) <= VH + 2, "<=362")
        qd = pg.evaluate("() => { const q = document.querySelector('#stage-plate .pquote'); return !q || getComputedStyle(q).display === 'none'; }")
        check("大厅.台词块已收起", qd, qd, "display:none")

    if screen in ("lib", "all"):
        pg.evaluate("() => document.getElementById('lobby-lib').click()")
        pg.wait_for_timeout(900)
        sc = pg.evaluate("""() => { const c = document.getElementById('lib-card');
            const i = c.querySelector('.lib-img');
            return { sh: c.scrollHeight, ch: c.clientHeight,
                     arrows: document.querySelectorAll('.lib-arrow').length,
                     imgH: i ? Math.round(i.getBoundingClientRect().height) : 0,
                     disp: i ? [i.getBoundingClientRect().width, i.getBoundingClientRect().height] : [0,0],
                     nat: i ? [i.naturalWidth, i.naturalHeight] : [0,0],
                     fit: i ? getComputedStyle(i).objectFit : '' }; }""")
        check("角色库.零滚动(sh==ch)", sc["sh"], sc["sh"] <= sc["ch"] + 4, "<=ch+4")
        check("角色库.左右切换箭头存在", sc["arrows"], sc["arrows"] >= 2, ">=2")
        check("角色库.立绘高>=220px", sc["imgH"], sc["imgH"] >= 220, ">=220")
        # 无裁断断言：显示宽高比须≈原图宽高比(±3%)——cover 裁切会差数十个百分点
        if sc["nat"][0] and sc["nat"][1]:
            ratio_err = abs(sc["disp"][0] / sc["disp"][1] - sc["nat"][0] / sc["nat"][1]) / (sc["nat"][0] / sc["nat"][1]) * 100
            check("角色库.立绘等比无裁切(比例差<=3%)", round(ratio_err, 1), ratio_err <= 3.0, "<=3%")
            check("角色库.objectFit==contain", sc["fit"], sc["fit"] == "contain", "contain")
        # 点击立绘出全屏预览
        pg.evaluate("() => document.querySelector('.lib-img').click()")
        pg.wait_for_timeout(400)
        fv = pg.evaluate("() => { const f = document.getElementById('lib-fullview'); return !!f && !f.classList.contains('hidden') && f.querySelector('img').src.length > 0; }")
        check("角色库.点立绘全屏预览", fv, fv, "visible")
        pg.evaluate("() => document.getElementById('lib-fullview').click()")
        pg.evaluate("() => document.getElementById('lib-modal').classList.add('hidden')")

    if screen in ("book", "all"):
        pg.evaluate("() => document.getElementById('lobby-book').click()")
        pg.wait_for_timeout(900)
        sc = pg.evaluate("""() => { const c = document.getElementById('book-card');
            return { sh: c.scrollHeight, ch: c.clientHeight,
                     tabs: document.querySelectorAll('.book-tab').length }; }""")
        check("图鉴.单页无滚动(sh==ch)", sc["sh"], sc["sh"] <= sc["ch"] + 4, "<=ch+4")
        check("图鉴.角色分页签存在", sc["tabs"], sc["tabs"] >= 6, ">=6")
        pg.evaluate("() => document.getElementById('book-modal').classList.add('hidden')")

    if screen in ("action", "all", "portrait"):
        if screen == "portrait":
            pg.set_viewport_size({"width": 390, "height": 844})
            pg.wait_for_timeout(600)
        if enter_game():
            ab = pg.evaluate("""() => { const a = document.getElementById('actionbar');
                return Math.round(a.getBoundingClientRect().height); }""")
            if screen == "portrait":
                check("竖屏.行动条高<=120px", ab, ab <= 120, "<=120")
                ow = pg.evaluate("() => document.documentElement.scrollWidth")
                check("竖屏.无横向溢出", ow, ow <= 392, "<=392")
            else:
                check("行动条.总高<=92px", ab, ab <= 92, "<=92")
                collapsed = pg.evaluate("""() => { const b = document.getElementById('raise-box');
                    if (!b) return false;
                    const r = b.getBoundingClientRect();
                    return r.height === 0 || getComputedStyle(b).display === 'none' || !b.offsetParent; }""")
                check("行动条.加注面板默认收起", collapsed, collapsed, "hidden")
                pg.evaluate("() => { const t = document.getElementById('raise-tune'); if (t) t.click(); }")
                pg.wait_for_timeout(400)
                sw = pg.evaluate("""() => { const s = document.getElementById('raise-slider');
                    return s ? s.offsetWidth : 0; }""")
                check("滑条.宽>=140px(面板开)", sw, sw >= 140, ">=140")
                ph = pg.evaluate("() => { const p = document.getElementById('presets'); return p ? Math.round(p.getBoundingClientRect().height) : 0; }")
                check("快捷注.单行高<=44px", ph, ph <= 44, "<=44")
                fold_w = pg.evaluate("() => (document.getElementById('btn-fold')||{offsetWidth:999}).offsetWidth")
                raise_w = pg.evaluate("() => (document.getElementById('btn-raise')||{offsetWidth:0}).offsetWidth")
                check("主次.加注宽>弃牌宽+40", raise_w - fold_w, raise_w > fold_w + 40, ">+40")
            name_f = pg.evaluate("() => { const n = document.querySelector('.seat:not(.me) .name'); return n ? parseFloat(getComputedStyle(n).fontSize) : 0; }")
            check("座位.名字号>=12px", name_f, name_f >= 12, ">=12")
            ov = pg.evaluate("""() => {
              const seats = Array.from(document.querySelectorAll('.seat')).map(s => s.getBoundingClientRect());
              for (let i = 0; i < seats.length; i++) for (let j = i + 1; j < seats.length; j++) {
                const a = seats[i], b = seats[j];
                if (a.left < b.right - 2 && b.left < a.right - 2 && a.top < b.bottom - 2 && b.top < a.bottom - 2) return i + '-' + j;
              }
              return '';
            }""")
            check("座位.六座位零重叠", ov or "none", ov == "", "零重叠")
            # 翻牌后公共牌可见断言(用户实锤"看不到牌"后的盲区补丁): 跟注推进到 board>=3
            floped = False; bw = 0
            for _ in range(40):
                pg.evaluate("() => { const b = document.getElementById('btn-checkcall'); if (b && !b.disabled && b.offsetParent) b.click(); }")
                pg.wait_for_timeout(800)
                n, w0 = pg.evaluate("() => { const c = document.querySelector('#board .card'); const all = document.querySelectorAll('#board .card'); return [all.length, c ? Math.round(c.getBoundingClientRect().width) : 0]; }")
                if n >= 3:
                    floped = True; bw = w0
                    break
            if floped:
                check("公共牌.翻牌后>=3张且宽>=38px", bw, bw >= 38, ">=38")
            else:
                check("公共牌.翻牌推进可达", "timeout", False, "board>=3")
        else:
            check("行动条.进入对局超时", "timeout", False, "controls visible")

    if screen in ("data", "all"):
        pg.evaluate("""() => { const t = Array.from(document.querySelectorAll('#landing .mc-title, #landing div'))
            .find(d => d.textContent.trim() === '数据分析'); if (t) t.click(); }""")
        pg.wait_for_timeout(1500)
        sc = pg.evaluate("""() => { const b = document.getElementById('data-body');
            const cvs = b ? b.querySelector('canvas') : null;
            return { sh: b ? b.scrollHeight : 0, ch: b ? b.clientHeight : 0,
                     chartH: cvs ? Math.round(cvs.getBoundingClientRect().height) : 0 }; }""")
        ratio = round(sc["sh"] / max(sc["ch"], 1), 1)
        check("数据页.滚动深度<=3屏", ratio, ratio <= 3.0, "<=3.0")
        check("数据页.图表高>=160px", sc["chartH"], sc["chartH"] >= 160, ">=160")

    br.close()
    return res


def px(el, prop):
    if not el:
        return None
    return el.evaluate(f"e => Math.round(e.getBoundingClientRect().{prop})")


def run_wide(pw):
    """报告 AC-02/03: 1374x586(折叠屏展开) 档——座位零重叠/无横向滚动/650断点命中"""
    res = {"screen": "wide", "checks": [], "ok": True}
    br = pw.chromium.launch(headless=True)
    pg = br.new_context(viewport={"width": 1374, "height": 586}).new_page()
    pg.goto(URL); pg.wait_for_load_state("domcontentloaded")
    pg.evaluate("() => { try { localStorage.setItem('gto-tutored','1'); } catch(e){} }")
    pg.reload(); pg.wait_for_timeout(1800)
    def check(name, value, ok, target):
        res["checks"].append({"name": name, "value": value, "target": target, "ok": bool(ok)})
        if not ok:
            res["ok"] = False
    m = pg.evaluate("() => matchMedia('(orientation: landscape) and (max-height: 650px)').matches")
    check("宽横屏.650断点命中(586折叠屏)", m, m, "true")
    ow = pg.evaluate("() => document.documentElement.scrollWidth")
    check("宽横屏.大厅无横向滚动", ow, ow <= 1376, "<=1376")
    cta = pg.evaluate("""() => { const c = document.getElementById('mc-train'); if (!c) return null;
        const r = c.getBoundingClientRect();
        return { primary: c.classList.contains('mc-primary'), h: Math.round(r.height), bottom: Math.round(r.bottom) }; }""")
    check("宽横屏.主CTA存在且≥52px且在首屏", cta, bool(cta and cta.get("primary") and cta["h"] >= 52 and cta["bottom"] <= 586), "primary&h>=52&首屏")
    pg.evaluate("""() => { const t = Array.from(document.querySelectorAll('#landing .mc-title, #landing div')).find(d => d.classList && d.classList.contains('mc-title') && d.textContent.indexOf('开始对局') >= 0); if (t) t.click(); }""")
    entered = False
    for _ in range(24):
        pg.wait_for_timeout(700)
        if pg.evaluate("() => !document.getElementById('action-controls').classList.contains('hidden')"): entered = True; break
    check("宽横屏.成功进入对局", entered, entered, "controls visible")
    overlap = pg.evaluate("""() => {
      const seats = Array.from(document.querySelectorAll('.seat')).map(s => s.getBoundingClientRect());
      for (let i = 0; i < seats.length; i++) for (let j = i + 1; j < seats.length; j++) {
        const a = seats[i], b = seats[j];
        if (a.left < b.right - 2 && b.left < a.right - 2 && a.top < b.bottom - 2 && b.top < a.bottom - 2) return i + '-' + j;
      }
      return '';
    }""")
    check("宽横屏.六座位零重叠", overlap or "none", overlap == "", "零重叠")
    clipped = pg.evaluate("""() => {
      const vw = innerWidth, vh = innerHeight; let n = 0;
      document.querySelectorAll('.seat, #board, #pot, #actionbar button').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.right > vw + 2 || r.bottom > vh + 2 || r.left < -2) n++;
      });
      return n;
    }""")
    check("宽横屏.关键元素零裁切", clipped, clipped == 0, "0")
    ab = pg.evaluate("() => Math.round(document.getElementById('actionbar').getBoundingClientRect().height)")
    check("宽横屏.行动条≤92px", ab, ab <= 92, "<=92")
    br.close()
    return res


def main():
    ensure_server()
    screen = sys.argv[1] if len(sys.argv) > 1 else "all"
    with sync_playwright() as pw:
        if screen == "wide":
            res = run_wide(pw)
        else:
            res = run(pw, screen)
    if screen == "all":
        with sync_playwright() as pw:
            wide = run_wide(pw)
        res["wide"] = wide
        if not wide["ok"]:
            res["ok"] = False
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0 if res["ok"] else 1)


if __name__ == "__main__":
    main()
