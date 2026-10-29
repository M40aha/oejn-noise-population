# A5 integration contract

Conventions between stages: **SI units, UTC timestamps, WGS84 coordinates.** A5 tables keep native ANP units
internally (see `units_registry`).

## Aircraft identity → A5 (one row per flight or per airframe)

| field | required | example | note |
|---|---|---|---|
| `icao_type` | yes | `A20N` | ICAO Doc 8643 designator |
| `airframe_model` | no | `A320-251N` | improves resolution |
| `engine_type` | no | `LEAP-1A26` | removes engine ambiguity (A20N, A320, A332/A333, A388…) |
| `mtow_kg` | no | `79000` | certified MTOW option; otherwise the highest MTOW is assumed |
| `identity_source`, `lookup_date` | yes | `OpenSky aircraft DB`, `2026-10-27` | provenance |

A5 never looks up ICAO24 addresses or registrations; that belongs to the aircraft-identity input (OpenSky / adsbdb in the noise run).

```python
from a5.mapping import Mapper, MappingPolicy
mapping, candidates = mapper.resolve(identity_records)   # same columns as aircraft_noise_mapping
```

## A5 → noise model

`aircraft_noise_mapping` (one row per input key): `anp_acft_id, npd_id, delta_applied_db, n_applied,
substitution_method, dep_spectral_class_id, lateral_directivity, power_parameter_kind, has_hitemp_ratings,
thrust_ratings, departure_profiles, mapping_method, confidence, abs_delta_dep_db, usable_for_noise,
verified_data_available, evidence, source_ref, a5_release_id`.

Plus `NPDLookup` (Eq. 4-3/4-4/4-5), `anp_jet_coefficients`, `anp_aero_coefficients`, `anp_departure_steps`,
`anp_default_weights`, `anp_spectral_long`, `doc29_constants`, `doc29_table_d1`.

Rules for the consumer:
- Use only rows with `usable_for_noise = True`; report the **flight-weighted** share of the others
  (`a5.mapping.flight_weighted_coverage`).
- Add `delta_applied_db` to NPD levels (Method A). Use `n_applied` only for energy metrics under Method B.
- Do not use the stage lengths flagged in QC check `physics.default_weight_le_mtow` without a documented cap.
- Record `a5_release_id` with every result.

## A4 → noise model (not A5)
Hourly at the aerodrome: air temperature (°C), pressure (hPa) and **relative humidity (%)**, for the impedance
adjustment (Eq. 4-6), the Appendix D atmospheric adjustment and the NPD applicability check. Temperature along the
path, for the thrust temperature breakpoint (HiTemp ratings). *Humidity is currently missing from A4.*

## A2 → noise model (not A5)
Trajectories in SI with **height above the aerodrome / receptor**. ADS-B barometric altitude is a pressure
altitude (1013.25 hPa) and must be QNH-corrected with A4 pressure before computing slant distances.
