"""OEJN departure noise and population exposure for one observed day (Doc 29 5th Ed.).

    python -m noise.run                  (from src/, or PYTHONPATH=src)

Inputs (config/noise.yaml): A2 trajectory extract, METAR, optional A3 aircraft identity, A1 runways,
A5 release (ANP 2.3 + mapping), A6 receptors. Outputs under data/noise/{processed,validation} and docs/noise/.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from a5.mapping import Mapper, MappingPolicy
from a5.npd import NPDLookup, NPDPolicy
from . import doc29 as D
from .atmosphere import npd_increment
from .event import AdjustedNPD, event_levels
from .flightpath import PathPolicy, build_path, segments
from .performance import Thrust, cutback_height_ft
from .site import FT, Site, prepare_observations
from .weather import load_metar, met_for

ROOT = Path(__file__).resolve().parents[2]
ENV = {"a2_dir": "NOISE_A2_DIR", "metar_csv": "NOISE_METAR_CSV", "aircraft_identity_csv": "NOISE_A3_CSV"}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def path_of(cfg, key) -> Path:
    v = os.environ.get(ENV.get(key, ""), cfg["inputs"][key])
    p = Path(v)
    return p if p.is_absolute() else ROOT / p


# ------------------------------------------------------------------------------------------------ setup
def load_a5(cfg):
    a5 = path_of(cfg, "a5_processed")
    rd = lambda n: pd.read_parquet(a5 / f"{n}.parquet")
    t = {n: rd(n) for n in ("anp_aircraft", "anp_jet_coefficients", "anp_departure_steps", "anp_npd_long",
                            "anp_spectral_long", "easa_subst_icao", "easa_subst_config", "easa_verified_types")}
    a5cfg = yaml.safe_load((ROOT / "config" / "a5.yaml").read_text())
    pol = a5cfg["policies"]
    kind = dict(zip(t["anp_aircraft"].npd_id, t["anp_aircraft"].power_parameter_kind))
    t["lookup"] = NPDLookup(t["anp_npd_long"], NPDPolicy(**pol["npd"]), kind)
    analyst = pd.read_csv(ROOT / "data" / "a5" / "reviews" / "analyst_proxies.csv", dtype=str)
    t["mapper"] = Mapper(t["easa_subst_icao"], t["easa_subst_config"], t["anp_aircraft"], t["easa_verified_types"], analyst,
                         MappingPolicy(substitution_method=cfg["mapping"]["substitution_method"],
                                       mtow_match_tolerance_kg=pol["mapping"]["mtow_match_tolerance_kg"],
                                       engine_family_min_chars=pol["mapping"]["engine_family_min_chars"]),
                         "a5-anp2.3-doc29e5-v1")
    t["analyst"] = analyst
    t["thrust"] = Thrust(t["anp_jet_coefficients"])
    return t


def grid(cfg, site: Site):
    s, hw = cfg["grid"]["spacing_m"], cfg["grid"]["half_width_m"]
    ax = np.arange(-hw, hw + s / 2, s)
    X, Y = np.meshgrid(ax, ax)                    # rows = northing offset, cols = easting offset
    return ax, X.ravel() / FT, Y.ravel() / FT


def bilinear_weights(ax_m, ex_m, ny_m):
    """Bilinear interpolation weights of points (offsets from ARP, m) on the square grid ax_m x ax_m."""
    s = ax_m[1] - ax_m[0]
    n = len(ax_m)
    fx = (ex_m - ax_m[0]) / s
    fy = (ny_m - ax_m[0]) / s
    ok = (fx >= 0) & (fy >= 0) & (fx <= n - 1) & (fy <= n - 1)
    i0 = np.clip(np.floor(fx).astype(int), 0, n - 2)
    j0 = np.clip(np.floor(fy).astype(int), 0, n - 2)
    wx, wy = fx - i0, fy - j0
    idx = np.stack([j0 * n + i0, j0 * n + i0 + 1, (j0 + 1) * n + i0, (j0 + 1) * n + i0 + 1], 1)
    w = np.stack([(1 - wx) * (1 - wy), wx * (1 - wy), (1 - wx) * wy, wx * wy], 1)
    return ok, idx, w


def resolve_aircraft(flights, ident, t, cfg, qc):
    """A5 Mapper per flight. Type/engine from A3 identity (OpenSky / adsbdb) when available."""
    f = flights.copy()
    f["icao24"] = f.icao24.str.lower()
    if ident is not None:
        ident = ident.copy()
        ident["icao24"] = ident.icao24.str.lower()
        f = f.merge(ident[["icao24", "registration", "icao_type", "model", "engine_type", "operator_icao", "source"]]
                    .rename(columns={"source": "identity_source"}), on="icao24", how="left")
    else:
        for c in ("registration", "icao_type", "model", "engine_type", "operator_icao", "identity_source"):
            f[c] = np.nan
    f["icao_type"] = f.icao_type.where(f.icao_type.notna() & (f.icao_type.astype(str).str.strip() != ""), np.nan)
    rec = f[f.icao_type.notna()][["icao_type", "model", "engine_type"]].drop_duplicates() \
        .rename(columns={"model": "airframe_model"})
    if len(rec):
        mp, _ = t["mapper"].resolve(rec.assign(engine_type=rec.engine_type.replace("", np.nan)))
        mp = mp.rename(columns={"airframe_model_in": "model", "engine_type_in": "engine_type"})
        f = f.merge(mp, on=["icao_type", "model", "engine_type"], how="left", suffixes=("", "_map"))
    pend = set(t["analyst"][t["analyst"].review_status != "REVIEWED"].icao_type)
    f["noise_status"] = "OK"
    f.loc[f.icao_type.isna(), "noise_status"] = "NO_TYPE"
    if "usable_for_noise" not in f:
        f["usable_for_noise"] = False
    f["usable_for_noise"] = f.usable_for_noise.fillna(False).astype(bool)
    if cfg["mapping"]["pending_proxy_policy"] == "proxy_zero_delta":
        prox = dict(zip(t["analyst"].icao_type, t["analyst"].proxy_anp_id))
        m = f.icao_type.isin(pend) & ~f.usable_for_noise
        for i in f.index[m]:
            a = t["anp_aircraft"].set_index("acft_id").loc[prox[f.at[i, "icao_type"]]]
            f.loc[i, ["anp_acft_id", "npd_id", "dep_spectral_class_id", "lateral_directivity", "anp_engine_type"]] = \
                [a.name, a.npd_id, a.dep_spectral_class_id, a.lateral_directivity, a.engine_type]
            f.loc[i, ["delta_applied_db", "mapping_method", "usable_for_noise", "noise_status"]] = \
                [0.0, "ANALYST_PROXY_PENDING", True, "PROXY_ZERO_DELTA"]
    f.loc[f.icao_type.notna() & ~f.usable_for_noise, "noise_status"] = "UNMAPPED"
    jet = f.get("anp_engine_type").eq("Jet") if "anp_engine_type" in f else False
    f.loc[f.usable_for_noise & ~jet, "noise_status"] = "NOT_JET_UNSUPPORTED"
    return f


# ------------------------------------------------------------------------------------------------ per flight
_W = {}


def _sid(v) -> str:
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        return str(v).strip()


def _init_worker(state):
    _W.update(state)


def model_flight(fr, obs, met, s=None):
    """Flight path + acoustic set-up of one departure (no receptor evaluation)."""
    s = s or _W
    cfg, t = s["cfg"], s["t"]
    flags = []
    site, rw = s["site"], s["site"].runway(fr["runway"])
    prep = prepare_observations(obs, site, rw, met, cfg["flight_path"]["height_source"])
    acft = fr["anp_acft_id"]
    cut = cutback_height_ft(t["anp_departure_steps"], acft)
    if not np.isfinite(cut):
        cut = cfg["power"]["cutback_fallback_ft"]
        flags.append("CUTBACK_FALLBACK")
    th = t["thrust"]
    if not (th.has(acft, "MaxTakeoff") and th.has(acft, "MaxClimb")):
        raise ValueError(f"ANP {acft} lacks MaxTakeoff/MaxClimb jet coefficients")
    rating = {"MaxTakeoff": cfg["power"]["takeoff_rating"], "MaxClimb": cfg["power"]["climb_rating"]}
    pfn = lambda r, c, h, tc: th.cnt(acft, rating[r], c, h, tc)
    pp = PathPolicy(**{k: v for k, v in cfg["flight_path"].items() if k != "height_source"})
    nodes, info = build_path(prep, rw["sor_xy"], rw["axis_u"], rw["tora_ft"], pfn, cut, pp)
    segs = segments(nodes)
    spec = s["spectra"][_sid(fr["dep_spectral_class_id"])]
    qfe = met["qnh_hpa"] * (1 - 6.8755856e-6 * rw["elev_ft"]) ** 5.2558797
    dL = npd_increment(spec, met["t_c"], met["rh_pct"], qfe / 10.0) if cfg["weather"]["atmospheric_adjustment"] else None
    imp = D.impedance_adjustment(met["t_c"], qfe) if cfg["weather"]["impedance_adjustment"] else 0.0
    npd = AdjustedNPD(t["lookup"], fr["npd_id"], "D", dL)
    ev = lambda x, y, prune: event_levels(segs, x, y, np.zeros_like(x), npd, fr["lateral_directivity"], "Jet", imp,
                                          float(fr["delta_applied_db"]), prune)
    return {"segs": segs, "nodes": nodes, "info": info, "prep": prep, "cut": cut, "dL": dL, "imp": imp, "flags": flags,
            "evaluate": ev}


def _flight(job):
    s = _W
    cfg = s["cfg"]
    fr, obs = job["flight"], job["obs"]
    out = {"flight_id": fr["flight_id"], "status": "OK", "flags": []}
    try:
        m = model_flight(fr, obs, job["met"], s)
        segs, nodes, info, prep, cut, dL, imp = (m[k] for k in ("segs", "nodes", "info", "prep", "cut", "dL", "imp"))
        out["flags"] += m["flags"]
        pr = cfg["grid"].get("prune_m")
        sel, lmax = m["evaluate"](s["rx"], s["ry"], None if pr is None else pr / FT)
        out.update({"sel": sel.astype(np.float32), "lmax": lmax.astype(np.float32), "cutback_ft": cut,
                    "impedance_db": imp, "dL_1000ft_db": float(dL[3]) if dL is not None else 0.0,
                    "dL_10000ft_db": float(dL[7]) if dL is not None else 0.0, **{k: v for k, v in info.items() if k != "flags"},
                    "n_segments": int(len(segs)),
                    "z_source_geometric_frac": float((prep.z_source == "geometric").mean()),
                    "cas_source_ias_frac": float((prep.cas_source == "IAS").mean()),
                    "geo_minus_baro_median_ft": float(np.nanmedian(prep.z_geo_ft - prep.z_baro_ft)) if np.isfinite(prep.z_geo_ft - prep.z_baro_ft).any() else np.nan,
                    "max_z_ft": float(nodes.z_ft.max()), "P_max": float(nodes.P.max()), "P_min_air": float(nodes[nodes.kind != "roll"].P.min())})
        out["flags"] += info["flags"]
        out["nodes"] = nodes.assign(flight_id=fr["flight_id"])
    except Exception as e:                                    # recorded, never hidden
        out["status"] = "PATH_FAILED"
        out["error"] = f"{type(e).__name__}: {e}"
    return out


# ------------------------------------------------------------------------------------------------ main
def main(cfg_file: Path = ROOT / "config" / "noise.yaml", out_root: Path | None = None):
    t0 = time.time()
    cfg = yaml.safe_load(Path(cfg_file).read_text())
    out_root = Path(out_root or os.environ.get("NOISE_OUT_ROOT", ROOT))
    P = {k: out_root / "data" / "noise" / k for k in ("processed", "validation", "interim")}
    for p in P.values():
        p.mkdir(parents=True, exist_ok=True)
    qc = []

    a2 = path_of(cfg, "a2_dir")
    flights = pd.read_csv(a2 / "a2_noise_flights.csv", dtype={"icao24": str})
    obs = pd.read_parquet(a2 / "a2_noise_departures.parquet")
    metar_p = path_of(cfg, "metar_csv")
    metar = load_metar(metar_p) if metar_p.exists() else None
    ident_p = path_of(cfg, "aircraft_identity_csv")
    ident = pd.read_csv(ident_p, dtype=str) if ident_p.exists() else None
    rwys = pd.read_csv(path_of(cfg, "runways_csv"))
    site = Site(rwys, cfg["aerodrome"]["arp_lat"], cfg["aerodrome"]["arp_lon"])
    t = load_a5(cfg)
    inputs = {str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p): sha(p) for p in
              [a2 / "a2_noise_flights.csv", a2 / "a2_noise_departures.parquet", path_of(cfg, "runways_csv")]
              + [p for p in (metar_p, ident_p) if p.exists()]}
    qc.append(("inputs.metar", "PASS" if metar is not None else "WARNING",
               f"METAR rows: {len(metar)}" if metar is not None else "no METAR file: weather fallback for every flight"))
    qc.append(("inputs.aircraft_identity", "PASS" if ident is not None else "WARNING",
               f"A3 identity rows: {len(ident)}" if ident is not None else "no A3 identity file: aircraft type unknown for every flight"))

    # flights in scope
    f = flights.copy()
    f["in_scope"] = f.runway_status.isin(cfg["flights"]["runway_status"]) & f.runway.isin(cfg["flights"]["runways"])
    f = resolve_aircraft(f, ident, t, cfg, qc)
    f.loc[~f.in_scope, "noise_status"] = "OUT_OF_SCOPE_A2_STATUS"
    f["anchor_utc"] = pd.to_datetime(f.anchor_ms, unit="ms", utc=True)
    f["anchor_local"] = f.anchor_utc + pd.Timedelta(hours=cfg["local_utc_offset_h"])
    hr = f.anchor_local.dt.hour
    per = cfg["metrics"]["periods_local"]
    f["period"] = np.where((hr >= per["day"][0]) & (hr < per["day"][1]), "day",
                           np.where((hr >= per["evening"][0]) & (hr < per["evening"][1]), "evening", "night"))
    model = f[f.noise_status.isin(["OK", "PROXY_ZERO_DELTA"])]

    ax, rx, ry = grid(cfg, site)
    spectra = {_sid(k): g.sort_values("frequency_hz").level_db.to_numpy()
               for k, g in t["anp_spectral_long"][t["anp_spectral_long"].op_type.str.strip().str.lower().str.startswith("d")]
               .groupby("spectral_class_id")}
    jobs = []
    for fr in model.to_dict("records"):
        o = obs[obs.flight_id == fr["flight_id"]]
        met = met_for(metar, fr["anchor_utc"], cfg["weather"]["max_age_min"], cfg["weather"]["fallback"])
        jobs.append({"flight": fr, "obs": o, "met": met})
    state = {"cfg": cfg, "t": {k: t[k] for k in ("lookup", "thrust", "anp_departure_steps")}, "site": site,
             "rx": rx, "ry": ry, "spectra": spectra}
    res = []
    if cfg["run"]["workers"] > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(cfg["run"]["workers"], initializer=_init_worker, initargs=(state,)) as ex:
            res = list(ex.map(_flight, jobs, chunksize=1))
    else:
        _init_worker(state)
        res = [_flight(j) for j in jobs]

    # ---------------------------------------------------------------- aggregation
    pen = cfg["metrics"]["penalties_db"]
    E = {k: np.zeros(rx.shape) for k in ("day", "evening", "night")}
    NA = {thr: np.zeros(rx.shape, np.int32) for thr in cfg["metrics"]["number_above_db"]}
    by_rwy = {}
    rec = pd.read_parquet(path_of(cfg, "a6_receptors"), columns=["x_utm37n_m", "y_utm37n_m", "population", "lon", "lat"])
    ok, idx, w = bilinear_weights(ax, rec.x_utm37n_m.to_numpy() - site.E0, rec.y_utm37n_m.to_numpy() - site.N0)
    rec_in = rec[ok].reset_index(drop=True)
    idx, w = idx[ok], w[ok]
    pop = rec_in.population.to_numpy()
    interp = lambda g: np.sum(np.where(np.isfinite(g[idx]), g[idx], -999.0) * w, axis=1)
    jobs_by_id = {j["flight"]["flight_id"]: j for j in jobs}
    rows, all_nodes = [], []
    for r in res:
        fr = jobs_by_id[r["flight_id"]]
        row = {"flight_id": r["flight_id"], "path_status": r["status"], "flags": ";".join(r.get("flags", [])),
               "error": r.get("error"), **{k: fr["met"][k] for k in ("t_c", "rh_pct", "qnh_hpa", "wind_kt", "met_source", "met_age_min")}}
        if r["status"] == "OK":
            sel, lmax = r["sel"].astype(float), r["lmax"].astype(float)
            e = np.where(np.isfinite(sel), 10 ** (sel / 10), 0.0)
            p = fr["flight"]["period"]
            E[p] += e
            key = fr["flight"]["runway"]
            by_rwy.setdefault(key, {k: np.zeros(rx.shape) for k in ("day", "evening", "night")})[p] += e
            for thr in NA:
                NA[thr] += (lmax >= thr).astype(np.int32)
            lm_p, se_p = interp(lmax), interp(sel)
            for thr in cfg["metrics"]["per_flight_lamax_db"]:
                row[f"pop_lamax_ge_{thr}"] = float(pop[lm_p >= thr].sum())
            for thr in cfg["metrics"]["per_flight_sel_db"]:
                row[f"pop_sel_ge_{thr}"] = float(pop[se_p >= thr].sum())
            row["max_sel_grid_db"] = float(np.nanmax(sel))
            row.update({k: r[k] for k in r if k not in ("sel", "lmax", "nodes", "flags", "flight_id", "status", "error")})
            all_nodes.append(r["nodes"])
            if cfg["run"]["save_flight_grids"]:
                np.savez_compressed(P["interim"] / f"{r['flight_id']}.npz", sel=r["sel"], lmax=r["lmax"])
        rows.append(row)
    fres = f.merge(pd.DataFrame(rows), on="flight_id", how="left") if rows else f.assign(path_status=np.nan)
    fres.loc[fres.noise_status.isin(["OK", "PROXY_ZERO_DELTA"]) & (fres.path_status != "OK"), "noise_status"] = "PATH_FAILED"
    modelled = fres.path_status.eq("OK")

    def lev(en, seconds):
        with np.errstate(divide="ignore"):
            return 10 * np.log10(en / seconds)
    Etot = E["day"] + E["evening"] + E["night"]
    G = pd.DataFrame({"x_utm37n_m": site.E0 + rx * FT, "y_utm37n_m": site.N0 + ry * FT})
    G["LAeq24"] = lev(Etot, 86400)
    G["Lden"] = lev(E["day"] * 10 ** (pen["day"] / 10) + E["evening"] * 10 ** (pen["evening"] / 10) + E["night"] * 10 ** (pen["night"] / 10), 86400)
    G["Lday"] = lev(E["day"], 12 * 3600)
    G["Levening"] = lev(E["evening"], 4 * 3600)
    G["Lnight"] = lev(E["night"], 8 * 3600)
    for thr in NA:
        G[f"N{thr}"] = NA[thr]
    for k, ee in by_rwy.items():
        G[f"Lden_{k}"] = lev(ee["day"] * 10 ** (pen["day"] / 10) + ee["evening"] * 10 ** (pen["evening"] / 10) + ee["night"] * 10 ** (pen["night"] / 10), 86400)
    G = G.replace(-np.inf, np.nan)
    from pyproj import Transformer
    lon, lat = Transformer.from_crs(32637, 4326, always_xy=True).transform(G.x_utm37n_m.to_numpy(), G.y_utm37n_m.to_numpy())
    G.insert(2, "lon", lon)
    G.insert(3, "lat", lat)
    G.to_parquet(P["processed"] / "noise_grid.parquet", index=False, compression="zstd")
    write_geotiffs(G, ax, site, P["processed"])

    # population exposure
    expo = []
    for metric, bands in (("Lden", cfg["metrics"]["lden_bands_db"]), ("Lnight", cfg["metrics"]["lnight_bands_db"])):
        v = interp(G[metric].fillna(-999).to_numpy())
        edges = list(bands) + [np.inf]
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (v >= lo) & (v < hi)
            expo.append({"metric": metric, "band": f"{lo}-{hi}" if np.isfinite(hi) else f">={lo}", "lower_db": lo,
                         "population": float(pop[m].sum()), "cells": int(m.sum())})
        for lo in bands:
            expo.append({"metric": metric, "band": f">={lo} (cumulative)", "lower_db": lo, "population": float(pop[v >= lo].sum()),
                         "cells": int((v >= lo).sum())})
    for thr in NA:
        v = interp(G[f"N{thr}"].astype(float).to_numpy())
        for n in (1, 5, 10, 20, 50, 100):
            expo.append({"metric": f"N{thr}", "band": f">={n} events", "lower_db": thr, "population": float(pop[v >= n - 1e-9].sum()),
                         "cells": int((v >= n - 1e-9).sum())})
    for k in by_rwy:
        v = interp(G[f"Lden_{k}"].fillna(-999).to_numpy())
        for lo in cfg["metrics"]["lden_bands_db"]:
            expo.append({"metric": f"Lden_{k}_alone", "band": f">={lo}", "lower_db": lo, "population": float(pop[v >= lo].sum()), "cells": int((v >= lo).sum())})
    # WHO 2018 exposure-response (indicative only)
    ld = interp(G["Lden"].fillna(-999).to_numpy())
    ln = interp(G["Lnight"].fillna(-999).to_numpy())
    ha = np.where((ld >= 40) & (ld <= 75), -50.9693 + 1.0168 * ld + 0.0072 * ld ** 2, np.where(ld > 75, -50.9693 + 1.0168 * 75 + 0.0072 * 75 ** 2, 0.0))
    hsd = np.where((ln >= 40) & (ln <= 65), 16.79 - 0.9293 * ln + 0.0198 * ln ** 2, np.where(ln > 65, 16.79 - 0.9293 * 65 + 0.0198 * 65 ** 2, 0.0))
    expo.append({"metric": "WHO2018_highly_annoyed_indicative", "band": "Lden 40-75 dB", "lower_db": 40, "population": float(np.sum(pop * np.clip(ha, 0, 100) / 100)), "cells": int((ld >= 40).sum())})
    expo.append({"metric": "WHO2018_highly_sleep_disturbed_indicative", "band": "Lnight 40-65 dB", "lower_db": 40, "population": float(np.sum(pop * np.clip(hsd, 0, 100) / 100)), "cells": int((ln >= 40).sum())})
    expo = pd.DataFrame(expo)
    expo.to_csv(P["processed"] / "population_exposure.csv", index=False)

    # per-runway / per-procedure summary
    fm = fres[modelled].copy()
    fm["procedure"] = fm.procedure.fillna("(no unique SID match)")
    summ = []
    for keys, g in list(fm.groupby("runway")) + list(fm.groupby(["runway", "procedure"])):
        keys = keys if isinstance(keys, tuple) else (keys, "ALL")
        d = {"runway": keys[0], "procedure": keys[1], "departures": len(g)}
        for c in [c for c in fm.columns if c.startswith("pop_")]:
            d[f"mean_{c}"] = float(g[c].mean())
            d[f"median_{c}"] = float(g[c].median())
        summ.append(d)
    pd.DataFrame(summ).to_csv(P["processed"] / "runway_procedure_summary.csv", index=False)
    keep = [c for c in fres.columns if c not in ("anchor_utc", "anchor_local")]
    fres_out = fres[keep].assign(anchor_utc=fres.anchor_utc.astype(str), anchor_local=fres.anchor_local.astype(str))
    fres_out.to_csv(P["processed"] / "flight_results.csv", index=False)
    if all_nodes:
        pd.concat(all_nodes).to_parquet(P["interim"] / "flight_path_nodes.parquet", index=False, compression="zstd")

    # QC: grid interpolation and pruning errors on the most exposing flight
    _init_worker(state)
    ok_res = [r for r in res if r["status"] == "OK"]
    if ok_res:
        fm_ = fres[modelled].set_index("flight_id")
        fid = fm_["pop_lamax_ge_65"].idxmax()
        r = next(x for x in ok_res if x["flight_id"] == fid)
        j = jobs_by_id[fid]
        m = model_flight(j["flight"], j["obs"], j["met"])
        rng = np.random.default_rng(0)
        lm_p = interp(r["lmax"].astype(float))
        cand = np.nonzero((lm_p >= 50) & (pop > 0))[0]
        pick = rng.choice(cand, size=min(2000, len(cand)), replace=False) if len(cand) else np.array([], int)
        if len(pick):
            px = (rec_in.x_utm37n_m.to_numpy()[pick] - site.E0) / FT
            py = (rec_in.y_utm37n_m.to_numpy()[pick] - site.N0) / FT
            se_x, lm_x = m["evaluate"](px, py, None)
            d_sel = interp(r["sel"].astype(float))[pick] - se_x
            d_lm = lm_p[pick] - lm_x
            qc.append(("grid.interpolation_error", "PASS" if np.percentile(np.abs(d_lm), 95) < 1.0 else "WARNING",
                       f"flight {fid}: bilinear grid->receptor vs exact at {len(pick)} populated receptors with LAmax >= 50 dB: "
                       f"SEL |err| p50 {np.median(np.abs(d_sel)):.2f} / p95 {np.percentile(np.abs(d_sel), 95):.2f} dB; "
                       f"LAmax |err| p50 {np.median(np.abs(d_lm)):.2f} / p95 {np.percentile(np.abs(d_lm), 95):.2f} dB; "
                       f"mean signed SEL err {d_sel.mean():+.2f} dB"))
        if cfg["grid"].get("prune_m") is not None:
            gi = rng.choice(len(rx), size=3000, replace=False)
            se_np, _ = m["evaluate"](rx[gi], ry[gi], None)
            sp = r["sel"].astype(float)[gi]
            affected = np.isfinite(se_np) & (se_np >= 50)
            d = np.where(np.isfinite(sp), se_np - sp, np.inf)[affected]
            worst = float(np.abs(d).max()) if affected.any() else 0.0
            qc.append(("grid.prune_error", "PASS" if worst < 0.1 else "WARNING",
                       f"flight {fid}: pruning at {cfg['grid']['prune_m'] / 1000:.0f} km vs none at 3000 random grid points: "
                       f"max |dSEL| where SEL >= 50 dB = {worst:.3f} dB (inf: a receptor lost every contribution)"))
        ex = fres[modelled][["z_source_geometric_frac", "geo_minus_baro_median_ft"]]
        qc.append(("path.height_sources", "PASS", f"geometric-height share (median over flights) {ex.z_source_geometric_frac.median():.2f}; "
                   f"median per-flight (geometric - baro) height difference {ex.geo_minus_baro_median_ft.median():+.0f} ft "
                   f"(p95 |.| {ex.geo_minus_baro_median_ft.abs().quantile(.95):.0f} ft)"))
        fl = fres.loc[modelled, "flags"].fillna("")
        qc.append(("path.flags", "PASS" if (fl == "").all() else "WARNING",
                   f"flights with path flags: {int((fl != '').sum())}; " + "; ".join(sorted(set(";".join(fl).split(";")) - {""}))))

    # QC
    n_in = int(f.in_scope.sum())
    cov = fres[f.in_scope].noise_status.value_counts().to_dict()
    qc.append(("coverage.modelled", "PASS" if modelled.sum() == n_in else "WARNING",
               f"{int(modelled.sum())} of {n_in} in-scope departures modelled; status counts {cov}"))
    nfb = int((fres[modelled].met_source == "MET_FALLBACK").sum())
    qc.append(("weather.fallback", "PASS" if nfb == 0 else "WARNING", f"{nfb} modelled flights used the weather fallback"))
    edge = G[["LAeq24"]].to_numpy().reshape(len(ax), len(ax))
    border = np.nanmax(np.r_[edge[0], edge[-1], edge[:, 0], edge[:, -1]])
    qc.append(("grid.border_level", "PASS" if not np.isfinite(border) or border < cfg["metrics"]["lden_bands_db"][0] - 5 else "WARNING",
               f"max LAeq,24h on the grid border {border:.1f} dB (grid large enough when well below the lowest reported band)"))
    pop_grid = float(pop.sum())
    qc.append(("population.in_grid", "PASS", f"A6 population inside the noise grid: {pop_grid:,.0f} on {len(pop)} receptors"))
    man = {"release_id": cfg["release_id"], "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "inputs_sha256": inputs, "flights_total": int(len(f)), "flights_in_scope": n_in, "flights_modelled": int(modelled.sum()),
           "status_counts": {k: int(v) for k, v in fres.noise_status.value_counts().items()},
           "grid": {"spacing_m": cfg["grid"]["spacing_m"], "half_width_m": cfg["grid"]["half_width_m"], "n": int(len(rx))},
           "runtime_s": round(time.time() - t0, 1), "qc": [{"check": a, "status": b, "detail": c} for a, b, c in qc]}
    (P["validation"] / "noise_manifest.json").write_text(json.dumps(man, indent=2, default=str))
    pd.DataFrame(man["qc"]).to_csv(P["validation"] / "noise_qc.csv", index=False)
    print(json.dumps({k: man[k] for k in ("flights_total", "flights_in_scope", "flights_modelled", "status_counts", "runtime_s")}, indent=1))
    return man


def write_geotiffs(G, ax, site, outdir):
    import rasterio
    from rasterio.transform import from_origin
    n, s = len(ax), ax[1] - ax[0]
    tr = from_origin(site.E0 + ax[0] - s / 2, site.N0 + ax[-1] + s / 2, s, s)
    cols = ["LAeq24", "Lden", "Lnight"] + [c for c in G.columns if c.startswith("N") and c[1:].isdigit()]
    with rasterio.open(outdir / "noise_grid_utm37n.tif", "w", driver="GTiff", height=n, width=n, count=len(cols), dtype="float32",
                       crs="EPSG:32637", transform=tr, nodata=np.nan, compress="deflate") as ds:
        for i, c in enumerate(cols, 1):
            ds.write(np.flipud(G[c].to_numpy(float).reshape(n, n)).astype("float32"), i)
            ds.set_band_description(i, c)


if __name__ == "__main__":
    main(*(Path(a) for a in sys.argv[1:2]))
