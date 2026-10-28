"""OEJN RNAV SIDs, RWY 34C (2W) and 34L (3X), for VISUALISATION in the A5/A6 atlas.

Transcribed from Saudi AIP AD 2 OEJN-110/111/114/115 (AIP AMDT 10/26, 17 SEP 2026).
This is NOT the A1 deliverable (the A1 owner's dataset is authoritative). Every fix-to-fix (TF) leg is
checked against the published leg distance; the CF leg from the runway to the first fix is not drawn as a
published path because runway-threshold coordinates are not in the project data.
"""
from __future__ import annotations

import numpy as np
from pyproj import Geod

GEOD = Geod(ellps="WGS84")


def _dms(d, m, s):
    return d + m / 60 + s / 3600


WAYPOINTS = {  # name: (lat, lon)
    # RWY 34C list (AD 2 OEJN-115)
    "JN274": (_dms(22, 21, 30), _dms(38, 42, 47)), "BOMOX": (_dms(22, 29, 49), _dms(38, 27, 4)),
    "DENBU": (_dms(21, 1, 29), _dms(38, 20, 31)), "EGREP": (_dms(22, 27, 54), _dms(39, 50, 7)),
    "JN234": (_dms(22, 15, 36), _dms(38, 53, 54)), "JN259": (_dms(21, 6, 12), _dms(39, 32, 5)),
    "JN383": (_dms(22, 9, 53), _dms(38, 56, 37)), "JN520": (_dms(22, 23, 57), _dms(39, 31, 45)),
    "JN522": (_dms(21, 19, 57), _dms(39, 1, 7)), "JN610": (_dms(21, 38, 33), _dms(38, 42, 25)),
    "KAROX": (_dms(20, 57, 17), _dms(38, 15, 47)), "NIVBA": (_dms(21, 47, 22), _dms(38, 49, 56)),
    "RIBAM": (_dms(20, 42, 31), _dms(39, 5, 51)), "ASPAG": (_dms(22, 4, 13), _dms(38, 43, 1)),
    "DATAP": (_dms(22, 39, 27), _dms(39, 29, 10)), "EGPOB": (_dms(20, 55, 28), _dms(39, 47, 10)),
    "ISLAM": (_dms(21, 46, 48), _dms(39, 52, 0)), "JN254": (_dms(21, 53, 47), _dms(39, 4, 19)),
    "JN276": (_dms(22, 0, 23), _dms(39, 1, 10)), "JN510": (_dms(22, 33, 59), _dms(39, 22, 51)),
    "JN521": (_dms(21, 10, 31), _dms(39, 4, 57)), "JN530": (_dms(22, 11, 32), _dms(39, 24, 12)),
    "JN733": (_dms(21, 23, 30), _dms(38, 29, 36)), "MIGDA": (_dms(22, 38, 29), _dms(38, 42, 53)),
    "RALVI": (_dms(22, 18, 2), _dms(39, 4, 30)),
    # RWY 34L list (AD 2 OEJN-111), names not already above
    "JN264": (_dms(21, 40, 10), _dms(38, 53, 30)), "JN266": (_dms(22, 9, 46), _dms(38, 40, 10)),
    "JN272": (_dms(21, 46, 9), _dms(39, 5, 7)), "JN278": (_dms(21, 19, 58), _dms(38, 36, 11)),
    "JN279": (_dms(21, 16, 27), _dms(38, 33, 12)), "JN382": (_dms(21, 10, 17), _dms(38, 41, 32)),
    "JN385": (_dms(21, 4, 56), _dms(38, 46, 19)), "JN390": (_dms(21, 6, 17), _dms(38, 59, 28)),
    "JN395": (_dms(21, 1, 35), _dms(39, 20, 19)), "ORSOD": (_dms(21, 52, 53), _dms(38, 56, 29)),
    "SERSO": (_dms(22, 4, 11), _dms(38, 51, 6)),
}

# (sid, runway, exit, fixes after the runway, published TF leg distances in NM; None = CF leg, no distance)
_C = ["JN254", "JN276", "JN383"]
_Cd = [None, 7.2, 10.4]
SIDS = [
    ("ISLAM2W", "34C", "ISLAM", _C + ["RALVI", "JN530", "ISLAM"], _Cd + [10.9, 19.4, 35.7]),
    ("EGREP2W", "34C", "EGREP", _C + ["RALVI", "JN520", "EGREP"], _Cd + [10.9, 25.9, 17.5]),
    ("DATAP2W", "34C", "DATAP", _C + ["RALVI", "JN510", "DATAP"], _Cd + [10.9, 23.3, 8.0]),
    ("MIGDA2W", "34C", "MIGDA", _C + ["JN234", "MIGDA"], _Cd + [6.2, 25.0]),
    ("BOMOX2W", "34C", "BOMOX", _C + ["JN234", "JN274", "BOMOX"], _Cd + [6.2, 11.8, 16.7]),
    ("EGPOB2W", "34C", "EGPOB", _C + ["ASPAG", "NIVBA", "JN522", "JN521", "JN259", "EGPOB"], _Cd + [13.8, 18.0, 29.2, 10.1, 25.7, 17.7]),
    ("RIBAM2W", "34C", "RIBAM", _C + ["ASPAG", "NIVBA", "JN522", "JN521", "RIBAM"], _Cd + [13.8, 18.0, 29.2, 10.1, 27.9]),
    ("KAROX2W", "34C", "KAROX", _C + ["ASPAG", "NIVBA", "JN610", "JN733", "DENBU", "KAROX"], _Cd + [13.8, 18.0, 11.2, 19.2, 23.5, 6.1]),
    ("ISLAM3X", "34L", "ISLAM", ["JN272", "ORSOD", "SERSO", "JN383", "RALVI", "JN530", "ISLAM"], [None, None, 12.3, 7.6, 10.9, 19.4, 35.7]),
    ("EGREP3X", "34L", "EGREP", ["JN272", "ORSOD", "SERSO", "JN383", "RALVI", "JN520", "EGREP"], [None, None, 12.3, 7.6, 10.9, 25.9, 17.5]),
    ("DATAP3X", "34L", "DATAP", ["JN272", "ORSOD", "SERSO", "JN383", "RALVI", "JN510", "DATAP"], [None, None, 12.3, 7.6, 10.9, 23.3, 8.0]),
    ("BOMOX3X", "34L", "BOMOX", ["JN272", "ORSOD", "SERSO", "JN266", "BOMOX"], [None, None, 12.3, 11.6, 23.4]),
    # tabulation 1 prints 'JN300' here; the routing text and waypoint list give JN390 (flagged as an AIP inconsistency)
    ("EGPOB3X", "34L", "EGPOB", ["JN272", "JN264", "JN278", "JN382", "JN390", "JN395", "EGPOB"], [None, None, 25.9, 10.9, 17.2, 20.1, 25.8]),
    ("RIBAM3X", "34L", "RIBAM", ["JN272", "JN264", "JN278", "JN382", "JN385", "RIBAM"], [None, None, 25.9, 10.9, 7.0, 28.9]),
    ("KAROX3X", "34L", "KAROX", ["JN272", "JN264", "JN278", "JN279", "DENBU", "KAROX"], [None, None, 25.9, 4.5, 19.0, 6.1]),
    ("MIGDA3X", "34L", "MIGDA", ["JN272", "ORSOD", "SERSO", "JN274", "MIGDA"], [None, None, 12.3, 18.9, 16.9]),
]

AIP_NOTES = [
    "EGPOB3X tabulation 1 (AD 2 OEJN-110) lists JN300; the routing text and waypoint list (AD 2 OEJN-111) give JN390.",
    "EGREP2W and RIBAM2W tabulation rows show magnetic variation '3.8' without the minus sign used elsewhere (-3.8).",
    "RIBAM2W tabulation shows '@`2000' for JN521; the routing text gives 12000 ft.",
    "The CF leg JN272 -> ORSOD / JN264 (RWY 34L) has no published distance.",
]

NM = 1852.0


def leg_check() -> list[dict]:
    """Compare geodesic fix-to-fix distances with the published leg distances."""
    out = []
    for sid, rwy, _, fixes, dists in SIDS:
        for a, b, d in zip(fixes[:-1], fixes[1:], dists[1:]):
            if d is None:
                continue
            (la1, lo1), (la2, lo2) = WAYPOINTS[a], WAYPOINTS[b]
            _, _, m = GEOD.inv(lo1, la1, lo2, la2)
            out.append({"sid": sid, "from": a, "to": b, "published_nm": d, "computed_nm": m / NM, "diff_nm": m / NM - d})
    return out


def polyline(sid_fixes: list[str], step_m: float = 500.0) -> np.ndarray:
    """Geodesic densified polyline (lon, lat) through the fixes."""
    pts = []
    for a, b in zip(sid_fixes[:-1], sid_fixes[1:]):
        (la1, lo1), (la2, lo2) = WAYPOINTS[a], WAYPOINTS[b]
        _, _, m = GEOD.inv(lo1, la1, lo2, la2)
        n = max(int(m // step_m), 1)
        mid = GEOD.npts(lo1, la1, lo2, la2, n - 1) if n > 1 else []
        pts += [(lo1, la1)] + list(mid)
    la, lo = WAYPOINTS[sid_fixes[-1]]
    pts.append((lo, la))
    return np.array(pts)
