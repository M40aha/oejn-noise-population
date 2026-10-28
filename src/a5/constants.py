"""Exact unit definitions and Doc 29 reference constants.

Unit factors are exact by international definition, so conversions carry no
rounding error. ANP tables keep their native (imperial) units; these factors
are used only at the boundary with A2/A4/A6, which exchange SI.
"""

# --- exact unit definitions -------------------------------------------------
FT_TO_M = 0.3048                    # international foot (exact)
NMI_TO_M = 1852.0                   # international nautical mile (exact)
LB_TO_KG = 0.45359237               # avoirdupois pound (exact)
KT_TO_MS = 1852.0 / 3600.0          # knot (exact)
G0 = 9.80665                        # standard gravity, m/s^2 (exact, CGPM 1901)
LBF_TO_N = LB_TO_KG * G0            # pound-force (exact)

M_TO_FT = 1.0 / FT_TO_M
KG_TO_LB = 1.0 / LB_TO_KG
MS_TO_KT = 1.0 / KT_TO_MS

# --- ANP table structure (Doc 29 Vol 2 Appendix G) ---------------------------
NPD_DISTANCES_FT = (200.0, 400.0, 630.0, 1000.0, 2000.0, 4000.0,
                    6300.0, 10000.0, 16000.0, 25000.0)
NPD_LEVEL_COLUMNS = tuple(f"L_{int(d)}ft" for d in NPD_DISTANCES_FT)

SPECTRAL_BANDS_HZ = (50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630,
                     800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000,
                     6300, 8000, 10000)
SPECTRAL_LEVEL_COLUMNS = tuple(f"L_{f}Hz" for f in SPECTRAL_BANDS_HZ)
SPECTRAL_NORMALISATION_HZ = 1000
SPECTRAL_NORMALISATION_DB = 70.0     # observed: every ANP spectrum is 70.0 dB at 1 kHz

# Table D-1: average atmospheric attenuation rates (dB/100 m) used to normalise
# ANP NPD data ("AIR-1845 atmosphere"). Doc 29 5th Ed. Vol 2, Appendix D, p. D-2.
TABLE_D1_DB_PER_100M = {
    50: 0.033, 63: 0.033, 80: 0.033, 100: 0.066, 125: 0.066, 160: 0.098,
    200: 0.131, 250: 0.131, 315: 0.197, 400: 0.230, 500: 0.295, 630: 0.361,
    800: 0.459, 1000: 0.590, 1250: 0.754, 1600: 0.983, 2000: 1.311,
    2500: 1.705, 3150: 2.295, 4000: 3.115, 5000: 3.607, 6300: 5.246,
    8000: 7.213, 10000: 9.836,
}

V2 = "Doc 29 5th Ed. Vol 2"
V1 = "Doc 29 5th Ed. Vol 1"

# name, value, unit, meaning, source document, location
DOC29_CONSTANTS = [
    ("npd_reference_pressure", 101.325, "kPa", "Atmospheric pressure of NPD reference conditions", V2, "§2.5 p.9; App. G4.2 p.G-8"),
    ("npd_reference_groundspeed", 160.0, "kt", "Reference speed of NPD SEL data (duration correction)", V2, "§2.5 p.9; App. G4.2 p.G-8"),
    ("npd_reference_groundspeed_fts", 270.05, "ft/s", "Vref used in finite-segment correction", V2, "§4 p.43"),
    ("npd_reference_max_windspeed", 8.0, "m/s", "NPD reference condition: wind below 8 m/s (15 kt)", V2, "§2.5 p.9"),
    ("npd_applicability_max_temperature", 30.0, "degC", "NPD applicability envelope: near-surface air temperature below 30 C", V2, "§2.5 p.10"),
    ("npd_applicability_min_T_times_RH", 500.0, "degC*%", "NPD applicability envelope: T(C) x RH(%) above 500", V2, "§2.5 p.10"),
    ("npd_applicability_max_windspeed", 8.0, "m/s", "NPD applicability envelope: wind below 8 m/s", V2, "§2.5 p.10"),
    ("performance_reference_temperature", 15.0, "degC", "Reference air temperature of ANP aerodynamic/engine data", V2, "§2.5 p.10"),
    ("impedance_reference", 409.81, "N.s/m^3", "Air impedance of NPD reference conditions (Eq. 4-6)", V2, "§4.2.1 p.29"),
    ("impedance_constant", 416.86, "N.s/m^3", "Constant in rho*c = 416.86*(delta/theta^0.5) (Eq. 4-7)", V2, "§4.2.1 p.29"),
    ("npd_distance_floor", 30.0, "m", "Recommended lower limit on NPD slant distance", V2, "§4.2 p.29"),
    ("npd_power_floor", 1.0, "lb/engine", "Negative CNT reset to one pound per engine before extrapolation", V2, "§4.2 p.28"),
    ("npd_power_extrapolation_caution", 5.0, "dB", "Caution: power extrapolation > 5 dB beyond NPD envelope", V2, "§4.2 p.28"),
    ("substitution_unknown_variant_rule", None, "-", "If MTOW or engine unknown, assume the highest-MTOW variant (conservative)", V1, "§6.4.4.1 p.45"),
    ("substitution_method_B_scope", None, "-", "Method B (movement factor N) applies only to equivalent (energy) levels, not LAmax", V1, "§6.4.4 p.45"),
    ("substitution_delta_dep_equation", None, "dB", "Delta_dep = (FO_miss + LAT_miss - FO_proxy - LAT_proxy)/2 (Eq. 6-1)", V1, "§6.4.4.2 p.46"),
]
