"""Doc 29 Vol 3 reference material: schema fixtures and executable validation.

Vol 3 aircraft (JETF, JETW, PROP) are hypothetical, so they validate the A5
REPRESENTATION and CODE, never the ANP 2.3 values themselves.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .constants import NPD_DISTANCES_FT, NPD_LEVEL_COLUMNS, FT_TO_M, NMI_TO_M
from .ingest import read_xlsx_sheet
from .anp_checks import npd_long
from .npd import NPDLookup, NPDPolicy
from .qc import QCRegistry

# Vol 3 header -> A5 canonical column (same meaning, Vol 3 spelling differs)
CROSSWALK = {
    "A-1_Aircraft": {
        "Aircraft Identifier": "acft_id", "Description": "description", "Engine Type": "engine_type",
        "Number of Engines": "n_engines", "Weight Class": "weight_class",
        "Maximum Gross Takeoff Weight (lb)": "mtow_lb", "Maximum Gross Landing Weight (lb)": "mlw_lb",
        "Maximum Landing Distance (ft)": "max_landing_distance_ft", "Maximum Sea Level Static Thrust (lb)": "max_static_thrust_lb",
        "NPD Identifier": "npd_id", "Power Parameter": "power_parameter",
        "Approach Spectral Class Identifier": "app_spectral_class_id",
        "Departure Spectral Class Identifier": "dep_spectral_class_id",
        "Lateral Directivity Identifier": "lateral_directivity",
    },
    "A-2_Jet_Coefficients": {
        "Aircraft Identifier": "acft_id", "Thurst Rating": "thrust_rating", "E (lb)": "E", "F (lb/kt)": "F",
        "Ga (lb/ft)": "Ga", "Gb (lb/ft2)": "Gb", "H (lb/degC)": "H", "K1 (lb/EPR)": "K1", "K2 (lb/EPR2)": "K2",
        "K3 (lb/(N1/sqrt(theta)))": "K3", "K4 (lb/(N1/sqrt(theta))2)": "K4",
    },
    "A-7_NPD_Curves": {
        "Aircraft Identifier": "npd_id", "Noise Descriptor": "noise_metric", "Operation Mode": "op_mode",
        "Power Setting (lb)": "power_setting",
        **{f"L_{int(d)} (ft)": c for d, c in zip(NPD_DISTANCES_FT, NPD_LEVEL_COLUMNS)},
    },
    "A-8_Spectral_Class": {
        "Spectral Class Identifier": "spectral_class_id", "Operation Mode": "op_type", "Description": "description",
    },
}

NUMERIC_NA = {"n/a", "N/A", "", None}


def _apply_crosswalk(df: pd.DataFrame, sheet: str, qc: QCRegistry) -> pd.DataFrame:
    cw = CROSSWALK[sheet]
    data_cols = [c for c in df.columns if c not in ("src_file", "src_member", "src_row")]
    passthrough = [c for c in data_cols if c.startswith("L_") and c.endswith("Hz")]  # spectral bands already canonical
    unmapped = [c for c in data_cols if c not in cw and c not in passthrough]
    qc.add(f"validation.vol3_fixture.{sheet}", "validation", "PASS" if not unmapped else "WARNING",
           f"Vol 3 {sheet}: {len(data_cols) - len(unmapped)}/{len(data_cols)} columns map onto the A5 canonical schema"
           + (f"; unmapped: {unmapped}" if unmapped else ""), len(unmapped))
    out = df.rename(columns=cw)
    return out.replace({v: np.nan for v in NUMERIC_NA if v is not None})


def load_fixtures(wb1: Path, qc: QCRegistry) -> dict[str, pd.DataFrame]:
    fx = {}
    for sheet in CROSSWALK:
        fx[sheet] = _apply_crosswalk(read_xlsx_sheet(wb1, sheet), sheet, qc)
    # Aerodynamic sheet: Vol 3 merges C and D into one 'C/D' column; ANP 2.3 keeps them separate.
    aero = read_xlsx_sheet(wb1, "A-4_Aerodynamic_Coefficients")
    qc.add("validation.vol3_fixture.A-4_Aerodynamic_Coefficients", "validation", "INFO",
           "Vol 3 A-4 stores take-off C and landing D in one 'C/D' column; ANP 2.3 stores C and D separately. "
           "A5 keeps the ANP layout; a Vol 3 loader must split C/D by operation type (D->C, A->D).", 1,
           str([c for c in aero.columns if c not in ("src_file", "src_member", "src_row")]))
    fx["A-4_Aerodynamic_Coefficients"] = aero
    return fx


def validate_npd_against_b2(wb1: Path, fixtures: dict[str, pd.DataFrame], policy: NPDPolicy,
                            tol_max: float, tol_target: float, qc: QCRegistry) -> pd.DataFrame:
    """Reproduce Vol 3 B-2 'baseline_SEL' from NPD_interpolation_distance/thrust using Vol 3's own NPD table."""
    npd = fixtures["A-7_NPD_Curves"].copy()
    npd["power_setting"] = npd["power_setting"].astype(float)
    for c in NPD_LEVEL_COLUMNS:
        npd[c] = npd[c].astype(float)
    lk = NPDLookup(npd_long(npd), policy)

    b2 = read_xlsx_sheet(wb1, "B-2_Segment_Results")
    b2 = b2.rename(columns={"NPD_interpolation_distance(ft)": "d_ft", "NPD_interpolation_thrust(lb/e)": "p_lb",
                            "baseline_SEL(dB)": "ref_sel"})
    b2["acft"] = b2.case_ID.str[:4]
    b2["op_mode"] = b2.case_ID.str[4]
    out = []
    for (acft, mode), g in b2.groupby(["acft", "op_mode"]):
        r = lk.lookup(acft, "SEL", mode, g.p_lb.astype(float).to_numpy(), g.d_ft.astype(float).to_numpy())
        gg = g[["src_row", "case_ID", "receptor_ID", "segment_ID", "d_ft", "p_lb", "ref_sel"]].copy()
        gg["a5_sel"] = r.level_db.to_numpy()
        gg["power_extrapolated"] = r.power_extrapolated.to_numpy()
        gg["distance_extrapolated"] = r.distance_extrapolated.to_numpy()
        gg["distance_floored"] = r.distance_floored.to_numpy()
        out.append(gg)
    res = pd.concat(out, ignore_index=True)
    res["abs_diff_db"] = (res.a5_sel - res.ref_sel.astype(float)).abs()
    mx = float(res.abs_diff_db.max())
    rms = float(np.sqrt((res.abs_diff_db ** 2).mean()))
    n_over = int((res.abs_diff_db > tol_max).sum())
    sev = "ERROR" if n_over else ("WARNING" if mx > tol_target else "PASS")
    qc.add("validation.vol3_b2_baseline_sel", "validation", sev,
           f"NPD lookup reproduces Vol 3 B-2 baseline_SEL for {len(res)} segments: max |diff| = {mx:.2e} dB, "
           f"RMS = {rms:.2e} dB (ERROR > {tol_max} dB, target <= {tol_target} dB). Includes "
           f"{int(res.distance_extrapolated.sum())} distance-extrapolated and {int(res.power_extrapolated.sum())} "
           f"power-extrapolated lookups.", n_over)
    return res


def validate_unit_constants(wb1: Path, tol_rel: float, qc: QCRegistry) -> None:
    """Vol 3 gives coordinates in both nmi and m (and ft and m): check the exact conversion factors reproduce them."""
    worst = 0.0
    n = 0
    rec = read_xlsx_sheet(wb1, "A-12_Receptors")
    for a, b, f in (("X coordinate (nmi)", "X coordinate (m)", NMI_TO_M), ("Y coordinate (nmi)", "Y coordinate (m)", NMI_TO_M),
                    ("Height (ft)", "Height (m)", FT_TO_M)):
        x, y = rec[a].astype(float).to_numpy(), rec[b].astype(float).to_numpy()
        nz = y != 0
        if nz.any():
            worst = max(worst, float(np.max(np.abs(x[nz] * f - y[nz]) / np.abs(y[nz]))))
        n += len(x)
    sev = "PASS" if worst <= tol_rel else "WARNING"
    qc.add("validation.unit_constants_vs_vol3", "validation", sev,
           f"Exact unit constants reproduce Vol 3 metric/imperial receptor coordinates: worst relative difference {worst:.1e} "
           f"over {n} values (tolerance {tol_rel:.0e}).", 0 if sev == "PASS" else 1)
