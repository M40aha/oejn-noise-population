"""A5 test suite. Run after `python -m a5.build`:  PYTHONPATH=src pytest -q"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from a5 import constants as C
from a5.npd import NPDLookup, NPDPolicy
from a5.mapping import Mapper, MappingPolicy

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "a5" / "processed"
VAL = ROOT / "data" / "a5" / "validation"


def P(name):
    return pd.read_parquet(PROC / f"{name}.parquet")


# ----------------------------------------------------------------------------- units
def test_unit_constants_are_exact_definitions():
    assert C.FT_TO_M == 0.3048
    assert C.NMI_TO_M == 1852.0
    assert C.LB_TO_KG == 0.45359237
    assert math.isclose(C.KT_TO_MS * 3600, 1852.0, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(C.LBF_TO_N, 4.4482216152605, rel_tol=1e-13)
    assert math.isclose(C.M_TO_FT * C.FT_TO_M, 1.0, rel_tol=1e-15)


# ----------------------------------------------------------------------------- NPD lookup (synthetic, analytic)
@pytest.fixture
def synthetic():
    rows = []
    for p, base in ((1000.0, 90.0), (3000.0, 100.0)):
        for d in C.NPD_DISTANCES_FT:
            rows.append(("T", "SEL", "D", p, d, base - 20 * math.log10(d / 200.0)))
    df = pd.DataFrame(rows, columns=["npd_id", "noise_metric", "op_mode", "power_setting", "distance_ft", "level_db"])
    return NPDLookup(df, NPDPolicy())


def test_grid_points_exact(synthetic):
    r = synthetic.lookup("T", "SEL", "D", [1000.0, 3000.0], [200.0, 25000.0])
    assert np.allclose(r.level_db, [90.0, 100 - 20 * math.log10(125)], atol=1e-12)


def test_log_distance_interpolation(synthetic):
    d = math.sqrt(200 * 400)  # geometric midpoint -> arithmetic midpoint in level (Eq. 4-4)
    r = synthetic.lookup("T", "SEL", "D", 1000.0, d)
    assert math.isclose(r.level_db.iat[0], 90 - 20 * math.log10(d / 200), abs_tol=1e-12)


def test_linear_power_interpolation_and_extrapolation(synthetic):
    r = synthetic.lookup("T", "SEL", "D", [2000.0, 5000.0], [200.0, 200.0])
    assert np.allclose(r.level_db, [95.0, 110.0], atol=1e-12)            # Eq. 4-3 inside and outside
    assert list(r.power_extrapolated) == [False, True]
    assert list(r.power_extrapolation_warning) == [False, True]          # 10 dB beyond envelope edge > 5 dB


def test_distance_extrapolation_outward_inward(synthetic):
    r = synthetic.lookup("T", "SEL", "D", 1000.0, [50000.0, 150.0])
    assert np.allclose(r.level_db, [90 - 20 * math.log10(250), 90 - 20 * math.log10(150 / 200)], atol=1e-10)
    assert r.distance_extrapolated.all()


def test_floors(synthetic):
    r = synthetic.lookup("T", "SEL", "D", -50.0, 10.0)
    assert r.power_used.iat[0] == 1.0 and r.power_floored.iat[0]
    assert math.isclose(r.distance_used_ft.iat[0], 30 / 0.3048) and r.distance_floored.iat[0]


def test_lookup_rejects_bad_input(synthetic):
    with pytest.raises(ValueError):
        synthetic.lookup("T", "SEL", "D", np.nan, 1000.0)
    with pytest.raises(KeyError):
        synthetic.lookup("T", "LAmax", "D", 1000.0, 1000.0)


# ----------------------------------------------------------------------------- build outputs
def test_build_has_no_errors():
    s = json.loads((VAL / "build_summary.json").read_text())
    assert s["qc_counts"]["ERROR"] == 0, "QC errors present: see data/a5/validation/qc_report.md"


def test_vol3_b2_reproduced():
    b2 = pd.read_parquet(VAL / "vol3_b2_npd_validation.parquet")
    assert len(b2) > 3000
    assert b2.abs_diff_db.max() <= 0.001


def test_raw_sources_unchanged():
    src = P("sources")
    assert src.sha256_matches_lock.all()


def test_npd_long_matches_wide_exactly():
    w = P("anp_npd_wide")
    l = P("anp_npd_long")
    assert len(l) == len(w) * 10
    piv = l.pivot_table(index=["npd_id", "noise_metric", "op_mode", "power_setting"], columns="source_column",
                        values="level_db", aggfunc="first")[list(C.NPD_LEVEL_COLUMNS)]
    w = w.set_index(["npd_id", "noise_metric", "op_mode", "power_setting"])[list(C.NPD_LEVEL_COLUMNS)]
    assert (piv.loc[w.index].to_numpy() == w.to_numpy()).all()


def test_provenance_present():
    for t in ("anp_aircraft", "anp_npd_wide", "anp_departure_steps", "easa_subst_icao", "easa_subst_config"):
        df = P(t)
        assert {"src_file", "src_member", "src_row"} <= set(df.columns)
        assert df.src_row.notna().all()


def test_mapping_contract():
    m = P("aircraft_noise_mapping")
    ac = P("anp_aircraft")
    ok = m[m.anp_acft_id.notna()]
    assert ok.anp_acft_id.isin(ac.acft_id).all()
    assert set(m.confidence) <= {"HIGH", "MEDIUM", "LOW", "NONE"}
    # nothing is usable without a numeric delta
    assert not m[m.usable_for_noise & m.delta_dep_db.isna()].shape[0]
    # pending analyst proxies are never silently given delta = 0
    pend = m[(m.mapping_method == "ANALYST_PROXY")]
    assert pend.delta_dep_db.isna().all() or (pend.review_status == "REVIEWED").all()
    for c in ("npd_id", "dep_spectral_class_id", "lateral_directivity", "power_parameter_kind", "evidence", "source_ref"):
        assert c in m.columns


# ----------------------------------------------------------------------------- mapping behaviour on real EASA data
@pytest.fixture(scope="module")
def mapper():
    analyst = pd.read_csv(ROOT / "data" / "a5" / "reviews" / "analyst_proxies.csv", dtype=str)
    return Mapper(P("easa_subst_icao"), P("easa_subst_config"), P("anp_aircraft"), P("easa_verified_types"),
                  analyst, MappingPolicy(), "test")


def _one(mapper, **kw):
    m, c = mapper.resolve(pd.DataFrame([kw]))
    return m.iloc[0], c


def test_a20n_unknown_engine_is_conservative(mapper):
    r, c = _one(mapper, icao_type="A20N")
    assert r.mapping_method == "EASA_ICAO_AMBIGUOUS" and r.anp_acft_id == "A320-232" and r.delta_dep_db == -3.5
    assert r.confidence == "LOW" and len(c) == 2


def test_a20n_with_engine_and_mtow_uses_configuration(mapper):
    r, _ = _one(mapper, icao_type="A20N", engine_type="LEAP-1A26", mtow_kg=70000)
    assert r.mapping_method == "EASA_CONFIG" and r.anp_acft_id == "A320-211" and r.confidence == "HIGH"
    assert r.delta_dep_db < -6.7          # specific configuration is quieter than the ICAO-tab envelope


def test_a20n_engine_without_mtow_takes_max_mtow(mapper):
    r, _ = _one(mapper, icao_type="A20N", engine_type="PW1127G-JM")
    assert r.mapping_method == "EASA_CONFIG_MAXMTOW" and r.anp_acft_id == "A320-232" and r.conservative_choice


def test_engine_family_prefix(mapper):
    r, _ = _one(mapper, icao_type="A20N", engine_type="LEAP-1A")
    assert r.mapping_method == "EASA_CONFIG_ENGINE_FAMILY" and r.confidence == "MEDIUM"


def test_b789_mtow_matters_more_than_engine(mapper):
    """For the 787-9 the certified-MTOW option drives delta_dep (-1.8 .. +3.2 dB for one GEnx engine)."""
    icao, _ = _one(mapper, icao_type="B789")
    genx_max, _ = _one(mapper, icao_type="B789", engine_type="GEnx-1B70/P2G01")
    genx_light, _ = _one(mapper, icao_type="B789", engine_type="GEnx-1B70/P2G01", mtow_kg=181436)
    assert icao.delta_dep_db == 3.2
    assert genx_max.mapping_method == "EASA_CONFIG_MAXMTOW" and genx_max.selected_mtow_kg == 254011
    # three certified rows contain this engine at 181,436 kg (-1.8, -1.4, -1.3): the noisiest (-1.3) is taken
    assert genx_light.mapping_method == "EASA_CONFIG" and genx_light.delta_dep_db == -1.3


def test_missing_types_pending_not_zero(mapper):
    for t in ("A339", "B78X", "B39M"):
        r, _ = _one(mapper, icao_type=t)
        assert r.mapping_method == "ANALYST_PROXY" and np.isnan(r.delta_dep_db) and not r.usable_for_noise


def test_analyst_delta_eq_6_1():
    analyst = pd.DataFrame([{"icao_type": "B39M", "description": "x", "proxy_anp_id": "7378MAX", "rationale": "r",
                             "miss_flyover_epndb": "85.0", "miss_lateral_epndb": "90.0", "miss_cert_source": "test",
                             "reviewer": "t", "review_date": "2026-10-27", "review_status": "REVIEWED", "notes": ""}])
    mp = Mapper(P("easa_subst_icao"), P("easa_subst_config"), P("anp_aircraft"), P("easa_verified_types"),
                analyst, MappingPolicy(), "test")
    r = mp.resolve(pd.DataFrame([{"icao_type": "B39M"}]))[0].iloc[0]
    cfg = P("easa_subst_config")
    prox = cfg[(cfg.anp_proxy == "7378MAX") & (cfg.delta_dep_db == 0) & (cfg.delta_app_db == 0)]
    s = (prox.flyover_epndb + prox.lateral_epndb).iloc[0]
    assert math.isclose(r.delta_dep_db, (85 + 90 - s) / 2, abs_tol=1e-9) and r.confidence == "LOW" and r.usable_for_noise


def test_unknown_type_unresolved(mapper):
    r, _ = _one(mapper, icao_type="ZZZZ")
    assert r.mapping_method == "UNRESOLVED" and not r.usable_for_noise
