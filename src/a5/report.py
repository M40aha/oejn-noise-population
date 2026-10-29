"""Generate the QC report and the data dictionary from the build outputs."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schemas import ANP_TABLES

ICON = {"PASS": "✅", "INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "UNRESOLVED": "❓"}

DERIVED_DESC = {
    ("anp_aircraft", "power_parameter_kind"): ("-", "Machine-readable power parameter: CNT_LB_PER_ENGINE | CNT_PCT_MAX_STATIC | RPM"),
    ("anp_aircraft", "has_jet_coefficients"): ("-", "Aircraft has jet thrust coefficients"),
    ("anp_aircraft", "has_hitemp_ratings"): ("-", "Aircraft has high-temperature thrust ratings (temperature breakpoint)"),
    ("anp_aircraft", "thrust_ratings"): ("-", "Available thrust ratings, '|' separated"),
    ("anp_aircraft", "has_departure_steps"): ("-", "Aircraft has procedural departure steps"),
    ("anp_aircraft", "departure_profiles"): ("-", "Available departure profile IDs, '|' separated"),
    ("anp_aircraft", "has_fixed_point_departure"): ("-", "Aircraft has fixed-point departure profiles"),
    ("anp_aircraft", "mtow_kg"): ("kg", "MTOW converted with the exact factor 0.45359237 (convenience only)"),
    ("anp_npd_long", "distance_ft"): ("ft", "NPD slant distance"),
    ("anp_npd_long", "level_db"): ("dB", "Noise level"),
    ("anp_npd_long", "source_column"): ("-", "Wide-format source column of this value"),
    ("anp_spectral_long", "frequency_hz"): ("Hz", "1/3-octave band centre frequency"),
    ("anp_spectral_long", "level_db"): ("dB", "Normalised band level"),
}

MAPPING_DESC = {
    "icao_type": "ICAO Doc 8643 type designator (input key)",
    "airframe_model_in": "Airframe model from the aircraft-identity input (optional)",
    "engine_type_in": "Engine type from the aircraft-identity input (optional)",
    "mtow_kg_in": "MTOW from the aircraft-identity input (optional)",
    "mapping_method": "Resolution rule applied (see methodology)",
    "anp_acft_id": "ANP aircraft used to model this type",
    "delta_dep_db": "Departure decibel adjustment of the proxy (Doc 29 Vol 1 Method A)",
    "delta_app_db": "Approach decibel adjustment (carried; departures study)",
    "n_dep": "Departure movement factor (Method B; valid for energy metrics only)",
    "n_app": "Approach movement factor (Method B)",
    "delta_applied_db": "Adjustment to add to proxy NPD levels under the configured method",
    "n_applied": "Movement multiplier under the configured method (1 for Method A)",
    "substitution_method": "A (dB on NPD, all metrics) or B (movement factor, energy metrics only)",
    "abs_delta_dep_db": "|delta_dep| (large values flag a weak proxy)",
    "confidence": "HIGH | MEDIUM | LOW | NONE (categorical, evidence-based)",
    "conservative_choice": "True when an unknown MTOW/engine was resolved with the Doc 29 conservative rule",
    "selected_airframe": "Certified configuration used (configuration-tab methods)",
    "selected_engine": "Certified engine used (configuration-tab methods)",
    "selected_mtow_kg": "Certified MTOW used (configuration-tab methods)",
    "candidates_count": "Number of candidate mappings considered (see mapping_candidates)",
    "evidence": "Human-readable justification",
    "source_ref": "File | sheet | row of the evidence",
    "review_status": "For analyst proxies: PENDING | REVIEWED",
    "notes": "Warnings, fallbacks and pending items",
    "verified_data_available": "EASA holds newer verified ANP data for this ICAO type",
    "verified_variants": "Verified airframe/engine variants",
    "usable_for_noise": "True when an ANP aircraft and a numeric delta exist",
    "npd_id": "NPD set of the ANP aircraft",
    "dep_spectral_class_id": "Departure spectral class",
    "lateral_directivity": "Wing | Fuselage | Prop (engine-installation correction)",
    "power_parameter": "NPD power parameter (as ANP)",
    "power_parameter_kind": "Machine-readable power parameter",
    "has_jet_coefficients": "ANP aircraft has jet thrust coefficients",
    "has_hitemp_ratings": "ANP aircraft has HiTemp thrust ratings",
    "thrust_ratings": "Available thrust ratings",
    "has_departure_steps": "ANP aircraft has procedural departure steps",
    "departure_profiles": "Available departure profiles",
    "anp_description": "ANP airframe/engine description",
    "anp_engine_type": "Jet | Turboprop | Piston",
    "anp_n_engines": "Number of engines of the ANP aircraft",
    "anp_mtow_lb": "ANP MTOW (lb)",
    "a5_release_id": "A5 release that produced this row",
}


def _table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_none_\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]).replace("|", "/").replace("\n", " ") for c in cols) + " |")
    return "\n".join(lines) + "\n"


def write_reports(root: Path, out: dict[str, pd.DataFrame], summary: dict, cfg: dict) -> None:
    qc = out["qc_results"]
    mp = out["aircraft_noise_mapping"]
    b2 = out["vol3_b2_npd_validation"]
    lines = [f"# A5 quality-control report — `{summary['release_id']}`", "",
             f"Built {summary['built_utc']} · Python {summary['python']} · pandas {summary['packages']['pandas']} · "
             f"duckdb {summary['packages']['duckdb']}", "", "## Summary", "",
             "| Severity | Checks |", "|---|---|"]
    for s, n in summary["qc_counts"].items():
        lines.append(f"| {ICON[s]} {s} | {n} |")
    lines += ["", f"**Doc 29 Vol 3 B-2 NPD validation:** {summary['vol3_b2_segments']} segments, "
              f"max |difference| = {summary['vol3_b2_max_abs_diff_db']:.2e} dB "
              f"(tolerance {cfg['tolerances']['vol3_b2_baseline_sel_max_abs_db']} dB).", ""]
    lines += ["## Sources", "", _table(out["sources"][["source_key", "file", "version", "sha256_matches_lock"]])]
    for cat in ["source", "structure", "normalisation", "integrity", "physics", "logic", "cross_source", "validation", "mapping"]:
        q = qc[qc.category == cat]
        if q.empty:
            continue
        q = q.assign(severity=q.severity.map(lambda s: f"{ICON[s]} {s}"))
        lines += [f"## {cat.replace('_', ' ').title()}", "", _table(q[["check_id", "severity", "message", "n_affected"]])]
    lines += ["## Mapping overview (ICAO-only resolution of every EASA code)", "",
              _table(mp.groupby(["mapping_method", "confidence"]).size().rename("types").reset_index()),
              "### Types needing attention", "",
              _table(mp[mp.mapping_method.isin(["EASA_ICAO_AMBIGUOUS", "ANALYST_PROXY", "UNRESOLVED"]) | (mp.abs_delta_dep_db >= 5)]
                     [["icao_type", "mapping_method", "anp_acft_id", "delta_dep_db", "confidence", "notes"]])]
    lines += ["## Details of non-PASS checks", ""]
    for _, r in qc[~qc.severity.isin(["PASS"]) & (qc.details.astype(str) != "")].iterrows():
        lines += [f"- **{r.check_id}** ({r.severity}): `{str(r.details)[:600]}`"]
    (root / "data" / "a5" / "validation" / "qc_report.md").write_text("\n".join(lines) + "\n")

    # data dictionary
    dd = ["# A5 data dictionary", "",
          "Units are **native ANP units** unless stated. See `units_registry` for SI factors. "
          "Every ANP-derived row carries `src_file`, `src_member`, `src_row` (provenance).", ""]
    for name, spec in ANP_TABLES.items():
        dd += [f"## `{name}`" + (" (carried, not used for OEJN departures)" if spec.get("carried_only") else ""),
               f"Source: `{spec['member']}` · key: {spec['key']} · rows: {len(out[name])}", "",
               "| column | type | unit | description | source header |", "|---|---|---|---|---|"]
        for src, canon, kind, unit, desc in spec["columns"]:
            dd.append(f"| {canon} | {kind} | {unit} | {desc} | {src} |")
        for (tbl, col), (unit, desc) in DERIVED_DESC.items():
            if tbl == name:
                dd.append(f"| {col} | derived | {unit} | {desc} | (derived) |")
        dd.append("")
    for name in ("anp_npd_long", "anp_spectral_long"):
        dd += [f"## `{name}`", f"Tidy reshape of the wide table; rows: {len(out[name])}", "",
               "| column | unit | description |", "|---|---|---|"]
        for (tbl, col), (unit, desc) in DERIVED_DESC.items():
            if tbl == name:
                dd.append(f"| {col} | {unit} | {desc} |")
        dd.append("")
    dd += ["## `aircraft_noise_mapping` (integration contract: aircraft identity → A5 → noise model)", "",
           "| column | description |", "|---|---|"]
    for c in mp.columns:
        dd.append(f"| {c} | {MAPPING_DESC.get(c, '')} |")
    dd += ["", "## Other tables", ""]
    for name in ("mapping_candidates", "mapping_analyst_proxies", "easa_subst_icao", "easa_subst_config", "easa_verified_types",
                 "doc29_constants", "doc29_table_d1", "units_registry", "normalization_log", "sources", "qc_results",
                 "vol3_b2_npd_validation", "vol3_fixture_aircraft", "vol3_fixture_jet_coefficients", "vol3_fixture_npd",
                 "vol3_fixture_spectral"):
        dd.append(f"- `{name}` — {len(out[name])} rows; columns: {', '.join(map(str, out[name].columns))}")
    (root / "docs" / "a5" / "data_dictionary.md").write_text("\n".join(dd) + "\n")
