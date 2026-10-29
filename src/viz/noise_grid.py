"""500 m presentation grid of a noise run: Lden, Lnight, N70 and flown-departure density per cell.

Used by the atlas and the 3D map. Density counts departures whose modelled flight path crosses a cell
(aggregate only; no individual track leaves this function).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pyproj import Transformer

TO_UTM = Transformer.from_crs(4326, 32637, always_xy=True)


def grid500(root: Path, step: int = 2) -> tuple[pd.DataFrame, dict]:
    cfg = yaml.safe_load((root / "config" / "noise.yaml").read_text())
    g = pd.read_parquet(root / "data" / "noise" / "processed" / "noise_grid.parquet")
    n = int(round(np.sqrt(len(g))))
    idx = np.arange(len(g)).reshape(n, n)[::step, ::step]
    m = idx.shape[0]
    s = g.iloc[idx.ravel()].reset_index(drop=True)
    E0, N0 = TO_UTM.transform(cfg["aerodrome"]["arp_lon"], cfg["aerodrome"]["arp_lat"])
    cell = cfg["grid"]["spacing_m"] * step
    xs = np.sort(s.x_utm37n_m.unique())
    ys = np.sort(s.y_utm37n_m.unique())
    dens = np.zeros((m, m), int)                       # rows = northing index (ascending), cols = easting index
    nodes_p = root / "data" / "noise" / "interim" / "flight_path_nodes.parquet"
    if nodes_p.exists():
        nd = pd.read_parquet(nodes_p, columns=["flight_id", "x_ft", "y_ft"])
        for _, d in nd.groupby("flight_id", sort=False):
            e = E0 + d.x_ft.to_numpy() * 0.3048
            nn = N0 + d.y_ft.to_numpy() * 0.3048
            L = np.hypot(np.diff(e), np.diff(nn))
            pts = np.vstack([np.c_[np.linspace(e[i], e[i + 1], int(L[i] // 100) + 2), np.linspace(nn[i], nn[i + 1], int(L[i] // 100) + 2)]
                             for i in range(len(L))])
            ci = np.round((pts[:, 0] - xs[0]) / cell).astype(int)
            cj = np.round((pts[:, 1] - ys[0]) / cell).astype(int)
            ok = (ci >= 0) & (ci < m) & (cj >= 0) & (cj < m)
            cells = np.unique(cj[ok] * m + ci[ok])
            dens.ravel()[cells] += 1
    ii = np.round((s.x_utm37n_m.to_numpy() - xs[0]) / cell).astype(int)
    jj = np.round((s.y_utm37n_m.to_numpy() - ys[0]) / cell).astype(int)
    s["dens"] = dens[jj, ii]
    meta = {"cell_m": cell, "n": m, "x0": float(xs[0]), "y0": float(ys[0]), "E0": E0, "N0": N0, "release": cfg["release_id"]}
    return s, meta
