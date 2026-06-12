#!/usr/bin/env python3
"""Build the offline world map asset.

Fetches public-domain world country outlines (Natural Earth derived GeoJSON),
projects them to an equirectangular 1000x500 canvas, simplifies the geometry,
and writes data/worldmap.json with a single SVG path string. The app never
touches the network: this runs once at build time.
"""
import json
import os
import sys
import urllib.request

URLS = [
    "https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json",
]

W, H = 1000.0, 500.0
SIMPLIFY_EPS = 0.7      # min px between kept points
MIN_RING_SPAN = 1.1     # drop rings smaller than this in both dimensions

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "worldmap.json")


def proj(lon, lat):
    return ((lon + 180.0) / 360.0 * W, (90.0 - lat) / 180.0 * H)


def simplify(ring):
    pts = [proj(lon, lat) for lon, lat in ring]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if (max(xs) - min(xs)) < MIN_RING_SPAN and (max(ys) - min(ys)) < MIN_RING_SPAN:
        return None
    kept = [pts[0]]
    for p in pts[1:]:
        last = kept[-1]
        if abs(p[0] - last[0]) + abs(p[1] - last[1]) >= SIMPLIFY_EPS:
            kept.append(p)
    if len(kept) < 4:
        return None
    return kept


def ring_to_d(pts):
    parts = ["M%.1f %.1f" % pts[0]]
    parts += ["L%.1f %.1f" % p for p in pts[1:]]
    parts.append("Z")
    return "".join(parts)


def main():
    geo = None
    for url in URLS:
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                geo = json.load(r)
            print("fetched", url)
            break
        except Exception as e:  # noqa: BLE001
            print("failed", url, e, file=sys.stderr)
    if geo is None:
        sys.exit("could not fetch any world geojson source")

    rings = []
    for feat in geo["features"]:
        g = feat.get("geometry") or {}
        if g.get("type") == "Polygon":
            polys = [g["coordinates"]]
        elif g.get("type") == "MultiPolygon":
            polys = g["coordinates"]
        else:
            continue
        for poly in polys:
            for ring in poly:
                pts = simplify(ring)
                if pts:
                    rings.append(pts)

    d = "".join(ring_to_d(r) for r in rings)
    out = {"viewBox": "0 0 1000 500", "width": W, "height": H, "land": d,
           "attribution": "Country outlines derived from Natural Earth (public domain)"}
    with open(OUT, "w") as f:
        json.dump(out, f)
    print("rings kept:", len(rings))
    print("worldmap.json bytes:", os.path.getsize(OUT))


if __name__ == "__main__":
    main()
