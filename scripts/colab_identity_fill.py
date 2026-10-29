"""Fill aircraft types that the OpenSky database does not know (new airframes), in Colab (internet access).

    python scripts/colab_identity_fill.py  data/inputs/a3_aircraft_identity.csv  data/inputs/a2/a2_noise_flights.csv

For every icao24 of an accepted departure whose icao_type is empty, queries hexdb.io (community Mode-S database)
and writes data/inputs/a3_aircraft_identity_fill.csv with the same columns (source = hexdb.io, lookup date).
The noise model uses a filled row only where the primary file has no type. Nothing is guessed: not found stays empty.
"""
import datetime as dt
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ident = pd.read_csv(sys.argv[1], dtype=str)
fl = pd.read_csv(sys.argv[2], dtype=str)
acc = set(fl[fl.runway_status == "accepted_departure_candidate"].icao24.str.lower())
known = set(ident[ident.icao_type.fillna("").str.strip() != ""].icao24.str.lower())
todo = sorted(acc - known)
rows = []
for ic in todo:
    url = f"https://hexdb.io/api/v1/aircraft/{ic}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OEJN-noise-research/1.0"})
        j = json.loads(urllib.request.urlopen(req, timeout=30).read())
        rows.append({"icao24": ic, "registration": j.get("Registration", ""), "icao_type": j.get("ICAOTypeCode", ""),
                     "model": j.get("Type", ""), "engine_type": "", "operator_icao": j.get("OperatorFlagCode", ""),
                     "operator": j.get("RegisteredOwners", ""), "source": "hexdb.io", "source_url": url})
    except Exception as e:
        rows.append({"icao24": ic, "registration": "", "icao_type": "", "model": "", "engine_type": "", "operator_icao": "",
                     "operator": "", "source": f"not found ({type(e).__name__})", "source_url": url})
    time.sleep(0.5)
out = pd.DataFrame(rows)
out["lookup_date"] = dt.date.today().isoformat()
p = Path(sys.argv[1]).with_name("a3_aircraft_identity_fill.csv")
out.to_csv(p, index=False)
print(f"{len(todo)} untyped departures' aircraft; type found for {int((out.icao_type.fillna('') != '').sum())} -> {p}")
print(out[["icao24", "registration", "icao_type", "model", "operator"]].to_string())
