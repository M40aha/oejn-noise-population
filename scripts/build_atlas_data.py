"""Build docs/atlas/atlas_data.js from the A5 and A6 outputs (run after both builds).

Everything shown in the atlas is computed here from the processed tables, so every number traces back
to A5/A6. Route statistics are indicative: they use the published SID ground tracks (fix-to-fix legs),
not flown trajectories, and no noise levels are computed (that is the noise-model stage).

    PYTHONPATH=src python scripts/build_atlas_data.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from viz.sids import AIP_NOTES, SIDS, WAYPOINTS, leg_check  # noqa: E402

A5 = ROOT / "data" / "a5"
A6 = ROOT / "data" / "a6"
OUT = ROOT / "docs" / "atlas"
EXTENT = {"south": 20.6, "north": 22.8, "west": 38.15, "east": 40.0}
FLEET = ["A20N", "A21N", "A320", "A321", "A333", "A339", "A359", "A35K", "A388",
         "B38M", "B39M", "B738", "B744", "B772", "B77W", "B788", "B789", "B78X", "E190", "E195"]
TO_UTM = Transformer.from_crs(4326, 32637, always_xy=True)


def r(x, n):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), n)


def population():
    rec = pd.read_parquet(A6 / "processed" / "a6_receptors.parquet")
    g = pd.read_parquet(A6 / "processed" / "a6_grid_6px.parquet")
    g = g[g.lon_c.between(EXTENT["west"], EXTENT["east"]) & g.lat_c.between(EXTENT["south"], EXTENT["north"])]
    grid = [[r(a, 4), r(b, 4), r(c, 1)] for a, b, c in zip(g.lon_c, g.lat_c, g.population)]
    rings = pd.read_csv(A6 / "processed" / "a6_population_rings.csv")
    summ = json.loads((A6 / "validation" / "build_summary.json").read_text())
    return rec, {"grid": grid, "bin_deg": float(g.bin_deg.iloc[0]),
                 "rings": rings.to_dict(orient="records"), "summary": {
                     "receptors": summ["receptors"], "study_population": summ["study_area_population"],
                     "national_population": summ["national_population"], "qc": summ["qc_counts"],
                     "window": summ["study_window"], "source_mode": summ.get("source_mode")}}


def corridor_stats(rec: pd.DataFrame):
    px, py = rec.x_utm37n_m.to_numpy(), rec.y_utm37n_m.to_numpy()
    pop = rec.population.to_numpy()
    out = []
    for sid, rwy, exit_, fixes, _ in SIDS:
        lon = [WAYPOINTS[f][1] for f in fixes]
        lat = [WAYPOINTS[f][0] for f in fixes]
        X, Y = TO_UTM.transform(lon, lat)
        X, Y = np.array(X), np.array(Y)
        seg_len = np.hypot(np.diff(X), np.diff(Y))
        cum = np.concatenate([[0], np.cumsum(seg_len)])
        box = (px > X.min() - 6000) & (px < X.max() + 6000) & (py > Y.min() - 6000) & (py < Y.max() + 6000)
        qx, qy, qp = px[box], py[box], pop[box]
        best = np.full(qx.shape, np.inf)
        along = np.zeros(qx.shape)
        for i in range(len(X) - 1):
            dx, dy = X[i + 1] - X[i], Y[i + 1] - Y[i]
            t = np.clip(((qx - X[i]) * dx + (qy - Y[i]) * dy) / (dx * dx + dy * dy), 0, 1)
            d = np.hypot(qx - (X[i] + t * dx), qy - (Y[i] + t * dy))
            m = d < best
            best[m] = d[m]
            along[m] = cum[i] + t[m] * seg_len[i]
        prof_bins = np.arange(0, cum[-1] + 2000, 2000)
        within3 = best <= 3000
        hist, _ = np.histogram(along[within3], bins=prof_bins, weights=qp[within3])
        out.append({
            "sid": sid, "runway": rwy, "exit": exit_, "fixes": fixes,
            "path": [[r(a, 5), r(b, 5)] for a, b in zip(lon, lat)],
            "track_km": r(cum[-1] / 1000, 1),
            "pop_1km": r(qp[best <= 1000].sum(), 0), "pop_3km": r(qp[within3].sum(), 0),
            "pop_3km_first30km": r(qp[within3 & (along <= 30000)].sum(), 0),
            "profile_3km_per2km": [r(v, 0) for v in hist],
        })
    return out


def a5_block():
    mp = pd.read_parquet(A5 / "processed" / "aircraft_noise_mapping.parquet")
    npd = pd.read_parquet(A5 / "processed" / "anp_npd_long.parquet")
    ac = pd.read_parquet(A5 / "processed" / "anp_aircraft.parquet")
    cfg = pd.read_parquet(A5 / "processed" / "easa_subst_config.parquet")
    b2 = pd.read_parquet(A5 / "validation" / "vol3_b2_npd_validation.parquet")
    summ = json.loads((A5 / "validation" / "build_summary.json").read_text())
    fleet = mp[mp.icao_type.isin(FLEET)].set_index("icao_type").loc[[f for f in FLEET if f in set(mp.icao_type)]]
    fleet_rows = [{"icao": i, "method": row.mapping_method, "anp": row.anp_acft_id, "delta": r(row.delta_dep_db, 1),
                   "confidence": row.confidence, "verified": bool(row.verified_data_available),
                   "npd": row.npd_id if isinstance(row.npd_id, str) else None,
                   "desc": row.anp_description if isinstance(row.anp_description, str) else None}
                  for i, row in fleet.iterrows()]
    ids = {f["npd"] for f in fleet_rows if f["npd"]}
    sub = npd[npd.npd_id.isin(ids) & (npd.op_mode == "D") & npd.noise_metric.isin(["SEL", "LAmax"])]
    curves = {}
    for (nid, met, p), g in sub.groupby(["npd_id", "noise_metric", "power_setting"]):
        curves.setdefault(nid, {}).setdefault(met, []).append({"p": r(p, 1), "L": [r(v, 1) for v in g.sort_values("distance_ft").level_db]})
    # MTOW x engine -> delta for A20N and B789 (certified configurations)
    brackets = {}
    for code in ("A20N", "B789", "A21N"):
        c = cfg[cfg.icao_code == code]
        fam = c.engine_type.str.upper().str.extract(r"^(LEAP|PW\d|GENX|TRENT)")[0].fillna("OTHER")
        brackets[code] = [{"mtow_t": r(m / 1000, 1), "delta": r(d, 1), "family": f}
                          for m, d, f in zip(c.mtow_kg, c.delta_dep_db, fam)]
    samp = b2.sample(min(900, len(b2)), random_state=7)
    return {"fleet": fleet_rows, "curves": curves, "brackets": brackets,
            "distances_ft": [200, 400, 630, 1000, 2000, 4000, 6300, 10000, 16000, 25000],
            "vol3": {"n": int(len(b2)), "max_abs_diff": float(b2.abs_diff_db.max()),
                     "points": [[r(a, 3), r(b, 3)] for a, b in zip(samp.ref_sel, samp.a5_sel)]},
            "qc": summ["qc_counts"], "n_aircraft": int(len(ac)), "n_npd_points": int(len(npd)),
            "mapping_methods": summ["mapping_methods"]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rec, pop = population()
    legs = pd.DataFrame(leg_check())
    data = {
        "generated_from": {"a5": json.loads((A5 / "validation" / "build_summary.json").read_text())["release_id"],
                           "a6": json.loads((A6 / "validation" / "build_summary.json").read_text())["release_id"]},
        "extent": EXTENT, "arp": {"lat": 21.681111, "lon": 39.156111},
        "population": pop, "sids": corridor_stats(rec),
        "waypoints": {k: [r(v[1], 5), r(v[0], 5)] for k, v in WAYPOINTS.items()},
        "sid_check": {"legs": int(len(legs)), "max_abs_diff_nm": r(legs.diff_nm.abs().max(), 3)},
        "aip_notes": AIP_NOTES, "a5": a5_block(),
    }
    js = "window.ATLAS = " + json.dumps(data, separators=(",", ":")) + ";\n"
    (OUT / "atlas_data.js").write_text(js)
    # stand-alone copy for the repository: one file, data inlined, opens with a double click
    page = (OUT / "index.html").read_text().replace('<script src="atlas_data.js"></script>', "<script>" + js + "</script>")
    (OUT / "OEJN_Noise_Atlas.html").write_text(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>\n'
        + page + "\n</body></html>\n")
    print(f"atlas_data.js: {len(js) / 1e6:.2f} MB, {len(pop['grid'])} population bins, {len(data['sids'])} SIDs")


if __name__ == "__main__":
    main()
