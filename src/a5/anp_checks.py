"""Referential, physical and logical checks on the ANP tables, plus tidy (long) reshapes."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import (LB_TO_KG, NPD_DISTANCES_FT, NPD_LEVEL_COLUMNS, SPECTRAL_BANDS_HZ,
                        SPECTRAL_LEVEL_COLUMNS, SPECTRAL_NORMALISATION_DB)
from .qc import QCRegistry
from .schemas import POWER_PARAMETER_KIND


def _missing_fk(child: pd.DataFrame, child_cols, parent: pd.DataFrame, parent_cols) -> pd.DataFrame:
    left = child[child_cols].dropna().drop_duplicates()
    right = parent[parent_cols].drop_duplicates()
    right.columns = child_cols
    m = left.merge(right, how="left", on=child_cols, indicator=True)
    return m[m["_merge"] == "left_only"][child_cols]


def referential_integrity(t: dict[str, pd.DataFrame], qc: QCRegistry) -> None:
    ac = t["anp_aircraft"]
    fks = [
        ("aircraft.npd_id->npd", ac, ["npd_id"], t["anp_npd_wide"], ["npd_id"]),
        ("aircraft.dep_spectral->spectral", ac, ["dep_spectral_class_id"], t["anp_spectral_wide"], ["spectral_class_id"]),
        ("aircraft.app_spectral->spectral", ac, ["app_spectral_class_id"], t["anp_spectral_wide"], ["spectral_class_id"]),
        ("dep_steps.acft->aircraft", t["anp_departure_steps"], ["acft_id"], ac, ["acft_id"]),
        ("dep_steps.flap->aero(D)", t["anp_departure_steps"], ["acft_id", "flap_id"],
         t["anp_aero_coefficients"].query("op_type == 'D'"), ["acft_id", "flap_id"]),
        ("dep_steps.stage->weights", t["anp_departure_steps"], ["acft_id", "stage_length"],
         t["anp_default_weights"], ["acft_id", "stage_length"]),
        ("jet_coeffs.acft->aircraft", t["anp_jet_coefficients"], ["acft_id"], ac, ["acft_id"]),
        ("prop_coeffs.acft->aircraft", t["anp_propeller_coefficients"], ["acft_id"], ac, ["acft_id"]),
        ("aero.acft->aircraft", t["anp_aero_coefficients"], ["acft_id"], ac, ["acft_id"]),
        ("weights.acft->aircraft", t["anp_default_weights"], ["acft_id"], ac, ["acft_id"]),
        ("fixed_point.acft->aircraft", t["anp_fixed_point_profiles"], ["acft_id"], ac, ["acft_id"]),
        ("app_steps.acft->aircraft", t["anp_approach_steps"], ["acft_id"], ac, ["acft_id"]),
    ]
    for name, child, cc, parent, pc in fks:
        miss = _missing_fk(child, cc, parent, pc)
        qc.check(f"integrity.{name}", "integrity", len(miss), f"{name}: every reference resolves",
                 f"{name}: unresolved references", details=str(miss.head(10).values.tolist()))

    # departure steps that are jets must find their thrust rating in jet coefficients
    jets = set(ac.loc[ac.engine_type == "Jet", "acft_id"])
    dj = t["anp_departure_steps"][t["anp_departure_steps"].acft_id.isin(jets)]
    miss = _missing_fk(dj, ["acft_id", "thrust_rating"], t["anp_jet_coefficients"], ["acft_id", "thrust_rating"])
    qc.check("integrity.dep_steps.thrust_rating->jet_coeffs", "integrity", len(miss),
             "Every jet departure step's thrust rating has engine coefficients",
             "Jet departure steps reference thrust ratings without coefficients", details=str(miss.head(10).values.tolist()))

    # departure spectral IDs must be of Departure type
    sp = t["anp_spectral_wide"].set_index("spectral_class_id")["op_type"]
    wrong = ac[ac.dep_spectral_class_id.map(sp) != "Departure"]
    qc.check("integrity.dep_spectral_type", "integrity", len(wrong),
             "Every departure spectral class is of Departure type", "Departure spectral class of wrong type",
             details=str(wrong.acft_id.tolist()))

    # NPD sets that nobody uses
    unused = set(t["anp_npd_wide"].npd_id) - set(ac.npd_id)
    qc.check("integrity.npd_unused", "integrity", len(unused), "Every NPD set is used by at least one aircraft",
             "NPD sets not referenced by any aircraft", "INFO", str(sorted(unused)))

    # aircraft sharing an NPD set must share the power parameter
    g = ac.groupby("npd_id")["power_parameter"].nunique()
    qc.check("integrity.npd_power_parameter_consistent", "integrity", int((g > 1).sum()),
             f"All aircraft sharing an NPD set ({int((ac.npd_id.value_counts() > 1).sum())} shared sets) use the same power parameter",
             "Aircraft sharing an NPD set disagree on the power parameter", details=str(g[g > 1].index.tolist()))

    # coverage facts (informational, not errors)
    no_jet = sorted(jets - set(t["anp_jet_coefficients"].acft_id))
    qc.add("integrity.jets_without_jet_coefficients", "integrity", "INFO",
           f"{len(no_jet)} legacy jets have no jet coefficients (they use fixed-point profiles)", len(no_jet), str(no_jet))
    no_dep = sorted(set(ac.acft_id) - set(t["anp_departure_steps"].acft_id))
    qc.add("integrity.aircraft_without_departure_steps", "integrity", "INFO",
           f"{len(no_dep)} aircraft have no procedural departure steps", len(no_dep), str(no_dep))


def physics_and_logic(t: dict[str, pd.DataFrame], qc: QCRegistry) -> None:
    npd = t["anp_npd_wide"]
    L = npd[list(NPD_LEVEL_COLUMNS)].to_numpy()

    qc.check("physics.npd_complete", "physics", int(np.isnan(L).sum()),
             "NPD: no missing level at any of the 10 distances", "NPD: missing levels")
    rng_bad = int(((L < 0) | (L > 160)).sum())
    qc.check("physics.npd_range", "physics", rng_bad, "NPD: all levels within 0-160 dB", "NPD: implausible levels")
    qc.check("physics.npd_power_positive", "physics", int((npd.power_setting <= 0).sum()),
             "NPD: all power settings > 0", "NPD: non-positive power settings")

    dec_bad = (np.diff(L, axis=1) >= 0).any(axis=1)
    qc.check("physics.npd_decreasing_with_distance", "physics", int(dec_bad.sum()),
             "NPD: level strictly decreases with distance on every curve",
             "NPD: curves not strictly decreasing with distance",
             details=str(npd.loc[dec_bad, ["npd_id", "noise_metric", "op_mode", "power_setting"]].head(10).values.tolist()))

    fam = npd.groupby(["npd_id", "noise_metric", "op_mode"])
    nonmono, counts = [], fam.size()
    for k, g in fam:
        g = g.sort_values("power_setting")
        if (np.diff(g[list(NPD_LEVEL_COLUMNS)].to_numpy(), axis=0) < 0).any():
            nonmono.append(k)
    dep_core = [k for k in nonmono if k[2] == "D" and k[1] in ("SEL", "LAmax")]
    qc.add("physics.npd_monotonic_in_power", "physics", "WARNING" if nonmono else "PASS",
           f"NPD: level decreases with increasing power somewhere in {len(nonmono)} of {len(counts)} curve families "
           f"({len(dep_core)} are departure SEL/LAmax). Not an error by itself: the ANP 2.3 release note documents deliberate "
           "non-monotonic patterns (e.g. ATR72). Doc 29 interpolation handles them linearly as tabulated.",
           len(nonmono), f"departure SEL/LAmax families: {dep_core}")
    two = counts[counts == 2]
    qc.add("physics.npd_power_points", "physics", "INFO",
           f"NPD: {len(two)} of {len(counts)} curve families have only 2 power settings (extrapolation more likely)",
           len(two), str(counts.value_counts().sort_index().to_dict()))

    # SEL vs LAmax (same NPD, mode, power): SEL < LAmax is only plausible at very short distance
    s = npd[npd.noise_metric == "SEL"].set_index(["npd_id", "op_mode", "power_setting"])[list(NPD_LEVEL_COLUMNS)]
    m = npd[npd.noise_metric == "LAmax"].set_index(["npd_id", "op_mode", "power_setting"])[list(NPD_LEVEL_COLUMNS)]
    j = s.join(m, lsuffix="_sel", rsuffix="_lmax", how="inner")
    diff = pd.DataFrame(j[[c + "_sel" for c in NPD_LEVEL_COLUMNS]].to_numpy() - j[[c + "_lmax" for c in NPD_LEVEL_COLUMNS]].to_numpy(),
                        index=j.index, columns=NPD_LEVEL_COLUMNS)
    neg = diff < 0
    beyond_200 = int(neg.drop(columns=["L_200ft"]).any(axis=1).sum())
    qc.add("physics.sel_vs_lamax", "physics", "WARNING" if beyond_200 else "INFO",
           f"SEL < LAmax in {int(neg.any(axis=1).sum())} curve pairs; {int(neg['L_200ft'].sum())} at 200 ft "
           f"(plausible: effective event duration < 1 s at very short range) and {beyond_200} pairs at > 200 ft",
           int(neg.any(axis=1).sum()),
           str([(k, {c: round(float(diff.loc[k, c]), 2) for c in NPD_LEVEL_COLUMNS if diff.loc[k, c] < 0})
                for k in neg.drop(columns=["L_200ft"]).any(axis=1)[lambda s: s].index]))

    # spectral classes normalised to 70 dB at 1 kHz
    sp = t["anp_spectral_wide"]
    bad = sp[~np.isclose(sp["L_1000Hz"], SPECTRAL_NORMALISATION_DB, atol=0)]
    qc.check("physics.spectral_normalisation", "physics", len(bad),
             "Every spectral class equals 70.0 dB at 1 kHz (normalised spectra)", "Spectral classes not normalised at 1 kHz",
             details=str(bad.spectral_class_id.tolist()))
    S = sp[list(SPECTRAL_LEVEL_COLUMNS)].to_numpy()
    qc.check("physics.spectral_complete", "physics", int(np.isnan(S).sum()), "Spectral: all 24 bands present", "Spectral: missing bands")

    # departure procedural logic
    dep = t["anp_departure_steps"]
    grp = dep.sort_values("step_number").groupby(["acft_id", "profile_id", "stage_length"])
    noncontig = grp["step_number"].apply(lambda s: list(s) != list(range(1, len(s) + 1)))
    qc.check("logic.dep_steps_contiguous", "logic", int(noncontig.sum()),
             f"All {len(noncontig)} departure profiles have contiguous step numbers 1..n",
             "Departure profiles with gaps in step numbers", details=str(noncontig[noncontig].index.tolist()[:10]))
    first = grp["step_type"].first()
    qc.check("logic.dep_steps_start_takeoff", "logic", int((first != "Takeoff").sum()),
             "Every departure profile starts with a Takeoff step", "Profiles not starting with Takeoff")
    climb_no_alt = dep[(dep.step_type == "Climb") & dep.end_altitude_ft.isna()]
    qc.check("logic.climb_has_end_altitude", "logic", len(climb_no_alt), "Every Climb step has an end altitude",
             "Climb steps without end altitude")
    acc = dep[dep.step_type == "Accelerate"]
    acc_bad = acc[acc.end_cas_kt.isna() | (acc.rate_of_climb_ftmin.isna() & acc.accel_percentage.isna())]
    qc.check("logic.accelerate_complete", "logic", len(acc_bad),
             "Every Accelerate step has an end CAS and a rate of climb or acceleration percentage",
             "Accelerate steps missing CAS or climb/acceleration parameter")
    # climb end altitudes must not decrease within a profile
    def _alt_drop(g):
        a = g.sort_values("step_number").end_altitude_ft.dropna().to_numpy()
        return bool((np.diff(a) < 0).any())
    drops = grp.apply(_alt_drop)
    qc.check("logic.climb_altitudes_non_decreasing", "logic", int(drops.sum()),
             "Climb end altitudes never decrease within a profile", "Profiles whose climb altitudes decrease",
             "WARNING", str(drops[drops].index.tolist()[:10]))

    # take-off flap configurations need B and C (ground roll and take-off speed)
    aero = t["anp_aero_coefficients"].query("op_type == 'D'")
    to = dep[dep.step_type == "Takeoff"][["acft_id", "flap_id"]].drop_duplicates()
    m2 = to.merge(aero, on=["acft_id", "flap_id"], how="left")
    bad = m2[m2.B.isna() | m2.C.isna()]
    qc.check("logic.takeoff_flaps_have_B_C", "logic", len(bad),
             "Every take-off flap configuration has coefficients B and C",
             "Take-off flap configurations without B or C", details=str(bad[["acft_id", "flap_id"]].values.tolist()[:10]))
    qc.check("logic.aero_R_present", "logic", int(t["anp_aero_coefficients"].R.isna().sum()),
             "Every aerodynamic configuration has R", "Aerodynamic rows without R")

    # stage length 'M' meaning (documented, not assumed): compare with MTOW
    w = t["anp_default_weights"]
    mw = w[w.stage_length == "M"].merge(t["anp_aircraft"][["acft_id", "mtow_lb"]], on="acft_id")
    mw["ratio"] = mw.weight_lb / mw.mtow_lb
    qc.add("logic.stage_length_M", "logic", "INFO",
           f"Stage length 'M' appears for {len(mw)} aircraft; its weight / MTOW ranges "
           f"{mw.ratio.min():.3f}-{mw.ratio.max():.3f}. Interpreted as a maximum-weight profile, kept as category 'M'.",
           len(mw), str(mw[["acft_id", "weight_lb", "mtow_lb"]].values.tolist()))
    over = w.merge(t["anp_aircraft"][["acft_id", "mtow_lb"]], on="acft_id")
    over = over[over.weight_lb > over.mtow_lb + 0.5]
    # A genuine inconsistency INSIDE the ANP 2.3 source. A5 preserves the values unchanged (no silent capping);
    # the noise-model stage must not use these stage lengths, or must cap them explicitly and document it.
    qc.check("physics.default_weight_le_mtow", "physics", len(over), "No default take-off weight exceeds MTOW",
             f"ANP 2.3 source inconsistency: {len(over)} default stage-length weights exceed the aircraft's own tabulated MTOW "
             "(values preserved unchanged; do not use these stage lengths without an explicit, documented cap)",
             "WARNING", str(over[["acft_id", "stage_length", "weight_lb", "mtow_lb"]].values.tolist()))
    ac = t["anp_aircraft"]
    qc.check("physics.mlw_le_mtow", "physics", int((ac.mlw_lb > ac.mtow_lb).sum()), "MLW <= MTOW for all aircraft", "MLW above MTOW")


def npd_long(npd_wide: pd.DataFrame) -> pd.DataFrame:
    keep = ["npd_id", "noise_metric", "op_mode", "power_setting", "src_file", "src_member", "src_row"]
    long = npd_wide.melt(id_vars=keep, value_vars=list(NPD_LEVEL_COLUMNS), var_name="level_column", value_name="level_db")
    dist = dict(zip(NPD_LEVEL_COLUMNS, NPD_DISTANCES_FT))
    long.insert(4, "distance_ft", long.pop("level_column").map(dist))
    long["source_column"] = long["distance_ft"].map({v: k for k, v in dist.items()})
    return long.sort_values(["npd_id", "noise_metric", "op_mode", "power_setting", "distance_ft"]).reset_index(drop=True)


def spectral_long(sp_wide: pd.DataFrame) -> pd.DataFrame:
    keep = ["spectral_class_id", "op_type", "description", "src_file", "src_member", "src_row"]
    long = sp_wide.melt(id_vars=keep, value_vars=list(SPECTRAL_LEVEL_COLUMNS), var_name="band", value_name="level_db")
    long.insert(3, "frequency_hz", long.pop("band").map(dict(zip(SPECTRAL_LEVEL_COLUMNS, SPECTRAL_BANDS_HZ))).astype(int))
    return long.sort_values(["spectral_class_id", "frequency_hz"]).reset_index(drop=True)


def roundtrip_checks(t: dict[str, pd.DataFrame], qc: QCRegistry) -> None:
    w = t["anp_npd_wide"].set_index(["npd_id", "noise_metric", "op_mode", "power_setting"])[list(NPD_LEVEL_COLUMNS)]
    back = (t["anp_npd_long"].pivot_table(index=["npd_id", "noise_metric", "op_mode", "power_setting"],
                                          columns="source_column", values="level_db", aggfunc="first")[list(NPD_LEVEL_COLUMNS)])
    back = back.loc[w.index]
    n_bad = int((back.to_numpy() != w.to_numpy()).sum())
    qc.check("structure.npd_long_roundtrip", "structure", n_bad,
             f"NPD long -> wide reproduces all {w.size} source values exactly", "NPD long/wide round-trip differences")
    sw = t["anp_spectral_wide"].set_index("spectral_class_id")[list(SPECTRAL_LEVEL_COLUMNS)]
    sb = t["anp_spectral_long"].pivot(index="spectral_class_id", columns="frequency_hz", values="level_db")
    sb.columns = [f"L_{c}Hz" for c in sb.columns]
    n_bad = int((sb.loc[sw.index, list(SPECTRAL_LEVEL_COLUMNS)].to_numpy() != sw.to_numpy()).sum())
    qc.check("structure.spectral_long_roundtrip", "structure", n_bad,
             f"Spectral long -> wide reproduces all {sw.size} source values exactly", "Spectral round-trip differences")


def aircraft_derived(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    ac = t["anp_aircraft"].copy()
    jet = t["anp_jet_coefficients"]
    ac["power_parameter_kind"] = ac.power_parameter.map(POWER_PARAMETER_KIND).astype("string")
    ac["has_jet_coefficients"] = ac.acft_id.isin(jet.acft_id)
    ac["has_hitemp_ratings"] = ac.acft_id.isin(jet.loc[jet.thrust_rating.str.contains("HiTemp"), "acft_id"])
    ac["thrust_ratings"] = ac.acft_id.map(jet.groupby("acft_id").thrust_rating.apply(lambda s: "|".join(sorted(s)))).astype("string")
    dep = t["anp_departure_steps"]
    ac["has_departure_steps"] = ac.acft_id.isin(dep.acft_id)
    ac["departure_profiles"] = ac.acft_id.map(dep.groupby("acft_id").profile_id.apply(lambda s: "|".join(sorted(set(s))))).astype("string")
    fpp = t["anp_fixed_point_profiles"]
    ac["has_fixed_point_departure"] = ac.acft_id.isin(fpp.loc[fpp.op_type == "D", "acft_id"])
    ac["mtow_kg"] = ac.mtow_lb * LB_TO_KG
    return ac
