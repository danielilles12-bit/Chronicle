#!/usr/bin/env python3
"""Image variant builder (P5.3a) — small WebP copies for actual serving.

For every assets/img/<name>.<ext> source, emits assets/img/w800/<name>.webp:
same picture, longest edge capped at 800px, WebP quality ~80. Skipped when
the variant is already newer than its source, so re-runs after a fresh
tools/fetch_commons.py pull only touch new or replaced files.

Originals are never modified or deleted — they stay in place as the client's
fallback (js/app.js, js/revealgame.js try the w800 WebP first and swap to
the original on any load error) and as the zoomed-inspection source, which
is plenty sharp at 800px.

Usage:
  python3 tools/build_image_variants.py
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "assets/img"
OUT_DIR = SRC_DIR / "w800"
MAX_EDGE = 800
QUALITY = 80
EXTS = {".jpg", ".jpeg", ".png"}


def needs_build(src, dst):
    return not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime


def build_variant(src, dst):
    with Image.open(src) as im:
        # Bake in EXIF rotation before resizing — a re-saved WebP carries no
        # orientation tag of its own, so skipping this would leave rotated
        # source photos displaying sideways.
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        w, h = im.size
        scale = MAX_EDGE / max(w, h)
        if scale < 1:
            im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
        im.save(dst, "WEBP", quality=QUALITY, method=6)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in SRC_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTS)
    built = skipped = failed = 0
    for src in sources:
        dst = OUT_DIR / (src.stem + ".webp")
        if not needs_build(src, dst):
            skipped += 1
            continue
        try:
            build_variant(src, dst)
            built += 1
        except Exception as e:
            failed += 1
            print(f"FAILED {src.name}: {e}", file=sys.stderr)
    print(f"variants: {built} built, {skipped} up to date, {failed} failed "
          f"-> {OUT_DIR.relative_to(ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
