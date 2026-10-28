"""Aerodrome weather per departure from the OEJN METAR archive (IEM ASOS export, ext_metar_oejn.csv).

Per flight the METAR closest in time to the lift-off anchor is used (within max_age_min). Temperature and dew
point come from the report; relative humidity is recomputed from them (Magnus, atmosphere.relative_humidity);
QNH is read from the 'Qnnnn' group of the raw METAR (hPa, as reported in Saudi Arabia), else from the IEM
altimeter column (inHg x 33.8639). Wind: direction (deg true, from) and speed (kt); VRB/calm -> 0 kt.
Nothing is filled silently: a flight without a METAR within max_age_min gets the configured fallback and the
flag MET_FALLBACK.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .atmosphere import relative_humidity

INHG_TO_HPA = 33.8639


def load_metar(path) -> pd.DataFrame:
    m = pd.read_csv(path)
    m.columns = [c.strip().lower() for c in m.columns]
    tcol = "valid" if "valid" in m else m.columns[1]
    m["time"] = pd.to_datetime(m[tcol], utc=True)
    for c in ("tmpc", "dwpc", "relh", "alti", "sknt", "drct"):
        if c in m:
            m[c] = pd.to_numeric(m[c], errors="coerce")
    raw = m["metar"].astype(str) if "metar" in m else pd.Series([""] * len(m))
    q = raw.str.extract(r"\bQ(\d{4})\b")[0].astype(float)
    m["qnh_hpa"] = q.where(q.notna(), m.get("alti", np.nan) * INHG_TO_HPA)
    m["qnh_source"] = np.where(q.notna(), "METAR Q group", "IEM alti (inHg)")
    m["rh_pct"] = relative_humidity(m.tmpc, m.dwpc)
    m["wind_dir_deg"] = m.get("drct", np.nan)
    m["wind_kt"] = m.get("sknt", np.nan).fillna(0.0)
    m = m.dropna(subset=["tmpc", "dwpc", "qnh_hpa"]).sort_values("time").reset_index(drop=True)
    return m[["time", "tmpc", "dwpc", "rh_pct", "qnh_hpa", "qnh_source", "wind_dir_deg", "wind_kt"]
             + (["metar"] if "metar" in m else [])]


def met_for(metar: pd.DataFrame | None, t_utc: pd.Timestamp, max_age_min: float, fallback: dict) -> dict:
    if metar is not None and len(metar):
        dt = (metar.time - t_utc).abs()
        i = int(dt.idxmin())
        if dt[i] <= pd.Timedelta(minutes=max_age_min):
            r = metar.loc[i]
            return {"t_c": float(r.tmpc), "td_c": float(r.dwpc), "rh_pct": float(r.rh_pct), "qnh_hpa": float(r.qnh_hpa),
                    "wind_dir_deg": float(r.wind_dir_deg) if np.isfinite(r.wind_dir_deg) else np.nan,
                    "wind_kt": float(r.wind_kt), "met_time": r.time.isoformat(), "met_age_min": dt[i].total_seconds() / 60,
                    "met_source": "METAR", "qnh_source": r.qnh_source}
    return {**fallback, "td_c": np.nan, "wind_dir_deg": np.nan, "wind_kt": 0.0, "met_time": None, "met_age_min": np.nan,
            "met_source": "MET_FALLBACK", "qnh_source": "fallback"}
