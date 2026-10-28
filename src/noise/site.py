"""OEJN site adapter: A2 observations -> the local-frame observation table used by flightpath.build_path.

Frame: UTM 37N (EPSG:32637, the A2 and A6 projected CRS) shifted to the aerodrome reference point (ARP), feet.
Reference plane: elevation of the departure runway threshold (start of roll); heights z are above that plane and
receptors lie on it (flat-terrain assumption of Doc 29 without the optional topography adjustment).

Heights (configurable, `height_source`):
  geometric : GNSS altitude (WGS84 ellipsoid, readsb alt_geom) - geoid undulation (AIP AD 2, A1 runway table)
  baro      : pressure altitude -> height above the threshold with the hypsometric relation for the actual
              aerodrome temperature and the ISA lapse rate (Doc 29 Appendix B atmosphere), QFE from the METAR QNH
  auto      : geometric where reported, else baro (per point; source recorded)
Power inputs: pressure altitude = barometric altitude as reported (B-9 uses pressure altitude); CAS = IAS where
reported, else (ground speed + headwind component of the METAR wind) * sqrt(sigma) (B-8 with TAS from GS);
temperature at altitude from Eq. B-2.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import Transformer

from .performance import ratios

FT = 0.3048
TO_UTM = Transformer.from_crs(4326, 32637, always_xy=True)
LAPSE_K_PER_FT = 0.0019812        # 6.5 K/km
EXP = 0.190263                    # R L / g (ISA)


class Site:
    def __init__(self, runways: pd.DataFrame, arp_lat: float, arp_lon: float):
        self.rw = runways.set_index("runway_end")
        self.E0, self.N0 = TO_UTM.transform(arp_lon, arp_lat)

    def to_local(self, e_m, n_m):
        return (np.asarray(e_m, float) - self.E0) / FT, (np.asarray(n_m, float) - self.N0) / FT

    def runway(self, end: str) -> dict:
        r = self.rw.loc[end]
        e1, n1 = TO_UTM.transform(r.threshold_longitude_deg, r.threshold_latitude_deg)
        e2, n2 = TO_UTM.transform(r.opposite_threshold_longitude_deg, r.opposite_threshold_latitude_deg)
        x1, y1 = self.to_local(e1, n1)
        x2, y2 = self.to_local(e2, n2)
        u = np.array([x2 - x1, y2 - y1], float)
        return {"sor_xy": (float(x1), float(y1)), "axis_u": u / np.linalg.norm(u), "tora_ft": float(r.full_length_tora_m) / FT,
                "elev_ft": float(r.threshold_elevation_ft_amsl), "geoid_ft": float(r.geoid_undulation_ft),
                "length_ft": float(np.linalg.norm(u))}


def baro_height_afe(press_alt_ft, qnh_hpa, t_apt_c, elev_ft):
    """Height above the aerodrome from pressure altitude: p from ISA pressure altitude; QFE from QNH reduced to the
    aerodrome elevation with ISA; hypsometric with the actual aerodrome temperature and ISA lapse."""
    p = 1013.25 * (1 - 6.8755856e-6 * np.asarray(press_alt_ft, float)) ** 5.2558797
    qfe = qnh_hpa * (1 - 6.8755856e-6 * elev_ft) ** 5.2558797
    T0 = t_apt_c + 273.15
    return T0 / LAPSE_K_PER_FT * (1 - (p / qfe) ** EXP)


def prepare_observations(obs: pd.DataFrame, site: Site, rw: dict, met: dict, height_source: str = "auto") -> pd.DataFrame:
    o = obs.copy()
    if "quality_flags" in o:
        o = o[~o.quality_flags.fillna("").str.contains("implausible")]
    o = o.dropna(subset=["easting_m", "northing_m", "timestamp_ms"])
    x, y = site.to_local(o.easting_m, o.northing_m)
    baro = pd.to_numeric(o.get("barometric_altitude_ft"), errors="coerce").to_numpy(float)
    geo = pd.to_numeric(o.get("geometric_altitude_ft"), errors="coerce").to_numpy(float) if "geometric_altitude_ft" in o else np.full(len(o), np.nan)
    z_geo = geo - rw["geoid_ft"] - rw["elev_ft"]
    z_baro = baro_height_afe(baro, met["qnh_hpa"], met["t_c"], rw["elev_ft"])
    if height_source == "geometric":
        z, src = z_geo, np.where(np.isfinite(z_geo), "geometric", "none")
    elif height_source == "baro":
        z, src = z_baro, np.where(np.isfinite(z_baro), "baro", "none")
    else:
        z = np.where(np.isfinite(z_geo), z_geo, z_baro)
        src = np.where(np.isfinite(z_geo), "geometric", np.where(np.isfinite(z_baro), "baro", "none"))
    # pressure altitude for thrust: reported baro; else from the geometric height (inverse hypsometric)
    h_press = baro.copy()
    miss = ~np.isfinite(h_press) & np.isfinite(z)
    if miss.any():
        T0 = met["t_c"] + 273.15
        qfe = met["qnh_hpa"] * (1 - 6.8755856e-6 * rw["elev_ft"]) ** 5.2558797
        p = qfe * (1 - LAPSE_K_PER_FT * z[miss] / T0) ** (1 / EXP)
        h_press[miss] = (1 - (p / 1013.25) ** (1 / 5.2558797)) / 6.8755856e-6
    gs = pd.to_numeric(o.get("ground_speed_kt"), errors="coerce").to_numpy(float)
    trk = pd.to_numeric(o.get("track_deg"), errors="coerce").to_numpy(float)
    wd, ws = met.get("wind_dir_deg", np.nan), met.get("wind_kt", 0.0) or 0.0
    head = ws * np.cos(np.radians(wd - trk)) if np.isfinite(wd) else np.zeros(len(o))
    head = np.where(np.isfinite(head), head, 0.0)
    r = ratios(rw["elev_ft"] + np.maximum(np.nan_to_num(z, nan=0.0), 0.0), met["t_c"], met["qnh_hpa"], rw["elev_ft"])
    ias = pd.to_numeric(o.get("indicated_airspeed_kt"), errors="coerce").to_numpy(float) if "indicated_airspeed_kt" in o else np.full(len(o), np.nan)
    cas = np.where(np.isfinite(ias), ias, (gs + head) * np.sqrt(r["sigma"]))
    r0 = ratios(rw["elev_ft"], met["t_c"], met["qnh_hpa"], rw["elev_ft"])
    og = o.on_ground if "on_ground" in o else pd.Series(False, index=o.index)
    out = pd.DataFrame({"t_s": o.timestamp_ms.to_numpy() / 1000.0, "x_ft": x, "y_ft": y, "z_ft": z, "z_source": src,
                        "z_geo_ft": z_geo, "z_baro_ft": z_baro, "gs_kt": gs, "cas_kt": cas,
                        "cas_source": np.where(np.isfinite(ias), "IAS", "GS+wind"), "headwind_kt": head,
                        "h_press_ft": h_press, "t_c": r["t_c"], "t_c0": float(r0["t_c"]), "sigma0": float(r0["sigma"]), "h_press0": float(r0["h_press_ft"]),
                        "on_ground": og.astype("boolean").fillna(False).to_numpy(bool),
                        "observation_id": o.get("observation_id", pd.Series(index=o.index, dtype=str)).to_numpy()})
    return out.sort_values("t_s").reset_index(drop=True)
