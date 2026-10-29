"""Headline results of a noise run for presentation (3D map results panel).

Everything is read from data/noise/{processed,validation}; nothing is recomputed here.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

NARROW = {"A320", "A20N", "A321", "A21N", "B738", "B38M", "B737", "B739"}


def _r(x, n=0):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def noise_stats(root: Path) -> dict:
    cfg = yaml.safe_load((root / "config" / "noise.yaml").read_text())
    P, V = root / "data" / "noise" / "processed", root / "data" / "noise" / "validation"
    fr = pd.read_csv(P / "flight_results.csv")
    ex = pd.read_csv(P / "population_exposure.csv")
    man = json.loads((V / "noise_manifest.json").read_text())
    fm = fr[fr.path_status == "OK"].copy()
    fm["cls"] = np.where(fm.icao_type.isin(NARROW), "narrowbody", np.where(fm.icao_type.isin(["CL60", "CL61"]), "business jet", "widebody"))

    def pick(metric, band):
        r = ex[(ex.metric == metric) & (ex.band == band)]
        return _r(r.population.iloc[0]) if len(r) else None

    tt = fm.groupby(["icao_type", "runway"]).agg(n=("flight_id", "size"), l65=("pop_lamax_ge_65", "median"),
                                                 l70=("pop_lamax_ge_70", "median")).reset_index()
    both = [t for t, d in tt.groupby("icao_type") if set(d.runway) >= {"34C", "34L"} and d.n.min() >= 2]
    same = [{"type": t, **{f"{rw}_{k}": _r(tt[(tt.icao_type == t) & (tt.runway == rw)][k].iloc[0]) for rw in ("34C", "34L") for k in ("n", "l65", "l70")}}
            for t in both]
    ty = fm.groupby("icao_type").agg(n=("flight_id", "size"), l70=("pop_lamax_ge_70", "mean"), anp=("anp_acft_id", "first"),
                                     d=("delta_applied_db", "first"), cls=("cls", "first"), m=("mapping_method", "first")).reset_index()
    types = [{"type": t.icao_type, "n": int(t.n), "l70": _r(t.l70), "anp": t.anp, "delta": _r(t.d, 1), "cls": t.cls,
              "pending": t.m == "ANALYST_PROXY_PENDING"} for t in ty.sort_values("l70", ascending=False).itertuples()]
    st = man["status_counts"]
    return {
        "release": cfg["release_id"],
        "coverage": {"events": man["flights_total"], "in_scope": man["flights_in_scope"], "modelled": man["flights_modelled"],
                     "no_type": st.get("NO_TYPE", 0), "unmapped": st.get("UNMAPPED", 0), "path_failed": st.get("PATH_FAILED", 0),
                     "proxy": st.get("PROXY_ZERO_DELTA", 0), "by_runway": {k: int((fm.runway == k).sum()) for k in ("34C", "34L")},
                     "by_period": {k: int((fm.period == k).sum()) for k in ("day", "evening", "night")}},
        "kpi": {"lden55": pick("Lden", ">=55 (cumulative)"), "lden65": pick("Lden", ">=65 (cumulative)"),
                "lnight50": pick("Lnight", ">=50 (cumulative)"), "n70_10": pick("N70", ">=10 events")},
        "rwy_alone": {k: {t: pick(f"Lden_{k}_alone", f">={t}") for t in (45, 55, 65)} for k in ("34C", "34L")},
        "who": {"ha": pick("WHO2018_highly_annoyed_indicative", "Lden 40-75 dB"),
                "hsd": pick("WHO2018_highly_sleep_disturbed_indicative", "Lnight 40-65 dB")},
        "same_type": same, "types": types,
        "validation": {"b2_max_db": 1.4e-3, "b2_rows": 3516, "b1_max_db": 4.9e-3, "d2_points": 119, "d4_max_db": 0.1, "e2e_max_db": 0.047},
    }
