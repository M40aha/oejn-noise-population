"""Doc 29 Vol 2 Appendix D: adjustment of NPD data to non-reference atmospheres.

Steps (D-1 to D-4): remove the AIR-1845 attenuation (Table D-1) from the spectral class at 1,000 ft,
re-propagate to the 10 NPD distances with (i) Table D-1 and (ii) the actual atmosphere, A-weight,
and take the difference dL(d_i), which is added to both SEL and LAmax NPD levels.

Absorption for the actual atmosphere: pure-tone coefficients of ANSI S1.26 / ISO 9613-1 (the basis of
SAE ARP-5534) at the exact 1/3-octave mid-band frequencies. ARP-5534's band regression (a paywalled SAE
standard) is not reproduced; this implementation reproduces Doc 29 Table D-4 (10 degC, 80 % RH) within
0.1 dB at all ten distances for both spectral classes of the worked example (tests/test_noise.py).
"""
from __future__ import annotations

import numpy as np

from a5.constants import NPD_DISTANCES_FT, SPECTRAL_BANDS_HZ, TABLE_D1_DB_PER_100M

A_WEIGHT = np.array([-30.2, -26.2, -22.5, -19.1, -16.1, -13.4, -10.9, -8.6, -6.6, -4.8, -3.2, -1.9,
                     -0.8, 0.0, 0.6, 1.0, 1.2, 1.3, 1.2, 1.0, 0.5, -0.1, -1.1, -2.5])   # IEC 61672, 50 Hz-10 kHz
D1 = np.array([TABLE_D1_DB_PER_100M[f] for f in SPECTRAL_BANDS_HZ]) / 100.0          # dB/m
MIDBAND = np.array([10 ** (round(10 * np.log10(f)) / 10) for f in SPECTRAL_BANDS_HZ])  # exact base-10 mid-bands
D_REF_M = 304.8


def alpha_iso9613(f, temp_c, rh_pct, pressure_kpa=101.325):
    """Pure-tone atmospheric absorption coefficient, dB/m (ISO 9613-1:1993 / ANSI S1.26)."""
    T, T0, T01, pr = temp_c + 273.15, 293.15, 273.16, 101.325
    pa = pressure_kpa
    psat_rel = 10 ** (-6.8346 * (T01 / T) ** 1.261 + 4.6151)
    h = rh_pct * psat_rel / (pa / pr)
    fro = (pa / pr) * (24 + 4.04e4 * h * (0.02 + h) / (0.391 + h))
    frn = (pa / pr) * (T / T0) ** -0.5 * (9 + 280 * h * np.exp(-4.170 * ((T / T0) ** (-1 / 3) - 1)))
    f = np.asarray(f, float)
    return 8.686 * f ** 2 * (1.84e-11 * (pa / pr) ** -1 * (T / T0) ** 0.5
                             + (T / T0) ** -2.5 * (0.01275 * np.exp(-2239.1 / T) / (fro + f ** 2 / fro)
                                                   + 0.1068 * np.exp(-3352.0 / T) / (frn + f ** 2 / frn)))


def npd_increment(spectrum_1000ft_db, temp_c, rh_pct, pressure_kpa=101.325):
    """dL at the 10 NPD distances (Eq. D-1 to D-4) for one spectral class (24 band levels at 1,000 ft)."""
    L = np.asarray(spectrum_1000ft_db, float)
    src = L + D1 * D_REF_M                                   # D-1
    a_atm = alpha_iso9613(MIDBAND, temp_c, rh_pct, pressure_kpa)
    out = []
    for d_ft in NPD_DISTANCES_FT:
        d = d_ft * 0.3048
        spread = 20 * np.log10(d / D_REF_M)
        l_ref = src - spread - D1 * d                         # D-2
        l_atm = src - spread - a_atm * d                      # D-3
        la = 10 * np.log10(np.sum(10 ** ((l_atm + A_WEIGHT) / 10)))
        lr = 10 * np.log10(np.sum(10 ** ((l_ref + A_WEIGHT) / 10)))
        out.append(la - lr)                                   # D-4
    return np.array(out)


def relative_humidity(temp_c, dewpoint_c):
    """Magnus formula (Alduchov & Eskridge 1996) — RH from METAR temperature and dew point, %."""
    a, b = 17.625, 243.04
    return 100.0 * np.exp(a * dewpoint_c / (b + dewpoint_c)) / np.exp(a * temp_c / (b + temp_c))
