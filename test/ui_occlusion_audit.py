# ui_occlusion_audit.py — 全功能 UI 遮挡审计（矩形相交 + 视口裁切 + 逐状态截图）
# 用法:
#   单机: python ui_occlusion_audit.py --out DIR --viewport 1600x900 --mode single [--seats 6] [--costume glam] [--nick NAME]
#   多人: python ui_occlusion_audit.py --out DIR --viewport 1600x900 --mode multi [--seats 6]
# 输出: DIR/<state>.png + DIR/audit.json（所有矩形、相交对、视口裁切、横向溢出）
import sys, time, json, os, argparse, traceback

URL = "http://localhost:8787/"

# 采集选择器（tag, selector, 是否装饰性）
SEL = [
    ("topbar", "#topbar", 0),
    ("topbar.stats", "#session-stats", 0),
    ("topbar.controls", "#topbar .controls", 0),
    ("landing.root", "#landing", 0),
    ("landing.card", "#landing-card", 0),
    ("landing.modecard", ".mode-card", 0),
    ("landing.char", "#landing-chars .lchar", 0),
    ("landing.tagline", ".tagline", 0),
    ("landing.foot", ".landing-foot", 0),
    ("modal.start", "#start-modal", 0),
    ("modal.startcard", "#start-card", 0),
    ("pick.charcard", "#char-grid .char-card", 0),
    ("pick.costume", "#costume-row", 0),
    ("btn.start", "#btn-start", 0),
    ("pick.preview", "#char-preview", 0),
    ("modal.multi", "#multi-modal", 0),
    ("mp.player", "#mp-players .mp-pl", 0),
    ("mp.statusline", "#mp-lobby-status", 0),
    ("mp.roomcode", "#mp-room-code", 0),
    ("btn.mpstart", "#mp-btn-start", 0),
    ("btn.mpready", "#mp-btn-ready", 0),
    ("btn.mpleave", "#mp-btn-leave", 0),
    ("mp.status", "#mp-status", 0),
    ("modal.data", "#data-modal", 0),
    ("table.felt", "#table-felt", 0),
    ("table.boardcard", "#board .card", 0),
    ("table.pot", "#pot", 0),
    ("seat", ".seat", 0),
    ("seat.pos", ".seat .pos", 0),
    ("seat.hole", ".seat .cards .card", 0),
    ("seat.emote", ".seat .emote.show", 0),
    ("side", "#side", 0),
    ("side.portrait", "#portrait-panel", 0),
    ("side.coach", "#coach", 0),
    ("side.log", "#logpanel", 0),
    ("side.logbody", "#log", 0),
    ("bar", "#actionbar", 0),
    ("bar.controls", "#action-controls", 0),
    ("btn.fold", "#btn-fold", 0),
    ("btn.checkcall", "#btn-checkcall", 0),
    ("btn.raise", "#btn-raise", 0),
    ("bar.preset", "#presets button", 0),
    ("bar.clock", "#turn-clock", 0),
    ("bar.hint", "#action-hint", 0),
    ("emote.strip", "#emote-strip", 0),
    ("emote.chip", "#emote-strip .emote-chip", 0),
    ("overlay", "#overlay", 0),
    ("overlay.card", "#overlay-card", 0),
    ("overlay.quote", "#overlay-body .ov-quotes", 0),
    ("coach.suggest", "#coach-body .suggest", 0),
    ("toast.error", "body > div[style*='position:fixed']", 0),
    ("petal", ".petals i", 1),   # 装饰层：仍采集，便于判断 z 序遮挡
]

MEASURE_JS = """
(sels) => {
  const out = [];
  const vw = window.innerWidth, vh = window.innerHeight;
  function layerOf(el) {
    const root = el.closest('#landing,#overlay,#multi-modal,#start-modal,#data-modal');
    if (!root) return 'base';
    if (root.id === 'landing') return 'landing';
    if (root.id === 'overlay') return 'overlay';
    return 'modal';
  }
  const nodes = [];
  sels.forEach(function (s) {
    const list = document.querySelectorAll(s.sel);
    let n = 0;
    list.forEach(function (el) {
      if (n >= 8) return;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return;
      if (r.width < 2 || r.height < 2) return;
      nodes.push({ el: el, meta: { tag: s.tag, deco: !!s.deco, i: n,
        x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
        z: cs.zIndex, pos: cs.position, layer: layerOf(el) } });
      n++;
    });
  });
  const els = nodes.map(function (n) { return n.meta; });
  const pairs = [];
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const A = nodes[i], B = nodes[j], a = A.meta, b = B.meta;
      if (a.layer !== b.layer) continue;                      // 跨层（遮罩 vs 底下内容）不算
      if (a.deco && b.deco) continue;
      if (A.el.contains(B.el) || B.el.contains(A.el)) continue;  // 祖先-后代包含 = 正常嵌套
      const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (ox > 2 && oy > 2) {
        pairs.push({ a: a.tag + '#' + a.i, b: b.tag + '#' + b.i,
          deco: !!(a.deco || b.deco), ox: Math.round(ox), oy: Math.round(oy),
          aZ: a.z, bZ: b.z, layer: a.layer });
      }
    }
  }
  return { vw: vw, vh: vh,
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
    els: els, pairs: pairs };
}
"""

def collect(page, state, results):
    data = page.evaluate(MEASURE_JS, [{"sel": s, "tag": t, "deco": d} for (t, s, d) in SEL])
    data["state"] = state
    pairs = data["pairs"]
    data["pairs"] = pairs
    # 视口裁切（装饰性花瓣按设计会飘出视口下缘，单独标注）
    clipped = []
    for e in els_clipped(data):
        clipped.append(e)
    data["clipped"] = clipped
    data["h_overflow"] = data["scrollW"] - data["clientW"]
    results.append(data)
    try:
        page.screenshot(path=os.path.join(OUT, f"{state}.png"))
    except Exception:
        pass
    real = [p for p in pairs if not p["deco"]]
    print(f"  [state] {state}: els={len(data['els'])} pairs={len(pairs)}(deco={len(pairs)-len(real)}) clipped={len(clipped)} hOverflow={data['h_overflow']}", flush=True)

def els_clipped(data):
    out = []
    for e in data["els"]:
        if e["x"] < -1 or e["y"] < -1 or e["x"] + e["w"] > data["vw"] + 1 or e["y"] + e["h"] > data["vh"] + 1:
            out.append({"tag": e["tag"], "i": e["i"], "deco": e["deco"], "x": e["x"], "y": e["y"], "w": e["w"], "h": e["h"]})
    return out

def is_visible(page, sel, timeout=800):
    try:
        page.wait_for_selector(sel, timeout=timeout, state="attached")
        return page.locator(sel).first.is_visible()
    except Exception:
        return False

def play_single_until_overlay(page, results, tag_prefix, max_sec=150):
    """单机：从已点的开始牌局起，抓 我的回合/翻牌/转牌/河牌/结算 各状态"""
    seen = set()
    t0 = time.time()
    last_board = 0
    while time.time() - t0 < max_sec:
        if is_visible(page, "#overlay:not(.hidden)", 300):
            if "showdown" not in seen:
                time.sleep(0.9)
                collect(page, f"{tag_prefix}showdown", results)
                seen.add("showdown")
            return True
        if is_visible(page, "#action-controls", 300):
            if "myturn" not in seen:
                collect(page, f"{tag_prefix}myturn", results)
                seen.add("myturn")
                # 点一次表情气泡（若有 chip）
                try:
                    page.locator("#emote-strip .emote-chip").first.click(timeout=1200)
                    time.sleep(0.4)
                    collect(page, f"{tag_prefix}emote_bubble", results)
                except Exception:
                    pass
            bc = page.locator("#btn-checkcall").text_content() or ""
            if "过牌" in bc:
                page.locator("#btn-checkcall").click()
            else:
                amt = "".join(ch for ch in bc if ch.isdigit())
                if amt and int(amt) <= 60:
                    page.locator("#btn-checkcall").click()
                else:
                    try:
                        page.locator("#btn-fold").click(timeout=1200)
                    except Exception:
                        page.locator("#btn-checkcall").click()
            time.sleep(0.8)
            continue
        n = page.locator("#board .card").count()
        if n == 3 and "flop" not in seen:
            collect(page, f"{tag_prefix}flop", results); seen.add("flop")
        elif n == 4 and "turn" not in seen:
            collect(page, f"{tag_prefix}turn", results); seen.add("turn")
        elif n == 5 and "river" not in seen:
            collect(page, f"{tag_prefix}river", results); seen.add("river")
        time.sleep(0.6)
    return False

def run_single(args, results):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_context(viewport={"width": args.vw, "height": args.vh}).new_page()
        pg.goto(URL); pg.wait_for_timeout(1800)
        collect(pg, "landing", results)
        pg.locator("#mc-train").click(); pg.wait_for_timeout(600)
        collect(pg, "start_modal", results)
        if args.costume:
            try:
                pg.locator("#costume-row label, #costume-row button").filter(has_text=args.costume).first.click(timeout=2000)
                pg.wait_for_timeout(1500)
                collect(pg, f"start_modal_{args.costume}", results)
            except Exception as e:
                print("  costume 切换失败:", e, flush=True)
        if args.seats:
            try:
                pg.locator(f'input[name="seats"][value="{args.seats}"]').check(timeout=1500)
            except Exception:
                pass
        pg.locator("#btn-start").click(); pg.wait_for_timeout(1500)
        collect(pg, "game_start", results)
        if args.vw <= 900:
            try:
                pg.locator("#emote-fab").click(timeout=1500); pg.wait_for_timeout(600)
                collect(pg, "emote_wheel", results)
                pg.locator("#emote-fab").click(timeout=800); pg.wait_for_timeout(300)
            except Exception as e:
                print("  emote_wheel 状态失败:", e, flush=True)
        play_single_until_overlay(pg, results, "")
        pg.wait_for_timeout(400)
        b.close()

def run_multi(args, results):
    from playwright.sync_api import sync_playwright
    suffix = f"{args.vw}x{args.vh}"
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": args.vw, "height": args.vh})
        host = ctx.new_page()
        host.goto(URL); host.wait_for_timeout(1600)
        collect(host, "m_host_landing", results)
        host.locator("#mc-multi").click(); host.wait_for_timeout(500)
        collect(host, "m_host_setup", results)
        host.locator("#mp-name").fill("遮挡房主")
        if args.seats:
            try:
                host.locator(f'input[name="mp-seats"][value="{args.seats}"]').check(timeout=1200)
            except Exception:
                pass
        host.locator("#mp-btn-create").click()
        code = ""
        for _ in range(20):
            code = (host.locator("#mp-room-code").text_content() or "").strip()
            if code and "-" not in code: break
            host.wait_for_timeout(500)
        host.wait_for_timeout(600)
        collect(host, "m_host_lobby", results)

        guest = ctx.new_page(); guest.goto(URL); guest.wait_for_timeout(1200)
        # 加入失败态（错误提示）
        guest.locator("#mc-multi").click(); guest.wait_for_timeout(400)
        guest.locator("#mp-name").fill("遮挡客人")
        guest.locator("#mp-tab-join").click()
        guest.locator("#mp-code").fill("ZZZZ99")
        guest.locator("#mp-btn-join").click()
        for _ in range(24):
            if (guest.locator("#mp-status").text_content() or "").strip():
                break
            guest.wait_for_timeout(500)
        collect(guest, "m_guest_joinfail", results)

        # 正常加入
        guest.locator("#mp-code").fill(code)
        guest.locator("#mp-btn-join").click()
        for _ in range(20):
            if guest.locator("#mp-lobby").is_visible(): break
            guest.wait_for_timeout(500)
        guest.wait_for_timeout(600)
        collect(guest, "m_guest_lobby", results)
        guest.locator("#mp-btn-ready").click()
        for _ in range(40):
            if guest.locator("#multi-modal").evaluate("el => el.classList.contains('hidden')"): break
            guest.wait_for_timeout(500)
        host.wait_for_timeout(1500)
        collect(guest, "m_guest_table", results)
        collect(host, "m_host_table", results)

        # 双端各抓一次行动/结算
        for who, page in (("host", host), ("guest", guest)):
            t0 = time.time(); acted = 0; showdown_done = False
            while time.time() - t0 < 240:
                if page.locator("#overlay:not(.hidden)").count():
                    time.sleep(0.9)
                    collect(page, f"m_{who}_showdown", results)
                    showdown_done = True
                    try: page.locator("#btn-next").click(timeout=1200)
                    except Exception: pass
                    break
                if page.locator("#action-controls").is_visible():
                    acted += 1
                    if acted == 1:
                        collect(page, f"m_{who}_myturn", results)
                    cb = page.locator("#btn-checkcall").text_content() or ""
                    if "过牌" in cb:
                        page.locator("#btn-checkcall").click()
                    else:
                        amt = "".join(ch for ch in cb if ch.isdigit())
                        if amt and int(amt) <= 60:
                            page.locator("#btn-checkcall").click()
                        else:
                            try: page.locator("#btn-fold").click(timeout=1200)
                            except Exception: page.locator("#btn-checkcall").click()
                    time.sleep(0.8)
                    continue
                time.sleep(0.8)
        # 下一局等一手（抓 stream of states for guest flop 等）
        b.close()

def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--viewport", default="1600x900")
    ap.add_argument("--mode", default="single", choices=["single", "multi"])
    ap.add_argument("--seats", default="")
    ap.add_argument("--costume", default="")
    ap.add_argument("--nick", default="")
    args = ap.parse_args()
    OUT = args.out
    os.makedirs(OUT, exist_ok=True)
    args.vw, args.vh = map(int, args.viewport.lower().split("x"))
    results = []
    try:
        if args.mode == "single":
            run_single(args, results)
        else:
            run_multi(args, results)
    except Exception:
        print(traceback.format_exc(), flush=True)
    json.dump({"viewport": args.viewport, "mode": args.mode, "seats": args.seats,
               "costume": args.costume, "states": results},
              open(os.path.join(OUT, "audit.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total_pairs = sum(len(r["pairs"]) for r in results)
    total_clip = sum(len(r["clipped"]) for r in results)
    print(f"DONE {args.mode}@{args.viewport}: states={len(results)} pairs={total_pairs} clipped={total_clip}", flush=True)

if __name__ == "__main__":
    main()
