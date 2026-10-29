# A5 data dictionary

Units are **native ANP units** unless stated. See `units_registry` for SI factors. Every ANP-derived row carries `src_file`, `src_member`, `src_row` (provenance).

## `anp_aircraft`
Source: `ANP2.3_Aircraft.csv` · key: ['acft_id'] · rows: 155

| column | type | unit | description | source header |
|---|---|---|---|---|
| acft_id | id | - | ANP aircraft identifier | ACFT_ID |
| description | str | - | Airframe / engine description | Description |
| engine_type | cat | - | Jet | Turboprop | Piston | Engine Type |
| n_engines | int | - | Number of engines | Number Of Engines |
| weight_class | cat | - | Small | Large | Heavy | Weight Class |
| owner_category | cat | - | Commercial | General Aviation | Military | Owner Category |
| mtow_lb | float | lb | Maximum gross take-off weight | Max Gross Takeoff Weight (lb) |
| mlw_lb | float | lb | Maximum gross landing weight | Max Gross Landing Weight (lb) |
| max_landing_distance_ft | float | ft | Maximum landing distance | Max Landing Distance (ft) |
| max_static_thrust_lb | float | lb | Maximum sea-level static thrust (as tabulated by ANP) | Max Sea Level Static Thrust (lb) |
| noise_chapter | int | - | ICAO Annex 16 noise chapter (0 = not stated) | Noise Chapter |
| npd_id | id | - | Identifier of the NPD curve set | NPD_ID |
| power_parameter | cat | - | Noise-related power parameter of the NPD data | Power Parameter |
| app_spectral_class_id | int | - | Approach spectral class | Approach Spectral Class ID |
| dep_spectral_class_id | int | - | Departure spectral class | Departure Spectral Class ID |
| lateral_directivity | cat | - | Wing | Fuselage | Prop (engine-installation correction) | Lateral Directivity Identifier |
| power_parameter_kind | derived | - | Machine-readable power parameter: CNT_LB_PER_ENGINE | CNT_PCT_MAX_STATIC | RPM | (derived) |
| has_jet_coefficients | derived | - | Aircraft has jet thrust coefficients | (derived) |
| has_hitemp_ratings | derived | - | Aircraft has high-temperature thrust ratings (temperature breakpoint) | (derived) |
| thrust_ratings | derived | - | Available thrust ratings, '|' separated | (derived) |
| has_departure_steps | derived | - | Aircraft has procedural departure steps | (derived) |
| departure_profiles | derived | - | Available departure profile IDs, '|' separated | (derived) |
| has_fixed_point_departure | derived | - | Aircraft has fixed-point departure profiles | (derived) |
| mtow_kg | derived | kg | MTOW converted with the exact factor 0.45359237 (convenience only) | (derived) |

## `anp_npd_wide`
Source: `ANP2.3_NPD_data.csv` · key: ['npd_id', 'noise_metric', 'op_mode', 'power_setting'] · rows: 2776

| column | type | unit | description | source header |
|---|---|---|---|---|
| npd_id | id | - | NPD identifier | NPD_ID |
| noise_metric | cat | - | SEL | LAmax | EPNL | PNLTM | Noise Metric |
| op_mode | cat | - | A = approach, D = departure | Op Mode |
| power_setting | float | per aircraft power_parameter (CNT lb/engine for jets) | Noise-related power parameter value | Power Setting |
| L_200ft | float | dB | Noise level at slant distance 200 ft | L_200ft |
| L_400ft | float | dB | Noise level at slant distance 400 ft | L_400ft |
| L_630ft | float | dB | Noise level at slant distance 630 ft | L_630ft |
| L_1000ft | float | dB | Noise level at slant distance 1000 ft | L_1000ft |
| L_2000ft | float | dB | Noise level at slant distance 2000 ft | L_2000ft |
| L_4000ft | float | dB | Noise level at slant distance 4000 ft | L_4000ft |
| L_6300ft | float | dB | Noise level at slant distance 6300 ft | L_6300ft |
| L_10000ft | float | dB | Noise level at slant distance 10000 ft | L_10000ft |
| L_16000ft | float | dB | Noise level at slant distance 16000 ft | L_16000ft |
| L_25000ft | float | dB | Noise level at slant distance 25000 ft | L_25000ft |

## `anp_spectral_wide`
Source: `ANP2.3_Spectral_classes.csv` · key: ['spectral_class_id'] · rows: 41

| column | type | unit | description | source header |
|---|---|---|---|---|
| spectral_class_id | int | - | Spectral class identifier | Spectral Class ID |
| op_type | cat | - | Departure | Approach | Op Type |
| description | str | - | Class description | Description |
| L_50Hz | float | dB | 1/3-octave band level at 50 Hz (normalised) | L_50Hz |
| L_63Hz | float | dB | 1/3-octave band level at 63 Hz (normalised) | L_63Hz |
| L_80Hz | float | dB | 1/3-octave band level at 80 Hz (normalised) | L_80Hz |
| L_100Hz | float | dB | 1/3-octave band level at 100 Hz (normalised) | L_100Hz |
| L_125Hz | float | dB | 1/3-octave band level at 125 Hz (normalised) | L_125Hz |
| L_160Hz | float | dB | 1/3-octave band level at 160 Hz (normalised) | L_160Hz |
| L_200Hz | float | dB | 1/3-octave band level at 200 Hz (normalised) | L_200Hz |
| L_250Hz | float | dB | 1/3-octave band level at 250 Hz (normalised) | L_250Hz |
| L_315Hz | float | dB | 1/3-octave band level at 315 Hz (normalised) | L_315Hz |
| L_400Hz | float | dB | 1/3-octave band level at 400 Hz (normalised) | L_400Hz |
| L_500Hz | float | dB | 1/3-octave band level at 500 Hz (normalised) | L_500Hz |
| L_630Hz | float | dB | 1/3-octave band level at 630 Hz (normalised) | L_630Hz |
| L_800Hz | float | dB | 1/3-octave band level at 800 Hz (normalised) | L_800Hz |
| L_1000Hz | float | dB | 1/3-octave band level at 1000 Hz (normalised) | L_1000Hz |
| L_1250Hz | float | dB | 1/3-octave band level at 1250 Hz (normalised) | L_1250Hz |
| L_1600Hz | float | dB | 1/3-octave band level at 1600 Hz (normalised) | L_1600Hz |
| L_2000Hz | float | dB | 1/3-octave band level at 2000 Hz (normalised) | L_2000Hz |
| L_2500Hz | float | dB | 1/3-octave band level at 2500 Hz (normalised) | L_2500Hz |
| L_3150Hz | float | dB | 1/3-octave band level at 3150 Hz (normalised) | L_3150Hz |
| L_4000Hz | float | dB | 1/3-octave band level at 4000 Hz (normalised) | L_4000Hz |
| L_5000Hz | float | dB | 1/3-octave band level at 5000 Hz (normalised) | L_5000Hz |
| L_6300Hz | float | dB | 1/3-octave band level at 6300 Hz (normalised) | L_6300Hz |
| L_8000Hz | float | dB | 1/3-octave band level at 8000 Hz (normalised) | L_8000Hz |
| L_10000Hz | float | dB | 1/3-octave band level at 10000 Hz (normalised) | L_10000Hz |

## `anp_departure_steps`
Source: `ANP2.3_Default_departure_procedural_steps.csv` · key: ['acft_id', 'profile_id', 'stage_length', 'step_number'] · rows: 9378

| column | type | unit | description | source header |
|---|---|---|---|---|
| acft_id | id | - | ANP aircraft identifier | ACFT_ID |
| profile_id | id | - | Procedure profile identifier | Profile_ID |
| stage_length | cat | - | Stage length 1-9 or M | Stage Length |
| step_number | int | - | Order of the step within the profile | Step Number |
| step_type | cat | - | Takeoff | Climb | Accelerate | Step Type |
| thrust_rating | cat | - | Thrust rating used in this step | Thrust Rating |
| flap_id | id | - | Flap configuration (joins aerodynamic coefficients) | Flap_ID |
| end_altitude_ft | float | ft | Climb step end altitude (AFE) | End Point Altitude (ft) |
| rate_of_climb_ftmin | float | ft/min | Accelerate step rate of climb | Rate Of Climb (ft/min) |
| end_cas_kt | float | kt | Accelerate step end calibrated airspeed | End Point CAS (kt) |
| accel_percentage | float | % | Energy share used for acceleration | Accel Percentage (%) |

## `anp_approach_steps` (carried, not used for OEJN departures)
Source: `ANP2.3_Default_approach_procedural_steps.csv` · key: ['acft_id', 'profile_id', 'step_number'] · rows: 1065

| column | type | unit | description | source header |
|---|---|---|---|---|
| acft_id | id | - | ANP aircraft identifier | ACFT_ID |
| profile_id | id | - | Procedure profile identifier | Profile_ID |
| step_number | int | - | Order of the step | Step Number |
| step_type | cat | - | Approach step type | Step Type |
| flap_id | id | - | Flap configuration | Flap_ID |
| start_altitude_ft | float | ft | Start altitude | Start Altitude(ft) |
| start_cas_kt | float | kt | Start calibrated airspeed | Start CAS (kt) |
| descent_angle_deg | float | deg | Descent angle | Descent Angle (deg) |
| touchdown_roll_ft | float | ft | Touchdown roll | Touchdown Roll (ft) |
| distance_ft | float | ft | Step distance | Distance (ft) |
| start_thrust | float | per aircraft power_parameter (CNT lb/engine for jets) | Start thrust | Start Thrust |

## `anp_jet_coefficients`
Source: `ANP2.3_Jet_engine_coefficients.csv` · key: ['acft_id', 'thrust_rating'] · rows: 464

| column | type | unit | description | source header |
|---|---|---|---|---|
| acft_id | id | - | ANP aircraft identifier | ACFT_ID |
| thrust_rating | cat | - | Thrust rating | Thrust Rating |
| E | float | lb | Jet thrust coefficient E | E |
| F | float | lb/kt | Jet thrust coefficient F | F |
| Ga | float | lb/ft | Jet thrust coefficient Ga | Ga |
| Gb | float | lb/ft^2 | Jet thrust coefficient Gb | Gb |
| H | float | lb/degC | Jet thrust coefficient H | H |
| K1 | float | lb/EPR | EPR/N1 coefficient K1 (where applicable) | K1 |
| K2 | float | lb/EPR^2 | EPR/N1 coefficient K2 (where applicable) | K2 |
| K3 | float | lb/(N1/sqrt(theta)) | EPR/N1 coefficient K3 (where applicable) | K3 |
| K4 | float | lb/(N1/sqrt(theta))^2 | EPR/N1 coefficient K4 (where applicable) | K4 |

## `anp_propeller_coefficients` (carried, not used for OEJN departures)
Source: `ANP2.3_Propeller_engine_coefficients.csv` · key: ['acft_id', 'thrust_rating'] · rows: 38

| column | type | unit | description | source header |
|---|---|---|---|---|
| acft_id | id | - | ANP aircraft identifier | ACFT_ID |
| thrust_rating | cat | - | Thrust rating | Thrust Rating |
| propeller_efficiency | float | - | Propeller efficiency | Propeller Efficiency |
| installed_power_hp | float | hp | Installed net propulsive power | Installed Net Propulsive Power (hp) |

## `anp_aero_coefficients`
Source: `ANP2.3_Aerodynamic_coefficients.csv` · key: ['acft_id', 'op_type', 'flap_id'] · rows: 1218

| column | type | unit | description | source header |
|---|---|---|---|---|
| acft_id | id | - | ANP aircraft identifier | ACFT_ID |
| op_type | cat | - | A | D | Op Type |
| flap_id | id | - | Flap configuration | Flap_ID |
| B | float | ft/lb | Take-off ground-roll coefficient B | B |
| C | float | kt/sqrt(lb) | Take-off speed coefficient C | C |
| D | float | kt/sqrt(lb) | Landing speed coefficient D | D |
| R | float | - | Drag-to-lift ratio R | R |

## `anp_default_weights`
Source: `ANP2.3_Default_weights.csv` · key: ['acft_id', 'stage_length'] · rows: 632

| column | type | unit | description | source header |
|---|---|---|---|---|
| acft_id | id | - | ANP aircraft identifier | ACFT_ID |
| stage_length | cat | - | Stage length 1-9 or M | Stage Length |
| weight_lb | float | lb | Default take-off weight for the stage length | Weight (lb) |

## `anp_fixed_point_profiles` (carried, not used for OEJN departures)
Source: `ANP2.3_Default_fixed_point_profiles.csv` · key: ['acft_id', 'op_type', 'profile_id', 'stage_length', 'point_number'] · rows: 896

| column | type | unit | description | source header |
|---|---|---|---|---|
| acft_id | id | - | ANP aircraft identifier | ACFT_ID |
| op_type | cat | - | A | D | Op Type |
| profile_id | id | - | Profile identifier | Profile_ID |
| stage_length | cat | - | Stage length | Stage Length |
| point_number | int | - | Point order | Point Number |
| distance_ft | float | ft | Distance along track | Distance (ft) |
| altitude_afe_ft | float | ft | Altitude above field elevation | Altitude AFE (ft) |
| tas_kt | float | kt | True airspeed | TAS (kt) |
| power_setting | float | per aircraft power_parameter (CNT lb/engine for jets) | Power setting | Power Setting |

## `anp_npd_long`
Tidy reshape of the wide table; rows: 27760

| column | unit | description |
|---|---|---|
| distance_ft | ft | NPD slant distance |
| level_db | dB | Noise level |
| source_column | - | Wide-format source column of this value |

## `anp_spectral_long`
Tidy reshape of the wide table; rows: 984

| column | unit | description |
|---|---|---|
| frequency_hz | Hz | 1/3-octave band centre frequency |
| level_db | dB | Normalised band level |

## `aircraft_noise_mapping` (integration contract: aircraft identity → A5 → noise model)

| column | description |
|---|---|
| icao_type | ICAO Doc 8643 type designator (input key) |
| airframe_model_in | Airframe model from the aircraft-identity input (optional) |
| engine_type_in | Engine type from the aircraft-identity input (optional) |
| mtow_kg_in | MTOW from the aircraft-identity input (optional) |
| mapping_method | Resolution rule applied (see methodology) |
| anp_acft_id | ANP aircraft used to model this type |
| delta_dep_db | Departure decibel adjustment of the proxy (Doc 29 Vol 1 Method A) |
| delta_app_db | Approach decibel adjustment (carried; departures study) |
| n_dep | Departure movement factor (Method B; valid for energy metrics only) |
| n_app | Approach movement factor (Method B) |
| selected_airframe | Certified configuration used (configuration-tab methods) |
| selected_engine | Certified engine used (configuration-tab methods) |
| selected_mtow_kg | Certified MTOW used (configuration-tab methods) |
| conservative_choice | True when an unknown MTOW/engine was resolved with the Doc 29 conservative rule |
| evidence | Human-readable justification |
| source_ref | File | sheet | row of the evidence |
| review_status | For analyst proxies: PENDING | REVIEWED |
| notes | Warnings, fallbacks and pending items |
| confidence | HIGH | MEDIUM | LOW | NONE (categorical, evidence-based) |
| abs_delta_dep_db | |delta_dep| (large values flag a weak proxy) |
| candidates_count | Number of candidate mappings considered (see mapping_candidates) |
| verified_data_available | EASA holds newer verified ANP data for this ICAO type |
| verified_variants | Verified airframe/engine variants |
| delta_applied_db | Adjustment to add to proxy NPD levels under the configured method |
| n_applied | Movement multiplier under the configured method (1 for Method A) |
| substitution_method | A (dB on NPD, all metrics) or B (movement factor, energy metrics only) |
| usable_for_noise | True when an ANP aircraft and a numeric delta exist |
| npd_id | NPD set of the ANP aircraft |
| dep_spectral_class_id | Departure spectral class |
| lateral_directivity | Wing | Fuselage | Prop (engine-installation correction) |
| power_parameter | NPD power parameter (as ANP) |
| power_parameter_kind | Machine-readable power parameter |
| anp_engine_type | Jet | Turboprop | Piston |
| anp_n_engines | Number of engines of the ANP aircraft |
| has_jet_coefficients | ANP aircraft has jet thrust coefficients |
| has_hitemp_ratings | ANP aircraft has HiTemp thrust ratings |
| thrust_ratings | Available thrust ratings |
| has_departure_steps | ANP aircraft has procedural departure steps |
| departure_profiles | Available departure profiles |
| anp_description | ANP airframe/engine description |
| anp_mtow_lb | ANP MTOW (lb) |
| a5_release_id | A5 release that produced this row |

## Other tables

- `mapping_candidates` — 213 rows; columns: icao_type, airframe_model_in, engine_type_in, mtow_kg_in, source, anp_proxy, variant, delta_dep_db, src_row, selected
- `mapping_analyst_proxies` — 3 rows; columns: icao_type, description, proxy_anp_id, rationale, miss_flyover_epndb, miss_lateral_epndb, miss_cert_source, reviewer, review_date, review_status, notes
- `easa_subst_icao` — 210 rows; columns: src_file, src_member, src_row, airframe_manufacturer, icao_code, variant, anp_proxy, delta_dep_db, delta_app_db, n_dep, n_app
- `easa_subst_config` — 19565 rows; columns: src_file, src_member, src_row, source, record_number, icao_code, airframe_manufacturer, airframe_type, engine_manufacturer, engine_type, propeller_manufacturer, propeller_type, engine_number, mtow_kg, mlw_kg, noise_chapter, lateral_epndb, flyover_epndb, approach_epndb, anp_proxy, delta_dep_db, delta_app_db, n_dep, n_app, dep_cert_level_epndb
- `easa_verified_types` — 23 rows; columns: verified_anp_id, airframe_manufacturer, airframe_type, engine_manufacturer, engine_type, date_published, src_file, src_member, src_row, comments, icao_code, icao_code_source
- `doc29_constants` — 16 rows; columns: name, value, unit, meaning, source, location
- `doc29_table_d1` — 24 rows; columns: frequency_hz, attenuation_db_per_100m, source, location
- `units_registry` — 77 rows; columns: table, column, native_unit, si_unit, si_factor, note
- `normalization_log` — 339 rows; columns: table, column, src_file, src_member, src_row, original, normalised, rule
- `sources` — 9 rows; columns: source_key, file, publisher, title, version, date, sha256, bytes, sha256_matches_lock
- `qc_results` — 134 rows; columns: check_id, category, severity, message, n_affected, details
- `vol3_b2_npd_validation` — 3516 rows; columns: src_row, case_ID, receptor_ID, segment_ID, d_ft, p_lb, ref_sel, a5_sel, power_extrapolated, distance_extrapolated, distance_floored, abs_diff_db
- `vol3_fixture_aircraft` — 3 rows; columns: src_file, src_member, src_row, acft_id, description, engine_type, n_engines, weight_class, mtow_lb, mlw_lb, max_landing_distance_ft, max_static_thrust_lb, npd_id, power_parameter, app_spectral_class_id, dep_spectral_class_id, lateral_directivity
- `vol3_fixture_jet_coefficients` — 6 rows; columns: src_file, src_member, src_row, acft_id, thrust_rating, E, F, Ga, Gb, H, K1, K2, K3, K4
- `vol3_fixture_npd` — 36 rows; columns: src_file, src_member, src_row, npd_id, noise_metric, op_mode, power_setting, L_200ft, L_400ft, L_630ft, L_1000ft, L_2000ft, L_4000ft, L_6300ft, L_10000ft, L_16000ft, L_25000ft
- `vol3_fixture_spectral` — 6 rows; columns: src_file, src_member, src_row, spectral_class_id, op_type, description, L_50Hz, L_63Hz, L_80Hz, L_100Hz, L_125Hz, L_160Hz, L_200Hz, L_250Hz, L_315Hz, L_400Hz, L_500Hz, L_630Hz, L_800Hz, L_1000Hz, L_1250Hz, L_1600Hz, L_2000Hz, L_2500Hz, L_3150Hz, L_4000Hz, L_5000Hz, L_6300Hz, L_8000Hz, L_10000Hz
