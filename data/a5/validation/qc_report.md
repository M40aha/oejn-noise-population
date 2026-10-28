# A5 quality-control report — `a5-anp2.3-doc29e5-v1`

Built 2026-10-28T19:13:58+00:00 · Python 3.13.16 · pandas 3.0.5 · duckdb 2.0.0

## Summary

| Severity | Checks |
|---|---|
| ✅ PASS | 106 |
| ℹ️ INFO | 22 |
| ⚠️ WARNING | 5 |
| ❌ ERROR | 0 |
| ❓ UNRESOLVED | 1 |

**Doc 29 Vol 3 B-2 NPD validation:** 3516 segments, max |difference| = 1.28e-13 dB (tolerance 0.01 dB).

## Sources

| source_key | file | version | sha256_matches_lock |
|---|---|---|---|
| anp_tables | easa_anp_legacy_v2.3_tables.zip | 2.3 | True |
| anp_release_note | easa_anp_legacy_v2.3_release_note.pdf | 2.3 | True |
| easa_substitutions | easa_anp_aircraft_substitutions.xlsx | baseline ANP 2.2 (revision 22-02-2018, per workbook 'read me') | True |
| easa_verified_types | easa_verified_anp_aircraft_types.xlsx | as downloaded 2026-10-20 | True |
| doc29_vol1 | ecac_doc29_5e_vol1_applications.pdf | 5th Edition (endorsed DGCA/166, 19 May 2026); PDF metadata title wrongly says 4th Edition | True |
| doc29_vol2 | ecac_doc29_5e_vol2_technical.pdf | 5th Edition (endorsed DGCA/166, 19 May 2026); PDF metadata title wrongly says 4th Edition | True |
| doc29_vol3 | ecac_doc29_5e_vol3_reference.pdf | 5th Edition (endorsed DGCA/166, 19 May 2026); PDF metadata title wrongly says 4th Edition | True |
| doc29_vol3_wb1 | ecac_doc29_5e_vol3_workbook_part1.xlsx | 5th Edition | True |
| doc29_vol3_wb2 | ecac_doc29_5e_vol3_workbook_part2.xlsx | 5th Edition | True |

## Source

| check_id | severity | message | n_affected |
|---|---|---|---|
| source.sha256.anp_tables | ✅ PASS | easa_anp_legacy_v2.3_tables.zip: SHA-256 matches the locked value | 0 |
| source.sha256.anp_release_note | ✅ PASS | easa_anp_legacy_v2.3_release_note.pdf: SHA-256 matches the locked value | 0 |
| source.sha256.easa_substitutions | ✅ PASS | easa_anp_aircraft_substitutions.xlsx: SHA-256 matches the locked value | 0 |
| source.sha256.easa_verified_types | ✅ PASS | easa_verified_anp_aircraft_types.xlsx: SHA-256 matches the locked value | 0 |
| source.sha256.doc29_vol1 | ✅ PASS | ecac_doc29_5e_vol1_applications.pdf: SHA-256 matches the locked value | 0 |
| source.sha256.doc29_vol2 | ✅ PASS | ecac_doc29_5e_vol2_technical.pdf: SHA-256 matches the locked value | 0 |
| source.sha256.doc29_vol3 | ✅ PASS | ecac_doc29_5e_vol3_reference.pdf: SHA-256 matches the locked value | 0 |
| source.sha256.doc29_vol3_wb1 | ✅ PASS | ecac_doc29_5e_vol3_workbook_part1.xlsx: SHA-256 matches the locked value | 0 |
| source.sha256.doc29_vol3_wb2 | ✅ PASS | ecac_doc29_5e_vol3_workbook_part2.xlsx: SHA-256 matches the locked value | 0 |

## Structure

| check_id | severity | message | n_affected |
|---|---|---|---|
| structure.columns.anp_aircraft | ✅ PASS | anp_aircraft: all 16 expected columns present | 0 |
| structure.cast.anp_aircraft | ✅ PASS | anp_aircraft: every value cast to its declared type | 0 |
| structure.category.anp_aircraft.engine_type | ✅ PASS | anp_aircraft.engine_type: all values in controlled vocabulary | 0 |
| structure.category.anp_aircraft.weight_class | ✅ PASS | anp_aircraft.weight_class: all values in controlled vocabulary | 0 |
| structure.category.anp_aircraft.lateral_directivity | ✅ PASS | anp_aircraft.lateral_directivity: all values in controlled vocabulary | 0 |
| structure.category.anp_aircraft.power_parameter | ✅ PASS | anp_aircraft.power_parameter: all values in controlled vocabulary | 0 |
| structure.key_unique.anp_aircraft | ✅ PASS | anp_aircraft: primary key ['acft_id'] unique after normalisation | 0 |
| structure.rows.anp_aircraft | ℹ️ INFO | anp_aircraft: 155 rows | 155 |
| structure.columns.anp_npd_wide | ✅ PASS | anp_npd_wide: all 14 expected columns present | 0 |
| structure.cast.anp_npd_wide | ✅ PASS | anp_npd_wide: every value cast to its declared type | 0 |
| structure.category.anp_npd_wide.noise_metric | ✅ PASS | anp_npd_wide.noise_metric: all values in controlled vocabulary | 0 |
| structure.category.anp_npd_wide.op_mode | ✅ PASS | anp_npd_wide.op_mode: all values in controlled vocabulary | 0 |
| structure.key_unique.anp_npd_wide | ✅ PASS | anp_npd_wide: primary key ['npd_id', 'noise_metric', 'op_mode', 'power_setting'] unique after normalisation | 0 |
| structure.rows.anp_npd_wide | ℹ️ INFO | anp_npd_wide: 2776 rows | 2776 |
| structure.columns.anp_spectral_wide | ✅ PASS | anp_spectral_wide: all 27 expected columns present | 0 |
| structure.cast.anp_spectral_wide | ✅ PASS | anp_spectral_wide: every value cast to its declared type | 0 |
| structure.category.anp_spectral_wide.op_type | ✅ PASS | anp_spectral_wide.op_type: all values in controlled vocabulary | 0 |
| structure.key_unique.anp_spectral_wide | ✅ PASS | anp_spectral_wide: primary key ['spectral_class_id'] unique after normalisation | 0 |
| structure.rows.anp_spectral_wide | ℹ️ INFO | anp_spectral_wide: 41 rows | 41 |
| structure.columns.anp_departure_steps | ✅ PASS | anp_departure_steps: all 11 expected columns present | 0 |
| structure.cast.anp_departure_steps | ✅ PASS | anp_departure_steps: every value cast to its declared type | 0 |
| structure.category.anp_departure_steps.step_type | ✅ PASS | anp_departure_steps.step_type: all values in controlled vocabulary | 0 |
| structure.category.anp_departure_steps.stage_length | ✅ PASS | anp_departure_steps.stage_length: all values in controlled vocabulary | 0 |
| structure.key_unique.anp_departure_steps | ✅ PASS | anp_departure_steps: primary key ['acft_id', 'profile_id', 'stage_length', 'step_number'] unique after normalisation | 0 |
| structure.rows.anp_departure_steps | ℹ️ INFO | anp_departure_steps: 9378 rows | 9378 |
| structure.columns.anp_approach_steps | ✅ PASS | anp_approach_steps: all 11 expected columns present | 0 |
| structure.cast.anp_approach_steps | ✅ PASS | anp_approach_steps: every value cast to its declared type | 0 |
| structure.key_unique.anp_approach_steps | ✅ PASS | anp_approach_steps: primary key ['acft_id', 'profile_id', 'step_number'] unique after normalisation | 0 |
| structure.rows.anp_approach_steps | ℹ️ INFO | anp_approach_steps: 1065 rows | 1065 |
| structure.columns.anp_jet_coefficients | ✅ PASS | anp_jet_coefficients: all 11 expected columns present | 0 |
| structure.cast.anp_jet_coefficients | ✅ PASS | anp_jet_coefficients: every value cast to its declared type | 0 |
| structure.key_unique.anp_jet_coefficients | ✅ PASS | anp_jet_coefficients: primary key ['acft_id', 'thrust_rating'] unique after normalisation | 0 |
| structure.rows.anp_jet_coefficients | ℹ️ INFO | anp_jet_coefficients: 464 rows | 464 |
| structure.columns.anp_propeller_coefficients | ✅ PASS | anp_propeller_coefficients: all 4 expected columns present | 0 |
| structure.cast.anp_propeller_coefficients | ✅ PASS | anp_propeller_coefficients: every value cast to its declared type | 0 |
| structure.key_unique.anp_propeller_coefficients | ✅ PASS | anp_propeller_coefficients: primary key ['acft_id', 'thrust_rating'] unique after normalisation | 0 |
| structure.rows.anp_propeller_coefficients | ℹ️ INFO | anp_propeller_coefficients: 38 rows | 38 |
| structure.columns.anp_aero_coefficients | ✅ PASS | anp_aero_coefficients: all 7 expected columns present | 0 |
| structure.cast.anp_aero_coefficients | ✅ PASS | anp_aero_coefficients: every value cast to its declared type | 0 |
| structure.category.anp_aero_coefficients.op_type | ✅ PASS | anp_aero_coefficients.op_type: all values in controlled vocabulary | 0 |
| structure.key_unique.anp_aero_coefficients | ✅ PASS | anp_aero_coefficients: primary key ['acft_id', 'op_type', 'flap_id'] unique after normalisation | 0 |
| structure.rows.anp_aero_coefficients | ℹ️ INFO | anp_aero_coefficients: 1218 rows | 1218 |
| structure.columns.anp_default_weights | ✅ PASS | anp_default_weights: all 3 expected columns present | 0 |
| structure.cast.anp_default_weights | ✅ PASS | anp_default_weights: every value cast to its declared type | 0 |
| structure.category.anp_default_weights.stage_length | ✅ PASS | anp_default_weights.stage_length: all values in controlled vocabulary | 0 |
| structure.key_unique.anp_default_weights | ✅ PASS | anp_default_weights: primary key ['acft_id', 'stage_length'] unique after normalisation | 0 |
| structure.rows.anp_default_weights | ℹ️ INFO | anp_default_weights: 632 rows | 632 |
| structure.columns.anp_fixed_point_profiles | ✅ PASS | anp_fixed_point_profiles: all 9 expected columns present | 0 |
| structure.cast.anp_fixed_point_profiles | ✅ PASS | anp_fixed_point_profiles: every value cast to its declared type | 0 |
| structure.key_unique.anp_fixed_point_profiles | ✅ PASS | anp_fixed_point_profiles: primary key ['acft_id', 'op_type', 'profile_id', 'stage_length', 'point_number'] unique after normalisation | 0 |
| structure.rows.anp_fixed_point_profiles | ℹ️ INFO | anp_fixed_point_profiles: 896 rows | 896 |
| structure.npd_long_roundtrip | ✅ PASS | NPD long -> wide reproduces all 27760 source values exactly | 0 |
| structure.spectral_long_roundtrip | ✅ PASS | Spectral long -> wide reproduces all 984 source values exactly | 0 |
| structure.rows.easa_subst_icao | ℹ️ INFO | EASA 'by ICAO code': 210 rows, 189 ICAO codes, 21 codes with several variants | 210 |
| structure.rows.easa_subst_config | ℹ️ INFO | EASA 'by aircraft configuration': 19565 certified configurations | 19565 |
| structure.table_d1_bands | ✅ PASS | Table D-1 covers exactly the 24 spectral-class bands | 0 |

## Normalisation

| check_id | severity | message | n_affected |
|---|---|---|---|
| normalisation.whitespace.anp_aircraft | ℹ️ INFO | anp_aircraft: 3 cells had leading/trailing whitespace removed (logged) | 3 |
| normalisation.whitespace.anp_npd_wide | ✅ PASS | anp_npd_wide: no whitespace normalisation needed | 0 |
| normalisation.whitespace.anp_spectral_wide | ℹ️ INFO | anp_spectral_wide: 41 cells had leading/trailing whitespace removed (logged) | 41 |
| normalisation.whitespace.anp_departure_steps | ℹ️ INFO | anp_departure_steps: 294 cells had leading/trailing whitespace removed (logged) | 294 |
| normalisation.whitespace.anp_approach_steps | ℹ️ INFO | anp_approach_steps: 1 cells had leading/trailing whitespace removed (logged) | 1 |
| normalisation.whitespace.anp_jet_coefficients | ✅ PASS | anp_jet_coefficients: no whitespace normalisation needed | 0 |
| normalisation.whitespace.anp_propeller_coefficients | ✅ PASS | anp_propeller_coefficients: no whitespace normalisation needed | 0 |
| normalisation.whitespace.anp_aero_coefficients | ✅ PASS | anp_aero_coefficients: no whitespace normalisation needed | 0 |
| normalisation.whitespace.anp_default_weights | ✅ PASS | anp_default_weights: no whitespace normalisation needed | 0 |
| normalisation.whitespace.anp_fixed_point_profiles | ✅ PASS | anp_fixed_point_profiles: no whitespace normalisation needed | 0 |

## Integrity

| check_id | severity | message | n_affected |
|---|---|---|---|
| integrity.aircraft.npd_id->npd | ✅ PASS | aircraft.npd_id->npd: every reference resolves | 0 |
| integrity.aircraft.dep_spectral->spectral | ✅ PASS | aircraft.dep_spectral->spectral: every reference resolves | 0 |
| integrity.aircraft.app_spectral->spectral | ✅ PASS | aircraft.app_spectral->spectral: every reference resolves | 0 |
| integrity.dep_steps.acft->aircraft | ✅ PASS | dep_steps.acft->aircraft: every reference resolves | 0 |
| integrity.dep_steps.flap->aero(D) | ✅ PASS | dep_steps.flap->aero(D): every reference resolves | 0 |
| integrity.dep_steps.stage->weights | ✅ PASS | dep_steps.stage->weights: every reference resolves | 0 |
| integrity.jet_coeffs.acft->aircraft | ✅ PASS | jet_coeffs.acft->aircraft: every reference resolves | 0 |
| integrity.prop_coeffs.acft->aircraft | ✅ PASS | prop_coeffs.acft->aircraft: every reference resolves | 0 |
| integrity.aero.acft->aircraft | ✅ PASS | aero.acft->aircraft: every reference resolves | 0 |
| integrity.weights.acft->aircraft | ✅ PASS | weights.acft->aircraft: every reference resolves | 0 |
| integrity.fixed_point.acft->aircraft | ✅ PASS | fixed_point.acft->aircraft: every reference resolves | 0 |
| integrity.app_steps.acft->aircraft | ✅ PASS | app_steps.acft->aircraft: every reference resolves | 0 |
| integrity.dep_steps.thrust_rating->jet_coeffs | ✅ PASS | Every jet departure step's thrust rating has engine coefficients | 0 |
| integrity.dep_spectral_type | ✅ PASS | Every departure spectral class is of Departure type | 0 |
| integrity.npd_unused | ✅ PASS | Every NPD set is used by at least one aircraft | 0 |
| integrity.npd_power_parameter_consistent | ✅ PASS | All aircraft sharing an NPD set (29 shared sets) use the same power parameter | 0 |
| integrity.jets_without_jet_coefficients | ℹ️ INFO | 7 legacy jets have no jet coefficients (they use fixed-point profiles) | 7 |
| integrity.aircraft_without_departure_steps | ℹ️ INFO | 13 aircraft have no procedural departure steps | 13 |

## Physics

| check_id | severity | message | n_affected |
|---|---|---|---|
| physics.npd_complete | ✅ PASS | NPD: no missing level at any of the 10 distances | 0 |
| physics.npd_range | ✅ PASS | NPD: all levels within 0-160 dB | 0 |
| physics.npd_power_positive | ✅ PASS | NPD: all power settings > 0 | 0 |
| physics.npd_decreasing_with_distance | ✅ PASS | NPD: level strictly decreases with distance on every curve | 0 |
| physics.npd_monotonic_in_power | ⚠️ WARNING | NPD: level decreases with increasing power somewhere in 97 of 888 curve families (9 are departure SEL/LAmax). Not an error by itself: the ANP 2.3 release note documents deliberate non-monotonic patterns (e.g. ATR72). Doc 29 interpolation handles them linearly as tabulated. | 97 |
| physics.npd_power_points | ℹ️ INFO | NPD: 456 of 888 curve families have only 2 power settings (extrapolation more likely) | 456 |
| physics.sel_vs_lamax | ⚠️ WARNING | SEL < LAmax in 94 curve pairs; 94 at 200 ft (plausible: effective event duration < 1 s at very short range) and 2 pairs at > 200 ft | 94 |
| physics.spectral_normalisation | ✅ PASS | Every spectral class equals 70.0 dB at 1 kHz (normalised spectra) | 0 |
| physics.spectral_complete | ✅ PASS | Spectral: all 24 bands present | 0 |
| physics.default_weight_le_mtow | ⚠️ WARNING | ANP 2.3 source inconsistency: 5 default stage-length weights exceed the aircraft's own tabulated MTOW (values preserved unchanged; do not use these stage lengths without an explicit, documented cap) | 5 |
| physics.mlw_le_mtow | ✅ PASS | MLW <= MTOW for all aircraft | 0 |

## Logic

| check_id | severity | message | n_affected |
|---|---|---|---|
| logic.dep_steps_contiguous | ✅ PASS | All 1076 departure profiles have contiguous step numbers 1..n | 0 |
| logic.dep_steps_start_takeoff | ✅ PASS | Every departure profile starts with a Takeoff step | 0 |
| logic.climb_has_end_altitude | ✅ PASS | Every Climb step has an end altitude | 0 |
| logic.accelerate_complete | ✅ PASS | Every Accelerate step has an end CAS and a rate of climb or acceleration percentage | 0 |
| logic.climb_altitudes_non_decreasing | ✅ PASS | Climb end altitudes never decrease within a profile | 0 |
| logic.takeoff_flaps_have_B_C | ✅ PASS | Every take-off flap configuration has coefficients B and C | 0 |
| logic.aero_R_present | ✅ PASS | Every aerodynamic configuration has R | 0 |
| logic.stage_length_M | ℹ️ INFO | Stage length 'M' appears for 5 aircraft; its weight / MTOW ranges 0.963-1.000. Interpreted as a maximum-weight profile, kept as category 'M'. | 5 |

## Cross Source

| check_id | severity | message | n_affected |
|---|---|---|---|
| cross_source.easa_baseline_version | ⚠️ WARNING | EASA substitution workbook revision history ends at ANP 2.2 (22-02-2018); A5 uses ANP 2.3 data. All proxies still resolve (checked below); 2.3 revised A350-941 and 7378MAX data after these deltas were derived. | 0 |
| cross_source.easa_icao_proxies_in_anp | ✅ PASS | Every EASA 'icao' proxy exists in ANP 2.3 | 0 |
| cross_source.easa_icao_N_vs_delta_dep | ✅ PASS | EASA 'icao': N_dep = 10^(delta_dep/10) within published rounding for all rows | 0 |
| cross_source.easa_icao_N_vs_delta_app | ✅ PASS | EASA 'icao': N_app = 10^(delta_app/10) within published rounding for all rows | 0 |
| cross_source.easa_config_proxies_in_anp | ✅ PASS | Every EASA 'config' proxy exists in ANP 2.3 | 0 |
| cross_source.easa_config_N_vs_delta_dep | ✅ PASS | EASA 'config': N_dep = 10^(delta_dep/10) within published rounding for all rows | 0 |
| cross_source.easa_config_N_vs_delta_app | ✅ PASS | EASA 'config': N_app = 10^(delta_app/10) within published rounding for all rows | 0 |
| cross_source.easa_icao_is_noisiest_config | ✅ PASS | ICAO-tab departure delta equals the maximum configuration-tab delta for 210/210 ICAO/proxy pairs present in both tabs (0 pairs have no configuration rows) | 0 |
| cross_source.verified_types_icao | ✅ PASS | EASA verified-types list: 14 datasets, 23 airframe/engine rows; 17 ICAO codes from EASA, 6 analyst-entered, 0 unresolved | 0 |

## Validation

| check_id | severity | message | n_affected |
|---|---|---|---|
| validation.npd_lookup_reproduces_anp_grid | ✅ PASS | NPD lookup returns every tabulated ANP 2.3 value at its grid point (max /diff/ = 1.8e-15 dB, 27760 points) | 0 |
| validation.vol3_fixture.A-1_Aircraft | ✅ PASS | Vol 3 A-1_Aircraft: 14/14 columns map onto the A5 canonical schema | 0 |
| validation.vol3_fixture.A-2_Jet_Coefficients | ✅ PASS | Vol 3 A-2_Jet_Coefficients: 11/11 columns map onto the A5 canonical schema | 0 |
| validation.vol3_fixture.A-7_NPD_Curves | ✅ PASS | Vol 3 A-7_NPD_Curves: 14/14 columns map onto the A5 canonical schema | 0 |
| validation.vol3_fixture.A-8_Spectral_Class | ✅ PASS | Vol 3 A-8_Spectral_Class: 27/27 columns map onto the A5 canonical schema | 0 |
| validation.vol3_fixture.A-4_Aerodynamic_Coefficients | ℹ️ INFO | Vol 3 A-4 stores take-off C and landing D in one 'C/D' column; ANP 2.3 stores C and D separately. A5 keeps the ANP layout; a Vol 3 loader must split C/D by operation type (D->C, A->D). | 1 |
| validation.vol3_b2_baseline_sel | ✅ PASS | NPD lookup reproduces Vol 3 B-2 baseline_SEL for 3516 segments: max /diff/ = 1.28e-13 dB, RMS = 1.62e-14 dB (ERROR > 0.01 dB, target <= 0.001 dB). Includes 939 distance-extrapolated and 1784 power-extrapolated lookups. | 0 |
| validation.unit_constants_vs_vol3 | ✅ PASS | Exact unit constants reproduce Vol 3 metric/imperial receptor coordinates: worst relative difference 1.1e-16 over 54 values (tolerance 1e-12). | 0 |

## Mapping

| check_id | severity | message | n_affected |
|---|---|---|---|
| mapping.icao_reference.anp_exists | ✅ PASS | icao_reference: every mapped ANP aircraft exists in ANP 2.3 | 0 |
| mapping.icao_reference.npd_exists | ✅ PASS | icao_reference: every mapped aircraft has an NPD set | 0 |
| mapping.icao_reference.coverage | ℹ️ INFO | icao_reference: 192 keys -> ANALYST_PROXY 3, EASA_ICAO 168, EASA_ICAO_AMBIGUOUS 21 | 192 |
| mapping.icao_reference.pending_delta | ❓ UNRESOLVED | icao_reference: 3 analyst proxies await certified levels (Eq. 6-1); not usable until filled: ['A339', 'B39M', 'B78X'] | 3 |
| mapping.icao_reference.large_delta | ⚠️ WARNING | icao_reference: 13 mappings with /delta_dep/ >= 5 dB (Doc 29 Vol 1 note 2: proxy may be inappropriate) | 13 |

## Mapping overview (ICAO-only resolution of every EASA code)

| mapping_method | confidence | types |
|---|---|---|
| ANALYST_PROXY | NONE | 3 |
| EASA_ICAO | HIGH | 27 |
| EASA_ICAO | MEDIUM | 141 |
| EASA_ICAO_AMBIGUOUS | LOW | 21 |

### Types needing attention

| icao_type | mapping_method | anp_acft_id | delta_dep_db | confidence | notes |
|---|---|---|---|---|---|
| A20N | EASA_ICAO_AMBIGUOUS | A320-232 | -3.5 | LOW | resolve the engine (A3) to remove this ambiguity |
| A320 | EASA_ICAO_AMBIGUOUS | A320-211 | 0.2 | LOW | resolve the engine (A3) to remove this ambiguity |
| A332 | EASA_ICAO_AMBIGUOUS | A330-301 | 2.0 | LOW | resolve the engine (A3) to remove this ambiguity |
| A333 | EASA_ICAO_AMBIGUOUS | A330-301 | 2.0 | LOW | resolve the engine (A3) to remove this ambiguity |
| A339 | ANALYST_PROXY | A330-343 | nan | NONE | delta pending: certified levels of the missing type not yet entered (Eq. 6-1) |
| A388 | EASA_ICAO_AMBIGUOUS | A380-861 | 0.3 | LOW | resolve the engine (A3) to remove this ambiguity |
| AT75 | EASA_ICAO | HS748A | -9.2 | MEDIUM |  |
| ATP | EASA_ICAO | HS748A | -9.3 | MEDIUM |  |
| B39M | ANALYST_PROXY | 7378MAX | nan | NONE | delta pending: certified levels of the missing type not yet entered (Eq. 6-1) |
| B733 | EASA_ICAO_AMBIGUOUS | 7373B2 | 0.0 | LOW | resolve the engine (A3) to remove this ambiguity |
| B742 | EASA_ICAO_AMBIGUOUS | 74720B | 0.7 | LOW | resolve the engine (A3) to remove this ambiguity |
| B752 | EASA_ICAO_AMBIGUOUS | 757PW | 4.3 | LOW | resolve the engine (A3) to remove this ambiguity |
| B762 | EASA_ICAO_AMBIGUOUS | 767JT9 | 0.7 | LOW | resolve the engine (A3) to remove this ambiguity |
| B78X | ANALYST_PROXY | 7878R | nan | NONE | delta pending: certified levels of the missing type not yet entered (Eq. 6-1) |
| C500 | EASA_ICAO | CNA500 | 6.1 | MEDIUM |  |
| C550 | EASA_ICAO_AMBIGUOUS | CNA560U | 0.7 | LOW | resolve the engine (A3) to remove this ambiguity |
| C560 | EASA_ICAO_AMBIGUOUS | CNA560E | -8.9 | LOW | resolve the engine (A3) to remove this ambiguity |
| CN35 | EASA_ICAO | SF340 | 10.0 | MEDIUM |  |
| DC10 | EASA_ICAO_AMBIGUOUS | DC1030 | 2.6 | LOW | resolve the engine (A3) to remove this ambiguity |
| E145 | EASA_ICAO_AMBIGUOUS | EMB14L | 4.6 | LOW | resolve the engine (A3) to remove this ambiguity |
| F100 | EASA_ICAO_AMBIGUOUS | F10065 | 0.4 | LOW | resolve the engine (A3) to remove this ambiguity |
| F27 | EASA_ICAO_AMBIGUOUS | DHC830 | 0.3 | LOW | resolve the engine (A3) to remove this ambiguity |
| F28 | EASA_ICAO_AMBIGUOUS | F28MK4 | 0.8 | LOW | resolve the engine (A3) to remove this ambiguity |
| F2TH | EASA_ICAO_AMBIGUOUS | CL601 | 4.1 | LOW | resolve the engine (A3) to remove this ambiguity |
| FA20 | EASA_ICAO | FAL20 | 9.6 | MEDIUM |  |
| GLF2 | EASA_ICAO_AMBIGUOUS | GIIB | 0.0 | LOW | resolve the engine (A3) to remove this ambiguity |
| H25B | EASA_ICAO | IA1125 | 7.6 | MEDIUM |  |
| IL86 | EASA_ICAO | DC8QN | 5.0 | MEDIUM |  |
| IL96 | EASA_ICAO | A340-211 | 6.6 | MEDIUM |  |
| L101 | EASA_ICAO_AMBIGUOUS | L10115 | 0.0 | LOW | resolve the engine (A3) to remove this ambiguity |
| L29B | EASA_ICAO | EMB145 | 5.6 | HIGH |  |
| MD11 | EASA_ICAO_AMBIGUOUS | MD11PW | 0.0 | LOW | resolve the engine (A3) to remove this ambiguity |
| MD90 | EASA_ICAO_AMBIGUOUS | MD9028 | 1.0 | LOW | resolve the engine (A3) to remove this ambiguity |
| R722 | EASA_ICAO | 727D17 | -6.3 | MEDIUM |  |
| T204 | EASA_ICAO | 757RR | 5.6 | MEDIUM |  |
| T214 | EASA_ICAO | 757PW | 5.5 | HIGH |  |

## Details of non-PASS checks

- **integrity.jets_without_jet_coefficients** (INFO): `['707', '707120', '720', '727200', '747100', 'DC820', 'SABR80']`
- **integrity.aircraft_without_departure_steps** (INFO): `['707', '707120', '720', '727200', '747100', 'CNA206', 'CNA20T', 'CONCRD', 'DC1030', 'DC820', 'PA28', 'PA31', 'SABR80']`
- **physics.npd_monotonic_in_power** (WARNING): `departure SEL/LAmax families: [('CF680C', 'LAmax', 'D'), ('CF680C', 'SEL', 'D'), ('PT6A67', 'LAmax', 'D'), ('PT6A67', 'SEL', 'D'), ('PW545A', 'LAmax', 'D'), ('TPE331-5', 'LAmax', 'D'), ('TPE331-5', 'SEL', 'D'), ('TRENT7', 'LAmax', 'D'), ('TRENT7', 'SEL', 'D')]`
- **physics.npd_power_points** (INFO): `{2: 456, 3: 124, 4: 196, 5: 24, 6: 68, 7: 8, 8: 4, 10: 4, 13: 4}`
- **physics.sel_vs_lamax** (WARNING): `[(('2PW535', 'D', 1200.0), {'L_200ft': -5.3, 'L_400ft': -0.4}), (('2PW535', 'D', 1600.0), {'L_200ft': -6.6, 'L_400ft': -0.9})]`
- **logic.stage_length_M** (INFO): `[['7373B2', 139500.0, 139500.0], ['737400', 150000.0, 150000.0], ['737500', 128500.0, 133500.0], ['7378MAX', 181200.0, 181200.0], ['A350-941', 606271.0, 610681.0]]`
- **physics.default_weight_le_mtow** (WARNING): `[['A320-211', '5', 169800.0, 169756.0], ['A320-232', '5', 172000.0, 169756.0], ['A321-232', '5', 206100.0, 196211.0], ['A330-343', '7', 513700.0, 513677.0], ['A340-642', '7', 811300.0, 804687.0]]`
- **validation.vol3_fixture.A-4_Aerodynamic_Coefficients** (INFO): `['Aircraft Identifier', 'Operation Type', 'Flap Identifier', 'B', 'C/D (kt/sqrt(lb))', 'R']`
- **mapping.icao_reference.large_delta** (WARNING): `[['AT75', 'HS748A', -9.2], ['ATP', 'HS748A', -9.3], ['C500', 'CNA500', 6.1], ['C560', 'CNA560E', -8.9], ['CN35', 'SF340', 10.0], ['FA20', 'FAL20', 9.6], ['H25B', 'IA1125', 7.6], ['IL86', 'DC8QN', 5.0], ['IL96', 'A340-211', 6.6], ['L29B', 'EMB145', 5.6], ['R722', '727D17', -6.3], ['T204', '757RR', 5.6], ['T214', '757PW', 5.5]]`
