# Map 2 + departure noise — local copy

A copy of the team's **Map 2 · Departure Studio** (M-AlGhazali/Research-and-Innovation-department-SANS-project, `map-2/`)
with one addition: a **Noise · 1 Oct 2026** panel. It draws the departure-noise results of this repository on the ground of
the 3D scene:
- **Lden:** day–night level.
- **N70:** departures with LAmax ≥ 70 dB.
- **Flown:** observed departures per 250 m cell.

The team repository is **not modified**. Its files are copied unchanged (sha256 in `SOURCE.json`). Only two of them get a
small patch, made and checked by `scripts/build_map3d.py`:
- `studio.js`: mounts the noise layer.
- `index.html`: noise stylesheet, title and header label.

## Open

- **Double-click:** `OEJN_Map3D_Noise.html`. One file with everything embedded; open it in Chrome or Edge with WebGL.
- **Or serve the folder:** `python -m http.server 8000` inside `map3d/`, then open http://127.0.0.1:8000/.

## Rebuild after a new noise run or a new Map 2

```bash
PYTHONPATH=src python -m noise.run
PYTHONPATH=src python scripts/build_map3d.py ../Research-and-Innovation-department-SANS-project-main
```

## Local use only

The noise layer is derived from Wingbits ADS-B data (evaluation use, via A2). Do **not** deploy this folder to a public
site (e.g. GitHub Pages) until the team has confirmed that publishing aggregated results is permitted. The map shows
aggregates only, never individual flights. The procedure playback inside Map 2 is the team's illustrative demo, as in
the original.
