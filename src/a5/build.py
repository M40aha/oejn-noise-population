"""A5 build: raw sources -> interim (typed, provenance) -> processed (validated) -> validation reports.

Run from the a5_noise/ folder:  python -m a5.build   (with src/ on PYTHONPATH; see README)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

from . import constants as C
from .anp_checks import (aircraft_derived, npd_long, physics_and_logic, referential_integrity,
                         roundtrip_checks, spectral_long)
from .easa import load_substitutions, load_verified_types
from .ingest import build_manifest, cast_anp_table, read_anp_member
from .mapping import Mapper, MappingPolicy, mapping_qc
from .npd import NPDLookup, NPDPolicy
from .qc import QCRegistry
from .schemas import ANP_TABLES
from .vol3 import load_fixtures, validate_npd_against_b2, validate_unit_constants

ROOT = Path(__file__).resolve().parents[2]

SI = {  # native unit -> (SI unit, factor, note)
    "lb": ("kg", C.LB_TO_KG, "mass columns; thrust columns in lb are pound-force -> N factor 4.4482216152605"),
    "ft": ("m", C.FT_TO_M, ""), "kt": ("m/s", C.KT_TO_MS, ""), "ft/min": ("m/s", C.FT_TO_M / 60, ""),
    "dB": ("dB", 1.0, ""), "deg": ("deg", 1.0, ""), "%": ("%", 1.0, ""), "-": ("-", 1.0, ""), "hp": ("W", 745.69987158227022, "mechanical horsepower"),
}
COEFF_NOTE = "Doc 29 Eq. B-1 coefficient: keep native units; do not convert"
THRUST_COLS = {"max_static_thrust_lb"}


def _units_registry() -> pd.DataFrame:
    rows = []
    for tbl, spec in ANP_TABLES.items():
        for src, canon, kind, unit, desc in spec["columns"]:
            if kind not in ("int", "float"):
                continue
            if canon in ("E", "F", "Ga", "Gb", "H", "K1", "K2", "K3", "K4", "B", "C", "D", "R"):
                rows.append((tbl, canon, unit, None, None, COEFF_NOTE))
            elif canon in THRUST_COLS:
                rows.append((tbl, canon, "lbf", "N", C.LBF_TO_N, "pound-force"))
            elif unit.startswith("per aircraft"):
                rows.append((tbl, canon, unit, None, None, "unit depends on aircraft power_parameter"))
            else:
                si = SI.get(unit, (None, None, "unit not in registry"))
                rows.append((tbl, canon, unit, si[0], si[1], si[2] if unit != "lb" else "mass"))
    return pd.DataFrame(rows, columns=["table", "column", "native_unit", "si_unit", "si_factor", "note"])


def _sanitize(df: pd.DataFrame) -> pd.DataFrame:
    """Make object columns storable: all-numeric -> float, otherwise text (dates as ISO). Values are not altered."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype != object:
            continue
        nonnull = df[c].dropna()
        if len(nonnull) and nonnull.map(lambda v: isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)).all():
            df[c] = pd.to_numeric(df[c]).astype(float)
        elif len(nonnull) and nonnull.map(lambda v: isinstance(v, (bool, np.bool_))).all():
            df[c] = df[c].astype("boolean")
        else:
            df[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else
                              (v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else str(v))).astype("string")
    return df


def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


def run(config_path: Path = ROOT / "config" / "a5.yaml") -> dict:
    cfg = yaml.safe_load(config_path.read_text())
    raw = Path(os.environ.get("A5_RAW_DIR") or (ROOT / cfg["raw_dir"])).resolve()
    rel = cfg["release_id"]
    pol = cfg["policies"]
    tol = cfg["tolerances"]
    qc = QCRegistry()
    norm_log: list[dict] = []
    S = cfg["sources"]

    # 0. manifest
    sources = build_manifest(raw, S, qc)

    # 1-2. ANP tables
    zip_path = raw / S["anp_tables"]["file"]
    t = {name: cast_anp_table(name, read_anp_member(zip_path, spec["member"]), qc, norm_log)
         for name, spec in ANP_TABLES.items()}

    # 3-4. checks
    referential_integrity(t, qc)
    physics_and_logic(t, qc)
    t["anp_npd_long"] = npd_long(t["anp_npd_wide"])
    t["anp_spectral_long"] = spectral_long(t["anp_spectral_wide"])
    roundtrip_checks(t, qc)
    t["anp_aircraft"] = aircraft_derived(t)

    # NPD lookup sanity on the real ANP data: reproduces every tabulated value exactly
    npd_policy = NPDPolicy(**pol["npd"])
    kind = dict(zip(t["anp_aircraft"].npd_id, t["anp_aircraft"].power_parameter_kind))
    lk = NPDLookup(t["anp_npd_long"], npd_policy, kind)
    worst = 0.0
    for (nid, met, mode), g in t["anp_npd_long"].groupby(["npd_id", "noise_metric", "op_mode"]):
        r = lk.lookup(nid, met, mode, g.power_setting.to_numpy(), g.distance_ft.to_numpy())
        worst = max(worst, float(np.max(np.abs(r.level_db.to_numpy() - g.level_db.to_numpy()))))
    qc.add("validation.npd_lookup_reproduces_anp_grid", "validation", "PASS" if worst < 1e-9 else "ERROR",
           f"NPD lookup returns every tabulated ANP 2.3 value at its grid point (max |diff| = {worst:.1e} dB, "
           f"{len(t['anp_npd_long'])} points)")

    # 5. EASA
    icao, cfgtab = load_substitutions(raw / S["easa_substitutions"]["file"], set(t["anp_aircraft"].acft_id), qc)
    verified = load_verified_types(raw / S["easa_verified_types"]["file"], cfgtab, qc)

    # 6. Doc 29 constants
    const = pd.DataFrame(C.DOC29_CONSTANTS, columns=["name", "value", "unit", "meaning", "source", "location"])
    d1 = pd.DataFrame({"frequency_hz": list(C.TABLE_D1_DB_PER_100M),
                       "attenuation_db_per_100m": list(C.TABLE_D1_DB_PER_100M.values()),
                       "source": "Doc 29 5th Ed. Vol 2", "location": "Appendix D, Table D-1, p. D-2"})
    qc.check("structure.table_d1_bands", "structure", int(set(d1.frequency_hz) != set(C.SPECTRAL_BANDS_HZ)),
             "Table D-1 covers exactly the 24 spectral-class bands", "Table D-1 bands differ from spectral bands")

    # 7. Vol 3 fixtures + executable validation
    wb1 = raw / S["doc29_vol3_wb1"]["file"]
    fixtures = load_fixtures(wb1, qc)
    b2 = validate_npd_against_b2(wb1, fixtures, npd_policy, tol["vol3_b2_baseline_sel_max_abs_db"],
                                 tol["vol3_b2_baseline_sel_target_db"], qc)
    validate_unit_constants(wb1, tol["unit_conversion_rel"], qc)

    # 8. mapping
    analyst = pd.read_csv(ROOT / "data" / "a5" / "reviews" / "analyst_proxies.csv", dtype=str)
    mapper = Mapper(icao, cfgtab, t["anp_aircraft"], verified, analyst, MappingPolicy(
        substitution_method=pol["mapping"]["substitution_method"],
        mtow_match_tolerance_kg=pol["mapping"]["mtow_match_tolerance_kg"],
        engine_family_min_chars=pol["mapping"]["engine_family_min_chars"]), rel)
    mp, cands = mapper.icao_reference()
    mapping_qc(mp, t["anp_aircraft"], set(t["anp_npd_wide"].npd_id), qc, "icao_reference")

    # 9. assemble outputs
    out = {
        **{k: v for k, v in t.items()},
        "easa_subst_icao": icao, "easa_subst_config": cfgtab.drop(columns=["engine_norm", "model_norm"]),
        "easa_verified_types": verified, "doc29_constants": const, "doc29_table_d1": d1,
        "vol3_b2_npd_validation": b2,
        "vol3_fixture_aircraft": fixtures["A-1_Aircraft"], "vol3_fixture_jet_coefficients": fixtures["A-2_Jet_Coefficients"],
        "vol3_fixture_npd": fixtures["A-7_NPD_Curves"], "vol3_fixture_spectral": fixtures["A-8_Spectral_Class"],
        "aircraft_noise_mapping": mp, "mapping_candidates": cands,
        "mapping_analyst_proxies": analyst, "units_registry": _units_registry(),
        "normalization_log": pd.DataFrame(norm_log), "sources": sources,
    }
    qcdf = qc.frame()
    out["qc_results"] = qcdf

    proc = ROOT / "data" / "a5" / "processed"
    val = ROOT / "data" / "a5" / "validation"
    inter = ROOT / "data" / "a5" / "interim"
    for p in (proc, val, inter):
        p.mkdir(parents=True, exist_ok=True)
        for f in p.glob("*"):
            if f.is_file():
                f.unlink()
    for name in ANP_TABLES:
        t[name].to_parquet(inter / f"{name}.parquet", index=False)

    db_path = proc / f"{rel}.duckdb"
    con = duckdb.connect(str(db_path))
    out_manifest = []
    for name, df in out.items():
        df = _sanitize(df)
        target = val if name.startswith(("qc_", "vol3_b2")) else proc
        df.to_parquet(target / f"{name}.parquet", index=False)
        con.register("tmp_df", df)
        con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM tmp_df')
        con.unregister("tmp_df")
        out_manifest.append({"table": name, "rows": len(df), "columns": len(df.columns),
                             "content_sha256": _hash_df(df), "location": f"{target.name}/{name}.parquet"})
    # convenience views for the noise-model stage
    con.execute("""CREATE OR REPLACE VIEW v_departure_npd AS
                   SELECT a.acft_id, a.npd_id, a.power_parameter_kind, n.noise_metric, n.power_setting, n.distance_ft, n.level_db
                   FROM anp_aircraft a JOIN anp_npd_long n USING (npd_id)
                   WHERE n.op_mode = 'D' AND n.noise_metric IN ('SEL','LAmax')""")
    con.execute("""CREATE OR REPLACE VIEW v_mapping_usable AS
                   SELECT * FROM aircraft_noise_mapping WHERE usable_for_noise""")
    con.close()

    mp.to_csv(proc / "aircraft_noise_mapping.csv", index=False)
    cands.to_csv(proc / "mapping_candidates.csv", index=False)
    qcdf.to_csv(val / "qc_results.csv", index=False)
    pd.DataFrame(out_manifest).to_csv(proc / "output_manifest.csv", index=False)

    summary = {
        "release_id": rel, "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "packages": {m.__name__: m.__version__ for m in (pd, np, duckdb)},
        "qc_counts": {s: qc.count(s) for s in ("PASS", "INFO", "WARNING", "ERROR", "UNRESOLVED")},
        "vol3_b2_max_abs_diff_db": float(b2.abs_diff_db.max()), "vol3_b2_segments": int(len(b2)),
        "mapping_methods": mp.mapping_method.value_counts().to_dict(),
    }
    (val / "build_summary.json").write_text(json.dumps(summary, indent=2))
    from .report import write_reports
    write_reports(ROOT, out, summary, cfg)
    return summary


if __name__ == "__main__":
    s = run()
    print(json.dumps(s, indent=2))
    sys.exit(1 if s["qc_counts"]["ERROR"] else 0)
