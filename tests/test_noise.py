"""Noise-model test suite (Doc 29 5th Ed.).  PYTHONPATH=src pytest -q tests/test_noise.py

Reference values: Doc 29 Vol 3 workbooks (tests/fixtures/doc29_vol3, see README there) and Vol 2 text/tables.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from a5.anp_checks import npd_long
from a5.npd import NPDLookup, NPDPolicy
from noise import doc29 as D
from noise.atmosphere import alpha_iso9613, npd_increment, relative_humidity
from noise.event import AdjustedNPD, event_levels
from noise.flightpath import (PathPolicy, Z_PRIME_FT, bank_angle, build_path, ground_roll_nodes, initial_climb_nodes,
                              segments)
from noise.performance import Thrust, ratios, tas_to_cas
from noise.site import baro_height_afe

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "tests" / "fixtures" / "doc29_vol3"
FT = 0.3048
NMI_FT = 6076.0            # Vol 3 receptor tables: x(nmi) * 6076 ft reproduces the B-2 geometry


def fx(name):
    return pd.read_parquet(FX / f"{name}.parquet")


@pytest.fixture(scope="module")
def vol3():
    rc = fx("A-12_Receptors")
    rc["x"] = rc["X coordinate (nmi)"] * NMI_FT
    rc["y"] = rc["Y coordinate (nmi)"] * NMI_FT
    a7 = fx("A-7_NPD_Curves").rename(columns={
        "Aircraft Identifier": "npd_id", "Noise Descriptor": "noise_metric", "Operation Mode": "op_mode",
        "Power Setting (lb)": "power_setting",
        **{f"L_{d} (ft)": f"L_{d}ft" for d in [200, 400, 630, 1000, 2000, 4000, 6300, 10000, 16000, 25000]}})
    lk = NPDLookup(npd_long(a7.assign(src_file="", src_member="", src_row=0)), NPDPolicy())
    ac = fx("A-1_Aircraft")
    inst = dict(zip(ac["Aircraft Identifier"], ac["Lateral Directivity Identifier"]))
    return {"rc": rc, "lk": lk, "inst": inst, "b1": fx("B-1_SEL_Results"), "b2": fx("B-2_Segment_Results")}


# ------------------------------------------------------------------------------------------- Vol 3 Part 1
def _b2_rows(vol3):
    b2 = vol3["b2"].merge(vol3["rc"][["receptor_ID", "x", "y"]], on="receptor_ID")
    out = []
    etype = {"JETF": "Jet", "JETW": "Jet", "PROP": "Prop"}
    for r in b2.itertuples(index=False):
        ac, op = r.case_ID[:4], r.case_ID[4]
        s1 = (r[3], r[4], r[5])
        s2 = (r[6], r[7], r[8])
        g = D.segment_geometry(s1, s2, np.array([r.x]), np.array([r.y]), np.array([0.0]), bank_deg=r[20])
        gr = op if (s1[2] <= 3.29 and s2[2] <= 3.29) else None
        P = np.array([float(r[16])])
        res = D.segment_levels(g, P, np.array([float(r[24])]),
                               lambda p, d: vol3["lk"].lookup(ac, "SEL", op, p, d).level_db.to_numpy(),
                               lambda p, d: vol3["lk"].lookup(ac, "LAmax", op, p, d).level_db.to_numpy(),
                               vol3["inst"][ac], etype[ac], gr, float(r[28]))
        out.append({"sel": float(res["sel"][0]), "lam": g["lam"], "l": float(np.where(gr is not None and g["pos"][0] < 0, g["l_n"], g["l"])[0])})
    return b2, pd.DataFrame(out)


def test_vol3_b2_every_segment(vol3):
    """Doc 29 Vol 3 Part 1 table B-2: segment SEL of all 3,516 segment/receptor rows (JETF, JETW, PROP)."""
    b2, mine = _b2_rows(vol3)
    assert len(b2) == 3516
    assert np.max(np.abs(mine.lam - b2["segment_length(ft)"])) < 1e-6
    d = np.abs(mine.sel - b2["segment_SEL(dB)"].astype(float))
    assert d.max() < 2e-3, d.max()


def test_vol3_b1_event_sel(vol3):
    """Table B-1 event SEL = energy sum of the segments (Eq. 4-11)."""
    b2, mine = _b2_rows(vol3)
    b2 = b2.assign(mine=mine.sel.values)
    tot = b2.groupby(["case_ID", "receptor_ID"]).mine.apply(lambda s: 10 * np.log10(np.sum(10 ** (s / 10)))).reset_index()
    t = tot.merge(vol3["b1"], on=["case_ID", "receptor_ID"])
    assert len(t) == len(vol3["b1"])
    assert np.max(np.abs(t.mine - t["SEL(dB)"])) < 6e-3      # B-1 is printed to 0.01 dB


# ------------------------------------------------------------------------------------------- Vol 3 Part 2
def test_vol3_d2_thrust():
    """Part 2 table D-2 (JETW): every point flown at a maximum rating is reproduced by B-9 from TAS (B-8 with
    sigma from B-2..B-5) within the rounding of the printed TAS (0.05 kt x |F|) and CNT (0.05 lb).
    Points of reduced-thrust / level-flight procedures (cases 74, 80) are not maximum-rating points."""
    jc = fx("C2").rename(columns={"Aircraft Identifier": "acft_id", "Thrust Rating": "thrust_rating", "E (lb)": "E",
                                  "F (lb/kt)": "F", "Ga (lb/ft)": "Ga", "Gb (lb/ft2)": "Gb", "H (lb/degC)": "H"})
    th = Thrust(jc)
    d2 = fx("D2").merge(fx("C8"), on="Case Number")
    d2 = d2[(d2["Aircraft Identifier"] == "JETW") & ~d2["Case Number"].isin([74, 80])]
    r = ratios(d2["Elevation"] + d2["Altitude (ft)"], d2["Temperature (°C)"], d2["S/L Pressure (in-Hg)"] * 33.8653131, d2["Elevation"])
    cas = tas_to_cas(d2["True Airspeed (kt)"], r["sigma"])
    ref = d2["Corrected Net Thrust (lb per engine)"].to_numpy()
    ok = np.zeros(len(d2), bool)
    for rating in ("MaxTakeoff", "MaxClimb"):
        v = th.cnt("JETW", rating, cas, r["h_press_ft"], r["t_c"])
        tol = 0.05 * abs(th.c[("JETW", rating)].F) * np.sqrt(r["sigma"]) + 0.06
        ok |= np.abs(v - ref) <= tol
    assert len(d2) == 119 and ok.all(), d2[~ok]


def test_high_temperature_rule_b11():
    """B-11: above the break temperature (30 degC) take-off thrust falls 0.6 %/degC; CNT = min(B-9, B-11)."""
    jc = pd.DataFrame([{"acft_id": "X", "thrust_rating": "MaxTakeoff", "E": 25000, "F": -25, "Ga": 0.3, "Gb": 1e-5, "H": 0}])
    th = Thrust(jc)
    assert th.cnt("X", "MaxTakeoff", 0, 0, 15) == pytest.approx(25000)
    assert th.cnt("X", "MaxTakeoff", 0, 0, 40) == pytest.approx(25000 * (1 - 0.006 * 40) / (1 - 0.006 * 30))


# ------------------------------------------------------------------------------------------- Appendix D
def test_table_d4_atmospheric_increments():
    """Vol 2 Table D-4 (10 degC, 80 % RH): dL at the ten NPD distances for spectral classes 103 (dep) and 205 (app)."""
    sp = pd.read_parquet(ROOT / "data" / "a5" / "processed" / "anp_spectral_long.parquet")
    ref = {103: [.1, .3, .4, .7, 1.2, 1.8, 2.1, 2.4, 2.9, 3.6], 205: [0, .2, .3, .6, 1.1, 1.7, 2.2, 2.7, 3.2, 3.7]}
    for cls, r in ref.items():
        g = sp[sp.spectral_class_id.astype(float) == cls].sort_values("frequency_hz")
        dl = npd_increment(g.level_db.to_numpy(), 10.0, 80.0, 101.325)
        assert np.max(np.abs(dl - np.array(r))) < 0.1, (cls, np.round(dl, 2))


def test_iso9613_reference_point():
    """ISO 9613-1 Table 1 spot value: 1 kHz, 20 degC, 70 % RH, 101.325 kPa -> 4.98 dB/km (approx.)."""
    assert alpha_iso9613(1000.0, 20.0, 70.0) * 1000 == pytest.approx(4.98, abs=0.1)


def test_magnus_rh():
    assert relative_humidity(25.0, 25.0) == pytest.approx(100.0)
    assert relative_humidity(30.0, 20.0) == pytest.approx(55.2, abs=0.5)


# ------------------------------------------------------------------------------------------- flight path (Ch. 3)
def test_ground_roll_eq_3_3_example():
    """Vol 2 Fig. 3-5: s_TO = 1600 m, V_TO = 75 m/s -> 8 segments, lengths 25, 75, ..., 375 m."""
    v_kt = 75.0 / FT / 1.6878098571
    n = ground_roll_nodes((0.0, 0.0), np.array([1.0, 0.0]), 1600.0 / FT, v_kt)
    assert int(n.roll_n.iloc[0]) == 8
    ends = n.s_ft.to_numpy() * FT
    assert np.allclose(ends, [0, 25, 100, 225, 400, 625, 900, 1225, 1600])
    assert np.allclose(np.diff(ends), [25 * (2 * k - 1) for k in range(1, 9)])


def test_initial_climb_eq_3_4_example():
    """Vol 2 §3.6.4 example: z_e = 304.8 m -> nearest z' = 334.9 m (1099 ft), z1 = 17.2 m, z2 = 37.8 m."""
    ic = initial_climb_nodes({"x_ft": 0.0, "y_ft": 0.0, "V_kt": 150.0}, {"x_ft": 10000.0, "y_ft": 0.0, "z_ft": 1000.0, "V_kt": 160.0})
    z_m = ic.z_ft.to_numpy() * FT
    assert z_m[0] == pytest.approx(17.2, abs=0.05) and z_m[1] == pytest.approx(37.8, abs=0.05)
    assert len(z_m) == 6 and z_m[-1] < 304.8              # 7th height (= z_e) is the observed point itself
    assert Z_PRIME_FT[6] == pytest.approx(1099, abs=0.5)


def test_bank_angle_b14():
    """Steady observed turn: bank = atan(2.85 V^2 / (r g)) (Eq. B-14, V kt, r ft)."""
    V, r = 200.0, 15000.0
    w = V * 1.6878098571 / r
    t = np.arange(0, 120, 2.0)
    air = pd.DataFrame({"t_s": t, "x_ft": r * np.sin(w * t), "y_ft": r * np.cos(w * t), "gs_kt": V})   # clockwise = right turn
    eps = bank_angle(air.iloc[10:50], air, PathPolicy(bank_smoothing_s=2.0))
    expect = np.degrees(np.arctan(2.85 * V ** 2 / (r * 32.17405)))
    assert np.allclose(eps, expect, atol=0.05)


def _fpp_observations(acft, step_m=50.0):
    """Doc 29 Vol 3 fixed-point profile (A-6) re-sampled as an 'observed' track (z linear in distance,
    V and P by Eq. 3-2b/3-2d, time from distance/speed)."""
    p = fx("A-6_Fixed_Point_Profiles")
    p.columns = ["acft", "op", "prof", "stage", "pt", "s_m", "z_m", "v_ms", "P"]
    p = p[(p.acft.str.strip() == acft) & (p.op.str.strip() == "D")].sort_values("pt")
    rows, t, prev = [], 0.0, None
    for a, b in zip(p.iloc[:-1].itertuples(), p.iloc[1:].itertuples()):
        n = max(1, int(np.ceil((b.s_m - a.s_m) / step_m)))
        for k in range(n):
            f = k / n
            s, z = a.s_m + f * (b.s_m - a.s_m), a.z_m + f * (b.z_m - a.z_m)
            v = np.sqrt(a.v_ms ** 2 + f * (b.v_ms ** 2 - a.v_ms ** 2))
            P = np.sqrt(a.P ** 2 + f * (b.P ** 2 - a.P ** 2))
            if prev is not None:
                t += (s - prev[0]) / max((v + prev[1]) / 2, 0.5)
            rows.append((t, s, z, v, P))
            prev = (s, v)
    o = pd.DataFrame(rows, columns=["t_s", "s_m", "z_m", "v_ms", "P_obs"])
    o["z_ft"], o["gs_kt"], o["on_ground"] = o.z_m / FT, o.v_ms / FT / 1.6878098571, o.z_m <= 0
    o.attrs["P_roll"] = (float(p.P.iloc[0]), float(p.P.iloc[1]))
    return o


@pytest.mark.parametrize("acft", ["JETW", "JETF"])
@pytest.mark.parametrize("route", ["DS", "DC"])
def test_end_to_end_observed_path_reproduces_b1(vol3, acft, route):
    """The Vol 3 departure, fed to the flight-path builder as an observed track (lift-off detection, Eq. 3-3 roll,
    Eq. 3-4 sub-segmentation, node thinning) and to the event model, reproduces B-1 within 0.06 dB."""
    o = _fpp_observations(acft)
    rt = fx("A-11_Routes")
    tr = rt[rt.route_ID == route].sort_values("Track Points")
    px, py = tr["X coordinate (nmi)"].to_numpy() * NMI_FT, tr["Y coordinate (nmi)"].to_numpy() * NMI_FT
    cum = np.r_[0, np.cumsum(np.hypot(np.diff(px), np.diff(py)))]
    s = o.s_m / FT
    o["x_ft"], o["y_ft"] = np.interp(s, cum, px), np.interp(s, cum, py)
    nodes, info = build_path(o, (0.0, 0.0), (1.0, 0.0), 3000 / FT, None, 1000.0,
                             PathPolicy(height_smoothing_points=1, max_bank_deg=0.0))   # Vol 3 cases fly with zero bank
    assert info["s_lo_ft"] * FT == pytest.approx(1708.5, abs=0.5) and info["n_roll_segments"] == 9
    ref = vol3["b1"][vol3["b1"].case_ID == acft + route].merge(vol3["rc"], on="receptor_ID")
    npd = AdjustedNPD(vol3["lk"], acft, "D")
    sel, _ = event_levels(segments(nodes), ref.x.values, ref.y.values, np.zeros(len(ref)), npd, vol3["inst"][acft], "Jet", 0.0741)
    assert np.max(np.abs(sel - ref["SEL(dB)"].to_numpy())) < 0.06


def test_adjusted_npd_equals_a5_lookup(vol3):
    rng = np.random.default_rng(1)
    P, d = rng.uniform(-500, 30000, 500), rng.uniform(10, 60000, 500)
    npd = AdjustedNPD(vol3["lk"], "JETW", "D")
    for m in ("SEL", "LAmax"):
        assert np.allclose(npd(m, P, d), vol3["lk"].lookup("JETW", m, "D", P, d).level_db.to_numpy(), atol=1e-12)
    dl = np.linspace(0.1, 3.0, 10)
    nd = AdjustedNPD(vol3["lk"], "JETW", "D", dl)
    assert np.allclose(nd("SEL", [20000.0] * 10, [200, 400, 630, 1000, 2000, 4000, 6300, 10000, 16000, 25000]),
                       vol3["lk"].lookup("JETW", "SEL", "D", 20000.0, [200, 400, 630, 1000, 2000, 4000, 6300, 10000, 16000, 25000]).level_db + dl)


def test_baro_height_isa_identity():
    """ISA day at sea level (QNH 1013.25, 15 degC, elev 0): height above the aerodrome = pressure altitude."""
    h = np.array([0.0, 1000.0, 5000.0, 10000.0])
    assert np.allclose(baro_height_afe(h, 1013.25, 15.0, 0.0), h, atol=0.5)
    # warmer than ISA -> geometric height above the pressure-altitude difference
    assert baro_height_afe(5000.0, 1013.25, 35.0, 0.0) > 5000.0 * 1.06


# ------------------------------------------------------------------------------------------- pipeline (synthetic)
def test_pipeline_on_synthetic_inputs(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("syn", ROOT / "scripts" / "make_synthetic_noise_inputs.py")
    syn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(syn)
    syn.main(tmp_path / "in", 6)
    import yaml
    cfg = yaml.safe_load((ROOT / "config" / "noise.yaml").read_text())
    cfg["grid"].update({"spacing_m": 1000.0, "half_width_m": 15000.0})
    cfg["run"]["workers"] = 1
    cfg_p = tmp_path / "noise.yaml"
    cfg_p.write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv("NOISE_A2_DIR", str(tmp_path / "in" / "a2"))
    monkeypatch.setenv("NOISE_METAR_CSV", str(tmp_path / "in" / "ext_metar_oejn.csv"))
    monkeypatch.setenv("NOISE_IDENTITY_CSV", str(tmp_path / "in" / "aircraft_identity.csv"))
    from noise import run
    man = run.main(cfg_p, tmp_path / "out")
    proc = tmp_path / "out" / "data" / "noise" / "processed"
    fr = pd.read_csv(proc / "flight_results.csv")
    assert man["flights_modelled"] == 5                                   # 6th flight has no aircraft type
    assert set(fr.noise_status) == {"OK", "NO_TYPE", "OUT_OF_SCOPE_A2_STATUS"}
    g = pd.read_parquet(proc / "noise_grid.parquet")
    ok = g.LAeq24.notna()
    assert (g.Lden[ok] >= g.LAeq24[ok] - 1e-9).all()                     # penalties are non-negative
    ex = pd.read_csv(proc / "population_exposure.csv")
    cum = ex[(ex.metric == "Lden") & ex.band.str.contains("cumulative")].sort_values("lower_db").population.to_numpy()
    assert (np.diff(cum) <= 1e-6).all()
    assert (proc / "noise_grid_utm37n.tif").exists()
