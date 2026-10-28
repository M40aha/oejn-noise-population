"""Independent verification of the A5 outputs.

This script does NOT import anything from src/a5. It reads the ORIGINAL files in A5/ directly,
re-implements the Doc 29 NPD equations in a different way, and compares against the A5 outputs.

Run from the repository root:
    python scripts/verify_a5_independent.py  [path/to/A5]      (default: ../OEJN-Noise-Fuel-Capacity/A5)
"""
import hashlib
import io
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../OEJN-Noise-Fuel-Capacity/A5")
OUT = Path("data/a5/processed")
VAL = Path("data/a5/validation")
results = []


def report(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def sheet(path, name, header=1):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = [r for r in wb[name].iter_rows(values_only=True)]
    wb.close()
    hdr = [str(h).strip() if h is not None else f"c{i}" for i, h in enumerate(rows[header - 1])]
    body = [r for r in rows[header:] if r and any(c is not None for c in r)]
    return pd.DataFrame(body, columns=hdr)


# 1. raw files unchanged ---------------------------------------------------------------
expected = {
    "easa_anp_legacy_v2.3_tables.zip": "6147f05ea50f57df816ad2bbf8a1e870bcc74f253fb32bfeea5f468ea85d852f",
    "easa_anp_aircraft_substitutions.xlsx": "2691383eecae1bafb9995e315da1a817dc57c3f0390251ed403396784cd54ac2",
    "ecac_doc29_5e_vol3_workbook_part1.xlsx": "59cdb927840168ffab446e7d29c62973346abd87b2e881326d3f7ad058beddc3",
}
for f, h in expected.items():
    got = hashlib.sha256((RAW / f).read_bytes()).hexdigest()
    report(f"sha256 {f}", got == h, got[:16] + "…")

# 2. every ANP NPD value in A5 equals the raw CSV -------------------------------------
with zipfile.ZipFile(RAW / "easa_anp_legacy_v2.3_tables.zip") as z:
    def csv(m):
        return pd.read_csv(io.StringIO(z.read(m).decode("utf-8")), sep=";")
    raw_npd = csv("ANP2.3_NPD_data.csv")
    raw_ac = csv("ANP2.3_Aircraft.csv")
    raw_w = csv("ANP2.3_Default_weights.csv")
dist = [200, 400, 630, 1000, 2000, 4000, 6300, 10000, 16000, 25000]
raw_long = raw_npd.melt(id_vars=["NPD_ID", "Noise Metric", "Op Mode", "Power Setting"],
                        value_vars=[f"L_{d}ft" for d in dist], var_name="col", value_name="raw")
raw_long["distance_ft"] = raw_long.col.str.extract(r"L_(\d+)ft")[0].astype(float)
a5 = pd.read_parquet(OUT / "anp_npd_long.parquet")
m = raw_long.merge(a5, left_on=["NPD_ID", "Noise Metric", "Op Mode", "Power Setting", "distance_ft"],
                   right_on=["npd_id", "noise_metric", "op_mode", "power_setting", "distance_ft"], how="outer", indicator=True)
report("NPD: same number of points", len(a5) == len(raw_long), f"{len(a5)} vs {len(raw_long)}")
report("NPD: every point matched, none extra", (m._merge == "both").all())
report("NPD: every value identical to raw CSV", bool((m.raw == m.level_db).all()))

ac5 = pd.read_parquet(OUT / "anp_aircraft.parquet")
j = raw_ac.merge(ac5, left_on="ACFT_ID", right_on="acft_id")
report("Aircraft: 155 rows, NPD_ID and spectral classes identical",
       len(j) == 155 and (j.NPD_ID == j.npd_id).all() and (j["Departure Spectral Class ID"] == j.dep_spectral_class_id).all())

# 3. independent Doc 29 NPD interpolation vs Vol 3 B-2 ----------------------------------
def npd_level(curve: pd.DataFrame, P: float, d: float) -> float:
    """curve: rows = powers, columns = 10 distances. Eq. 4-3/4-4/4-5 written from scratch."""
    powers = curve.index.to_numpy(float)
    xs = [math.log10(x) for x in dist]
    lx = math.log10(max(d, 30 / 0.3048))

    def along_distance(levels):
        k = 0 if lx < xs[1] else (len(xs) - 2 if lx >= xs[-2] else max(i for i in range(len(xs) - 1) if xs[i] <= lx))
        return levels[k] + (levels[k + 1] - levels[k]) * (lx - xs[k]) / (xs[k + 1] - xs[k])

    Ld = [along_distance(curve.loc[p].to_numpy(float)) for p in powers]
    P = max(P, 1.0)
    k = 0 if P < powers[1] else (len(powers) - 2 if P >= powers[-2] else max(i for i in range(len(powers) - 1) if powers[i] <= P))
    return Ld[k] + (Ld[k + 1] - Ld[k]) * (P - powers[k]) / (powers[k + 1] - powers[k])


wb1 = RAW / "ecac_doc29_5e_vol3_workbook_part1.xlsx"
a7 = sheet(wb1, "A-7_NPD_Curves")
b2 = sheet(wb1, "B-2_Segment_Results")
lcols = [c for c in a7.columns if c.startswith("L_")]
diffs = []
for _, r in b2.iterrows():
    acft, mode = r["case_ID"][:4], r["case_ID"][4]
    c = a7[(a7["Aircraft Identifier"] == acft) & (a7["Noise Descriptor"] == "SEL") & (a7["Operation Mode"] == mode)]
    curve = c.set_index("Power Setting (lb)")[lcols].sort_index()
    diffs.append(abs(npd_level(curve, float(r["NPD_interpolation_thrust(lb/e)"]),
                               float(r["NPD_interpolation_distance(ft)"])) - float(r["baseline_SEL(dB)"])))
report("Vol 3 B-2: independent implementation reproduces baseline_SEL", max(diffs) < 0.01,
       f"{len(diffs)} segments, max |diff| = {max(diffs):.2e} dB")
a5b2 = pd.read_parquet(VAL / "vol3_b2_npd_validation.parquet")
report("Vol 3 B-2: A5 result agrees with the independent one",
       len(a5b2) == len(diffs) and a5b2.abs_diff_db.max() < 0.01, f"A5 max |diff| = {a5b2.abs_diff_db.max():.2e} dB")

# 4. mapping spot checks against the EASA workbook read directly ------------------------
icao = sheet(RAW / "easa_anp_aircraft_substitutions.xlsx", "by ICAO code")
mp = pd.read_parquet(OUT / "aircraft_noise_mapping.parquet")
bad = []
for _, r in mp[mp.mapping_method.isin(["EASA_ICAO", "EASA_ICAO_AMBIGUOUS"])].iterrows():
    rows = icao[(icao.ICAO_CODE == r.icao_type) & (icao.ANP_PROXY == r.anp_acft_id)]
    if rows.empty or not np.isclose(rows.DELTA_DEP_dB.iloc[0], r.delta_dep_db):
        bad.append(r.icao_type)
report("Mapping: every EASA-ICAO proxy and delta equals the workbook", not bad, f"mismatches: {bad[:10]}")
single = icao.groupby("ICAO_CODE").size()
amb = mp[mp.mapping_method == "EASA_ICAO_AMBIGUOUS"]
report("Mapping: AMBIGUOUS used exactly for codes with several variants",
       set(amb.icao_type) == set(single[single > 1].index), f"{len(amb)} codes")
a20n = mp[mp.icao_type == "A20N"].iloc[0]
report("Mapping: A20N (engine unknown) -> A320-232, -3.5 dB", a20n.anp_acft_id == "A320-232" and a20n.delta_dep_db == -3.5)
pend = mp[mp.icao_type.isin(["A339", "B78X", "B39M"])]
report("Mapping: A339/B78X/B39M pending, no silent delta = 0",
       len(pend) == 3 and pend.delta_dep_db.isna().all() and (~pend.usable_for_noise).all())
nofound = mp[mp.anp_acft_id.notna() & ~mp.anp_acft_id.isin(raw_ac.ACFT_ID)]
report("Mapping: every mapped ANP aircraft exists in the raw ANP table", nofound.empty)

# 5. the reported ANP inconsistency really exists in the raw data ------------------------
w = raw_w.merge(raw_ac[["ACFT_ID", "Max Gross Takeoff Weight (lb)"]], on="ACFT_ID")
over = w[w["Weight (lb)"] > w["Max Gross Takeoff Weight (lb)"]]
report("ANP raw: default weights above MTOW (expected 5)", len(over) == 5,
       str(over[["ACFT_ID", "Stage Length"]].values.tolist()))

print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} checks passed")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
