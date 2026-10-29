# Map 2 + departure noise — local copy

A copy of the team's **Map 2 · Departure Studio** (M-AlGhazali/Research-and-Innovation-department-SANS-project, `map-2/`)
with one addition: a **Noise · 1 Oct 2026** panel. It shows the departure-noise results of this repository in the 3D
scene:
- **Graded noise surface** (green → yellow → orange → red → dark red) for **Day–night (Lden)**, **Night (Lnight)** or
  **Loud events (N70)**, with contour lines.
- **Typical flight paths in 3D:** median track and median observed height of each group of departures, thickness by
  number of departures, coloured by runway, with a dashed ground shadow.
- **Neighbourhood names** (OpenStreetMap, Arabic and English).
- **Legend:** what each colour means and how many residents live in it.
- **Live ▶ (illustrative):** while Map 2 plays a departure, the ground shows the instantaneous noise under the moving
  aircraft (bright) and the loudest level reached so far (faded), with a dashed line down from the aircraft. It follows
  Map 2's concept playback (published procedure, demo heights) and uses a typical A320 (ANP A320-211, NPD CFM565 LAmax) at
  full take-off / climb thrust with Doc 29 lateral attenuation. It is a teaching view; the study results are the
  Day–night / Night / Loud-events layers computed from the observed flights.
- **– / +** in the panel header minimises / restores the panel (remembered in the browser).
- **Results ↗:** headline numbers, people per noise band, runway and aircraft comparisons, WHO indicators, method,
  validation and limits.

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
