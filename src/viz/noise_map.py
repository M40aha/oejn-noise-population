"""Presentation data for the 3D noise map: noise grids, contours, typical flight paths and a light basemap.

Frame: kilometres east / north of the aerodrome reference point in UTM 37N (EPSG:32637), the CRS of A2, A6 and the
noise grid, so every layer overlays without reprojection error.

Typical flight paths are aggregates: flights are grouped by runway and by the 20-degree sector in which they leave a 40 km
circle around the airport; each group with >= 3 departures is drawn as the median track (point-wise median after
resampling every 1 km along the path). No individual flight is exported.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import contourpy
import numpy as np
import pandas as pd
import yaml
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as sh_transform

TO_UTM = Transformer.from_crs(4326, 32637, always_xy=True)
R_EXIT_KM, SECTOR_DEG = 40.0, 20.0   # typical paths: group by bearing where the track leaves a 40 km circle
LEVELS = {"lden": [45, 50, 55, 60, 65, 70, 75], "lnight": [40, 45, 50, 55, 60, 65], "n70": [1, 5, 10, 20, 50, 100]}


def _r(v, n=2):
    return round(float(v), n)


def _geoms(g):
    return list(g.geoms) if hasattr(g, "geoms") else [g]


def map_block(root: Path) -> dict:
    cfg = yaml.safe_load((root / "config" / "noise.yaml").read_text())
    E0, N0 = TO_UTM.transform(cfg["aerodrome"]["arp_lon"], cfg["aerodrome"]["arp_lat"])
    g = pd.read_parquet(root / "data" / "noise" / "processed" / "noise_grid.parquet")
    n = int(round(np.sqrt(len(g))))
    g = g.sort_values(["y_utm37n_m", "x_utm37n_m"]).reset_index(drop=True)
    X = (g.x_utm37n_m.to_numpy().reshape(n, n) - E0) / 1000
    Y = (g.y_utm37n_m.to_numpy().reshape(n, n) - N0) / 1000
    out = {"cell_km": _r(X[0, 1] - X[0, 0], 4), "n": n, "x0": _r(X[0, 0], 4), "y0": _r(Y[0, 0], 4), "grids": {}, "contours": {}}
    for key, col in (("lden", "Lden"), ("lnight", "Lnight"), ("n70", "N70")):
        Z = g[col].to_numpy(float).reshape(n, n)
        Z = np.nan_to_num(Z, nan=0.0)
        b = np.clip(np.round(Z), 0, 255).astype(np.uint8)
        out["grids"][key] = base64.b64encode(b.tobytes()).decode("ascii")
        gen = contourpy.contour_generator(X, Y, Z)
        out["contours"][key] = {}
        for lv in LEVELS[key]:
            lines = []
            for seg in gen.lines(lv):
                if len(seg) < 4:
                    continue
                seg = seg[:: max(1, len(seg) // 400)]
                lines.append([v for x, y in seg for v in (_r(x), _r(y))])
            out["contours"][key][str(lv)] = lines
    # basemap
    bm = root / "data" / "external" / "basemap"
    def proj(x, y, z=None):
        ux, uy = TO_UTM.transform(np.asarray(x), np.asarray(y))
        return (np.asarray(ux) - E0) / 1000, (np.asarray(uy) - N0) / 1000
    land = []
    for f in json.loads((bm / "ne_10m_land_jeddah.geojson").read_text())["features"]:
        geom = sh_transform(proj, shape(f["geometry"])).simplify(0.05)
        for p in _geoms(geom):
            land.append([v for x, y in p.exterior.coords for v in (_r(x), _r(y))])
    to_km = lambda x, y, z=None: ((np.asarray(x) - E0) / 1000, (np.asarray(y) - N0) / 1000)
    roads = {"major": [], "secondary": []}
    for f in json.loads((bm / "osm_roads_utm37n.geojson").read_text())["features"]:
        k = "secondary" if f["properties"]["kind"].startswith("secondary") else "major"
        for ln in _geoms(sh_transform(to_km, shape(f["geometry"]))):
            roads[k].append([v for x, y in ln.coords for v in (_r(x), _r(y))])
    ne_roads = []
    for f in json.loads((bm / "ne_10m_roads_jeddah.geojson").read_text())["features"]:
        for ln in _geoms(sh_transform(proj, shape(f["geometry"]))):
            if ln.geom_type == "LineString":
                ne_roads.append([v for x, y in ln.coords for v in (_r(x), _r(y))])
    coast = []
    for f in json.loads((bm / "osm_coastline_utm37n.geojson").read_text())["features"]:
        for ln in _geoms(sh_transform(to_km, shape(f["geometry"]).simplify(20))):
            if ln.geom_type == "LineString":
                coast.append([v for x, y in ln.coords for v in (_r(x), _r(y))])
    places = []
    for f in json.loads((bm / "osm_places_utm37n.geojson").read_text())["features"]:
        x, y = f["geometry"]["coordinates"][:2]
        if f["properties"]["name"].startswith("King Abdulaziz"):
            continue
        places.append({"x": _r((x - E0) / 1000), "y": _r((y - N0) / 1000), "en": f["properties"]["name"], "ar": f["properties"].get("name_ar")})
    for f in json.loads((bm / "ne_10m_populated_places_simple_jeddah.geojson").read_text())["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        x, y = TO_UTM.transform(lon, lat)
        if f["properties"].get("name") == "Jeddah":
            places.append({"x": _r((x - E0) / 1000), "y": _r((y - N0) / 1000), "en": "Jeddah", "ar": "جدة", "city": True})
    # population (A6 600 m grid) as residents per km2
    a6 = pd.read_parquet(root / "data" / "a6" / "processed" / "a6_grid_6px.parquet")
    px, py = TO_UTM.transform(a6.lon_c.to_numpy(), a6.lat_c.to_numpy())
    kx, ky = (px - E0) / 1000, (py - N0) / 1000
    m = (np.abs(kx) <= 46) & (np.abs(ky) <= 46) & (a6.population.to_numpy() > 0)
    area = (a6.bin_deg.iloc[0] * 110.574) * (a6.bin_deg.iloc[0] * 111.32 * np.cos(np.radians(21.7)))
    pop = [[_r(a, 2), _r(b, 2), int(round(p / area))] for a, b, p in zip(kx[m], ky[m], a6.population.to_numpy()[m])]
    # runways
    rw = pd.read_csv(root / cfg["inputs"]["runways_csv"])
    runways = []
    for r in rw[rw.runway_end.isin(["34C", "34L", "34R"])].itertuples():
        a = TO_UTM.transform(r.threshold_longitude_deg, r.threshold_latitude_deg)
        b = TO_UTM.transform(r.opposite_threshold_longitude_deg, r.opposite_threshold_latitude_deg)
        runways.append({"id": r.runway_end, "a": [_r((a[0] - E0) / 1000, 3), _r((a[1] - N0) / 1000, 3)],
                        "b": [_r((b[0] - E0) / 1000, 3), _r((b[1] - N0) / 1000, 3)]})
    out.update({"land": land, "coast": coast, "roads": roads, "ne_roads": ne_roads, "places": places, "pop": pop,
                "pop_cell_km": _r(a6.bin_deg.iloc[0] * 110.574, 3), "runways": runways, "paths": typical_paths(root, E0, N0)})
    return out


def typical_paths(root: Path, E0: float, N0: float, min_n: int = 3) -> list:
    nodes_p = root / "data" / "noise" / "interim" / "flight_path_nodes.parquet"
    if not nodes_p.exists():
        return []
    nd = pd.read_parquet(nodes_p)
    fr = pd.read_csv(root / "data" / "noise" / "processed" / "flight_results.csv")[["flight_id", "runway"]]
    nd = nd.merge(fr, on="flight_id")
    groups = {}
    for (fid, rwy), d in nd.groupby(["flight_id", "runway"], sort=False):
        x, y = d.x_ft.to_numpy() * 0.3048 / 1000, d.y_ft.to_numpy() * 0.3048 / 1000
        s = np.r_[0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
        r = np.hypot(x, y)
        k = int(np.argmax(r >= R_EXIT_KM)) if (r >= R_EXIT_KM).any() else len(r) - 1
        if r[k] < 15:
            continue
        brg = (np.degrees(np.arctan2(x[k], y[k])) + 360) % 360
        key = (rwy, int(((brg + SECTOR_DEG / 2) % 360) // SECTOR_DEG))
        grid = np.arange(0, min(s[-1], 80) + 1e-9, 1.0)
        groups.setdefault(key, []).append((np.interp(grid, s, x), np.interp(grid, s, y), brg, np.interp(grid, s, d.z_ft.to_numpy())))
    paths = []
    for (rwy, sector), tr in groups.items():
        if len(tr) < min_n:
            continue
        L = max(len(t[0]) for t in tr)
        med, alt = [], []
        for i in range(L):
            have = [(t[0][i], t[1][i], t[3][i]) for t in tr if len(t[0]) > i]
            if len(have) < 0.6 * len(tr):
                break
            a = np.array(have)
            med.append([_r(np.median(a[:, 0])), _r(np.median(a[:, 1]))])
            alt.append(int(round(np.median(a[:, 2]))))
        paths.append({"runway": rwy, "n": len(tr), "bearing": int(round(np.median([t[2] for t in tr]))), "path": med, "alt_ft": alt})
    return sorted(paths, key=lambda p: -p["n"])
