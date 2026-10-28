"""Extract the A6 study area from the national WorldPop raster, bit-identically, with a provenance manifest.

Use this when the full national GeoTIFF (55.8 MB) cannot be moved around (upload limits, small disks).
The extract is a pixel-aligned window (no resampling, values unchanged) plus a JSON manifest that ties it
to the SHA-256 of the national file. `a6.build` accepts the extract only if the manifest matches the lock.

    python scripts/a6_extract_study_area.py  sau_pop_2026_CN_100m_R2025A_v1.tif  out_dir/

Works stand-alone (e.g. in Colab): needs only numpy + rasterio.
"""
import datetime as dt
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import rasterio

LOCK_SHA256 = os.environ.get("A6_LOCK_SHA256") or "3ed9bc9ad51cd99d75461816e6c01ad71d466303adaab0809d1a989aabe57410"
STUDY = {"south": 20.0, "north": 23.0, "west": 38.0, "east": 41.0}   # = config/a6.yaml study_area


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapped_window(ds, a):
    inv = ~ds.transform
    c0, r0 = inv * (a["west"], a["north"])
    c1, r1 = inv * (a["east"], a["south"])
    col0, row0 = math.floor(round(c0, 6)), math.floor(round(r0, 6))
    col1, row1 = math.ceil(round(c1, 6)), math.ceil(round(r1, 6))
    return max(col0, 0), max(row0, 0), min(col1, ds.width), min(row1, ds.height)


def main(src, out_dir):
    src, out_dir = Path(src), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    h = sha256(src)
    print("national raster SHA-256:", h, "(matches lock)" if h == LOCK_SHA256 else "(DOES NOT MATCH LOCK)")
    if h != LOCK_SHA256:
        sys.exit("Refusing to extract from a file that does not match the locked WorldPop release.")
    with rasterio.open(src) as ds:
        col0, row0, col1, row1 = snapped_window(ds, STUDY)
        win = rasterio.windows.Window(col0, row0, col1 - col0, row1 - row0)
        a = ds.read(1, window=win)
        total, n_pos = 0.0, 0
        for _, bw in ds.block_windows(1):
            b = ds.read(1, window=bw)
            v = b[(b != ds.nodata) & np.isfinite(b)].astype(np.float64)
            total += float(v.sum())
            n_pos += int((v > 0).sum())
        prof = ds.profile.copy()
        prof.update(width=win.width, height=win.height, transform=ds.window_transform(win), driver="GTiff",
                    compress="deflate", predictor=3, zlevel=9, tiled=True, blockxsize=256, blockysize=256)
        src_meta = {"width": ds.width, "height": ds.height, "crs_epsg": ds.crs.to_epsg(), "res": list(ds.res),
                    "nodata": ds.nodata, "dtype": ds.dtypes[0], "transform": list(ds.transform)[:6]}
    ext = out_dir / "a6_study_area_extract.tif"
    with rasterio.open(ext, "w", **prof) as dst:
        dst.write(a, 1)
    with rasterio.open(ext) as chk:
        assert np.array_equal(chk.read(1), a), "extract is not bit-identical"
    valid = a[(a != prof["nodata"]) & np.isfinite(a)].astype(np.float64)
    man = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source_file": src.name, "source_sha256": h, "source_raster": src_meta,
        "study_area_requested": STUDY,
        "window": {"col_off": col0, "row_off": row0, "width": col1 - col0, "height": row1 - row0},
        "extract_file": ext.name, "extract_sha256": sha256(ext),
        "extract_window_total": math.fsum(valid.tolist()),
        "national_total": total, "national_populated_cells": n_pos,
        "rasterio": rasterio.__version__, "gdal": rasterio.__gdal_version__,
    }
    (out_dir / "a6_study_area_extract.json").write_text(json.dumps(man, indent=2))
    print(json.dumps({k: man[k] for k in ("window", "extract_sha256", "extract_window_total", "national_total")}, indent=2))
    print("size of extract:", round(ext.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".")
