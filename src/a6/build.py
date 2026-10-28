"""A6 build: WorldPop 2026 raster -> population receptors and aggregates for the OEJN study area.

Principles
- The raster is never modified. It is read through a pixel-aligned window (no resampling).
- WorldPop values are COUNTS (people per cell), not densities. Any reprojection or resampling of
  the raster would change the total, so the raster is never warped: every populated cell becomes a
  point receptor at its pixel centre, and only the point coordinates are projected (UTM 37N).
  The study-area total is therefore conserved exactly (checked with math.fsum).
- Every receptor keeps its source row/column in the national raster (provenance).

Run from the repository root:  PYTHONPATH=src python -m a6.build
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import yaml
from pyproj import Geod, Transformer
from rasterio.windows import Window
from affine import Affine

from a5.qc import QCRegistry

ROOT = Path(__file__).resolve().parents[2]
GEOD = Geod(ellps="WGS84")


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_raster(ds, exp: dict, qc: QCRegistry) -> None:
    checks = {
        "crs": (ds.crs.to_epsg() == exp["crs_epsg"], f"EPSG:{ds.crs.to_epsg()}"),
        "pixel_size": (abs(ds.res[0] - exp["pixel_size_deg"]) < 1e-12 and abs(ds.res[1] - exp["pixel_size_deg"]) < 1e-12,
                       f"{ds.res}"),
        "north_up": (ds.transform.b == 0 and ds.transform.d == 0 and ds.transform.e < 0, str(tuple(ds.transform)[:6])),
        "dimensions": (ds.width == exp["width"] and ds.height == exp["height"], f"{ds.width} x {ds.height}"),
        "nodata": (ds.nodata == exp["nodata"], f"{ds.nodata}"),
        "dtype": (ds.dtypes[0] == exp["dtype"], ds.dtypes[0]),
        "band_count": (ds.count == exp["band_count"], f"{ds.count}"),
    }
    for k, (ok, got) in checks.items():
        qc.add(f"a6.raster.{k}", "structure", "PASS" if ok else "ERROR",
               f"Raster {k}: {got}" + ("" if ok else f" (expected {exp.get(k, exp)})"))


def pixel_window(ds, area: dict, qc: QCRegistry) -> tuple[Window, dict]:
    """Smallest whole-pixel window covering the study area (snapped outward)."""
    inv = ~ds.transform
    c0, r0 = inv * (area["west"], area["north"])
    c1, r1 = inv * (area["east"], area["south"])
    col0, row0 = math.floor(round(c0, 6)), math.floor(round(r0, 6))
    col1, row1 = math.ceil(round(c1, 6)), math.ceil(round(r1, 6))
    inside = col0 >= 0 and row0 >= 0 and col1 <= ds.width and row1 <= ds.height
    qc.add("a6.study_area.inside_raster", "structure", "PASS" if inside else "ERROR",
           f"Study area {area} lies inside the raster (pixel window cols {col0}-{col1}, rows {row0}-{row1})")
    col0, row0 = max(col0, 0), max(row0, 0)
    col1, row1 = min(col1, ds.width), min(row1, ds.height)
    w = Window(col0, row0, col1 - col0, row1 - row0)
    west, north = ds.transform * (col0, row0)
    east, south = ds.transform * (col1, row1)
    return w, {"west": west, "east": east, "south": south, "north": north,
               "col_off": col0, "row_off": row0, "width": col1 - col0, "height": row1 - row0}


def cell_area_m2(t, rows: np.ndarray) -> np.ndarray:
    """Exact geodesic (WGS84) area of one pixel for each absolute raster row (area depends on latitude only)."""
    out = np.empty(len(rows))
    for i, r in enumerate(rows):
        lon0 = t.c
        lat_top = t.f + t.e * r
        lat_bot = lat_top + t.e
        lons = [lon0, lon0 + t.a, lon0 + t.a, lon0]
        lats = [lat_top, lat_top, lat_bot, lat_bot]
        out[i] = abs(GEOD.polygon_area_perimeter(lons, lats)[0])
    return out


def national_total(ds) -> tuple[float, int]:
    total, n = 0.0, 0
    for _, win in ds.block_windows(1):
        a = ds.read(1, window=win, masked=False)
        v = a[a != ds.nodata]
        v = v[np.isfinite(v)]
        total += math.fsum(v.astype(np.float64).tolist()) if v.size < 2_000_000 else float(v.astype(np.float64).sum())
        n += int((v > 0).sum())
    return total, n


def load_source(cfg: dict, raw: Path, qc: QCRegistry) -> dict:
    """Full national raster if present; otherwise the study-area extract made by
    scripts/a6_extract_study_area.py, accepted only if its manifest ties it to the locked national file."""
    src, exp = cfg["source"], cfg["expected_raster"]
    full = raw / src["file"]
    ext, man_p = raw / cfg["extract"]["file"], raw / cfg["extract"]["manifest"]
    if full.exists():
        got = _sha256(full)
        ok = got == src["sha256"]
        qc.add("a6.source.sha256", "source", "PASS" if ok else "ERROR",
               f"{src['file']}: SHA-256 {'matches' if ok else 'DOES NOT MATCH'} the locked value",
               0 if ok else 1, "" if ok else f"expected {src['sha256']} got {got} (truncated download?)")
        if not ok and ext.exists():
            raise RuntimeError(f"{full} does not match the lock; remove it to use the extract, or replace it")
        with rasterio.open(full) as ds:
            check_raster(ds, exp, qc)
            win, snapped = pixel_window(ds, cfg["study_area"], qc)
            a = ds.read(1, window=win, masked=False)
            nat = national_total(ds) if cfg.get("compute_national_total") else (None, 0)
            return {"array": a, "nodata": ds.nodata, "transform": ds.transform, "snapped": snapped,
                    "national": nat, "source_sha256": got, "mode": "national_raster"}
    if not (ext.exists() and man_p.exists()):
        raise FileNotFoundError(f"Neither {full} nor the extract {ext} (+ manifest) found in {raw}. "
                                f"Download {src['url']} or run scripts/a6_extract_study_area.py")
    man = json.loads(man_p.read_text())
    qc.add("a6.source.mode", "source", "INFO",
           f"Using study-area extract {ext.name} created {man['created_utc']} (rasterio {man['rasterio']}, GDAL {man['gdal']})")
    ok = man["source_sha256"] == src["sha256"]
    qc.add("a6.source.sha256", "source", "PASS" if ok else "ERROR",
           f"Extract manifest: national source SHA-256 {'matches' if ok else 'DOES NOT MATCH'} the locked value", 0 if ok else 1)
    ok = _sha256(ext) == man["extract_sha256"]
    qc.add("a6.source.extract_sha256", "source", "PASS" if ok else "ERROR",
           f"Extract file SHA-256 {'matches' if ok else 'DOES NOT MATCH'} its manifest", 0 if ok else 1)
    sr = man["source_raster"]
    for k, want, have in (("dimensions", (exp["width"], exp["height"]), (sr["width"], sr["height"])),
                          ("crs", exp["crs_epsg"], sr["crs_epsg"]), ("nodata", exp["nodata"], sr["nodata"]),
                          ("dtype", exp["dtype"], sr["dtype"]),
                          ("pixel_size", True, all(abs(r - exp["pixel_size_deg"]) < 1e-12 for r in sr["res"]))):
        qc.add(f"a6.raster.{k}", "structure", "PASS" if want == have else "ERROR",
               f"National raster {k} (from manifest): {have}" + ("" if want == have else f" (expected {want})"))
    t = Affine(*sr["transform"])
    w = man["window"]

    class _T:  # minimal stand-in so pixel_window() recomputes the window from the national grid
        transform, width, height = t, sr["width"], sr["height"]
    _, snapped = pixel_window(_T, cfg["study_area"], qc)
    same = all(snapped[k] == w[k] for k in ("col_off", "row_off", "width", "height"))
    qc.check("a6.extract.window", "structure", int(not same),
             f"Extract window {w} equals the window recomputed from the study area", "Extract window differs from config")
    with rasterio.open(ext) as d:
        a = d.read(1, masked=False)
        aligned = d.transform.almost_equals(t * Affine.translation(w["col_off"], w["row_off"]), precision=1e-12)
        props = d.crs.to_epsg() == exp["crs_epsg"] and d.nodata == exp["nodata"] and d.dtypes[0] == exp["dtype"] \
            and (d.width, d.height) == (w["width"], w["height"])
    qc.check("a6.extract.aligned", "structure", int(not aligned), "Extract is pixel-aligned with the national WorldPop grid",
             "Extract transform not aligned with the national grid")
    qc.check("a6.extract.properties", "structure", int(not props), "Extract CRS, nodata, dtype and size as expected",
             "Extract properties differ")
    v = a[(a != exp["nodata"]) & np.isfinite(a)].astype(np.float64)
    tot = math.fsum(v.tolist())
    qc.check("a6.extract.total", "validation", int(tot != man["extract_window_total"]),
             "Extract total equals the total recorded at extraction time", "Extract total differs from its manifest")
    return {"array": a, "nodata": exp["nodata"], "transform": t, "snapped": snapped,
            "national": (man["national_total"], man["national_populated_cells"]),
            "source_sha256": man["source_sha256"], "mode": "study_area_extract"}


def run(config_path: Path = ROOT / "config" / "a6.yaml") -> dict:
    cfg = yaml.safe_load(config_path.read_text())
    raw = Path(os.environ.get("A6_RAW_DIR") or (ROOT / cfg["raw_dir"])).resolve()
    src = cfg["source"]
    path = raw / src["file"]
    qc = QCRegistry()
    out_root = Path(os.environ.get("A6_OUT_ROOT") or (ROOT / "data" / "a6"))
    out_dir = out_root / "processed"
    val_dir = out_root / "validation"
    for d in (out_dir, val_dir):
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*"):
            if f.is_file():
                f.unlink()

    # 0-1. source integrity + study window (full national raster, or a manifest-backed extract)
    S = load_source(cfg, raw, qc)
    a, nod, t, snapped, nat = S["array"], S["nodata"], S["transform"], S["snapped"], S["national"]
    got = S["source_sha256"]

    # 1. value audit
    is_nod = a == nod
    nan = ~np.isfinite(a)
    neg = (a < 0) & ~is_nod
    valid = ~is_nod & ~nan
    qc.check("a6.values.no_nan", "physics", int(nan.sum()), "No NaN/inf values in the study window", "NaN/inf values present")
    qc.check("a6.values.non_negative", "physics", int(neg.sum()), "No negative population values (other than nodata)",
             "Negative population values")
    n_pos = int((a[valid] > 0).sum())
    qc.add("a6.values.audit", "physics", "INFO",
           f"Study window {a.shape[1]} x {a.shape[0]} pixels: {int(is_nod.sum()):,} nodata (sea / outside settlements), "
           f"{int((a[valid] == 0).sum()):,} zero, {n_pos:,} populated; max {float(a[valid].max()):.2f} people per cell",
           n_pos)

    # 2. receptors (populated cells -> pixel-centre points); row/col are indices of the NATIONAL raster
    rr, cc = np.nonzero(valid & (a > 0))
    pop = a[rr, cc].astype(np.float64)
    abs_r = rr + snapped["row_off"]
    abs_c = cc + snapped["col_off"]
    lon = t.c + (abs_c + 0.5) * t.a
    lat = t.f + (abs_r + 0.5) * t.e
    uniq_rows, inv_idx = np.unique(abs_r, return_inverse=True)
    area = cell_area_m2(t, uniq_rows)[inv_idx]

    tr = Transformer.from_crs(4326, cfg["projected_crs_epsg"], always_xy=True)
    x, y = tr.transform(lon, lat)
    back = Transformer.from_crs(cfg["projected_crs_epsg"], 4326, always_xy=True).transform(x, y)
    rt_err = float(max(np.max(np.abs(back[0] - lon)), np.max(np.abs(back[1] - lat)))) if len(lon) else 0.0
    qc.check("a6.crs.utm_roundtrip", "validation", int(rt_err > 1e-9),
             f"WGS84 -> UTM 37N -> WGS84 round trip error {rt_err:.1e} deg (< 1e-9 deg, i.e. < 0.1 mm)",
             f"UTM round trip error too large: {rt_err}")
    arp = cfg["oejn_arp"]
    az, _, dist_m = GEOD.inv(np.full(len(lon), arp["lon"]), np.full(len(lat), arp["lat"]), lon, lat)
    rec = pd.DataFrame({
        "src_row": abs_r.astype(np.int32), "src_col": abs_c.astype(np.int32),
        "lon": lon, "lat": lat, "x_utm37n_m": x, "y_utm37n_m": y,
        "population": pop, "cell_area_m2": area, "density_per_km2": pop / (area / 1e6),
        "dist_arp_km": dist_m / 1000.0, "bearing_arp_deg": np.mod(az, 360.0),
    })

    # 3. conservation and integrity
    win_total = math.fsum(a[valid].astype(np.float64).tolist())
    rec_total = math.fsum(rec.population.tolist())
    qc.check("a6.conservation.total", "validation", int(win_total != rec_total),
             f"Population conserved exactly: window total = receptor total = {rec_total:,.3f}",
             f"Population NOT conserved: window {win_total} vs receptors {rec_total}")
    qc.check("a6.receptors.unique_ids", "structure", int(rec.duplicated(["src_row", "src_col"]).sum()),
             f"{len(rec):,} receptors, each identified by its unique (src_row, src_col) in the national raster",
             "Duplicate receptor cells")
    in_box = rec.lon.between(snapped["west"], snapped["east"]) & rec.lat.between(snapped["south"], snapped["north"])
    qc.check("a6.receptors.inside_window", "structure", int((~in_box).sum()), "Every receptor lies inside the study window",
             "Receptors outside the window")
    a_eq = 2 * math.pi * 6378137.0 / 360 * cfg["expected_raster"]["pixel_size_deg"]
    approx = (a_eq ** 2) * np.cos(np.radians(rec.lat)) if len(rec) else np.array([])
    rel = float(np.max(np.abs(rec.cell_area_m2 - approx) / approx)) if len(rec) else 0.0
    qc.add("a6.cell_area.sanity", "validation", "PASS" if rel < 0.01 else "WARNING",
           f"Geodesic cell area agrees with the spherical approximation within {rel:.2%} "
           f"(cells {rec.cell_area_m2.min():,.0f}-{rec.cell_area_m2.max():,.0f} m^2)" if len(rec) else "no receptors")
    if nat[0] is not None and not np.isnan(nat[0]):
        qc.add("a6.national_total", "cross_source", "INFO",
               f"National raster total (Saudi Arabia 2026, WorldPop R2025A): {nat[0]:,.0f} people in {nat[1]:,} populated cells; "
               f"study area holds {rec_total / nat[0]:.1%}", nat[1])
    # the airport itself should be (nearly) unpopulated
    near = rec[rec.dist_arp_km <= 1.0].population.sum()
    qc.add("a6.sanity.airport_core", "physics", "INFO",
           f"Population within 1 km of the OEJN reference point: {near:,.1f} (expected to be small: airfield)", 0)

    # 4. aggregates
    rings = pd.DataFrame({"radius_km": cfg["distance_rings_km"]})
    rings["population"] = [rec.population[rec.dist_arp_km <= r].sum() for r in rings.radius_km]
    rings["populated_cells"] = [int((rec.dist_arp_km <= r).sum()) for r in rings.radius_km]
    grids = {}
    for k in cfg["aggregation_pixels"]:
        g = rec.assign(gr=(rec.src_row - snapped["row_off"]) // k, gc=(rec.src_col - snapped["col_off"]) // k)
        agg = g.groupby(["gr", "gc"]).agg(population=("population", "sum"), area_m2=("cell_area_m2", "sum"),
                                          populated_cells=("population", "size")).reset_index()
        px = cfg["expected_raster"]["pixel_size_deg"]
        agg["lon_west"] = snapped["west"] + agg.gc * k * px
        agg["lat_north"] = snapped["north"] - agg.gr * k * px
        agg["lon_c"] = agg.lon_west + k * px / 2
        agg["lat_c"] = agg.lat_north - k * px / 2
        agg["bin_deg"] = k * px
        diff = abs(math.fsum(agg.population.tolist()) - rec_total)
        qc.check(f"a6.aggregate.{k}px.conserved", "validation", int(diff > 1e-6 * max(rec_total, 1)),
                 f"{k}x{k}-pixel grid ({k * px:.3f} deg): {len(agg):,} bins, total conserved",
                 f"{k}x{k}-pixel grid total differs by {diff}")
        grids[k] = agg

    # 5. write
    rec.to_parquet(out_dir / "a6_receptors.parquet", index=False, compression="zstd", compression_level=19)
    rings.to_csv(out_dir / "a6_population_rings.csv", index=False)
    for k, g in grids.items():
        g.to_parquet(out_dir / f"a6_grid_{k}px.parquet", index=False)
    prof = {"driver": "GTiff", "dtype": "float32", "count": 1, "crs": "EPSG:4326", "nodata": nod,
            "width": snapped["width"], "height": snapped["height"],
            "transform": t * Affine.translation(snapped["col_off"], snapped["row_off"]),
            "compress": "deflate", "predictor": 3, "tiled": True, "blockxsize": 256, "blockysize": 256}
    with rasterio.open(out_dir / "a6_population_study_area.tif", "w", **prof) as dst:
        dst.write(a, 1)
    with rasterio.open(out_dir / "a6_population_study_area.tif") as chk:
        same = np.array_equal(chk.read(1), a)
    qc.check("a6.clip.bit_identical", "validation", int(not same),
             "Clipped GeoTIFF is bit-identical to the source window (no resampling)", "Clipped raster differs from source")

    qcdf = qc.frame()
    qcdf.to_csv(val_dir / "qc_results.csv", index=False)
    summary = {
        "release_id": cfg["release_id"], "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "packages": {"pandas": pd.__version__, "numpy": np.__version__, "rasterio": rasterio.__version__},
        "source_sha256": got, "study_window": snapped,
        "receptors": int(len(rec)), "study_area_population": rec_total,
        "national_population": nat[0], "source_mode": S["mode"],
        "rings": rings.to_dict(orient="records"),
        "qc_counts": {s: qc.count(s) for s in ("PASS", "INFO", "WARNING", "ERROR", "UNRESOLVED")},
    }
    (val_dir / "build_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    _report(val_dir, qcdf, summary, cfg)
    return summary


def _report(val_dir: Path, qc: pd.DataFrame, s: dict, cfg: dict) -> None:
    icon = {"PASS": "✅", "INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "UNRESOLVED": "❓"}
    L = [f"# A6 quality-control report — `{s['release_id']}`", "", f"Built {s['built_utc']}", "",
         "| Severity | Checks |", "|---|---|"] + [f"| {icon[k]} {k} | {v} |" for k, v in s["qc_counts"].items()]
    L += ["", f"**Receptors:** {s['receptors']:,} populated cells · **study-area population:** {s['study_area_population']:,.0f}",
          "", "## Population within distance of the OEJN reference point", "", "| radius (km) | population | populated cells |", "|---|---|---|"]
    L += [f"| {r['radius_km']} | {r['population']:,.0f} | {r['populated_cells']:,} |" for r in s["rings"]]
    L += ["", "## Checks", "", "| check | severity | message |", "|---|---|---|"]
    L += [f"| {r.check_id} | {icon[r.severity]} {r.severity} | {r.message} |" for r in qc.itertuples()]
    (val_dir / "qc_report.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    s = run()
    print(json.dumps({k: v for k, v in s.items() if k not in ("rings",)}, indent=2, default=float))
    sys.exit(1 if s["qc_counts"]["ERROR"] else 0)
