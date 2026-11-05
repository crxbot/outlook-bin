#!/usr/bin/env python3
"""Lädt die Waldbrand-WebP, lässt waldbrand_meta.py alles erzeugen
und kann einen Punkt (lat/lon) nachschlagen."""
import argparse, json, sys, urllib.request
from pathlib import Path
from urllib.parse import urljoin
import numpy as np

from waldbrand_meta import LEGEND, build, merc_y

JSON_URL = "https://app-prod-static.warnwetter.de/v16/waldbrand_animation_overview.json"
UA = {"User-Agent": "Mozilla/5.0"}


def http_get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def find_waldbrand_file(obj):
    """Sucht rekursiv den Eintrag "WALDBRAND" -> "file"."""
    if isinstance(obj, dict):
        wb = obj.get("WALDBRAND")
        if isinstance(wb, dict) and isinstance(wb.get("file"), str):
            return wb["file"]
        for v in obj.values():
            r = find_waldbrand_file(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_waldbrand_file(v)
            if r:
                return r
    return None


def download_webp(json_url):
    meta = json.loads(http_get(json_url))
    fname = find_waldbrand_file(meta)
    if not fname:
        sys.exit('Kein Eintrag "WALDBRAND" -> "file" im JSON gefunden.')
    print("Dateiname laut JSON:", fname)
    # Wo genau die Datei liegt, ist nicht bekannt -> mehrere Kandidaten probieren
    names = [fname, fname.replace(".", "_", fname.count(".") - 1)]
    cands = []
    for n in dict.fromkeys(names):
        cands += [urljoin(json_url, n), urljoin(json_url, "mobile/" + n)]
    for u in cands:
        try:
            data = http_get(u)
            print("Geladen von:", u)
            return data
        except Exception as e:
            print("  nicht gefunden:", u, "-", e)
    sys.exit("WebP nicht gefunden. Mit --webp-url oder --webp manuell angeben.")


def lookup(out, lat, lon):
    m = json.loads((out / "meta.json").read_text())
    b, W, H = m["bounds"], m["width"], m["height"]
    x = int((lon - b["west"]) / (b["east"] - b["west"]) * W)
    y = int((merc_y(b["north"]) - merc_y(lat)) / (merc_y(b["north"]) - merc_y(b["south"])) * H)
    if not (0 <= x < W and 0 <= y < H):
        sys.exit("Punkt liegt außerhalb des Bildes.")
    print(f"Pixel x={x}, y={y}")
    for d in m["days"]:
        v = np.fromfile(out / d["file"], dtype=np.uint8).reshape(H, W)[y, x]
        print(d["date"], int(v), LEGEND[int(v)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-url", default=JSON_URL)
    ap.add_argument("--webp-url", help="WebP direkt von dieser URL laden")
    ap.add_argument("--webp", help="lokale WebP-Datei verwenden")
    ap.add_argument("--out", default="waldbrand_out")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    a = ap.parse_args()
    out = Path(a.out)

    if a.lat is not None and a.lon is not None and not (a.webp or a.webp_url) and (out / "meta.json").exists():
        return lookup(out, a.lat, a.lon)

    if a.webp:
        raw = Path(a.webp).read_bytes()
    elif a.webp_url:
        raw = http_get(a.webp_url)
    else:
        raw = download_webp(a.json_url)

    build(raw, out)  # schreibt Tagesdateien + meta.json
    print("Fertig ->", out.resolve())
    if a.lat is not None and a.lon is not None:
        lookup(out, a.lat, a.lon)


if __name__ == "__main__":
    main()