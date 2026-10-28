"""Aircraft -> ANP mapping (Doc 29 Vol 1 §6.4.4 + EASA substitution tables).

Resolution ladder (first applicable rule wins; every candidate is kept):
  ANALYST_PROXY           type absent from EASA tables; proxy chosen with Doc 29 criteria (review file);
                          delta from Eq. 6-1 once certified levels are filled, else PENDING (no silent delta = 0)
  EASA_CONFIG             ICAO + engine (+ model) + MTOW match a certified configuration
  EASA_CONFIG_MAXMTOW     ICAO + engine (+ model) match, MTOW unknown/unmatched -> highest MTOW (Doc 29 conservative)
  EASA_CONFIG_ENGINE_FAMILY  engine given only as a family prefix (e.g. 'LEAP-1A') -> conservative within family
  EASA_ICAO               only the ICAO code known, single variant -> ICAO tab (EASA: noisiest configuration)
  EASA_ICAO_AMBIGUOUS     several variants, engine unknown -> conservative variant (highest certified departure
                          level at max MTOW, Doc 29 Vol 1 p.45); all variants kept as candidates (sensitivity bracket)
  UNRESOLVED              no defensible mapping; kept and reported, never dropped silently
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .constants import LB_TO_KG
from .easa import norm_engine, norm_model
from .qc import QCRegistry

CONFIDENCE = {
    "EASA_CONFIG": "HIGH", "EASA_CONFIG_MAXMTOW": "HIGH", "EASA_CONFIG_ENGINE_FAMILY": "MEDIUM",
    "EASA_ICAO": "MEDIUM", "EASA_ICAO_AMBIGUOUS": "LOW", "ANALYST_PROXY": "LOW", "UNRESOLVED": "NONE",
}

ANP_ATTRS = ["npd_id", "dep_spectral_class_id", "lateral_directivity", "power_parameter", "power_parameter_kind",
             "engine_type", "n_engines", "has_jet_coefficients", "has_hitemp_ratings", "thrust_ratings",
             "has_departure_steps", "departure_profiles", "description", "mtow_lb"]


@dataclass
class MappingPolicy:
    substitution_method: str = "A"
    mtow_match_tolerance_kg: float = 0.5
    engine_family_min_chars: int = 5


def _tokens(s) -> set[str]:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return set()
    return {norm_engine(x) for x in re.split(r"[,;]", str(s)) if norm_engine(x)}


def _conservative(rows: pd.DataFrame) -> tuple[pd.Series, str]:
    """Doc 29 Vol 1 p.45: highest MTOW variant; among equals, highest certified departure level; then highest delta."""
    r = rows[rows.mtow_kg == rows.mtow_kg.max()]
    r = r[r.dep_cert_level_epndb == r.dep_cert_level_epndb.max()] if r.dep_cert_level_epndb.notna().any() else r
    r = r.sort_values("delta_dep_db", ascending=False)
    note = "" if r[["anp_proxy", "delta_dep_db"]].drop_duplicates().shape[0] == 1 else \
        f"tie between {r[['anp_proxy', 'delta_dep_db']].drop_duplicates().values.tolist()}: highest delta taken"
    return r.iloc[0], note


class Mapper:
    def __init__(self, icao_tab: pd.DataFrame, cfg_tab: pd.DataFrame, anp_aircraft: pd.DataFrame,
                 verified: pd.DataFrame, analyst: pd.DataFrame, policy: MappingPolicy, release_id: str):
        self.icao = icao_tab
        self.cfg = cfg_tab.copy()
        self.cfg["engine_tokens"] = self.cfg.engine_type.map(_tokens)
        self.cfg["model_norm"] = self.cfg.airframe_type.map(norm_model)
        if "dep_cert_level_epndb" not in self.cfg:
            self.cfg["dep_cert_level_epndb"] = (self.cfg.flyover_epndb + self.cfg.lateral_epndb) / 2.0
        self.anp = anp_aircraft.set_index("acft_id")
        self.verified = verified
        self.analyst = analyst.set_index("icao_type") if len(analyst) else analyst
        self.policy = policy
        self.release_id = release_id

    # ------------------------------------------------------------------ helpers
    def _proxy_cert_sum(self, proxy: str) -> tuple[float, str]:
        """FO + LAT certified EPNdB of the ANP proxy itself (Eq. 6-1 only needs the sum).
        Taken from configuration rows that EASA maps to this proxy with zero departure and approach delta,
        preferring rows whose MTOW equals the ANP MTOW. Rows must agree on the sum to 0.05 dB."""
        r = self.cfg[(self.cfg.anp_proxy == proxy) & (self.cfg.delta_dep_db == 0) & (self.cfg.delta_app_db == 0)]
        if r.empty:
            return np.nan, "no zero-delta configuration row for the proxy in the EASA configuration tab"
        anp_mtow_kg = float(self.anp.loc[proxy, "mtow_lb"]) * LB_TO_KG
        exact = r[(r.mtow_kg - anp_mtow_kg).abs() <= 1.0]
        use = exact if not exact.empty else r
        sums = (use.flyover_epndb + use.lateral_epndb).round(2).unique()
        rows = ",".join(str(x) for x in use.src_row.head(6))
        if sums.max() - sums.min() > 0.05:
            return np.nan, f"proxy zero-delta rows {rows} disagree on FO+LAT ({sorted(sums.tolist())})"
        lv = use[["flyover_epndb", "lateral_epndb"]].drop_duplicates().values.tolist()
        return float(sums[0]), f"EASA configuration tab rows {rows} (proxy, delta 0): FO/LAT {lv}, FO+LAT = {sums[0]:.1f} EPNdB"

    def _verified_info(self, icao: str) -> tuple[bool, str]:
        v = self.verified[self.verified.icao_code.fillna("").str.split("|").map(lambda s: icao in s)]
        if v.empty:
            return False, ""
        return True, "; ".join(f"{a} / {e} ({d})" for a, e, d in
                               zip(v.airframe_type, v.engine_type, v.verified_anp_id))

    # ------------------------------------------------------------------ single resolution
    def _resolve_one(self, icao: str, model, engine, mtow) -> tuple[dict, list[dict]]:
        icao = (icao or "").strip().upper()
        cands: list[dict] = []
        res = {"mapping_method": "UNRESOLVED", "anp_acft_id": None, "delta_dep_db": np.nan, "delta_app_db": np.nan,
               "n_dep": np.nan, "n_app": np.nan, "selected_airframe": None, "selected_engine": None,
               "selected_mtow_kg": np.nan, "conservative_choice": False, "evidence": "", "source_ref": "",
               "review_status": None, "notes": ""}

        # 1. analyst proxies (types absent from EASA tables)
        if len(self.analyst) and icao in self.analyst.index:
            a = self.analyst.loc[icao]
            sum_p, proxy_src = self._proxy_cert_sum(a.proxy_anp_id)
            fo_m, lat_m = pd.to_numeric(a.miss_flyover_epndb, errors="coerce"), pd.to_numeric(a.miss_lateral_epndb, errors="coerce")
            res.update(mapping_method="ANALYST_PROXY", anp_acft_id=a.proxy_anp_id, review_status=a.review_status,
                       evidence=f"{a.rationale} Proxy certified levels: {proxy_src}.",
                       source_ref="data/a5/reviews/analyst_proxies.csv")
            if np.isfinite(fo_m) and np.isfinite(lat_m) and np.isfinite(sum_p):
                d = (fo_m + lat_m - sum_p) / 2.0          # Eq. 6-1
                res.update(delta_dep_db=d, n_dep=10 ** (d / 10))
            else:
                res["notes"] = "delta pending: certified levels of the missing type not yet entered (Eq. 6-1)"
            cands.append({"source": "analyst_proxies.csv", "anp_proxy": a.proxy_anp_id, "delta_dep_db": res["delta_dep_db"],
                          "selected": True})
            return res, cands

        cfg = self.cfg[self.cfg.icao_code == icao]
        notes = []
        if model and isinstance(model, str) and model.strip() and not cfg.empty:
            mm = cfg[cfg.model_norm == norm_model(model)]
            if mm.empty:
                notes.append(f"airframe model '{model}' not in EASA configuration tab for {icao}; model ignored")
            else:
                cfg = mm

        # 2-4. engine-resolved configuration matches
        e = norm_engine(engine)
        if e and not cfg.empty:
            exact = cfg[cfg.engine_tokens.map(lambda t: e in t)]
            method = None
            if not exact.empty:
                rows = exact
                if mtow is not None and np.isfinite(mtow):
                    m = rows[(rows.mtow_kg - mtow).abs() <= self.policy.mtow_match_tolerance_kg]
                    if not m.empty:
                        rows, method = m, "EASA_CONFIG"
                    else:
                        notes.append(f"MTOW {mtow} kg not among certified MTOWs for this engine; highest MTOW used")
                method = method or "EASA_CONFIG_MAXMTOW"
            elif len(e) >= self.policy.engine_family_min_chars:
                fam = cfg[cfg.engine_tokens.map(lambda t: any(x.startswith(e) for x in t))]
                if not fam.empty:
                    rows, method = fam, "EASA_CONFIG_ENGINE_FAMILY"
            if method:
                for _, r in rows.iterrows():
                    cands.append({"source": "EASA config", "anp_proxy": r.anp_proxy, "delta_dep_db": r.delta_dep_db,
                                  "airframe_type": r.airframe_type, "engine_type": r.engine_type, "mtow_kg": r.mtow_kg,
                                  "dep_cert_level_epndb": r.dep_cert_level_epndb, "src_row": r.src_row, "selected": False})
                sel, tie = _conservative(rows) if method != "EASA_CONFIG" or len(rows) > 1 else (rows.iloc[0], "")
                for c in cands:
                    c["selected"] = c.get("src_row") == sel.src_row
                res.update(mapping_method=method, anp_acft_id=sel.anp_proxy, delta_dep_db=sel.delta_dep_db,
                           delta_app_db=sel.delta_app_db, n_dep=sel.n_dep, n_app=sel.n_app,
                           selected_airframe=sel.airframe_type, selected_engine=sel.engine_type, selected_mtow_kg=sel.mtow_kg,
                           conservative_choice=method != "EASA_CONFIG",
                           evidence=f"EASA configuration tab: {sel.airframe_type} / {sel.engine_type} @ {sel.mtow_kg:.0f} kg "
                                    f"(certified FO {sel.flyover_epndb} / LAT {sel.lateral_epndb} EPNdB) -> {sel.anp_proxy}",
                           source_ref=f"{sel.src_file} | by aircraft configuration | row {sel.src_row}",
                           notes="; ".join(notes + ([tie] if tie else [])))
                return res, cands
            notes.append(f"engine '{engine}' not found for {icao} in EASA configuration tab; ICAO-level fallback")

        # 5-6. ICAO-level
        it = self.icao[self.icao.icao_code == icao]
        for _, r in it.iterrows():
            cands.append({"source": "EASA ICAO", "anp_proxy": r.anp_proxy, "variant": r.variant,
                          "delta_dep_db": r.delta_dep_db, "src_row": r.src_row, "selected": False})
        if len(it) == 1:
            r = it.iloc[0]
            n_cfg = int((self.cfg.icao_code == icao).sum())
            method = "EASA_ICAO"
            res.update(mapping_method=method, anp_acft_id=r.anp_proxy, delta_dep_db=r.delta_dep_db, delta_app_db=r.delta_app_db,
                       n_dep=r.n_dep, n_app=r.n_app, conservative_choice=n_cfg > 1,
                       evidence=f"EASA ICAO tab: {icao} -> {r.anp_proxy} (delta = noisiest of {n_cfg} certified configurations)",
                       source_ref=f"{r.src_file} | by ICAO code | row {r.src_row}", notes="; ".join(notes))
            res["_single_config"] = n_cfg <= 1
            cands[-1]["selected"] = True
            return res, cands
        if len(it) > 1:
            allcfg = self.cfg[self.cfg.icao_code == icao]
            if not allcfg.empty and allcfg.anp_proxy.isin(it.anp_proxy).any():
                sel_cfg, tie = _conservative(allcfg[allcfg.anp_proxy.isin(it.anp_proxy)])
                r = it[it.anp_proxy == sel_cfg.anp_proxy].iloc[0]
                why = (f"conservative variant per Doc 29 Vol 1 p.45: highest MTOW ({sel_cfg.mtow_kg:.0f} kg) and highest certified "
                       f"departure level ({sel_cfg.dep_cert_level_epndb:.2f} EPNdB: {sel_cfg.engine_type})")
            else:
                r = it.sort_values("delta_dep_db", ascending=False).iloc[0]
                tie, why = "", "no configuration rows: highest-delta variant taken"
            for c in cands:
                c["selected"] = c["src_row"] == r.src_row
            res.update(mapping_method="EASA_ICAO_AMBIGUOUS", anp_acft_id=r.anp_proxy, delta_dep_db=r.delta_dep_db,
                       delta_app_db=r.delta_app_db, n_dep=r.n_dep, n_app=r.n_app, conservative_choice=True,
                       evidence=f"EASA ICAO tab has {len(it)} variants for {icao} "
                                f"({', '.join(f'{v}: {p} {d:+.1f} dB' for v, p, d in zip(it.variant, it.anp_proxy, it.delta_dep_db))}); "
                                f"engine unknown -> {r.variant} ({why})",
                       source_ref=f"{r.src_file} | by ICAO code | row {r.src_row}",
                       notes="; ".join(notes + ([tie] if tie else []) + ["resolve the engine (A3) to remove this ambiguity"]))
            return res, cands

        res["notes"] = "; ".join(notes + [f"{icao or '(blank)'} not in EASA substitution tables or analyst proxies"])
        return res, cands

    # ------------------------------------------------------------------ public API
    def resolve(self, records: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """records: columns icao_type (required), airframe_model, engine_type, mtow_kg (optional)."""
        recs = records.copy()
        for c in ("airframe_model", "engine_type", "mtow_kg"):
            if c not in recs:
                recs[c] = np.nan
        out, cand_rows = [], []
        for _, r in recs.iterrows():
            mt = float(r.mtow_kg) if pd.notna(r.mtow_kg) else None
            res, cands = self._resolve_one(r.icao_type, r.airframe_model if pd.notna(r.airframe_model) else None,
                                           r.engine_type if pd.notna(r.engine_type) else None, mt)
            single = res.pop("_single_config", False)
            conf = CONFIDENCE[res["mapping_method"]]
            if res["mapping_method"] == "EASA_ICAO" and single:
                conf = "HIGH"
            if res["mapping_method"] == "ANALYST_PROXY" and (np.isnan(res["delta_dep_db"]) or res["review_status"] != "REVIEWED"):
                conf = "NONE"
            key = {"icao_type": str(r.icao_type).strip().upper(), "airframe_model_in": r.airframe_model,
                   "engine_type_in": r.engine_type, "mtow_kg_in": r.mtow_kg}
            ver, ver_txt = self._verified_info(key["icao_type"])
            row = {**key, **res, "confidence": conf, "abs_delta_dep_db": abs(res["delta_dep_db"]),
                   "candidates_count": len(cands), "verified_data_available": ver, "verified_variants": ver_txt}
            row["delta_applied_db"] = res["delta_dep_db"] if self.policy.substitution_method == "A" else 0.0
            row["n_applied"] = res["n_dep"] if self.policy.substitution_method == "B" else 1.0
            row["substitution_method"] = self.policy.substitution_method
            usable = res["anp_acft_id"] is not None and np.isfinite(res["delta_dep_db"])
            row["usable_for_noise"] = bool(usable)
            if res["anp_acft_id"] is not None:
                a = self.anp.loc[res["anp_acft_id"]]
                for c in ANP_ATTRS:
                    row[f"anp_{c}" if c in ("description", "engine_type", "n_engines", "mtow_lb") else c] = a[c]
            row["a5_release_id"] = self.release_id
            out.append(row)
            for c in cands:
                cand_rows.append({**key, **c})
        mp = pd.DataFrame(out)
        cd = pd.DataFrame(cand_rows)
        return mp, cd

    def icao_reference(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Resolve every ICAO code known to EASA plus the analyst-proxy types, with the ICAO code only."""
        codes = sorted(set(self.icao.icao_code) | (set(self.analyst.index) if len(self.analyst) else set()))
        return self.resolve(pd.DataFrame({"icao_type": codes}))


def mapping_qc(mp: pd.DataFrame, anp_aircraft: pd.DataFrame, npd_ids: set[str], qc: QCRegistry, label: str) -> None:
    resolved = mp[mp.anp_acft_id.notna()]
    bad_acft = resolved[~resolved.anp_acft_id.isin(anp_aircraft.acft_id)]
    qc.check(f"mapping.{label}.anp_exists", "mapping", len(bad_acft), f"{label}: every mapped ANP aircraft exists in ANP 2.3",
             f"{label}: mapped ANP aircraft missing", details=str(bad_acft.icao_type.tolist()))
    bad_npd = resolved[~resolved.npd_id.isin(npd_ids)]
    qc.check(f"mapping.{label}.npd_exists", "mapping", len(bad_npd), f"{label}: every mapped aircraft has an NPD set",
             f"{label}: mapped aircraft without NPD", details=str(bad_npd.icao_type.tolist()))
    counts = mp.mapping_method.value_counts().to_dict()
    qc.add(f"mapping.{label}.coverage", "mapping", "INFO",
           f"{label}: {len(mp)} keys -> " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), len(mp))
    pend = mp[(mp.mapping_method == "ANALYST_PROXY") & ~mp.usable_for_noise]
    if len(pend):
        qc.add(f"mapping.{label}.pending_delta", "mapping", "UNRESOLVED",
               f"{label}: {len(pend)} analyst proxies await certified levels (Eq. 6-1); not usable until filled: "
               f"{pend.icao_type.tolist()}", len(pend))
    unres = mp[mp.mapping_method == "UNRESOLVED"]
    if len(unres):
        qc.add(f"mapping.{label}.unresolved", "mapping", "UNRESOLVED", f"{label}: {len(unres)} keys unresolved",
               len(unres), str(unres.icao_type.tolist()[:20]))
    big = mp[mp.abs_delta_dep_db >= 5]
    qc.add(f"mapping.{label}.large_delta", "mapping", "WARNING" if len(big) else "PASS",
           f"{label}: {len(big)} mappings with |delta_dep| >= 5 dB (Doc 29 Vol 1 note 2: proxy may be inappropriate)",
           len(big), str(big[["icao_type", "anp_acft_id", "delta_dep_db"]].values.tolist()[:20]))


def flight_weighted_coverage(mapping: pd.DataFrame, flights: pd.DataFrame, key: str = "icao_type") -> pd.DataFrame:
    """Coverage weighted by observed flights. flights: one row per flight with `key` (from A2/A3)."""
    f = flights.merge(mapping[[key, "mapping_method", "confidence", "usable_for_noise"]].drop_duplicates(key),
                      on=key, how="left")
    f["mapping_method"] = f.mapping_method.fillna("UNRESOLVED")
    f["confidence"] = f.confidence.fillna("NONE")
    f["usable_for_noise"] = f.usable_for_noise.fillna(False)
    return (f.groupby(["mapping_method", "confidence"]).size().rename("flights").reset_index()
            .assign(share=lambda x: x.flights / x.flights.sum()))
