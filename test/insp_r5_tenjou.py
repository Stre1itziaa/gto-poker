# insp_r5_tenjou.py — R5 天证骑士 终审无头复现（只读验证，不改游戏代码）
# 1) 牌谱行 DOM 有但 09 截图视觉消失 → 定责（display/高度/滚动容器）
# 2) ⑤展开滚动让位：点开 details 后 scrollIntoView + scroll-margin-bottom 是否防遮挡
# 3) ④范围 chips 切换选中态视觉（全部/多人/单机）
# 4) 翻前/翻后行动流渲染口径抽验（读 DOM 文本）
import json, os, glob, time
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data5", "tenjou")
os.makedirs(OUT, exist_ok=True)
recs = []
for f in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "hand-logs", "STXJ8D", "hand_000[1-4]*.json"))):
    recs.append(json.load(open(f, encoding="utf-8")))
print("loaded recs:", len(recs))

def shot(page, tag):
    page.screenshot(path=os.path.join(OUT, f"{tag}.png"))
    print("shot", tag)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_context(viewport={"width": 1600, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8787/")
    pg.wait_for_timeout(1200)
    # 灌档（与客人端同源：DataPage.record）
    pg.evaluate("recs => recs.forEach(r => window.DataPage.record(JSON.parse(JSON.stringify(r))))", recs)
    pg.wait_for_timeout(300)
    pg.locator("#mc-data").click()
    pg.wait_for_timeout(1000)
    shot(pg, "11_data_replay")

    info = pg.evaluate("""() => {
      const body = document.getElementById('data-body');
      const rows = [...document.querySelectorAll('#data-body details.data-hand')];
      const cs = el => getComputedStyle(el);
      const one = rows.length ? rows[0] : null;
      let chain = [];
      let el = one;
      while (el && el.id !== 'data-body') {
        const s = cs(el);
        chain.push({tag: el.tagName, cls: el.className && String(el.className).slice(0,40),
          display: s.display, h: el.getBoundingClientRect().height,
          maxH: s.maxHeight, of: s.overflowY});
        el = el.parentElement;
      }
      return {
        rows: rows.length,
        bodyScroll: {sh: body.scrollHeight, ch: body.clientHeight, st: body.scrollTop, of: cs(body).overflowY},
        row0: one ? {display: cs(one).display, vis: cs(one).visibility, h: one.getBoundingClientRect().height,
                     text: (one.querySelector('summary')||{}).textContent || ''} : null,
        chain: chain,
        firstActs: one ? (one.textContent.match(/(翻前|翻牌|转牌|河牌)[^翻牌转河]{0,80}/g)||[]).slice(0,6) : []
      };
    }""")
    print("INFO:", json.dumps(info, ensure_ascii=False)[:900])
    shot(pg, "12_data_scrolled")

    # ⑤ 展开最后一条（第 4 手）→ 观察滚动让位
    pg.evaluate("""() => {
      const rows = [...document.querySelectorAll('#data-body details.data-hand')];
      rows[rows.length-1].scrollIntoView({block:'nearest'});
    }""")
    pg.wait_for_timeout(200)
    last = pg.locator("#data-body details.data-hand").last
    last.locator("summary").click()
    pg.wait_for_timeout(500)
    occl = pg.evaluate("""() => {
      const rows = [...document.querySelectorAll('#data-body details.data-hand')];
      const d = rows[rows.length-1];
      d.scrollIntoView({block:'nearest'});
      const r = d.getBoundingClientRect();
      const body = document.getElementById('data-body');
      const foot = document.querySelector('#data-modal .mp-row, #data-foot, #data-export');
      let footR = foot ? foot.getBoundingClientRect() : null;
      // 逐像素采样：行底部 20px 带中心是否被其它元素盖住
      let covered = null;
      const y = r.bottom - 10, x = r.left + r.width/2;
      const top = document.elementFromPoint(x, y);
      covered = top ? (top.tagName + '.' + String(top.className).slice(0,30)) : 'null';
      return {rowRect: {top: r.top, bottom: r.bottom, h: r.height},
        bodyRect: {bottom: body.getBoundingClientRect().bottom},
        coveredAtRowBottom: covered,
        smb: getComputedStyle(d).scrollMarginBottom,
        open: d.open, openRows: rows.filter(x=>x.open).length};
    }""")
    print("OCCL:", json.dumps(occl, ensure_ascii=False))
    shot(pg, "13_detail_expanded")

    # ④ chips 切换：多人 → 单机 → 全部，每步截取 chip 区
    for mode, tag in [("mp", "14_chip_mp"), ("sp", "15_chip_sp"), ("", "16_chip_all")]:
        pg.locator(f'#data-body .data-mode-chip[data-mode="{mode}"]').click()
        pg.wait_for_timeout(400)
        chip = pg.evaluate("""() => {
          const chips = [...document.querySelectorAll('#data-body .data-mode-chip')];
          const stats = window.DataPage.stats(window.DataPage.all());
          return {sel: chips.filter(c=>c.classList.contains('sel')).map(c=>c.dataset.mode),
            cls: chips.map(c=>c.dataset.mode+':'+(c.classList.contains('sel')?'sel':'')),
            visible: chips.map(c=>c.dataset.mode+':'+(c.offsetParent?1:0))};
        }""")
        print(mode or "all", "->", json.dumps(chip, ensure_ascii=False))
        pg.locator("#data-body .data-mode-chips, #data-body").first.scroll_into_view_if_needed()
        shot(pg, tag)

    # 牌谱行动流口径抽验（第 1、2 手：翻前 raise / 翻后首攻）
    acts = pg.evaluate("""() => {
      return [...document.querySelectorAll('#data-body details.data-hand')].map(d => {
        const segs = [...d.querySelectorAll('.data-acts')].map(x => x.textContent.trim());
        return {sum: (d.querySelector('summary')||{}).textContent, segs};
      });
    }""")
    print("ACTS:", json.dumps(acts, ensure_ascii=False)[:1500])
    pg.wait_for_timeout(200)
    shot(pg, "17_final_replay")
    print("js_errors:", errs[:5])
    b.close()
