# -*- coding: utf-8 -*-
"""同步 game/ → mobile/www/ （APK staging，可重复执行）

规则（与首版 staging 一致并修正 vendor 缺失）：
  index.html / privacy.html                    全量
  css/ js/（含 js/vendor）                     全量递归
  assets/cards  assets/chips  assets/table     全量递归
  assets/characters_v2                         仅 .webp（png 原图不进 APK）

用法: python sync_www.py
"""
import shutil
import sys
from pathlib import Path

GAME = Path(__file__).resolve().parent.parent   # game/
WWW = Path(__file__).resolve().parent / "www"   # game/mobile/www

FILES = ["index.html", "privacy.html"]
DIRS_FULL = ["css", "js", "assets/cards", "assets/chips", "assets/table"]
DIR_WEBP_ONLY = ["assets/characters_v2"]


def rm(p):
    if p.is_dir():
        shutil.rmtree(p)
    elif p.exists():
        p.unlink()


def copy_dir(src, dst, webp_only=False):
    rm(dst)
    dst.mkdir(parents=True)
    n = 0
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        if webp_only and f.suffix.lower() != ".webp":
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        n += 1
    return n


def main():
    total = 0
    for name in FILES:
        src = GAME / name
        if src.exists():
            shutil.copy2(src, WWW / name)
            total += 1
    for rel in DIRS_FULL:
        n = copy_dir(GAME / rel, WWW / rel)
        print(f"[{rel}] {n} files")
        total += n
    for rel in DIR_WEBP_ONLY:
        n = copy_dir(GAME / rel, WWW / rel, webp_only=True)
        print(f"[{rel}] {n} files (webp only)")
        total += n
    # 清掉历史遗留的空 vendor（peerjs 现随 js/vendor 递归进包）
    stray = WWW / "vendor"
    if stray.exists() and not any(stray.iterdir()):
        stray.rmdir()
        print("removed stray empty www/vendor")
    print(f"SYNC DONE · {total} files -> {WWW}")
    # gradle 打包的是 android/app/src/main/assets/public，必须经 cap copy 桥接
    import subprocess
    r = subprocess.run(["npx", "cap", "copy", "android"], cwd=Path(__file__).parent,
                       capture_output=True, text=True, shell=True)
    print(r.stdout[-300:] if r.returncode == 0 else "CAP COPY FAIL:\n" + (r.stderr or "")[-500:])
    sys.exit(r.returncode)


if __name__ == "__main__":
    sys.exit(main())
