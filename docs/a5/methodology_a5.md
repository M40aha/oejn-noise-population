# A5 methodology — aircraft noise data layer

*Written for direct reuse in the research methodology section.*

## 1. Purpose and scope
A5 provides the noise-source data needed to compute departure noise at OEJN with the ECAC Doc 29
(5th Edition, 2026) method. It owns: (i) the ANP aircraft, noise and performance tables, typed and validated;
(ii) the EASA substitution tables; (iii) Doc 29 constants that are not part of the ANP tables; (iv) the
mapping from observed aircraft types to ANP aircraft; and (v) an NPD lookup implementing Doc 29 Vol 2
Eq. 4-3, 4-4 and 4-5.

A5 deliberately does **not** compute anything that depends on the flight or the weather: thrust along a
trajectory, acoustic impedance (Eq. 4-6), atmospheric absorption (Appendix D), duration, engine-installation,
lateral-attenuation and finite-segment corrections, or contours. These belong to the noise-model stage and use
A2 (trajectories), A3 (aircraft identity) and A4 (weather) as inputs.

## 2. Sources

| Source | Version | Role |
|---|---|---|
| EASA ANP database, legacy format | 2.3 (release note 14/10/2020) | aircraft, NPD, spectra, profiles, coefficients |
| EASA ANP substitution tables | baseline ANP 2.2 (22/02/2018) | proxies and decibel adjustments |
| EASA list of verified ANP types | downloaded 20/10/2026 | flags types with newer verified data |
| ECAC Doc 29 Vol 1–3 | 5th Edition, endorsed 19 May 2026 | method, substitution rules, reference cases |
| Doc 29 Vol 3 workbooks 1–2 | 5th Edition | validation data |

Every file is locked by SHA-256 in `config/a5.yaml`; a changed file stops the build. The Doc 29 PDF metadata
carries the title "4th Edition" although the content is the 5th Edition; this is recorded, not corrected.

## 3. Processing
1. **Ingest without inference.** The ANP CSVs are read directly from the ZIP as text, the workbooks read-only.
   Each row keeps `src_file`, `src_member` (CSV member or sheet) and `src_row` (line or row number).
2. **Explicit typing.** Every column has a declared kind and **native unit** (`src/a5/schemas.py`). A value that
   cannot be cast is an error; nothing is coerced silently. Blank numeric cells stay missing: in ANP they mean
   "not applicable to this step type" (e.g. no rate of climb on a Climb step), which is checked by logic rules.
3. **Normalisation.** Only leading/trailing whitespace is removed (339 cells: padded profile IDs of the 737800,
   flap IDs, spectral operation types, three descriptions). Every changed cell is logged with its original
   value in `normalization_log`; no key collides after normalisation.
4. **Tidy reshapes.** NPD and spectral tables are also provided in long format; both round-trip to the source
   exactly (27,760 NPD values, 984 spectral values).
5. **Derived attributes** on `anp_aircraft`: power-parameter kind, availability of jet coefficients, HiTemp
   ratings, departure profiles and fixed-point profiles.

## 4. Units
ANP tables keep their native units (lb, ft, kt, °C, dB). Doc 29's thrust equation (Vol 2 App. B) is written for
coefficients in lb, kt, ft and °C, so converting them would only add risk. `units_registry` gives, for every
numeric column, the native unit and the exact SI factor (ft = 0.3048 m, nmi = 1852 m, lb = 0.45359237 kg,
kt = 1852/3600 m/s, lbf = 4.4482216152605 N); thrust coefficients are marked "do not convert". The other
stages exchange SI, UTC and WGS84; conversion happens once, at the boundary.

## 5. Validation
- **Source integrity:** SHA-256 of all nine files.
- **Structure:** expected columns, types, controlled vocabularies, unique primary keys.
- **Referential integrity:** aircraft→NPD, aircraft→spectral class (and its operation type), steps→aircraft,
  steps→flap configuration, steps→stage-length weight, jet steps→thrust-rating coefficients: all resolve.
- **Physics and logic:** NPD complete and in range; level strictly decreasing with distance on every curve;
  spectra normalised to 70 dB at 1 kHz; every departure profile contiguous and starting with Takeoff; climb
  steps have altitudes, accelerate steps have CAS and a climb/acceleration parameter; take-off flap
  configurations have coefficients B and C.
- **Executable validation against Doc 29 Vol 3:** the Vol 3 hypothetical aircraft are loaded through the same
  schema, and the NPD lookup reproduces the `baseline_SEL` of all 3,516 B-2 segments (including distance and
  power extrapolation) with a maximum difference of 1.3 × 10⁻¹³ dB. The exact unit constants reproduce the
  Vol 3 metric/imperial coordinates. Vol 3 aircraft are hypothetical, so this validates the representation
  and the code, not the ANP 2.3 values; evidence for the values is the hash, the release note and the checks above.
- **EASA cross-checks:** every proxy exists in ANP 2.3; N = 10^(Δ/10) within published rounding; the ICAO-tab
  delta equals the noisiest configuration-tab delta for each ICAO/proxy pair, as EASA states.

## 6. NPD lookup (Doc 29 Vol 2 §4.2)
Linear in power (Eq. 4-3) and linear in log₁₀ distance (Eq. 4-4); outside the tabulated envelope, linear
extrapolation from the two nearest points (Eq. 4-3, 4-5a, 4-5b). Corrected net thrust below 1 lb per engine is
reset to 1 lb before extrapolating; slant distance is floored at 30 m (recommended, configurable). Power
extrapolation that moves the level more than 5 dB beyond the envelope edge is flagged, never clipped.

## 7. Aircraft → ANP mapping (Doc 29 Vol 1 §6.4.4)
Input from A3: ICAO type (required), airframe model, engine type, MTOW (optional). The first applicable rule wins,
and every candidate is stored in `mapping_candidates`:

| Method | Rule | Confidence |
|---|---|---|
| EASA_CONFIG | engine (+ model) + MTOW match a certified configuration | HIGH |
| EASA_CONFIG_MAXMTOW | engine (+ model) match, MTOW unknown → highest MTOW (Vol 1 p.45) | HIGH |
| EASA_CONFIG_ENGINE_FAMILY | engine given as a family prefix only | MEDIUM |
| EASA_ICAO | ICAO code only, one variant (EASA: noisiest configuration) | MEDIUM (HIGH if a single configuration exists) |
| EASA_ICAO_AMBIGUOUS | several engine variants, engine unknown → highest MTOW, then highest certified departure level | LOW |
| ANALYST_PROXY | type absent from EASA tables; proxy by Vol 1 criteria; Δ from Eq. 6-1 | LOW once reviewed, NONE while pending |
| UNRESOLVED | no defensible mapping; kept and reported | NONE |

The substitution adjustment is applied with **Method A** (decibels added to the proxy NPD), which is valid for
all metrics. Method B (movement factor N) is stored but applies only to energy-equivalent levels (Vol 1 p.45),
not to LAmax or number-above metrics. A large |Δ| (≥ 5 dB) is flagged as a possibly inappropriate proxy (Vol 1
note 2). The certified departure level used for conservative choices is (flyover + lateral EPNdB)/2, the same
combination as Eq. 6-1.

## 8. Findings that matter for OEJN

1. **A320neo family.** With the engine unknown, A20N maps to A320-232 with Δ = −3.5 dB (IAE variant, chosen by the
   Doc 29 conservative rule). With the engine known, the specific configuration applies: e.g. LEAP-1A26 at 70 t
   is −8.1 dB on A320-211. Engine family and certified MTOW together span about 5 dB.
2. **Certified MTOW drives Δ for widebodies.** For the 787-9 with one GEnx engine, Δ ranges from −1.8 dB (181 t)
   to +3.2 dB (254 t). Without the MTOW option, the conservative highest-MTOW value is used.
3. **Types missing from EASA tables.** A339 (A330-900), B78X (787-10) and B39M (737 MAX 9) are absent from both EASA
   tabs (baseline 2018). Proxies are A330-343, 7878R and 7378MAX; their Δ needs the certified levels of the
   operated configuration from the EASA type-certificate noise database, entered in
   `data/a5/reviews/analyst_proxies.csv`. Until then they are **not usable**; no silent Δ = 0.
4. **Verified data.** EASA holds verified ANP datasets for A20N (both engine families), A21N (PW), A339, A35K,
   B789 (GEnx) and a new B77W NPD. Obtaining them would replace the largest substitutions.
5. **ANP 2.3 inconsistency.** Five default stage-length weights exceed the aircraft's own tabulated MTOW
   (A320-211, A320-232 and A321-232 at stage 5; A330-343 and A340-642 at stage 7). Values are preserved; those
   stage lengths must not be used without an explicit, documented cap.
6. **Non-monotonic NPDs.** Nine departure SEL/LAmax curve families decrease with power somewhere, including
   TRENT7 (A330-343, the proxy for A333 RR and A339). Doc 29 interpolates them as tabulated; the noise stage
   should report flights whose thrust falls in those ranges.
7. **Hot-day applicability.** NPD data apply when air temperature is below 30 °C and T×RH > 500 (Vol 2 p.10).
   ERA5 shows ≥ 30 °C at OEJN for 17 of 24 hours on 1 October 2026, so the Appendix D atmospheric adjustment
   (SAE-ARP-5534) is required in the noise stage. It needs relative humidity, which A4 does not yet provide.

## 9. Limitations
ANP 2.3 is a 2020 legacy release; the substitution tables date from 2018; Δ values are certification-based
approximations applied uniformly to all distances and powers; the NPD lookup is validated against hypothetical
Vol 3 aircraft only. Results for proxy-mapped types inherit the proxy's spectral class and directivity.
