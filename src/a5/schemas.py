"""Canonical schemas for the ANP 2.3 tables.

Each column: (source header, canonical name, kind, unit, description).
kind: id | cat | str | int | float.  Units are the NATIVE ANP units (never converted here).
"""
from __future__ import annotations

from .constants import NPD_LEVEL_COLUMNS, NPD_DISTANCES_FT, SPECTRAL_LEVEL_COLUMNS, SPECTRAL_BANDS_HZ

PP = "per aircraft power_parameter (CNT lb/engine for jets)"

ANP_TABLES: dict[str, dict] = {
    "anp_aircraft": {
        "member": "ANP2.3_Aircraft.csv",
        "key": ["acft_id"],
        "columns": [
            ("ACFT_ID", "acft_id", "id", "-", "ANP aircraft identifier"),
            ("Description", "description", "str", "-", "Airframe / engine description"),
            ("Engine Type", "engine_type", "cat", "-", "Jet | Turboprop | Piston"),
            ("Number Of Engines", "n_engines", "int", "-", "Number of engines"),
            ("Weight Class", "weight_class", "cat", "-", "Small | Large | Heavy"),
            ("Owner Category", "owner_category", "cat", "-", "Commercial | General Aviation | Military"),
            ("Max Gross Takeoff Weight (lb)", "mtow_lb", "float", "lb", "Maximum gross take-off weight"),
            ("Max Gross Landing Weight (lb)", "mlw_lb", "float", "lb", "Maximum gross landing weight"),
            ("Max Landing Distance (ft)", "max_landing_distance_ft", "float", "ft", "Maximum landing distance"),
            ("Max Sea Level Static Thrust (lb)", "max_static_thrust_lb", "float", "lb", "Maximum sea-level static thrust (as tabulated by ANP)"),
            ("Noise Chapter", "noise_chapter", "int", "-", "ICAO Annex 16 noise chapter (0 = not stated)"),
            ("NPD_ID", "npd_id", "id", "-", "Identifier of the NPD curve set"),
            ("Power Parameter", "power_parameter", "cat", "-", "Noise-related power parameter of the NPD data"),
            ("Approach Spectral Class ID", "app_spectral_class_id", "int", "-", "Approach spectral class"),
            ("Departure Spectral Class ID", "dep_spectral_class_id", "int", "-", "Departure spectral class"),
            ("Lateral Directivity Identifier", "lateral_directivity", "cat", "-", "Wing | Fuselage | Prop (engine-installation correction)"),
        ],
    },
    "anp_npd_wide": {
        "member": "ANP2.3_NPD_data.csv",
        "key": ["npd_id", "noise_metric", "op_mode", "power_setting"],
        "columns": [
            ("NPD_ID", "npd_id", "id", "-", "NPD identifier"),
            ("Noise Metric", "noise_metric", "cat", "-", "SEL | LAmax | EPNL | PNLTM"),
            ("Op Mode", "op_mode", "cat", "-", "A = approach, D = departure"),
            ("Power Setting", "power_setting", "float", PP, "Noise-related power parameter value"),
        ] + [(c, c, "float", "dB", f"Noise level at slant distance {int(d)} ft")
             for c, d in zip(NPD_LEVEL_COLUMNS, NPD_DISTANCES_FT)],
    },
    "anp_spectral_wide": {
        "member": "ANP2.3_Spectral_classes.csv",
        "key": ["spectral_class_id"],
        "columns": [
            ("Spectral Class ID", "spectral_class_id", "int", "-", "Spectral class identifier"),
            ("Op Type", "op_type", "cat", "-", "Departure | Approach"),
            ("Description", "description", "str", "-", "Class description"),
        ] + [(c, c, "float", "dB", f"1/3-octave band level at {f} Hz (normalised)")
             for c, f in zip(SPECTRAL_LEVEL_COLUMNS, SPECTRAL_BANDS_HZ)],
    },
    "anp_departure_steps": {
        "member": "ANP2.3_Default_departure_procedural_steps.csv",
        "key": ["acft_id", "profile_id", "stage_length", "step_number"],
        "columns": [
            ("ACFT_ID", "acft_id", "id", "-", "ANP aircraft identifier"),
            ("Profile_ID", "profile_id", "id", "-", "Procedure profile identifier"),
            ("Stage Length", "stage_length", "cat", "-", "Stage length 1-9 or M"),
            ("Step Number", "step_number", "int", "-", "Order of the step within the profile"),
            ("Step Type", "step_type", "cat", "-", "Takeoff | Climb | Accelerate"),
            ("Thrust Rating", "thrust_rating", "cat", "-", "Thrust rating used in this step"),
            ("Flap_ID", "flap_id", "id", "-", "Flap configuration (joins aerodynamic coefficients)"),
            ("End Point Altitude (ft)", "end_altitude_ft", "float", "ft", "Climb step end altitude (AFE)"),
            ("Rate Of Climb (ft/min)", "rate_of_climb_ftmin", "float", "ft/min", "Accelerate step rate of climb"),
            ("End Point CAS (kt)", "end_cas_kt", "float", "kt", "Accelerate step end calibrated airspeed"),
            ("Accel Percentage (%)", "accel_percentage", "float", "%", "Energy share used for acceleration"),
        ],
    },
    "anp_approach_steps": {
        "member": "ANP2.3_Default_approach_procedural_steps.csv",
        "key": ["acft_id", "profile_id", "step_number"],
        "carried_only": True,
        "columns": [
            ("ACFT_ID", "acft_id", "id", "-", "ANP aircraft identifier"),
            ("Profile_ID", "profile_id", "id", "-", "Procedure profile identifier"),
            ("Step Number", "step_number", "int", "-", "Order of the step"),
            ("Step Type", "step_type", "cat", "-", "Approach step type"),
            ("Flap_ID", "flap_id", "id", "-", "Flap configuration"),
            ("Start Altitude(ft)", "start_altitude_ft", "float", "ft", "Start altitude"),
            ("Start CAS (kt)", "start_cas_kt", "float", "kt", "Start calibrated airspeed"),
            ("Descent Angle (deg)", "descent_angle_deg", "float", "deg", "Descent angle"),
            ("Touchdown Roll (ft)", "touchdown_roll_ft", "float", "ft", "Touchdown roll"),
            ("Distance (ft)", "distance_ft", "float", "ft", "Step distance"),
            ("Start Thrust", "start_thrust", "float", PP, "Start thrust"),
        ],
    },
    "anp_jet_coefficients": {
        "member": "ANP2.3_Jet_engine_coefficients.csv",
        "key": ["acft_id", "thrust_rating"],
        "columns": [
            ("ACFT_ID", "acft_id", "id", "-", "ANP aircraft identifier"),
            ("Thrust Rating", "thrust_rating", "cat", "-", "Thrust rating"),
            ("E", "E", "float", "lb", "Jet thrust coefficient E"),
            ("F", "F", "float", "lb/kt", "Jet thrust coefficient F"),
            ("Ga", "Ga", "float", "lb/ft", "Jet thrust coefficient Ga"),
            ("Gb", "Gb", "float", "lb/ft^2", "Jet thrust coefficient Gb"),
            ("H", "H", "float", "lb/degC", "Jet thrust coefficient H"),
            ("K1", "K1", "float", "lb/EPR", "EPR/N1 coefficient K1 (where applicable)"),
            ("K2", "K2", "float", "lb/EPR^2", "EPR/N1 coefficient K2 (where applicable)"),
            ("K3", "K3", "float", "lb/(N1/sqrt(theta))", "EPR/N1 coefficient K3 (where applicable)"),
            ("K4", "K4", "float", "lb/(N1/sqrt(theta))^2", "EPR/N1 coefficient K4 (where applicable)"),
        ],
    },
    "anp_propeller_coefficients": {
        "member": "ANP2.3_Propeller_engine_coefficients.csv",
        "key": ["acft_id", "thrust_rating"],
        "carried_only": True,
        "columns": [
            ("ACFT_ID", "acft_id", "id", "-", "ANP aircraft identifier"),
            ("Thrust Rating", "thrust_rating", "cat", "-", "Thrust rating"),
            ("Propeller Efficiency", "propeller_efficiency", "float", "-", "Propeller efficiency"),
            ("Installed Net Propulsive Power (hp)", "installed_power_hp", "float", "hp", "Installed net propulsive power"),
        ],
    },
    "anp_aero_coefficients": {
        "member": "ANP2.3_Aerodynamic_coefficients.csv",
        "key": ["acft_id", "op_type", "flap_id"],
        "columns": [
            ("ACFT_ID", "acft_id", "id", "-", "ANP aircraft identifier"),
            ("Op Type", "op_type", "cat", "-", "A | D"),
            ("Flap_ID", "flap_id", "id", "-", "Flap configuration"),
            ("B", "B", "float", "ft/lb", "Take-off ground-roll coefficient B"),
            ("C", "C", "float", "kt/sqrt(lb)", "Take-off speed coefficient C"),
            ("D", "D", "float", "kt/sqrt(lb)", "Landing speed coefficient D"),
            ("R", "R", "float", "-", "Drag-to-lift ratio R"),
        ],
    },
    "anp_default_weights": {
        "member": "ANP2.3_Default_weights.csv",
        "key": ["acft_id", "stage_length"],
        "columns": [
            ("ACFT_ID", "acft_id", "id", "-", "ANP aircraft identifier"),
            ("Stage Length", "stage_length", "cat", "-", "Stage length 1-9 or M"),
            ("Weight (lb)", "weight_lb", "float", "lb", "Default take-off weight for the stage length"),
        ],
    },
    "anp_fixed_point_profiles": {
        "member": "ANP2.3_Default_fixed_point_profiles.csv",
        "key": ["acft_id", "op_type", "profile_id", "stage_length", "point_number"],
        "carried_only": True,
        "columns": [
            ("ACFT_ID", "acft_id", "id", "-", "ANP aircraft identifier"),
            ("Op Type", "op_type", "cat", "-", "A | D"),
            ("Profile_ID", "profile_id", "id", "-", "Profile identifier"),
            ("Stage Length", "stage_length", "cat", "-", "Stage length"),
            ("Point Number", "point_number", "int", "-", "Point order"),
            ("Distance (ft)", "distance_ft", "float", "ft", "Distance along track"),
            ("Altitude AFE (ft)", "altitude_afe_ft", "float", "ft", "Altitude above field elevation"),
            ("TAS (kt)", "tas_kt", "float", "kt", "True airspeed"),
            ("Power Setting", "power_setting", "float", PP, "Power setting"),
        ],
    },
}

CATEGORIES = {
    ("anp_aircraft", "engine_type"): {"Jet", "Turboprop", "Piston"},
    ("anp_aircraft", "weight_class"): {"Small", "Large", "Heavy"},
    ("anp_aircraft", "lateral_directivity"): {"Wing", "Fuselage", "Prop"},
    ("anp_aircraft", "power_parameter"): {"CNT (lb)", "CNT (% of Max Static Thrust)", "Other (RPM)"},
    ("anp_npd_wide", "noise_metric"): {"SEL", "LAmax", "EPNL", "PNLTM"},
    ("anp_npd_wide", "op_mode"): {"A", "D"},
    ("anp_spectral_wide", "op_type"): {"Departure", "Approach"},
    ("anp_departure_steps", "step_type"): {"Takeoff", "Climb", "Accelerate"},
    ("anp_departure_steps", "stage_length"): {"1", "2", "3", "4", "5", "6", "7", "8", "9", "M"},
    ("anp_default_weights", "stage_length"): {"1", "2", "3", "4", "5", "6", "7", "8", "9", "M"},
    ("anp_aero_coefficients", "op_type"): {"A", "D"},
}

POWER_PARAMETER_KIND = {
    "CNT (lb)": "CNT_LB_PER_ENGINE",
    "CNT (% of Max Static Thrust)": "CNT_PCT_MAX_STATIC",
    "Other (RPM)": "RPM",
}
