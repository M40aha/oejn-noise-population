# Noise model — methodology (ECAC Doc 29, 5th Edition, 2026)

Results of the 1-Oct run: [results_2026-10-01.md](results_2026-10-01.md)

Release `noise-doc29e5-oejn-2026-10-01-v1` · code `src/noise/` · configuration `config/noise.yaml` · tests `tests/test_noise.py`

**Scope.** Single-event and cumulative A-weighted noise of the *observed* jet departures from OEJN on 1 October 2026 (UTC day,
from the A2 reconstruction), computed with the Doc 29 segmentation method, and the number of residents (A6) exposed.
Arrivals, ground operations (taxi, APU, engine run-ups) and other days are **not** included, so cumulative levels are a
**departure-only, single-day** picture. They are not annual-average contours and not a regulatory noise map.

## 1. Pipeline

| Step | Doc 29 reference | Module |
|---|---|---|
| A2 departures → local frame (UTM 37N, origin ARP, feet); heights; CAS; pressure altitude | Vol 2 §3.2.1, App. B | `site.py` |
| Lift-off point; take-off ground roll from the start of roll | §3.6.2, Eq. 3-3a–e | `flightpath.py` |
| Initial-climb sub-segmentation | §3.6.4, Eq. 3-4 | `flightpath.py` |
| Airborne nodes = observed points (thinned only within §3.6.5 / §3.6.7 limits) | §3.6.1 (“radar data”), §3.6.5, §3.6.7 | `flightpath.py` |
| Engine power (corrected net thrust per engine) | App. B, Eq. B-9/B-10/B-11 | `performance.py` |
| Bank angle from the observed turn rate | Eq. B-14 | `flightpath.py` |
| NPD levels, atmosphere adjusted per flight | §4.2, App. D | `event.py`, `atmosphere.py` |
| Segment levels: duration, engine installation, lateral attenuation, finite segment, start-of-roll | §4.4–4.5, Eq. 4-8 to 4-25 | `doc29.py` |
| Event SEL (energy sum) and LAmax (maximum) | Eq. 4-10/4-11 | `event.py` |
| Cumulative metrics, number-above, population exposure | Vol 1; EU END Annex I | `run.py` |

## 2. Flight path from observations

Doc 29 §3.6.1: *"When matching flight profile segments to radar data … all end-point distances, heights, speeds and bank
angles are determined directly from the data; only the power settings have to be calculated using the performance equations."*
This is what is done; no procedure profile is imposed on the observed tracks.

- **Positions:** A2 `easting_m/northing_m` (EPSG:32637, same CRS as A6). Reports flagged `implausible_movement` by A2 are dropped.
- **Heights (`height_source: auto`):** GNSS geometric altitude (WGS84 ellipsoid) minus the AIP geoid undulation
  (14.7–14.9 ft) minus the departure-threshold elevation; where no geometric altitude is reported, barometric (pressure) altitude
  converted with the hypsometric relation for the METAR QNH and aerodrome temperature (ISA lapse). The per-flight median
  difference between the two is reported in `flight_results.csv` (`geo_minus_baro_median_ft`) and in QC. Heights are smoothed with a
  5-point running median, because altitude is quantised in 25 ft steps.
- **Reference plane:** the departure-runway threshold elevation. Receptors lie on that plane. This is Doc 29's flat-terrain
  default, with the optional topography adjustment not applied. Jeddah's coastal plain is flat near the airport; the ground rises
  towards the eastern escarpment (>25 km).
- **Lift-off:** a straight-line fit of height against distance from the start of roll (SOR) is extrapolated back to z = 0.
  The fit uses the heights between 100 and 1,000 ft within 120 s of the first point above 100 ft; ADS-B heights near the runway
  are 25-ft quantised and the roll itself is often not reported, so points below 100 ft are not used. The result is clamped to
  [1,500 ft, TORA] (flagged). The lift-off speed comes from the same points (V² linear in distance), with a plausibility window
  of 100–220 kt. On 1 Oct the median lift-off is ≈ 2,380 m from SOR at ≈ 172 kt.
- **Rejected paths:** a departure whose first airborne observation lies more than 5 km from the lift-off point or above 3,000 ft
  (the take-off was not observed near the runway) is not modelled (`PATH_FAILED`, reason recorded); so is a track with fewer
  than 3 airborne points.
- **Ground roll:** from the runway threshold (SOR = threshold, i.e. full-length take-off; intersection departures are not
  identified) to lift-off. It is split into n = int(1 + V_TO/10) segments (V_TO in m/s) of length s_TO(2k−1)/n², with speed
  steps V_TO/n and constant thrust steps (Eq. 3-3e). The source is 1 m above the runway.
- **Initial climb:** heights z_i = z_e·z′_i/z′_N are inserted between lift-off and the first observed point (Eq. 3-4, metric
  z′ set), with speed interpolated by Eq. 3-2b and power by Eq. 3-2d.
- **Airborne nodes:** every observed point is a candidate node. Points are dropped only when the next kept point stays within:
  500 / 1,000 / 3,000 ft of path (below 1,500 ft / below 4,231 ft / above), a 10 kt speed change (so every segment satisfies the
  §3.6.5 ≤ 20 kt rule), and a 5° track change. Points < 10 m apart are removed (§3.6.7). Speeds are observed **ground speed**
  (the Doc 29 duration-correction speed).
- **Bank angle:** ε = atan(V·ω/g), with V the ground speed and ω the turn rate from the smoothed observed track (20 s window).
  This is Eq. B-14 rearranged for observed turns. It is capped at 35°. Positive = right turn (starboard wing down); φ = β_p − ε for
  observers to starboard (§4.5.5).

## 3. Engine power

- CNT per engine from the ANP jet coefficients of the mapped ANP aircraft: B-9, with the high-temperature rule
  min(B-9, B-10), or B-11 with T_B = 30 °C when the aircraft has no high-temperature ratings.
  Inputs per node: CAS, pressure altitude, temperature at altitude (B-2).
- **CAS:** IAS where reported, otherwise (ground speed + METAR headwind component)·√σ (B-8, TAS from ground speed). The
  sensitivity is small: F ≈ −25 lb/kt gives ~1 % thrust per 10 kt, ≈ 0.1 dB.
- **Rating:** maximum take-off below the ANP DEFAULT-profile cut-back height (the end of its last take-off-rating step,
  typically 1,000 ft), maximum climb above. Full take-off thrust is used because Doc 29 Vol 2 §3.5 notes it is the more
  realistic assumption at high air temperatures (1 October: most hours ≥ 30 °C). Reduced-thrust take-offs, which are common in
  practice, would lower levels near the runway. This is a stated, conservative assumption.
- Aircraft weight does not enter B-9, so it is not needed with observed trajectories.

## 4. Acoustics

- **NPD:** A5 release (ANP 2.3), with interpolation linear in power and in lg(distance), end-pair extrapolation, a 30 m distance
  floor and a 1 lb power floor (A5 `NPDLookup` rules, reproduced exactly by `AdjustedNPD`).
- **Aircraft substitution:** A5 `Mapper` with the A3 identity (ICAO type, model, engine) per ICAO24: EASA configuration → engine
  family → ICAO tab. Method A applies Δ dB to all metrics. Without an engine the Doc 29 Vol 1 conservative rule applies (highest
  MTOW, then highest certified departure level). The B78X / A339 / B39M analyst proxies have no certified levels yet; they are
  modelled with Δ = 0 and flagged `PROXY_ZERO_DELTA`. A type without any mapping is excluded and reported (`UNMAPPED`, `NO_TYPE`).
  Turboprops are reported, not modelled.
- **Atmosphere (Appendix D):** for each flight, the METAR closest to lift-off (≤ 90 min) gives temperature and dew point (RH by
  Magnus) and QNH (Q group). Increments dL(d_i) at the 10 NPD distances are computed from the aircraft's departure spectral class
  (Eq. D-1 to D-4). They use ISO 9613-1 pure-tone absorption at exact mid-band frequencies, because the SAE ARP-5534 band
  algorithm is paywalled. The method is validated against Table D-4 within 0.1 dB. The increments are added to both the SEL and
  LAmax NPD levels.
- **Impedance:** Eq. 4-6/4-7 at aerodrome temperature and QFE.
- **Segment levels:** every Doc 29 term (Eq. 4-8 to 4-25), including the start-of-roll directivity behind the take-off roll and
  the finite-segment correction. Every segment is evaluated at every receptor: `prune_m: null`. Pruning was tested and rejected
  as a default, because segments 20 km away still produced single-event levels up to 58 dB SEL for a B77W.

## 5. Receptors, metrics and population

- **Grid:** 250 m, 80 km × 80 km square centred on the ARP (UTM 37N), 103,041 points. Outputs: `noise_grid.parquet` and the
  GeoTIFF `noise_grid_utm37n.tif` (bands LAeq24, Lden, Lnight, N60, N65, N70).
- **Metrics** for the modelled 24 h (UTC day), with periods in local time (UTC+3), EU END Annex I:
  - LAeq,24h;
  - Lden: day 07–19, evening 19–23 (+5 dB), night 23–07 (+10 dB);
  - Lday, Levening, Lnight;
  - N60, N65 and N70: number of departures with LAmax ≥ threshold;
  - per runway, Lden_<rwy> (that runway's departures alone).
- **Population:** A6 receptors (one per populated 100 m WorldPop cell, people per cell). Levels are bilinearly interpolated from
  the grid. The interpolation error is measured in QC against exact evaluation at 2,000 populated receptors.
  Outputs:
  - `population_exposure.csv`: Lden and Lnight 5 dB bands, cumulative, N-above counts, and per-runway alone;
  - `flight_results.csv`: per departure, people with LAmax ≥ 60/65/70 dB and SEL ≥ 80/90 dB;
  - `runway_procedure_summary.csv`: mean and median per runway and per A2 SID match.
- **Indicative health indicators:** WHO Environmental Noise Guidelines 2018 exposure–response functions: %HA from Lden
  (Guski et al. 2017) and %HSD from Lnight (Basner & McGuire 2018), within their validity ranges. They are designed for long-term
  average exposure from *all* operations. Applied to a single day of departures, they are only an indication.

## 6. Verification (tests/test_noise.py — 17 tests)

| Check | Reference | Result |
|---|---|---|
| Every segment SEL, JETF/JETW/PROP, all cases | Vol 3 Part 1 Table B-2 (3,516 rows) | max \|Δ\| 1.4 × 10⁻³ dB |
| Event SEL | Vol 3 Part 1 Table B-1 | max \|Δ\| 4.9 × 10⁻³ dB (table printed to 0.01) |
| Corrected net thrust | Vol 3 Part 2 Table D-2, JETW, all 119 maximum-rating points | all within print rounding |
| Atmospheric increments | Vol 2 Table D-4 (10 °C, 80 % RH), classes 103 and 205 | max \|Δ\| < 0.1 dB |
| Ground-roll segmentation | Vol 2 Fig. 3-5 example | exact |
| Initial-climb heights | Vol 2 §3.6.4 example | 17.2 m, 37.8 m |
| Bank angle | Eq. B-14, steady turn | < 0.05° |
| **End-to-end**: Vol 3 departure profile fed in as an *observed* track (lift-off detection, roll, sub-segmentation, thinning, event model), straight and curved routes, JETW and JETF | Vol 3 Table B-1 | max \|Δ\| 0.047 dB |
| NPD fast path = A5 lookup | A5 `NPDLookup` | identical to 10⁻¹² dB |
| Pipeline run on synthetic inputs | statuses, Lden ≥ LAeq, monotone cumulative exposure, GeoTIFF | pass |

The run-time QC (`data/noise/validation/noise_qc.csv`) also reports:
- coverage, by status;
- use of the weather fallback;
- the grid-border level (the grid must be large enough);
- grid → receptor interpolation error;
- geometric vs barometric height agreement;
- path flags (lift-off clamps, observation gaps, cut-back fallback).

## 7. Known limitations (state them with every result)

1. **Departures only, one day.** No arrivals, ground noise or other days. Lden/Lnight and WHO indicators are not long-term values.
2. **Full take-off thrust** assumed. Reduced-thrust take-offs would lower near-runway levels; the effect is a sensitivity to report.
3. **SOR = threshold** (full-length take-off). An intersection departure starts its roll further along the runway.
4. **Flat terrain**, with no topography or ground-type adjustments; the Doc 29 standard lateral attenuation applies.
5. **Aircraft identity** depends on A3: registration-level engine where found, otherwise the Doc 29 conservative variant. The
   three pending proxies (B78X, A339, B39M) use Δ = 0 until certified levels are entered.
6. **SID attribution** follows A2. Most A2 matches are *unmatched* or *ambiguous*, so per-procedure results are reported only
   where A2 found a unique candidate. Per-runway results are robust.
7. **Absorption:** ISO 9613-1 pure tone at mid-band, not the ARP-5534 band method (Table D-4 agreement < 0.1 dB).
8. **Data permissions:** Wingbits data are evaluation-only. Per-flight geometry stays in `data/noise/interim/` (git-ignored);
   only aggregated grids and per-flight summary values are published.

## 8. Presentation: the 3D map (`map3d/`, `scripts/build_map3d.py`, `src/viz/`)

The map only displays results of the run above; it recomputes nothing except the illustrative Live view.
- **Noise surface:** the 250 m grid (Lden, Lnight, N70), shown with a continuous green → red → dark-red ramp and contour
  lines (contourpy) at Lden 45–75 dB, Lnight 40–65 dB, N70 1–100 events. The resident counts in the legend are read
  from `population_exposure.csv`, not from the picture.
- **Typical flight paths** (aggregates; no individual track is exported): each modelled departure is grouped by runway and
  by the 20° sector where its path first leaves a 40 km circle around the ARP (paths that never pass 15 km are skipped).
  Every path is resampled every 1 km along track (first 80 km). For each group with ≥ 3 departures the drawn line is
  the point-wise median position and median height, continued only while ≥ 60 % of the group still has data. On 1 Oct:
  7 groups, 196 departures.
- **Population shading:** A6 600 m grid, as residents per km² (display only; exposure counts use the 100 m receptors).
- **Live ▶ (illustrative, not a result):** during Map 2 playback, LAmax under the moving aircraft from the NPD of a typical
  A320 (ANP A320-211, CFM565) at full take-off / climb thrust (B-9) with Doc 29 lateral attenuation, along Map 2's
  concept trajectory (published procedure, demo heights).
- **Source:** Map 2 is copied unchanged from the team repository (sha256 in `map3d/SOURCE.json`); two files get a small,
  asserted patch. Local use only (Wingbits evaluation data).

## 9. Run

```bash
# inputs (git-ignored): data/inputs/a2/{a2_noise_departures.parquet,a2_noise_flights.csv,a2_noise_manifest.json},
#                        data/inputs/ext_metar_oejn.csv, data/inputs/a3_aircraft_identity.csv
PYTHONPATH=src python -m noise.run            # ≈ 5–9 s per departure per core on the 250 m grid
PYTHONPATH=src python -m pytest -q tests/test_noise.py
```
Env overrides: `NOISE_A2_DIR`, `NOISE_METAR_CSV`, `NOISE_A3_CSV`, `NOISE_OUT_ROOT`.
To test the pipeline end to end without real data: `python scripts/make_synthetic_noise_inputs.py /tmp/syn`. The files are
invented; never report results from them.
