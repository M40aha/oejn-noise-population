"""A6 tests on a synthetic raster with the WorldPop grid geometry and KNOWN values.

The synthetic raster uses the same CRS, pixel size, origin alignment and nodata as the real
WorldPop file, so every rule (window snapping, conservation, provenance, projection) is checked
against answers known in advance. Run:  PYTHONPATH=src pytest -q tests/test_a6.py
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
import yaml
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
PX = 1 / 1200                    # 3 arc-seconds
WEST0, NORTH0 = 34.495, 32.155   # WorldPop SAU origin (A6/README.md)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("a6")
    raw = tmp / "raw"
    raw.mkdir()
    # a 4 x 4 degree synthetic raster on the WorldPop grid covering 19.6-23.6 N, 37.6-41.6 E
    col0 = round((37.6 - WEST0) / PX)
    row0 = round((NORTH0 - 23.6) / PX)
    w = h = 4800
    rng = np.random.default_rng(0)
    a = np.full((h, w), -99999.0, dtype=np.float32)
    land = rng.random((h, w)) < 0.30
    a[land] = rng.gamma(0.6, 8.0, land.sum()).astype(np.float32)
    a[land & (rng.random((h, w)) < 0.2)] = 0.0             # some zero-population land cells
    tf = from_origin(WEST0 + col0 * PX, NORTH0 - row0 * PX, PX, PX)
    path = raw / "sau_pop_2026_CN_100m_R2025A_v1.tif"
    with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=1, dtype="float32",
                       crs="EPSG:4326", transform=tf, nodata=-99999.0, compress="deflate") as d:
        d.write(a, 1)
    cfg = yaml.safe_load((ROOT / "config" / "a6.yaml").read_text())
    cfg["source"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    cfg["expected_raster"].update(width=w, height=h, pixel_size_deg=PX)
    cfg["compute_national_total"] = True
    cfg_path = tmp / "a6.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    import os
    os.environ["A6_RAW_DIR"] = str(raw)
    os.environ["A6_OUT_ROOT"] = str(tmp / "out")
    from a6.build import run
    s = run(cfg_path)
    del os.environ["A6_RAW_DIR"], os.environ["A6_OUT_ROOT"]
    # expected study-window values computed independently
    r0 = round((23.6 - 23.0) / PX)
    c0 = round((38.0 - 37.6) / PX)
    n = round(3.0 / PX)
    win = a[r0:r0 + n, c0:c0 + n]
    return {"summary": s, "out": tmp / "out", "window": win, "tmp": tmp, "a": a}


def test_no_errors(built):
    assert built["summary"]["qc_counts"]["ERROR"] == 0


def test_window_exact(built):
    s = built["summary"]["study_window"]
    assert s["width"] == s["height"] == 3600
    assert math.isclose(s["west"], 38.0, abs_tol=1e-9) and math.isclose(s["north"], 23.0, abs_tol=1e-9)


def test_population_conserved_exactly(built):
    win = built["window"]
    expected = math.fsum(win[win >= 0].astype(np.float64).tolist())
    rec = pd.read_parquet(built["out"] / "processed" / "a6_receptors.parquet")
    assert math.fsum(rec.population.tolist()) == expected
    assert len(rec) == int((win > 0).sum())


def test_receptor_provenance_and_values(built):
    rec = pd.read_parquet(built["out"] / "processed" / "a6_receptors.parquet")
    a = built["a"]                      # src_row/src_col index the source file itself
    sample = rec.sample(500, random_state=1)
    vals = a[sample.src_row, sample.src_col]
    assert np.array_equal(vals.astype(np.float64), sample.population.to_numpy())
    # pixel centres (synthetic file origin = 37.6 E, 23.6 N on the WorldPop grid)
    assert np.allclose(sample.lon, 37.6 + (sample.src_col + 0.5) * PX, atol=1e-6)
    assert np.allclose(sample.lat, 23.6 - (sample.src_row + 0.5) * PX, atol=1e-6)


def test_cell_area_and_density(built):
    rec = pd.read_parquet(built["out"] / "processed" / "a6_receptors.parquet")
    r = rec.iloc[0]
    assert 7850 < rec.cell_area_m2.min() and rec.cell_area_m2.max() < 8050   # 3" cell at 20-23 N: ~7,880-8,040 m^2
    assert (np.diff(rec.sort_values("lat").cell_area_m2.to_numpy()) <= 1e-6).all()  # shrinks towards the north
    assert math.isclose(r.density_per_km2, r.population / (r.cell_area_m2 / 1e6), rel_tol=1e-12)


def test_utm_projection(built):
    from pyproj import Transformer
    rec = pd.read_parquet(built["out"] / "processed" / "a6_receptors.parquet").head(50)
    x, y = Transformer.from_crs(4326, 32637, always_xy=True).transform(rec.lon, rec.lat)
    assert np.allclose(x, rec.x_utm37n_m) and np.allclose(y, rec.y_utm37n_m)


def test_aggregates_conserve(built):
    rec = pd.read_parquet(built["out"] / "processed" / "a6_receptors.parquet")
    tot = math.fsum(rec.population.tolist())
    for k in (6, 12, 24):
        g = pd.read_parquet(built["out"] / "processed" / f"a6_grid_{k}px.parquet")
        assert math.isclose(g.population.sum(), tot, rel_tol=1e-12)


def test_rings_monotonic(built):
    r = pd.read_csv(built["out"] / "processed" / "a6_population_rings.csv")
    assert (np.diff(r.population) >= 0).all()


def test_clip_bit_identical(built):
    with rasterio.open(built["out"] / "processed" / "a6_population_study_area.tif") as d:
        assert np.array_equal(d.read(1), built["window"])
        assert d.crs.to_epsg() == 4326 and d.nodata == -99999.0


def test_hash_mismatch_is_error(built, tmp_path):
    import os
    cfg = yaml.safe_load((built["tmp"] / "a6.yaml").read_text())
    cfg["source"]["sha256"] = "0" * 64
    cfg["compute_national_total"] = False
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(cfg))
    os.environ["A6_RAW_DIR"] = str(built["tmp"] / "raw")
    os.environ["A6_OUT_ROOT"] = str(tmp_path / "out")
    from a6.build import run
    s = run(p)
    del os.environ["A6_RAW_DIR"], os.environ["A6_OUT_ROOT"]
    assert s["qc_counts"]["ERROR"] >= 1


REAL = ROOT / "data" / "a6" / "validation" / "build_summary.json"


@pytest.mark.skipif(not REAL.exists(), reason="real A6 build not present")
def test_real_build_has_no_errors():
    s = json.loads(REAL.read_text())
    assert s["qc_counts"]["ERROR"] == 0
    assert s["source_sha256"] == "3ed9bc9ad51cd99d75461816e6c01ad71d466303adaab0809d1a989aabe57410"


def test_extract_mode_gives_identical_receptors(built, tmp_path):
    """Extract (scripts/a6_extract_study_area.py) -> build must give exactly the same receptors as the full raster."""
    import os
    import shutil
    import subprocess
    import sys
    raw_full = built["tmp"] / "raw"
    ext_dir = tmp_path / "raw_extract"
    cfg = yaml.safe_load((built["tmp"] / "a6.yaml").read_text())
    env = {**os.environ, "A6_LOCK_SHA256": cfg["source"]["sha256"]}
    subprocess.run([sys.executable, str(ROOT / "scripts" / "a6_extract_study_area.py"),
                    str(raw_full / cfg["source"]["file"]), str(ext_dir)], check=True, env=env, capture_output=True)
    os.environ["A6_RAW_DIR"] = str(ext_dir)
    os.environ["A6_OUT_ROOT"] = str(tmp_path / "out")
    from a6.build import run
    s = run(built["tmp"] / "a6.yaml")
    del os.environ["A6_RAW_DIR"], os.environ["A6_OUT_ROOT"]
    assert s["qc_counts"]["ERROR"] == 0 and s["source_mode"] == "study_area_extract"
    full = pd.read_parquet(built["out"] / "processed" / "a6_receptors.parquet")
    ext = pd.read_parquet(tmp_path / "out" / "processed" / "a6_receptors.parquet")
    pd.testing.assert_frame_equal(full, ext)
