"""EASA substitution tables and the verified-types list."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import openpyxl

from .ingest import read_xlsx_sheet
from .qc import QCRegistry

# ICAO Doc 8643 designators for verified airframes absent from the substitution configuration tab.
# Analyst-entered; marked as such in the output so they can be checked.
ANALYST_ICAO_FOR_AIRFRAME = {
    "A330-941": "A339", "A330-743L": "A337", "ERJ 190-300": "E290", "ERJ 190-400": "E295",
    "747-400F": "B744", "767-300": "B763", "767-300F": "B763", "Falcon 900EX": "F900",
    "Falcon 900LX": "F900", "GVI": "GLF6",
}


def norm_engine(s) -> str:
    """Normalise an engine designation for matching: upper case, drop spaces, hyphens, dots, slashes, brackets."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    return re.sub(r"[\s\-./()]", "", str(s)).upper()


def norm_model(s) -> str:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    return re.sub(r"[\s\-]", "", str(s)).upper()


def load_substitutions(path: Path, anp_ids: set[str], qc: QCRegistry) -> tuple[pd.DataFrame, pd.DataFrame]:
    icao = read_xlsx_sheet(path, "by ICAO code").rename(columns={
        "AIRFRAME_MANUFACTURER": "airframe_manufacturer", "ICAO_CODE": "icao_code", "AIRCRAFT_VARIANT": "variant",
        "ANP_PROXY": "anp_proxy", "DELTA_DEP_dB": "delta_dep_db", "DELTA_APP_dB": "delta_app_db",
        "N_DEP": "n_dep", "N_APP": "n_app"})
    cfg = read_xlsx_sheet(path, "by aircraft configuration").rename(columns=str.lower).rename(columns={
        "delta_dep_db": "delta_dep_db", "delta_app_db": "delta_app_db",
        "lateral_level_epndb": "lateral_epndb", "flyover_level_epndb": "flyover_epndb", "approach_level_epndb": "approach_epndb"})
    for df in (icao, cfg):
        for c in ("delta_dep_db", "delta_app_db", "n_dep", "n_app"):
            df[c] = pd.to_numeric(df[c], errors="raise").astype(float)
        for c in df.columns:
            if df[c].dtype == object and c not in ("src_row",):
                df[c] = df[c].map(lambda v: v.strip() if isinstance(v, str) else v)
    for c in ("mtow_kg", "mlw_kg", "lateral_epndb", "flyover_epndb", "approach_epndb", "engine_number", "noise_chapter"):
        cfg[c] = pd.to_numeric(cfg[c], errors="coerce").astype(float)
    cfg["dep_cert_level_epndb"] = (cfg.flyover_epndb + cfg.lateral_epndb) / 2.0
    cfg["engine_norm"] = cfg.engine_type.map(norm_engine)
    cfg["model_norm"] = cfg.airframe_type.map(norm_model)

    qc.add("structure.rows.easa_subst_icao", "structure", "INFO",
           f"EASA 'by ICAO code': {len(icao)} rows, {icao.icao_code.nunique()} ICAO codes, "
           f"{int((icao.icao_code.value_counts() > 1).sum())} codes with several variants", len(icao))
    qc.add("structure.rows.easa_subst_config", "structure", "INFO",
           f"EASA 'by aircraft configuration': {len(cfg)} certified configurations", len(cfg))
    qc.add("cross_source.easa_baseline_version", "cross_source", "WARNING",
           "EASA substitution workbook revision history ends at ANP 2.2 (22-02-2018); A5 uses ANP 2.3 data. "
           "All proxies still resolve (checked below); 2.3 revised A350-941 and 7378MAX data after these deltas were derived.")

    for name, df in (("icao", icao), ("config", cfg)):
        miss = sorted(set(df.anp_proxy.dropna()) - anp_ids)
        qc.check(f"cross_source.easa_{name}_proxies_in_anp", "cross_source", len(miss),
                 f"Every EASA '{name}' proxy exists in ANP 2.3", f"EASA '{name}' proxies missing from ANP 2.3", details=str(miss))
        # N must equal 10^(delta/10) within the rounding of the published values (delta 1 dp, N 2 dp)
        for op in ("dep", "app"):
            d, n = df[f"delta_{op}_db"], df[f"n_{op}"]
            lo = 10 ** ((d - 0.05) / 10) - 0.005 - 1e-9
            hi = 10 ** ((d + 0.05) / 10) + 0.005 + 1e-9
            bad = df[(n < lo) | (n > hi)]
            qc.check(f"cross_source.easa_{name}_N_vs_delta_{op}", "cross_source", len(bad),
                     f"EASA '{name}': N_{op} = 10^(delta_{op}/10) within published rounding for all rows",
                     f"EASA '{name}': N_{op} inconsistent with delta_{op}", "WARNING",
                     str(bad[["icao_code", "anp_proxy", f"delta_{op}_db", f"n_{op}"]].head(10).values.tolist()))

    # EASA states the ICAO tab holds the noisiest configuration for each ICAO code / proxy pair: verify.
    mx = cfg.groupby(["icao_code", "anp_proxy"]).delta_dep_db.max().rename("cfg_max_delta_dep")
    j = icao.merge(mx, left_on=["icao_code", "anp_proxy"], right_index=True, how="left")
    absent = j[j.cfg_max_delta_dep.isna()]
    mism = j[j.cfg_max_delta_dep.notna() & ((j.delta_dep_db - j.cfg_max_delta_dep).abs() > 0.05)]
    qc.add("cross_source.easa_icao_is_noisiest_config", "cross_source", "PASS" if mism.empty else "WARNING",
           f"ICAO-tab departure delta equals the maximum configuration-tab delta for "
           f"{len(j) - len(absent) - len(mism)}/{len(j) - len(absent)} ICAO/proxy pairs present in both tabs "
           f"({len(absent)} pairs have no configuration rows)", len(mism),
           str(mism[["icao_code", "anp_proxy", "delta_dep_db", "cfg_max_delta_dep"]].head(15).values.tolist()))
    return icao, cfg


def load_verified_types(path: Path, cfg: pd.DataFrame, qc: QCRegistry) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb["Sheet1"].iter_rows(values_only=True))
    wb.close()
    recs, cur = [], None
    for i, r in enumerate(rows[2:], start=3):
        anp_id, af_man, af_type, en_man, en_type, comment, date = (list(r) + [None] * 7)[:7]
        if anp_id:
            cur = {"verified_anp_id": str(anp_id).replace("\xa0", " ").strip(), "airframe_manufacturer": af_man,
                   "engine_manufacturer": en_man, "date_published": date, "comments": [], "last_airframe": None,
                   "last_engine": None}
        if cur is None:
            continue
        if comment:
            cur["comments"].append(str(comment).strip())
        if af_type or en_type:
            cur["last_airframe"] = af_type or cur["last_airframe"]
            cur["last_engine"] = en_type or cur["last_engine"]
            recs.append({"verified_anp_id": cur["verified_anp_id"], "airframe_manufacturer": cur["airframe_manufacturer"],
                         "airframe_type": cur["last_airframe"], "engine_manufacturer": cur["engine_manufacturer"],
                         "engine_type": cur["last_engine"], "date_published": cur["date_published"],
                         "comments_ref": cur, "src_file": path.name, "src_member": "Sheet1", "src_row": i})
    df = pd.DataFrame(recs)
    df["comments"] = df.pop("comments_ref").map(lambda c: " ".join(c["comments"]))
    model_to_icao = (cfg.dropna(subset=["airframe_type"]).assign(m=lambda x: x.airframe_type.map(norm_model))
                     .groupby("m").icao_code.agg(lambda s: "|".join(sorted(set(s)))))
    df["icao_code"] = df.airframe_type.map(lambda a: model_to_icao.get(norm_model(a)))
    df["icao_code_source"] = np.where(df.icao_code.notna(), "EASA configuration tab", None)

    def _series(a):
        """Same model series (e.g. A320-272N -> A320-27x): accept only if it gives exactly one ICAO code."""
        m = norm_model(a)
        for n in range(len(m) - 1, 5, -1):
            hits = {v for k, v in model_to_icao.items() if k.startswith(m[:n]) and k[-1:] == m[-1:]}
            if len(hits) == 1:
                return hits.pop()
            if len(hits) > 1:
                return None
        return None
    miss = df.icao_code.isna()
    df.loc[miss, "icao_code"] = df.loc[miss, "airframe_type"].map(_series)
    df.loc[miss & df.icao_code.notna(), "icao_code_source"] = "EASA configuration tab (same model series)"
    fill = df.icao_code.isna()
    df.loc[fill, "icao_code"] = df.loc[fill, "airframe_type"].map(ANALYST_ICAO_FOR_AIRFRAME)
    df.loc[fill & df.icao_code.notna(), "icao_code_source"] = "ICAO Doc 8643 designator, analyst-entered (verify)"
    unresolved = df[df.icao_code.isna()]
    qc.add("cross_source.verified_types_icao", "cross_source", "PASS" if unresolved.empty else "WARNING",
           f"EASA verified-types list: {df.verified_anp_id.nunique()} datasets, {len(df)} airframe/engine rows; "
           f"{int(df.icao_code_source.astype(str).str.startswith('EASA').sum())} ICAO codes from EASA, "
           f"{int(fill.sum() - len(unresolved))} analyst-entered, {len(unresolved)} unresolved", len(unresolved))
    return df
