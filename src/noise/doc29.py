"""ECAC Doc 29 (5th Ed., 2026) Vol 2 Chapter 4: single-event segment noise levels.

Implements, per flight-path segment and receptor:
  L_max,seg = Lmax(P, d_s) + dI(phi) - Lambda(beta, l)                        (4-8a)
  L_E,seg   = L_E(P, d)   + dV + dI(phi) - Lambda(beta, l) + dF               (4-8b)
  take-off ground roll, receptor behind the segment: + dSOR and dF'           (4-9a/b)
plus the acoustic impedance adjustment (4-6/4-7, added to NPD levels).
Event levels: L_max = max over segments (4-10); L_E = energy sum (4-11).

Geometry is in feet (ANP / Vol 3 convention); x, y horizontal, z height above the receptor plane.
Validated against Doc 29 Vol 3 Part 1 table B-2 (every intermediate column) in tests/test_noise.py.
"""
from __future__ import annotations

import numpy as np

FT = 0.3048
VREF_KT = 160.0                     # NPD reference ground speed
VREF_FTS = 270.05                   # Vol 2 p.43
D0_FT = 2.0 / np.pi * VREF_FTS      # scaled-distance constant, t0 = 1 s
DSOR0_FT = 2500.0                   # 762 m normalising distance (4-25)
INSTALL = {"Wing": (0.0039, 0.062, 0.8786), "Fuselage": (0.1225, 0.329, 1.0)}


def impedance_adjustment(temp_c: float, pressure_hpa: float) -> float:
    """Eq. 4-6/4-7: 10 lg(rho c / 409.81), rho c = 416.86 * delta / theta^0.5 at aerodrome conditions."""
    delta = pressure_hpa / 1013.25
    theta = (temp_c + 273.15) / (15.0 + 273.15)
    return 10.0 * np.log10(416.86 * delta / np.sqrt(theta) / 409.81)


def engine_installation(phi_deg, installation: str):
    """Eq. 4-15/4-16. Negative depression angles use dI(0)."""
    phi = np.radians(np.maximum(np.asarray(phi_deg, dtype=float), 0.0))
    if installation not in INSTALL:          # propeller aircraft
        return np.zeros_like(phi)
    a, b, c = INSTALL[installation]
    return 10.0 * np.log10((a * np.cos(phi) ** 2 + np.sin(phi) ** 2) ** b / (c * np.sin(2 * phi) ** 2 + np.cos(2 * phi) ** 2))


def lateral_attenuation(beta_deg, l_ft):
    """Eq. 4-18/4-19 (AIR-5662): Gamma(l) * Lambda(beta); l in metres inside Gamma."""
    beta = np.asarray(beta_deg, dtype=float)
    l_m = np.asarray(l_ft, dtype=float) * FT
    gamma = np.where(l_m <= 914.0, 1.089 * (1.0 - np.exp(-0.00274 * l_m)), 1.0)
    lam = np.where(beta <= 50.0, 1.137 - 0.0229 * beta + 9.72 * np.exp(-0.142 * beta), 0.0)
    lam = np.where(beta < 0.0, 10.857, lam)
    return gamma * lam


def finite_segment(q, lam, d_lambda):
    """Eq. 4-20; lower limit -150 dB."""
    a1 = -q / d_lambda
    a2 = -(q - lam) / d_lambda
    f = (a2 / (1 + a2 ** 2) + np.arctan(a2) - a1 / (1 + a1 ** 2) - np.arctan(a1)) / np.pi
    return np.maximum(10.0 * np.log10(np.maximum(f, 1e-300)), -150.0)


def finite_segment_behind_takeoff(lam, d_lambda):
    """Eq. 4-21a (q = 0 form) for receptors behind a take-off ground-roll segment."""
    a2 = lam / d_lambda
    f = (a2 / (1 + a2 ** 2) + np.arctan(a2)) / np.pi
    return np.maximum(10.0 * np.log10(np.maximum(f, 1e-300)), -150.0)


def start_of_roll(psi_deg, d_sor_ft, engine: str = "Jet"):
    """Eq. 4-24a (turbofan) / 4-24b (turboprop) and the distance factor 4-25."""
    psi = np.clip(np.asarray(psi_deg, dtype=float), 90.0, 180.0 - 1e-9)
    if engine == "Jet":
        r = np.pi * psi / 180.0
        d0 = 2329.44 - 8.0573 * psi + 11.51 * np.exp(r) - 3.4601 * psi / np.log(r) - 17403338.3 * np.log(r) / psi ** 2
    else:
        d0 = (-34643.898 + 30722162 / psi - 11491573931 / psi ** 2 + 2.34928567e12 / psi ** 3
              - 2.83584442e14 / psi ** 4 + 2.02271504e16 / psi ** 5 - 7.90084471e17 / psi ** 6 + 1.30506872e19 / psi ** 7)
    return np.where(d_sor_ft > DSOR0_FT, d0 * DSOR0_FT / d_sor_ft, d0)


def segment_geometry(s1, s2, rx, ry, rz=0.0, bank_deg=0.0):
    """Doc 29 §4.4.1 / §4.5.5 geometry for one segment and many receptors.

    s1, s2: (x, y, z) of segment start/end; rx, ry, rz: receptor arrays.
    Returns dict with lam, q, d1, d2, dp, ds, position (-1 behind, 0 alongside, 1 ahead), lateral l,
    elevation beta (LE: equivalent level path), depression phi, and the Lmax-specific beta/l.
    """
    s1 = np.asarray(s1, float)
    s2 = np.asarray(s2, float)
    seg = s2 - s1
    lam = float(np.linalg.norm(seg))
    u = seg / lam
    ox, oy, oz = np.asarray(rx, float), np.asarray(ry, float), np.asarray(rz, float) + 0.0 * np.asarray(rx, float)
    vx, vy, vz = ox - s1[0], oy - s1[1], oz - s1[2]
    q = vx * u[0] + vy * u[1] + vz * u[2]
    px, py, pz = s1[0] + q * u[0], s1[1] + q * u[1], s1[2] + q * u[2]        # Sp (on the extended segment)
    dp = np.sqrt((ox - px) ** 2 + (oy - py) ** 2 + (oz - pz) ** 2)
    d1 = np.sqrt(vx ** 2 + vy ** 2 + vz ** 2)
    d2 = np.sqrt((ox - s2[0]) ** 2 + (oy - s2[1]) ** 2 + (oz - s2[2]) ** 2)
    pos = np.where(q < 0, -1, np.where(q > lam, 1, 0))
    ds = np.where(pos < 0, d1, np.where(pos > 0, d2, dp))
    # horizontal (ground-track) geometry: lateral displacement from the extended ground track
    gx, gy = seg[0], seg[1]
    gl = np.hypot(gx, gy)
    if gl > 0:
        l_track = np.abs((ox - s1[0]) * gy - (oy - s1[1]) * gx) / gl
        side = np.sign((ox - s1[0]) * gy - (oy - s1[1]) * gx)      # >0: receptor to the right (starboard)
    else:
        l_track = np.hypot(ox - s1[0], oy - s1[1])
        side = np.ones_like(ox)
    # LE: equivalent level path (Fig. 4-6/4-7): h = RS, the perpendicular from the ground track to the segment
    # at its point nearest the observer (S1, Sp or S2) = height of that point / cos(climb angle); beta = atan(h / l).
    t = np.clip(q / lam, 0.0, 1.0)
    z_near = s1[2] + t * seg[2] - oz
    cos_g = gl / lam if lam > 0 else 1.0
    h_eq = np.maximum(z_near, 0.0) / max(cos_g, 1e-12)
    d_eq = np.sqrt(l_track ** 2 + h_eq ** 2)
    beta = np.degrees(np.arctan2(h_eq, l_track))
    # depression angle at the closest point of approach on the (extended) inclined path: phi = beta_p -/+ eps,
    # beta_p = angle SpOC = acos(l / dp)
    beta_p = np.sign(pz - oz) * np.degrees(np.arccos(np.clip(l_track / np.maximum(dp, 1e-12), -1, 1)))
    eps = float(bank_deg)
    phi = beta_p - side * eps
    # Lmax (and LE behind take-off roll): elevation and lateral distance of the nearest end point
    zn = np.where(pos < 0, s1[2], np.where(pos > 0, s2[2], pz)) - oz
    dn = np.where(pos < 0, d1, np.where(pos > 0, d2, dp))
    beta_n = np.degrees(np.arcsin(np.clip(zn / np.maximum(dn, 1e-9), -1, 1)))
    l_n = np.sqrt(np.maximum(dn ** 2 - zn ** 2, 0.0))
    q_h = ((ox - s1[0]) * gx + (oy - s1[1]) * gy) / gl if gl > 0 else np.zeros_like(ox)
    d1_h = np.hypot(ox - s1[0], oy - s1[1])
    return {"q_h": q_h, "d1_h": d1_h, "lam": lam, "q": q, "d1": d1, "d2": d2, "dp": dp, "ds": ds, "pos": pos, "l": l_track,
            "beta": beta, "d_eq": d_eq, "beta_p": beta_p, "phi": phi, "beta_n": beta_n, "l_n": l_n}


def segment_levels(g: dict, P, dV, lookup_sel, lookup_lmax, installation: str, engine: str = "Jet",
                   ground_roll: str | None = None, impedance_db: float = 0.0, delta_db: float = 0.0):
    """Segment SEL and LAmax for many receptors (Eq. 4-8 / 4-9).

    g: segment_geometry() output; P: equivalent power per receptor (Eq. 4-12, already resolved);
    dV: duration correction per receptor (Eq. 4-13/4-14); lookup_*(P, d_ft) -> NPD level (already
    atmosphere-adjusted if required); ground_roll: None, 'D' (take-off roll) or 'A' (landing roll);
    impedance_db: Eq. 4-6 adjustment; delta_db: substitution adjustment (Method A).
    Returns dict of arrays: sel, lmax and every component (for audit/validation).
    """
    pos = g["pos"]
    behind_to = (ground_roll == "D") & (pos < 0)
    ahead_ld = (ground_roll == "A") & (pos > 0)
    special = behind_to | ahead_ld
    # NPD distance for LE: dp in general; ds behind take-off roll / ahead of landing roll
    d_le = np.where(special, g["ds"], g["dp"])
    beta = np.where(special, g["beta_n"], g["beta"])
    lat_l = np.where(special, g["l_n"], g["l"])
    phi = np.where(special, g["beta_n"], g["phi"])
    dI = engine_installation(phi, installation)
    Lam = lateral_attenuation(beta, lat_l)
    base_sel = lookup_sel(P, d_le)
    # scaled distance from the NPD levels at the LE distance parameter (dp; ds behind take-off roll): that is
    # base_sel itself, since d_le = dp wherever the receptor is not behind the take-off roll / ahead of the landing roll
    le_dp = base_sel
    lmax_dp = lookup_lmax(P, d_le)
    d_lambda = D0_FT * 10.0 ** ((le_dp - lmax_dp) / 10.0)
    dF = np.where(behind_to, finite_segment_behind_takeoff(g["lam"], d_lambda),
                  finite_segment(g["q"], g["lam"], d_lambda))
    if ground_roll == "A":                                        # Eq. 4-21b ahead of landing-roll segments
        a1 = -g["lam"] / d_lambda
        f_a = (-a1 / (1 + a1 ** 2) - np.arctan(a1)) / np.pi
        dF = np.where(ahead_ld, np.maximum(10 * np.log10(np.maximum(f_a, 1e-300)), -150.0), dF)
    dsor = np.zeros_like(base_sel)
    if ground_roll == "D":
        # psi and d_SOR in the horizontal plane (Fig. 4-8)
        psi = np.degrees(np.arccos(np.clip(g["q_h"] / np.maximum(g["d1_h"], 1e-9), -1, 1)))
        dsor = np.where(behind_to, start_of_roll(psi, g["d1_h"], engine), 0.0)
    sel = base_sel + dV + dI - Lam + dF + dsor + impedance_db + delta_db
    lmax = lookup_lmax(P, g["ds"]) + engine_installation(np.where(special, g["beta_n"], np.where(pos == 0, g["phi"], g["beta_n"])), installation) \
        - lateral_attenuation(g["beta_n"], g["l_n"]) + dsor + impedance_db + delta_db
    return {"sel": sel, "lmax": lmax, "base_sel": base_sel, "d_le": d_le, "dI": dI, "Lambda": Lam, "dF": dF,
            "dSOR": dsor, "lmax_dp": lmax_dp, "beta": beta, "l": lat_l, "phi": phi}


def interp_power(P1, P2, q, lam, pos):
    """Eq. 4-12 (power at the closest point; nearest end point when behind/ahead). Powers floored at 1 lb (note 13)."""
    P1, P2 = max(P1, 1.0), max(P2, 1.0)
    f = np.clip(q / lam, 0.0, 1.0)
    return np.where(pos < 0, P1, np.where(pos > 0, P2, np.sqrt(P1 ** 2 + f * (P2 ** 2 - P1 ** 2))))


def duration_correction(V1, V2, q, lam, pos, ground_roll: bool):
    """Eq. 4-13a/b and 4-14 (speeds in kt, ground speed)."""
    if ground_roll:
        v = np.full(np.shape(q), (V1 + V2) / 2.0)
    else:
        f = np.clip(q / lam, 0.0, 1.0)
        v = np.where(pos < 0, V1, np.where(pos > 0, V2, np.sqrt(V1 ** 2 + f * (V2 ** 2 - V1 ** 2))))
    return 10.0 * np.log10(VREF_KT / np.maximum(v, 1e-6))
