"""Doc 29 Vol 2 Appendix B: atmosphere ratios and corrected net thrust (CNT) for observed flight states.

For radar/ADS-B flight paths Doc 29 §3.6.1: positions, heights and speeds come from the data; only the
power parameter is computed with the performance equations (B-9/B-10/B-11).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

KT = 1.0


def c_to_f(t_c):
    return np.asarray(t_c, float) * 9.0 / 5.0 + 32.0


def ratios(alt_ft_msl, t_apt_c, qnh_hpa, elev_ft):
    """Eq. B-2..B-6 (Doc 29 legacy constants kept on purpose): T at altitude (degC), theta, delta, sigma, pressure altitude h."""
    t_apt_f = c_to_f(t_apt_c)
    papt_inhg = qnh_hpa / 33.8653131            # 1 inHg = 3386.53131 Pa (Doc 29 Appendix B legacy factor)
    alt = np.asarray(alt_ft_msl, float)
    t_f = t_apt_f - 0.003566 * (alt - elev_ft)                                   # B-2
    theta = (459.67 + t_f) / 518.67                                              # B-3
    delta = ((papt_inhg / 29.92) ** (1 / 5.256) - 0.003566 * alt / 518.67) ** 5.256   # B-4
    sigma = delta / theta                                                        # B-5
    h_press = 518.67 / 0.003566 * (1 - delta ** (1 / 5.256))                     # B-6
    t_c = (t_f - 32.0) * 5.0 / 9.0                                               # B-1
    return {"t_c": t_c, "theta": theta, "delta": delta, "sigma": sigma, "h_press_ft": h_press}


def tas_to_cas(tas_kt, sigma):
    return np.sqrt(sigma) * np.asarray(tas_kt, float)                            # B-8


def pressure_alt_to_msl(press_alt_ft, qnh_hpa):
    """Barometric (pressure) altitude -> altitude above MSL using the actual QNH (ISA lapse, exact ISA relation)."""
    p = 1013.25 * (1 - np.asarray(press_alt_ft, float) / 145442.16) ** (1 / 0.190263)
    return 145442.16 * (1 - (p / qnh_hpa) ** 0.190263)


class Thrust:
    """CNT per engine from ANP jet coefficients with the Doc 29 high-temperature rule."""

    def __init__(self, jet_coefficients: pd.DataFrame):
        self.c = {(r.acft_id, r.thrust_rating): r for r in jet_coefficients.itertuples()}

    def has(self, acft: str, rating: str) -> bool:
        return (acft, rating) in self.c

    def cnt(self, acft: str, rating: str, vc_kt, h_press_ft, t_c):
        vc, h, t = (np.asarray(x, float) for x in (vc_kt, h_press_ft, t_c))
        k = self.c[(acft, rating)]
        cnt = k.E + k.F * vc + k.Ga * h + k.Gb * h ** 2 + k.H * t                         # B-9
        hi = {"MaxTakeoff": "MaxTkoffHiTemp", "MaxClimb": "MaxClimbHiTemp", "ReduceTakeoff": "ReduTkoffHiTemp",
              "ReduceClimb": "ReduceClimbHiTemp", "MaxContinuous": "MaxContHiTemp"}.get(rating)
        if hi and (acft, hi) in self.c:
            kh = self.c[(acft, hi)]
            cnt_hi = kh.E + kh.F * vc + kh.Ga * h + kh.Gb * h ** 2 + kh.H * t           # B-10
        else:
            tb = 30.0
            cnt_hi = k.F * vc + (k.E + k.H * tb) * (1 - 0.006 * t) / (1 - 0.006 * tb)   # B-11
        return np.minimum(cnt, cnt_hi)


def cutback_height_ft(departure_steps: pd.DataFrame, acft: str, profile: str = "DEFAULT", stage: str = "1") -> float:
    """Height AFE at which the ANP default procedure changes from the take-off to the climb rating:
    end altitude of the last step flown with a take-off rating."""
    s = departure_steps[(departure_steps.acft_id == acft) & (departure_steps.profile_id == profile)
                        & (departure_steps.stage_length == stage)].sort_values("step_number")
    if s.empty:
        return np.nan
    to = s[s.thrust_rating.isin(["MaxTakeoff", "ReduceTakeoff"])]
    alts = to.end_altitude_ft.dropna()
    return float(alts.max()) if len(alts) else np.nan
