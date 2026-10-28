# A6 methodology — population exposure layer

*Written for direct reuse in the research methodology section.*

## 1. Purpose and scope
A6 turns the WorldPop 2026 population raster into **population receptors**: one point per populated
100 m cell, carrying the number of people in that cell, ready for the noise model to evaluate noise at each
point and sum exposed population. A6 does not compute noise; it fixes *where people are* and *how many*.

## 2. Source

| Item | Value |
|---|---|
| Dataset | WorldPop Global2 **R2025A v1**, Saudi Arabia, **2026**, constrained (CN), 100 m |
| Unit | **people per grid cell** (a count, not a density) |
| Grid | EPSG:4326, 3 arc-seconds (0.000833…°), 25,407 × 18,930, nodata −99999, float32 |
| Licence | CC BY 4.0 — cite WorldPop |
| Lock | SHA-256 `3ed9bc9a…57410` (A6/README.md); any other file is rejected |
| Release | alpha public release (September 2025); a modelled annual estimate, not a census of 1 October 2026 |

WorldPop disaggregates census-based totals (aligned to UN WPP 2024) to 100 m cells with a random-forest
dasymetric model constrained to mapped settlements (release statement R2025A).

## 3. Study area
20–23° N, 38–41° E: the same box as the A2 ADS-B filter and the A4 ERA5 grid, so trajectories, weather and
receptors share one domain. It covers Jeddah, Makkah and every published 34C/34L SID to its exit fix. The box
is snapped **outward to whole pixels** (3,600 × 3,600 cells); no cell is split.

## 4. Processing rules
1. **Never resample, never reproject the raster.** Values are counts: bilinear or nearest-neighbour
   warping changes the total. The study window is read pixel-aligned and its values are kept bit-identical
   (the clipped GeoTIFF is checked cell by cell against the source window).
2. **Cells become points.** Each populated cell (value > 0) becomes a receptor at its pixel centre. Only the
   point coordinates are projected (WGS84 → UTM 37N, EPSG:32637) for metre-based noise geometry; the
   round-trip error is checked (< 1e-9°).
3. **Nodata is not zero population** in meaning (sea, outside settlements) but contributes zero people; it is
   counted separately in the audit, and never averaged into a cell.
4. **Population is conserved exactly**: the receptor total equals the window total under `math.fsum`, and
   every aggregation grid conserves it too.
5. **Provenance per receptor**: each receptor is identified by `(src_row, src_col)`, its row/column in the
   *national* raster, so any receptor can be found in the original file.
6. **Cell area** is the exact WGS84 geodesic area of the pixel (≈ 7,880–8,040 m² across 20–23° N); density
   per km² is derived from it, never assumed.

## 5. Moving the data: study-area extract
The national file is 55.8 MB. Where it cannot be moved (upload limits), `scripts/a6_extract_study_area.py`
verifies the national file against the lock, extracts the study window bit-identically and writes a manifest
(national SHA-256, window offsets, extract SHA-256, totals, library versions). `a6.build` accepts the extract
only if the manifest matches the lock, the window equals the one recomputed from the configuration, the
extract is aligned with the national grid and its total matches the manifest. A test proves the extract path
gives exactly the same receptors as the full raster.

## 6. Outputs (`data/a6/processed/`)

| File | Content |
|---|---|
| `a6_receptors.parquet` | one row per populated cell: `src_row, src_col, lon, lat, x_utm37n_m, y_utm37n_m, population, cell_area_m2, density_per_km2, dist_arp_km, bearing_arp_deg` |
| `a6_grid_{6,12,24}px.parquet` | aggregates at ~0.5 / 1 / 2 km for maps (whole-pixel bins, totals conserved) |
| `a6_population_rings.csv` | people within 5–100 km of the OEJN reference point |
| `a6_population_study_area.tif` | the study window, bit-identical to the source, for QGIS |

## 7. Validation (`data/a6/validation/qc_report.md`)
Lock hash · raster CRS, pixel size, orientation, size, nodata, dtype, band count · study window inside the
raster · no NaN, no negatives · exact conservation · unique receptor ids · receptors inside the window ·
geodesic area vs spherical approximation · UTM round trip · bit-identical clip · national total (context).
Tests (`tests/test_a6.py`) run the whole pipeline on a synthetic raster with the WorldPop grid geometry and
known values, including the extract path and a deliberate hash mismatch.

## 8. How the noise model should use A6
- Evaluate the noise metric at each receptor (`x_utm37n_m, y_utm37n_m`; receptor height = ground).
- Population exposed above a threshold = Σ `population` of receptors above it; population-weighted noise =
  Σ `population × metric`, as in the handoff definition.
- Report exposure with the receptor set's release id (`a6-worldpop-r2025a-2026-v1`).

## 9. Limitations
Residential (night-time) distribution only; no workplaces, schools or hospitals (add OpenStreetMap layers
later); modelled, not observed; new developments after the input building footprints may be missing; alpha
release that may be revised by WorldPop.
