# probe_sbm_chip.py — 选中超链接 chip 的绘制机制探针（transform? shadow? margin?）
import json
from playwright.sync_api import sync_playwright

JS = """() => {
  return Array.from(document.querySelectorAll('#data-body .data-mode-chip')).map(function(c){
    const cs = getComputedStyle(c); const r = c.getBoundingClientRect();
    return {t: c.textContent, sel: c.classList.contains('sel'),
            offsetW: c.offsetWidth, rectW: +r.width.toFixed(2), rectH: +r.height.toFixed(2),
            transform: cs.transform, borderWidth: cs.borderWidth, padding: cs.padding,
            outline: cs.outlineWidth + ' ' + cs.outlineStyle,
            shadow: cs.boxShadow === 'none' ? 'none' : cs.boxShadow.slice(0, 80)};
  });
}"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_context(viewport={"width": 1600, "height": 900}).new_page()
    pg.goto("http://localhost:8787/")
    pg.wait_for_timeout(1500)
    pg.locator("#mc-data").click()
    pg.wait_for_timeout(1200)
    print(json.dumps(pg.evaluate(JS), ensure_ascii=False, indent=1))
    b.close()
