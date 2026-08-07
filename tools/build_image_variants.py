#!/usr/bin/env python3
"""Image tool (P5.3a): keeps BOTH copies of every picture inside MAX_EDGE.

For every assets/img/<name>.<ext> source, emits assets/img/w800/<name>.webp:
same picture, longest edge capped at MAX_EDGE, WebP quality ~78. Skipped when
the variant is already newer than its source, so re-runs after a fresh
tools/fetch_commons.py pull only touch new or replaced files.

  python3 tools/build_image_variants.py              # build the served copies
  python3 tools/build_image_variants.py --force      # ...rebuild all of them
  python3 tools/build_image_variants.py --cap-originals   # shrink the originals

--cap-originals (7 Aug 2026) downscales the TOP-LEVEL originals in place to the
same MAX_EDGE. Run it after any batch that pulls full-resolution masters, and
run it BEFORE building variants so each variant is made from the master.

Why it exists: originals used to be left alone, because fetch_commons.py only
ever pulled a ~1200px thumbnail, so "untouched" and "small" were the same
thing. The "Sharper pictures" commit (e4748ec3, 7 Aug 2026) fetched 97 files
at FULL resolution instead, and nothing anywhere capped them: assets/img/ went
to 814 MB with three files over 25 MB. Cloudflare Pages refuses any file above
25 MiB, so every deploy failed and the live site sat on a stale build. The
originals are also the client's fallback (js/app.js loadImgFallback tries
w800 first and swaps to the original on any error) — so a 59 MB original is
a 59 MB download to somebody's phone the moment the variant misses.

Both ceilings are now the same number, and tools/repo_checks.py fails CI if
any tracked file gets near the host's limit again.

Usage:
  python3 tools/build_image_variants.py
"""
import io
import sys
import warnings
from pathlib import Path

from PIL import Image, ImageOps

# Deliberate ceiling, not Pillow's default. Pillow ships MAX_IMAGE_PIXELS at
# ~89 MP: above that it WARNS, and only above twice that does it refuse
# outright. Museum masters routinely exceed 89 MP for real (Neuschwanstein
# arrived at 155 MP), so the default meant our biggest, most urgent files
# processed while quietly printing a "decompression bomb" warning nobody read.
# 400 MP is above any legitimate Commons master and still refuses a genuine
# bomb; anything larger is reported by name and fails the run.
Image.MAX_IMAGE_PIXELS = 400_000_000
# ...and a warning about image size is never routine here — promote it to an
# error so it lands in the failure list with the filename instead of scrolling
# past in a 800-file run.
warnings.simplefilter("error", Image.DecompressionBombWarning)

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "assets/img"
OUT_DIR = SRC_DIR / "w800"
# 6 Aug 2026: raised from 800 to 1600. The game crops every picture to a SQUARE
# window and then allows 4x zoom, so an 800px longest edge left portrait and
# panoramic sources with only 400-650 usable pixels across the square — visibly
# soft on a modern phone, and softer still once zoomed. Measured cost of the
# change on a 30-image sample: 64KB -> 160KB average, i.e. 0.63MB -> 1.56MB for
# a day's ten puzzle images. The directory name stays w800 because that path is
# baked into js/app.js and js/revealgame.js; renaming it is a separate job.
MAX_EDGE = 1600
QUALITY = 78
EXTS = {".jpg", ".jpeg", ".png"}

# Quality for a capped ORIGINAL. Higher than the variant's because this file is
# the fallback that has to stand in for the variant: it must never be the worse
# picture. Measured over a 12-image sample of the hardest (largest, most
# detailed) files, both at 1600px: served WebP q78 averages 35.1 dB PSNR, this
# setting averages 39.0 dB — the fallback is ~4 dB BETTER than the copy players
# normally see, so a fallback can only ever improve the picture, never degrade
# it. 4:4:4 (no chroma subsampling) because Face Value and Relic tear and zoom
# into these, and subsampling is what smears a zoomed edge.
ORIGINAL_QUALITY = 92
ORIGINAL_SUBSAMPLING = 0  # 4:4:4
# Shrinking must never cost bytes. A file only just over the cap (1280x1674,
# say) loses almost no pixels, so re-encoding it at a quality more generous
# than its source arrived at would make the file BIGGER — 150 files grew by a
# combined 15 MB on the first run of this. Where that happens, quality steps
# down until the result is no larger than the source. The floor is the point
# below which the fallback would stop being clearly better than the served
# WebP, so quality is never traded away past it: a file that is still larger
# at the floor is written anyway and named in the summary. That is safe —
# these are all small files to begin with, nowhere near a deploy limit.
ORIGINAL_QUALITY_FLOOR = 84


def needs_build(src, dst):
    return not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime


def cap_original(src):
    """Shrink one original in place to MAX_EDGE. Returns (before, after) bytes,
    or None when it was already small enough (never upscale).

    Everything that identifies the file is preserved: same path, same name,
    same real format, same colour mode, same embedded colour profile. Only the
    pixel dimensions change. Written via a temporary file and then moved into
    place, so an interrupted run cannot leave a half-written picture.
    """
    before = src.stat().st_size
    with Image.open(src) as im:
        im.load()
        # The REAL format, which is not always the extension: fetch_commons.py
        # names every download <id>.jpg whatever Commons actually served, so a
        # handful of these are genuine PNG (some with transparency) and one is
        # an MPO. Re-saving a PNG as JPEG would flatten its alpha to black, so
        # the format is read from the bytes and kept.
        fmt = (im.format or "").upper()
        mode, icc = im.mode, im.info.get("icc_profile")
        w, h = im.size
        if max(w, h) <= MAX_EDGE:
            return None
        scale = MAX_EDGE / max(w, h)
        out = im.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                        Image.LANCZOS)

    kw = {}
    if icc:
        kw["icc_profile"] = icc
    if fmt in ("JPEG", "MPO"):
        # MPO is a JPEG carrying extra frames; saving the primary frame as
        # plain JPEG is exactly what every browser already displays.
        save_fmt = "JPEG"
        kw.update(optimize=True)
        if mode not in ("L", "1"):
            kw["subsampling"] = ORIGINAL_SUBSAMPLING
        qualities = list(range(ORIGINAL_QUALITY, ORIGINAL_QUALITY_FLOOR - 1, -2))
    elif fmt == "PNG":
        save_fmt = "PNG"
        kw["optimize"] = True
        qualities = [None]      # PNG is lossless; there is no dial to turn
    else:
        raise ValueError(
            f"unhandled image format {fmt!r} — add a rule for it rather than "
            f"guessing, so nothing is silently re-encoded into another format")

    blob = None
    for q in qualities:
        buf = io.BytesIO()
        out.save(buf, save_fmt, **({**kw, "quality": q} if q else kw))
        blob = buf.getvalue()
        if len(blob) <= before:
            break

    tmp = src.with_name(src.name + ".capping")
    try:
        tmp.write_bytes(blob)
        tmp.replace(src)
    finally:
        if tmp.exists():
            tmp.unlink()
    return before, src.stat().st_size


def cap_originals():
    """Bring every top-level original inside MAX_EDGE. Loud about anything it
    could not process — a skipped file here is a failed deploy later."""
    sources = sorted(p for p in SRC_DIR.iterdir()
                     if p.is_file() and p.suffix.lower() in EXTS)
    capped = untouched = failed = 0
    before_total = after_total = 0
    grew = []
    for src in sources:
        try:
            size_before = src.stat().st_size
            result = cap_original(src)
            before_total += size_before
            if result is None:
                untouched += 1
                after_total += size_before
            else:
                capped += 1
                after_total += result[1]
                if result[1] > size_before:
                    grew.append((result[1] - size_before, src.name))
        except Exception as e:
            failed += 1
            after_total += src.stat().st_size
            print(f"FAILED {src.name}: {type(e).__name__}: {e}", file=sys.stderr)
    print(f"originals: {capped} shrunk to {MAX_EDGE}px, {untouched} already "
          f"small enough, {failed} failed")
    print(f"           {before_total / 1048576:.1f} MB -> "
          f"{after_total / 1048576:.1f} MB")
    if grew:
        # Not a failure: these are small files that were only just over the
        # cap. Worth naming so nobody has to wonder why the total moved.
        print(f"           {len(grew)} file(s) still ended up larger, by "
              f"{sum(g for g, _ in grew) / 1048576:.1f} MB in total "
              f"(biggest: {sorted(grew, reverse=True)[0][1]})")
    if failed:
        print(f"\n{failed} file(s) could not be processed and are still "
              f"oversized. Fix them before deploying: Cloudflare Pages "
              f"rejects any single file over 25 MiB, and one rejected file "
              f"fails the WHOLE deploy.", file=sys.stderr)
    return 1 if failed else 0


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
    args = sys.argv[1:]
    # --cap-originals is its own job: it shrinks the top-level originals and
    # deliberately does NOT touch assets/img/w800/, so it can be run on its own
    # to fix an oversized corpus without re-encoding a variant set that is
    # already correct.
    if "--cap-originals" in args:
        return cap_originals()
    # --force rebuilds every variant regardless of mtime. Needed whenever
    # MAX_EDGE or QUALITY changes: the mtime check only knows about replaced
    # SOURCES, so without this a cap change silently leaves every untouched
    # image at the old size.
    force = "--force" in args
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in SRC_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTS)
    built = skipped = failed = 0
    for src in sources:
        dst = OUT_DIR / (src.stem + ".webp")
        if not force and not needs_build(src, dst):
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
