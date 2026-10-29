"""SYNTHETIC inputs for exercising the noise pipeline before the real A2 / METAR / aircraft-identity files arrive.

    python scripts/make_synthetic_noise_inputs.py  <out_dir>  [n_flights]

Writes <out_dir>/a2/{a2_noise_departures.parquet, a2_noise_flights.csv}, <out_dir>/ext_metar_oejn.csv and
<out_dir>/aircraft_identity.csv with the exact schemas of the real files. Trajectories are kinematic
departures from 34C / 34L (ground roll, climb, acceleration, a turn) sampled every 2 s with 25-ft altitude
quantisation. Every value is invented: results computed from these files are NOT study results.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

FT, KT = 0.3048, 0.514444
TO_UTM = Transformer.from_crs(4326, 32637, always_xy=True)
TO_LL = Transformer.from_crs(32637, 4326, always_xy=True)
RW = {"34C": (21.6611805556, 39.1649194444, 21.6950722222, 39.1515472222, 28.6),
      "34L": (21.6705611111, 39.1395944444, 21.7027583333, 39.1268833333, 15.5)}
TYPES = [("710101", "A320", "Airbus A320-214", "CFM56-5B4/3"), ("710102", "B789", "Boeing 787-9", "GEnx-1B74/75"),
         ("710103", "A20N", "Airbus A320-251N", "LEAP-1A26"), ("710104", "B77W", "Boeing 777-368ER", "GE90-115B"),
         ("710105", "A333", "Airbus A330-343", "Trent 772B-60"), ("710106", "ZZZZ", "", "")]


def press_alt(z_afe_ft, elev_ft, qnh=1010.0, t_c=30.0):
    """inverse of noise.site.baro_height_afe (ISA lapse, actual aerodrome temperature)"""
    qfe = qnh * (1 - 6.8755856e-6 * elev_ft) ** 5.2558797
    p = qfe * (1 - 0.0019812 * z_afe_ft / (t_c + 273.15)) ** (1 / 0.190263)
    return (1 - (p / 1013.25) ** (1 / 5.2558797)) / 6.8755856e-6


def departure(rw, t0_ms, turn_deg, rng, v_lo_kt=150.0, roll_m=1900.0, step_s=2.0, wind=(330.0, 8.0)):
    la1, lo1, la2, lo2, elev = RW[rw]
    e1, n1 = TO_UTM.transform(lo1, la1)
    e2, n2 = TO_UTM.transform(lo2, la2)
    hdg = np.arctan2(e2 - e1, n2 - n1)
    a = (v_lo_kt * KT) ** 2 / (2 * roll_m)
    rows, t = [], 0.0
    e, n, z, v, h = e1, n1, 0.0, 0.0, hdg
    turn_start, turned = None, 0.0
    while t < 900 and z < 18000 * FT:
        if z <= 0 and v < v_lo_kt * KT:            # ground roll
            v = min(v + a * step_s, v_lo_kt * KT)
            on_ground, climb = True, 0.0
        else:
            on_ground = False
            climb = (2500 if z < 3000 * FT else 1800) / 60 * FT
            if z > 1000 * FT:
                v = min(v + 0.8 * step_s, 290 * KT)
            if z > 2000 * FT and abs(turned) < abs(np.radians(turn_deg)):
                d = np.sign(turn_deg) * np.radians(1.5) * step_s
                h += d
                turned += d
        e += v * np.sin(h) * step_s
        n += v * np.cos(h) * step_s
        z = z + climb * step_s if not on_ground or v >= v_lo_kt * KT else 0.0
        t += step_s
        lon, lat = TO_LL.transform(e, n)
        wdir, wspd = wind
        trk = np.degrees(h) % 360
        gs = v / KT - wspd * np.cos(np.radians(wdir - trk))
        msl = z / FT + elev
        rows.append({"timestamp_ms": int(t0_ms + t * 1000), "latitude_deg": lat, "longitude_deg": lon, "easting_m": e,
                     "northing_m": n, "barometric_altitude_ft": int(round(press_alt(z / FT, elev) / 25) * 25) if not on_ground else None,
                     "geometric_altitude_ft": float(round(msl + 14.8 + rng.normal(0, 15))) if not on_ground else None,
                     "ground_speed_kt": round(gs + rng.normal(0, 1), 1), "indicated_airspeed_kt": None, "track_deg": round(trk, 1),
                     "on_ground": on_ground, "quality_flags": "", "observation_id": f"syn{t0_ms}{int(t)}"})
    return pd.DataFrame(rows)


def main(out, n=12):
    out = Path(out)
    (out / "a2").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    obs, fl = [], []
    for i in range(n):
        icao, *_ = TYPES[i % len(TYPES)]
        rw = "34C" if i % 3 else "34L"
        t0 = int(pd.Timestamp("2026-10-01T00:00Z").value // 1e6) + int(i * 86400e3 / n)
        d = departure(rw, t0, [-60, 40, 90, -20][i % 4], rng)
        fid = f"OEJN-2026-10-01-{icao}-{t0}"
        d.insert(0, "flight_id", fid)
        d.insert(1, "icao24", icao)
        d.insert(2, "callsign", f"SYN{i:03d}")
        obs.append(d)
        fl.append({"flight_id": fid, "icao24": icao, "start_ms": int(d.timestamp_ms.min()), "end_ms": int(d.timestamp_ms.max()),
                   "anchor_ms": int(d[~d.on_ground].timestamp_ms.min()), "runway": rw, "runway_status": "accepted_departure_candidate",
                   "match_status": "unmatched", "procedure": None})
    fl.append({"flight_id": "OEJN-2026-10-01-7101ff-0", "icao24": "7101ff", "start_ms": 0, "end_ms": 1, "anchor_ms": 0, "runway": None,
               "runway_status": "insufficient_evidence", "match_status": "insufficient_data", "procedure": None})
    pd.concat(obs).to_parquet(out / "a2" / "a2_noise_departures.parquet", index=False)
    pd.DataFrame(fl).to_csv(out / "a2" / "a2_noise_flights.csv", index=False)
    hours = pd.date_range("2026-09-30T18:00Z", "2026-10-02T06:00Z", freq="1h")
    met = pd.DataFrame({"station": "OEJN", "valid": hours.strftime("%Y-%m-%d %H:%M"), "tmpc": 30 + 4 * np.sin((hours.hour - 6) / 24 * 2 * np.pi),
                        "dwpc": 22.0, "relh": np.nan, "alti": 29.83, "mslp": np.nan, "sknt": 8, "drct": 330})
    met["metar"] = [f"OEJN {h:%d%H%M}Z 33008KT CAVOK {int(t):02d}/22 Q1010 NOSIG" for h, t in zip(hours, met.tmpc)]
    met.to_csv(out / "ext_metar_oejn.csv", index=False)
    pd.DataFrame([{"icao24": i, "registration": f"HZ-SY{k}", "icao_type": ty, "model": m, "engine_type": en, "operator_icao": "SYN",
                   "operator": "SYNTHETIC", "source": "synthetic", "source_url": "", "lookup_date": "2026-10-28"}
                  for k, (i, ty, m, en) in enumerate(TYPES)]).replace({"icao_type": {"ZZZZ": ""}}).to_csv(out / "aircraft_identity.csv", index=False)
    print("synthetic inputs written to", out)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 12)
