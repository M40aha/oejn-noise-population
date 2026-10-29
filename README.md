# OEJN Departure Noise & Population Exposure

Aircraft noise of the **observed jet departures** from King Abdulaziz International Airport, Jeddah (OEJN, runways 34C / 34L) on
**1 October 2026**, computed with **ECAC Doc 29, 5th Edition (2026)**, and the number of residents exposed.
Part of the SANS research *OEJN Noise–Fuel–Capacity* (layers A5 and A6 plus the noise model).

**Main output:** `map3d/OEJN_Map3D_Noise.html`. Download it and open it in Chrome or Edge. It shows the noise surface, typical
flight paths in 3D, residents per noise band and a Results panel ([details](map3d/README.md)).

## Key results — 1 Oct 2026

208 of 241 departures were modelled. The other 33 are listed in the results file with the reason.

| Indicator | Residents exposed |
|---|---|
| Lden ≥ 55 dB | **112,000** |
| Lden ≥ 65 dB | **16,100** |
| Lnight ≥ 50 dB | **86,000** |
| ≥ 10 events per day with LAmax ≥ 70 dB (N70) | **94,000** |

For the same aircraft type, runways 34C and 34L expose similar numbers of residents. 34C dominates the day because it carried
188 of the 208 modelled departures, almost all of the widebodies.
Full tables: [`docs/noise/results_2026-10-01.md`](docs/noise/results_2026-10-01.md).

## How the noise is computed

The method is the Doc 29 segmentation method, fed with the **flown trajectories** (ADS-B, via A2). Doc 29 §3.6.1 allows this:
positions, heights, speeds and bank angles come from the data, and only engine power is calculated.

**1. Engine power: corrected net thrust per engine** (Doc 29 App. B, Eq. B-9)

$$\frac{F_n}{\delta} = E + F\,V_C + G_a\,h + G_b\,h^2 + H\,T$$

- $V_C$ is the calibrated airspeed (kt), $h$ the pressure altitude (ft) and $T$ the air temperature (°C).
- $E, F, G_a, G_b, H$ are the ANP coefficients of the aircraft.
- Full take-off thrust is used up to the cut-back height, and maximum climb thrust above it.

**2. Level of each flight-path segment at a receptor** (Eq. 4-8 / 4-9)

$$L_{E,seg} = L_E(P,d) + \Delta_V + \Delta_I(\varphi) - \Lambda(\beta,\ell) + \Delta_F + \Delta_{SOR}$$

$$L_{max,seg} = L_{max}(P,d) + \Delta_I(\varphi) - \Lambda(\beta,\ell) + \Delta_{SOR}$$

| Term | Meaning |
|---|---|
| $L(P,d)$ | NPD level for power $P$ and distance $d$ (EASA ANP 2.3), adjusted for the day's temperature, humidity and pressure (App. D) |
| $\Delta_V = 10\lg(V_{ref}/V)$ | duration correction, $V_{ref}$ = 160 kt |
| $\Delta_I$ | engine-installation correction (depression angle $\varphi$) |
| $\Lambda$ | lateral attenuation (elevation angle $\beta$, lateral distance $\ell$) |
| $\Delta_F$ | finite-segment correction |
| $\Delta_{SOR}$ | start-of-roll directivity, behind the take-off roll only |

The impedance adjustment (Eq. 4-6) and the aircraft-substitution Δ (Method A) are added to both levels.

**3. One departure**

$$SEL = 10\lg\sum_{seg}10^{L_{E,seg}/10}, \qquad L_{Amax} = \max_{seg} L_{max,seg}$$

**4. The day** (EU END Annex I; local time; $T_0$ = 1 s)

$$L_{den} = 10\lg\left[\frac{T_0}{86400}\left(\sum_{day}10^{SEL/10} + \sum_{eve}10^{(SEL+5)/10} + \sum_{night}10^{(SEL+10)/10}\right)\right]$$

- Day is 07–19 h, evening 19–23 h (+5 dB) and night 23–07 h (+10 dB).
- $L_{night}$ is computed the same way over the 8 night hours, without the penalty.
- N70 is the number of departures with $L_{Amax}$ ≥ 70 dB.

**5. Population.** Levels are computed on a 250 m grid (80 × 80 km). They are then interpolated to the populated WorldPop
2026 cells (100 m; 3.8 M residents inside the grid). The run also gives the WHO 2018 exposure–response indicators, as an indication only.

**Verification.** All Doc 29 Vol 3 reference cases are reproduced:
- 3,516 segments, within 0.0014 dB;
- end-to-end test with a reference profile used as an "observed" track, within 0.05 dB.

50 automated tests pass. Full method: [`docs/noise/methodology_noise.md`](docs/noise/methodology_noise.md).

## Limitations

- **Scope:** departures only, on one day. No arrivals or ground noise. These are not annual or regulatory contours.
- **Engine thrust:** full take-off thrust is assumed (conservative near the runway).
- **Runway and terrain:** start of roll at the threshold, flat terrain.
- **Aircraft identity:**
  - 25 flights have no aircraft type, so they are not modelled;
  - 11 flights use a proxy aircraft with Δ = 0, because certified levels are pending.

## Repository

```
src/noise/      Doc 29 model: flightpath · performance · doc29 · atmosphere · event · run
src/a5/  src/a6/   aircraft noise data layer (ANP 2.3 + mapping) · population layer (WorldPop 2026)
map3d/          3D noise map (team Map 2 + noise layer) and its builder (scripts/build_map3d.py)
data/           processed outputs (noise grid, GeoTIFF, exposure, per-flight results) and QC
docs/           methodology (noise, A5, A6) · results · detailed notes (docs/README_detailed.md)
tests/          A5 · A6 · noise (Doc 29 Vol 3 reference cases)
```

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m pytest -q tests        # verify
PYTHONPATH=src python -m noise.run              # run (observed-traffic inputs in data/inputs/, not included)
```

## Data and licences

- **Noise data:** EASA ANP 2.3 and ECAC Doc 29, used under their publishers' terms. The raw files are not redistributed here.
- **Population:** WorldPop Global2 R2025A v1, CC BY 4.0.
- **Basemap:** OpenStreetMap contributors (ODbL) and Natural Earth.
- **Traffic:** ADS-B from Wingbits via the team's A2 stage. The raw tracks are not included.
