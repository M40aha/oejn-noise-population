"""Fetch the two external inputs the noise model needs, in Colab (internet access).

    python colab_external_data.py  a2_noise_flights.csv  out/

1. METAR OEJN for 30 Sep 18Z - 2 Oct 06Z 2026 (temperature, dew point, relative humidity, QNH) from the
   Iowa Environmental Mesonet ASOS/METAR archive -> ext_metar_oejn.csv
2. Aircraft identity for every departure icao24: registration, ICAO type, model, engine, operator.
   Primary source: OpenSky Network aircraft database (monthly CSV). Fallback for missing rows: adsbdb.com API
   (type only, no engine). -> aircraft_identity.csv
Every row records its source and lookup date. Nothing is guessed: missing stays empty.
"""
import datetime as dt
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

UA = {"User-Agent": "OEJN-noise-research/1.0"}


def get(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def metar(out):
    url = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=OEJN&data=tmpc&data=dwpc&data=relh"
           "&data=alti&data=mslp&data=sknt&data=drct&data=metar&year1=2026&month1=9&day1=30&hour1=18"
           "&year2=2026&month2=10&day2=2&hour2=6&tz=Etc%2FUTC&format=onlycomma&latlon=no&missing=empty"
           "&trace=empty&direct=no&report_type=3&report_type=4")
    df = pd.read_csv(io.BytesIO(get(url)))
    df["source"] = "IEM ASOS/METAR archive"
    df["retrieved_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    df.to_csv(out / "ext_metar_oejn.csv", index=False)
    print("METAR rows:", len(df))
    return url


OPENSKY = [  # newest first; the script uses the first that downloads
    "https://s3.opensky-network.org/data-samples/metadata/aircraft-database-complete-2025-08.csv",
    "https://s3.opensky-network.org/data-samples/metadata/aircraft-database-complete-2025-02.csv",
    "https://s3.opensky-network.org/data-samples/metadata/aircraft-database-complete-2024-10.csv",
    "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv",
]


def identity(flights_csv, out):
    icaos = sorted(set(pd.read_csv(flights_csv).icao24.str.lower()))
    db, used = None, None
    for u in OPENSKY:
        try:
            raw = get(u, timeout=600)
            db = pd.read_csv(io.BytesIO(raw), dtype=str, quotechar="'" if raw[:1] == b"'" else '"', on_bad_lines="skip")
            used = u
            break
        except Exception as e:
            print("OpenSky DB not available at", u, "->", e)
    rows = []
    if db is not None:
        db.columns = [c.strip("'\" ").lower() for c in db.columns]
        db["icao24"] = db["icao24"].str.strip("'\" ").str.lower()
        sub = db[db.icao24.isin(icaos)]
        for _, r in sub.iterrows():
            g = lambda k: (str(r.get(k)).strip("'\" ") if pd.notna(r.get(k)) else "")
            rows.append({"icao24": r.icao24, "registration": g("registration"), "icao_type": g("typecode"),
                         "model": g("model"), "engine_type": g("engines"), "operator_icao": g("operatoricao"),
                         "operator": g("operator"), "source": "OpenSky aircraft database", "source_url": used})
    found = {r["icao24"] for r in rows if r["icao_type"]}
    for ic in [i for i in icaos if i not in found]:
        try:
            j = json.loads(get(f"https://api.adsbdb.com/v0/aircraft/{ic}", timeout=30))
            a = j.get("response", {}).get("aircraft", {})
            rows = [r for r in rows if r["icao24"] != ic]
            rows.append({"icao24": ic, "registration": a.get("registration", ""), "icao_type": a.get("icao_type", ""),
                         "model": a.get("type", ""), "engine_type": "", "operator_icao": a.get("registered_owner_operator_flag_code", ""),
                         "operator": a.get("registered_owner", ""), "source": "adsbdb.com", "source_url": f"https://api.adsbdb.com/v0/aircraft/{ic}"})
        except Exception:
            if ic not in {r["icao24"] for r in rows}:
                rows.append({"icao24": ic, "registration": "", "icao_type": "", "model": "", "engine_type": "",
                             "operator_icao": "", "operator": "", "source": "not found", "source_url": ""})
        time.sleep(0.3)
    df = pd.DataFrame(rows)
    df["lookup_date"] = dt.date.today().isoformat()
    df.to_csv(out / "aircraft_identity.csv", index=False)
    print(f"aircraft: {len(icaos)} icao24, type found {int((df.icao_type != '').sum())}, engine found {int((df.engine_type != '').sum())}")


if __name__ == "__main__":
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "out")
    out.mkdir(parents=True, exist_ok=True)
    metar(out)
    identity(sys.argv[1], out)
