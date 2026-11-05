#!/usr/bin/env python3
"""Erzeugt aus der Waldbrand-WebP-Animation alle Ausgabedateien:
pro Tag eine Datei WALDBRAND_YYYYMMDD ohne Endung (uint8-Stufen) und eine meta.json.

Nutzung:  python waldbrand_meta.py --webp datei.webp --out waldbrand_out
"""
import argparse, datetime as dt, io, json, math, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageSequence

LEGEND = {0: "außerhalb / keine Daten", 1: "sehr gering", 2: "gering",
          3: "mittel", 4: "hoch", 5: "sehr hoch"}
R = 6378137.0


def merc_y(lat):  # Web-Mercator, Einheitskugel
    return math.asinh(math.tan(math.radians(lat)))


def read_xmp(im):
    x = im.info.get("xmp", b"")
    x = x.decode("utf-8", "ignore") if isinstance(x, bytes) else x
    g = lambda k: float(re.search(rf"<custom:{k}>([^<]+)<", x).group(1))
    return dict(start=g("start") / 1000, step=g("timestep") / 1000,
                west=g("lowerLongitude"), east=g("upperLongitude"),
                south=g("lowerLatitude"), north=g("upperLatitude"))


def frame_to_levels(frame):
    a = np.array(frame.convert("RGBA"))
    lvl = (a[..., 1] // 51 + 1).astype(np.uint8)          # Grünwert 0,51,102,... -> 1,2,3,...
    outside = (a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 0)
    lvl[outside] = 0                                      # Rot = außerhalb
    return lvl


def build(raw, out):
    """WebP-Bytes -> Tagesdatei pro Tag + meta.json in `out`. Gibt das Meta-Dict zurück."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    im = Image.open(io.BytesIO(raw))
    x = read_xmp(im)

    days, shape = [], None
    for i, f in enumerate(ImageSequence.Iterator(im)):
        lvl = frame_to_levels(f)
        shape = shape or lvl.shape
        d = dt.datetime.fromtimestamp(x["start"] + i * x["step"], dt.timezone.utc)
        fn = f"WALDBRAND_{d:%Y%m%d}"
        lvl.tofile(out / fn)
        days.append({"date": d.strftime("%d.%m.%Y"), "iso": d.strftime("%Y-%m-%d"), "file": fn})
        cnt = np.bincount(lvl.ravel(), minlength=6)
        print(fn, "Stufen 1-5:", cnt[1:].tolist())
    H, W = shape

    b = {k: x[k] for k in ("west", "east", "south", "north")}
    meta = {"width": W, "height": H, "dtype": "uint8",
            "order": "row-major, oben links beginnend",
            "projection": "EPSG:3857 (Web Mercator)", "bounds": b,
            "bounds_3857": {"west": R * math.radians(b["west"]), "east": R * math.radians(b["east"]),
                            "south": R * merc_y(b["south"]), "north": R * merc_y(b["north"])},
            "nodata": 0, "levels": {str(k): v for k, v in LEGEND.items()}, "days": days}
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--webp", required=True, help="lokale WebP-Datei")
    ap.add_argument("--out", default="waldbrand_out")
    a = ap.parse_args()
    build(Path(a.webp).read_bytes(), a.out)
    print("Fertig ->", Path(a.out).resolve())