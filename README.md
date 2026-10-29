# OEJN Noise & Population — A5 + A6 + Doc 29 noise model

Part of the **OEJN Noise–Fuel–Capacity** research (Jeddah, RWY 34C/34L departures, prototype day **1 October 2026**).
This repository holds the two preprocessed layers (A5, A6) and the **Doc 29 noise model** that runs on the observed A2 departures:

| Layer | What it answers | Release | Status |
|---|---|---|---|
| **A5 — aircraft noise data** | For an observed aircraft: which ANP aircraft, which noise curves (NPD), which correction (Δ dB), and how confident are we? | `a5-anp2.3-doc29e5-v1` | ✅ 0 errors · 106 checks passed · Doc 29 Vol 3 reproduced to 1.3 × 10⁻¹³ dB |
| **A6 — population exposure** | Where do people live, and how many, at 100 m resolution? | `a6-worldpop-r2025a-2026-v1` | ✅ 0 errors · 23 checks passed · population conserved exactly |
| **Noise model** (`src/noise/`) | SEL / LAmax per observed departure, LAeq,24h, Lden, Lnight, N60/65/70, and people exposed | `noise-doc29e5-oejn-2026-10-01-v1` | ✅ code validated: Vol 3 B-2 (3,516 segments) ≤ 1.4 × 10⁻³ dB · B-1 ≤ 4.9 × 10⁻³ dB · D-2 thrust 119/119 · Table D-4 < 0.1 dB · end-to-end observed-track test ≤ 0.05 dB. ✅ **run on 1 Oct 2026**: 208 of 241 departures modelled → [results](docs/noise/results_2026-10-01.md) |

Tests: **50 / 50 pass** (`tests/`: A5 21, A6 12, noise 17). Independent re-implementation check for A5: **15 / 15** (`scripts/verify_a5_independent.py`).

**Main output — 3D noise map (local):** `map3d/OEJN_Map3D_Noise.html` (double-click; Chrome or Edge). The team's Map 2
Departure Studio with the 1-Oct departure noise:
- graded noise surface (day–night, night, loud events) with contours;
- typical flight paths in 3D and neighbourhood names;
- a **Results** panel: people per noise band, runway and aircraft comparisons, WHO indicators, method, validation and limits.

Local use only (Wingbits-derived). See [`map3d/README.md`](map3d/README.md).

All numbers behind it are in [`docs/noise/results_2026-10-01.md`](docs/noise/results_2026-10-01.md) and `data/noise/processed/`.

---

## Quick start (for the next stage)

```python
import duckdb, pandas as pd, sys
sys.path.insert(0, "src")
from a5.npd import NPDLookup, NPDPolicy

# A5: noise data
con = duckdb.connect("data/a5/processed/a5-anp2.3-doc29e5-v1.duckdb", read_only=True)
mapping = con.execute("select * from aircraft_noise_mapping").df()          # ICAO type -> ANP aircraft + Δ
npd = NPDLookup(con.execute("select * from anp_npd_long").df(), NPDPolicy(),
                dict(con.execute("select npd_id, power_parameter_kind from anp_aircraft").fetchall()))
m = mapping.set_index("icao_type").loc["A20N"]
level = npd.lookup(m.npd_id, "SEL", "D", power=20000, distance_ft=3000).level_db + m.delta_applied_db

# A6: population receptors (one point per populated 100 m cell)
rec = pd.read_parquet("data/a6/processed/a6_receptors.parquet")   # x_utm37n_m, y_utm37n_m, population, ...
```
For flights with engine / model / MTOW from A3: `a5.mapping.Mapper.resolve(records)` (see `docs/a5/integration_contract.md`).

## Rebuild and verify

```bash
pip install -r requirements.txt
# raw data = the team data repo (OEJN-Noise-Fuel-Capacity) cloned next to this one, or set A5_RAW_DIR / A6_RAW_DIR
PYTHONPATH=src python -m a5.build
PYTHONPATH=src python -m a6.build        # full WorldPop file, or the study-area extract (see below)
PYTHONPATH=src python -m pytest -q tests
python scripts/verify_a5_independent.py ../OEJN-Noise-Fuel-Capacity/A5
PYTHONPATH=src python -m noise.run                      # noise run (inputs in data/inputs, git-ignored)
PYTHONPATH=src python scripts/noise_figures.py          # results_2026-10-01.md + figures
PYTHONPATH=src python scripts/build_map3d.py <A1/A2 repo>   # 3D noise map
```
Builds are deterministic: rebuilding gives byte-identical tables (checked with content hashes in `output_manifest.csv`).
**Colab:** `!PYTHONPATH=src python -m a5.build` etc. work unchanged.

## Repository layout

```
config/            a5.yaml, a6.yaml — source hashes (locks), policies, tolerances. No magic numbers in code.
src/a5/            ingest · schemas · anp_checks · npd · easa · mapping · vol3 · qc · report · build
src/a6/            build (window read, receptors, aggregates, QC)
src/viz/           sids (16 published SIDs) · noise_grid / noise_map / noise_stats (presentation data for the 3D map)
data/a5/           interim/ (typed, provenance) · processed/ (DuckDB + parquet) · validation/ (QC) · reviews/ (manual input)
data/a6/           processed/ (receptors, grids, rings, clipped GeoTIFF) · validation/ (QC)
docs/a5/           methodology · integration contract · decisions log · data dictionary
docs/a6/           methodology
map3d/             local 3D noise map (copy of team Map 2 + noise layer), stand-alone HTML
src/noise/         doc29 (segment levels) · atmosphere (App. D) · performance (App. B) · flightpath (Ch. 3, observed tracks)
                   · site (OEJN frame, heights, CAS) · weather (METAR) · event (SEL/LAmax) · run (pipeline, metrics, exposure)
config/noise.yaml  noise-model run configuration
data/external/     A1 runway table (AIP AMDT 10/26) used for start of roll / elevations
data/noise/        processed/ (grid, GeoTIFF, exposure, per-flight results) · validation/ (QC, manifest) · interim/ (git-ignored)
docs/noise/        methodology_noise.md · results_2026-10-01.md · figures (Lden, Lnight, N70, tracks, runways)
data/external/basemap/  Natural Earth + OSM layers (from A1 Map 1) with provenance
scripts/           independent A5 verification · A6 study-area extractor · 3D map builder · noise figures · A2 noise extract ·
                   Colab METAR/A3 fetch · synthetic noise inputs (pipeline testing only)
tests/             test_a5.py (21) · test_a6.py (12) · test_noise.py (17) · fixtures/doc29_vol3 (Vol 3 reference tables)
```

---

## A5 — what was done and the rules followed

Sources: EASA **ANP 2.3** (10 tables, 155 aircraft, 27,760 NPD points), **ECAC Doc 29 5th Edition** (May 2026, Vol 1–3 +
workbooks), EASA substitution tables (19,565 certified configurations), EASA verified-types list.

1. **Raw data never modified.** Every source file is locked by SHA-256; a change stops the build. ANP CSVs are read straight from the ZIP.
2. **No silent assumptions.** Read as text, cast explicitly; a value that cannot be cast is an error. Whitespace fixes (339 cells) are logged with the original value.
3. **Provenance on every row:** `src_file`, `src_member` (CSV/sheet), `src_row`.
4. **Native ANP units** (lb, ft, kt, °C) kept, because Doc 29's thrust coefficients are defined in them; `units_registry` gives exact SI factors. Other stages exchange SI + UTC + WGS84.
5. **Scope:** A5 holds data + mapping + NPD lookup only. Thrust, impedance, atmospheric absorption, duration, directivity, lateral attenuation and contours belong to the noise model.
6. **NPD lookup = Doc 29 Vol 2 §4.2 exactly:** linear in power (Eq. 4-3), linear in log-distance (Eq. 4-4), extrapolation from end pairs (Eq. 4-5), power floor 1 lb/engine, distance floor 30 m, power extrapolation > 5 dB **flagged, never clipped**.
7. **Mapping = Doc 29 Vol 1 §6.4.4:** EASA configuration (engine + MTOW) first, ICAO-code fallback; unknown engine/MTOW → **conservative** variant (highest MTOW, highest certified level). Δ applied by **Method A** (dB on NPD — valid for SEL *and* LAmax). Categorical confidence; every candidate kept.
8. **Validation:** referential integrity across all tables, physics checks, exact long/wide round-trip, EASA internal consistency, and the **ECAC Vol 3 reference cases reproduced** (3,516 segments).

**Findings the team should know**
- **A320neo family:** engine unknown → A320-232, Δ = −3.5 dB (conservative). With engine + MTOW the configuration can be down to −8.3 dB. **A3 must supply engine type (and MTOW option if possible).**
- **787-9:** Δ ranges −1.8 … +3.2 dB with the certified MTOW option, for the same engine.
- **A339, B78X, B39M** are absent from EASA tables → proxies A330-343 / 7878R / 7378MAX, **pending** certified levels (`data/a5/reviews/analyst_proxies.csv`, Eq. 6-1). Not usable until filled; no silent Δ = 0.
- **ANP 2.3 source inconsistency:** 5 default stage-length weights exceed MTOW (incl. A320-232, A321-232); preserved and flagged.
- **EASA verified ANP data** exists for most of the OEJN fleet (A20N, A21N, A339, A35K, B789, B77W NPD) → request it from EASA.

## A6 — what was done and the rules followed

Source: **WorldPop Global2 R2025A v1, Saudi Arabia 2026, constrained, 100 m** (people per cell; CC BY 4.0).
Study area **20–23° N, 38–41° E** = the A2 ADS-B box and the A4 ERA5 grid (one shared domain).

1. **Never resample or reproject the raster** — values are counts; warping changes the total. The window is read pixel-aligned; the clipped GeoTIFF is bit-identical to the source.
2. **Each populated cell → one receptor** at its pixel centre; only the point is projected to **UTM 37N (EPSG:32637)** for metre geometry.
3. **Exact conservation:** receptor total = window total (`math.fsum`), and every aggregation grid conserves it.
4. **Provenance:** each receptor keeps `(src_row, src_col)` in the national raster. Exact geodesic cell area (≈ 7,885–8,045 m²) and density per km².
5. **Study-area extract** (`scripts/a6_extract_study_area.py`) for when the 55.8 MB file can't be moved: accepted only if its manifest ties it to the locked national file; a test proves it gives identical receptors.

**Numbers:** 8.11 M people in 1,034,281 populated cells (23.3 % of Saudi Arabia's 34.87 M); 0.80 M within 10 km of the OEJN reference point, 3.72 M within 40 km.

**Noise result (1 Oct, flown tracks):** for the same aircraft type, 34C and 34L departures reach similar numbers of residents;
34C dominates the day's exposure because it carries 188 of 208 modelled departures and almost all widebodies.

---

## Noise model — run it

```bash
# 1. A2 owner (machine with SANS-output/a2/2026-10-01):  python scripts/a2_noise_extract.py <a2_output_dir> data/inputs/a2
# 2. Colab (internet):                                   python scripts/colab_external_data.py data/inputs/a2/a2_noise_flights.csv data/inputs
# 3. here:
PYTHONPATH=src python -m noise.run          # outputs in data/noise/processed + data/noise/validation
```
Method, assumptions and limits: [`docs/noise/methodology_noise.md`](docs/noise/methodology_noise.md). Main assumptions are full
take-off thrust, start of roll at the threshold, flat terrain, and departures only on one day.

## Open items before the noise model can produce final 1-Oct results

| # | Item | Owner |
|---|---|---|
| 1 | Engine type (+ MTOW option) per airframe from ICAO24 | A3 |
| 2 | METAR OEJN for 1 Oct (temperature, dew point → RH, QNH): `scripts/colab_external_data.py`. The Appendix D adjustment and the QNH height conversion are implemented in `src/noise/` | A4 / Colab |
| 3 | A2 trajectory extract for the noise model: `scripts/a2_noise_extract.py` | A2 |
| 4 | Certified levels for A339 / B78X / B39M (EASA certification noise levels) | A5 |
| 5 | Request EASA verified ANP dataset | A5 |
| 6 | AIP inconsistencies found while digitising SIDs (e.g. EGPOB3X lists JN300 vs JN390) | A1 |

## Licences and citation
EASA ANP data and ECAC Doc 29 are used under their publishers' terms; raw files are **not** redistributed here (they live in the
team data repository). WorldPop data: CC BY 4.0 — cite *WorldPop (www.worldpop.org) Global2 R2025A v1, University of Southampton*.

---

## ملخص بالعربي للفريق

- **A5 (بيانات الضجيج):** بيانات EASA ANP 2.3 ومنهجية ECAC Doc 29 (الإصدار الخامس 2026) صارت جداول نظيفة ومترابطة، وكل صف فيها يرجع لمصدره.
  - جدول ربط يحدد لكل نوع طيارة: البديل في ANP، ومنحنيات الضجيج، والتصحيح بالديسيبل، ودرجة الثقة.
  - دالة NPD أعادت نتائج ECAC الرسمية بفرق 10⁻¹³ dB.
- **A6 (السكان):** خريطة WorldPop 2026 بدقة 100 م تحوّلت إلى 1,034,281 نقطة سكانية، كل نقطة فيها عدد سكانها وإحداثياتها بنظام UTM.
  - بدون أي إعادة عيّنة، ومجموع السكان (8.11 مليون) محفوظ بالضبط.
- **نموذج الضجيج (`src/noise/`):** طبّقنا Doc 29 كاملاً على المسارات الفعلية من A2.
  - من بيانات ADS-B نستخرج: نقطة الإقلاع، ومرحلة الدحرجة على المدرج، والارتفاع (GNSS أو الضغطي مصحّح بالـ QNH)، والسرعة، والدفع (معادلات Appendix B).
  - ومنها نحسب SEL و LAmax لكل رحلة، ثم LAeq و Lden و Lnight و N70، وعدد السكان المتأثرين.
  - تحقّقنا منه على كل الحالات المرجعية في Vol 3: فرق ≤ 0.002 dB للمقاطع، وأقل من 0.05 dB في الاختبار الكامل من "مسار مرصود".
- **المطلوب لتشغيله على يوم 1 أكتوبر:**
  - A2: ملفات `a2_noise_extract.py`.
  - من Colab: METAR (الحرارة ونقطة الندى، ومنها الرطوبة، والـ QNH)، وهوية الطيارات (النوع والمحرك).
- **المخرج الرئيسي:** الخريطة الثلاثية الأبعاد `map3d/OEJN_Map3D_Noise.html` (للاستخدام المحلي فقط). افتحوها بدبل كليك، وفيها زر Results للنتائج والمنهجية.
