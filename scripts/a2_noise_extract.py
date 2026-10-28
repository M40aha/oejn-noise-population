"""Extract the departure trajectories needed by the noise model from the A2 pipeline outputs.

Run on the machine that holds the A2 outputs (SANS-output/a2/2026-10-01/):
    python a2_noise_extract.py  <a2_output_dir>  <out_dir>

Keeps every reconstructed departure (any runway status, flagged), its procedure-match result, and the
observations from the event start until the aircraft leaves 100 km of OEJN or climbs above 20,000 ft
(noise beyond that is negligible at the ground). Values are copied unchanged; nothing is interpolated.
Needs: duckdb, pandas, pyarrow.
"""
import hashlib
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

ARP = (21.6811111111, 39.1561111111)
MAX_KM, MAX_FT = 100.0, 20000.0
COLS = ["icao24", "callsign", "timestamp_ms", "latitude_deg", "longitude_deg", "easting_m", "northing_m",
        "barometric_altitude_ft", "geometric_altitude_ft", "ground_speed_kt", "indicated_airspeed_kt",
        "track_deg", "true_heading_deg", "barometric_rate_fpm", "geometric_rate_fpm", "on_ground",
        "quality_flags", "observation_id"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main(a2, out):
    a2, out = Path(a2), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    flights = json.loads((a2 / "flights.json").read_text())
    flights = flights if isinstance(flights, list) else flights.get("flights", flights.get("records", []))
    matches = json.loads((a2 / "matches.json").read_text())
    matches = matches if isinstance(matches, list) else matches.get("matches", matches.get("records", []))
    mt = {m["flight_id"]: m for m in matches}
    fl = pd.DataFrame([{
        "flight_id": f["flight_id"], "icao24": f["icao24"], "start_ms": f["start_ms"], "end_ms": f["end_ms"],
        "anchor_ms": f["anchor_ms"], "runway": f.get("runway"), "runway_status": f.get("runway_status"),
        "match_status": mt.get(f["flight_id"], {}).get("status"),
        "procedure": mt.get(f["flight_id"], {}).get("best_candidate"),
    } for f in flights])
    con = duckdb.connect()
    con.register("fl", fl)
    have = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{a2 / 'observations.parquet'}')").fetchall()]
    cols = ", ".join(f"o.{c}" for c in COLS if c in have)
    obs = con.execute(f"""
        SELECT fl.flight_id, {cols}
        FROM read_parquet('{a2 / 'observations.parquet'}') o
        JOIN fl ON o.icao24 = fl.icao24 AND o.timestamp_ms BETWEEN fl.start_ms AND fl.end_ms
        ORDER BY fl.flight_id, o.timestamp_ms""").df()
    dlat = (obs.latitude_deg - ARP[0]) * 111.32
    dlon = (obs.longitude_deg - ARP[1]) * 111.32 * 0.9295
    inside = ((dlat ** 2 + dlon ** 2) ** 0.5 <= MAX_KM) & (obs.barometric_altitude_ft.fillna(0) <= MAX_FT)
    # keep each flight from its first report until it first leaves the noise envelope
    obs["_out"] = (~inside).astype(int).groupby(obs.flight_id).cumsum()
    obs = obs[obs._out == 0].drop(columns="_out")
    obs.to_parquet(out / "a2_noise_departures.parquet", index=False, compression="zstd")
    fl.to_csv(out / "a2_noise_flights.csv", index=False)
    man = {"inputs": {n: sha(a2 / n) for n in ("flights.json", "matches.json", "observations.parquet")},
           "envelope": {"max_km_from_arp": MAX_KM, "max_baro_alt_ft": MAX_FT},
           "flights": int(len(fl)), "flights_with_points": int(obs.flight_id.nunique()), "points": int(len(obs)),
           "by_runway_status": fl.groupby(["runway", "runway_status"], dropna=False).size().reset_index().astype(str).values.tolist()}
    (out / "a2_noise_manifest.json").write_text(json.dumps(man, indent=2))
    print(json.dumps(man, indent=2))
    print("size MB:", round((out / "a2_noise_departures.parquet").stat().st_size / 1e6, 2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
