# A5 decisions log

| # | Decision | Choice | Evidence | Status |
|---|---|---|---|---|
| 1 | Scope | Data + mapping + NPD lookup only; state-dependent adjustments in the noise stage | Doc 29 Vol 2 §4.2 vs §4.2.1/App. D; B-2 separates baseline_SEL from impedance | Locked |
| 2 | ANP version | ANP 2.3 legacy, SHA-256 locked; verified EASA data = separate future release | release note 2020; A5 README | Locked |
| 3 | EASA strategy | configuration tab (model+engine+MTOW) first, ICAO tab as conservative fallback | EASA "read me": ICAO tab = noisiest configuration (verified by QC) | Locked |
| 4 | Doc 29 | 5th Edition, Vol 1–3; ARP-5534 for Appendix D | volume front matter | Locked |
| 5 | Units | native ANP units + `units_registry`; SI at interfaces; exact constants | Doc 29 App. B coefficient units | Locked |
| 6 | Mapping hierarchy | see methodology §7; Method A primary; categorical confidence | Doc 29 Vol 1 §6.4.4 | Locked |
| 7 | A20N | engine from A3 → config tab; unknown → conservative IAE variant (−3.5 dB); bracket as sensitivity | Vol 1 p.45; config tab | Locked |
| 8 | A339/B78X/B39M | analyst proxies A330-343 / 7878R / 7378MAX; Δ by Eq. 6-1 from EASA TCDSN; pending = unusable | Vol 1 §6.4.4.1, Eq. 6-1 | Rule locked; Δ pending data |
| 9 | NPD policy | Eq. 4-3/4-4/4-5; 1 lb floor; 30 m floor; flag > 5 dB power extrapolation | Vol 2 pp. 27–29 | Locked |
| 10 | Validation | Vol 3 B-2 executable check; schema fixtures; unit constants; EASA consistency | Vol 3 §2 | Done: max diff 1.3e-13 dB |
| 11 | Tolerances | B-2 ERROR > 0.01 dB, target ≤ 0.001 dB; units 1e-12 relative; round-trip exact | Vol 3 §4.3 (δRMS aim 0.01 dB) | Locked |
| 12 | Contract | `docs/integration_contract.md` | — | Locked |

## Corrections made during the build
- An earlier statement that NPDs are referenced to 25 °C / 70 % RH was wrong: Doc 29 App. D defines a notional
  "AIR-1845 atmosphere" (Table D-1 attenuation rates). A5 stores Table D-1.
- An earlier statement that the B789 Δ spread (~5 dB) comes from the engine was wrong: it comes mainly from the
  certified MTOW option (−1.8 dB at 181 t to +3.2 dB at 254 t for one GEnx engine). Tests now encode this.
- ANP default weights above MTOW were first raised as an ERROR; they are a property of the source, so they are
  kept unchanged and reported as a WARNING with usage guidance.

## Open items (external)
1. Request the EASA verified ANP dataset (form on the EASA ANP page).
2. Enter certified levels for A339, B78X, B39M from the EASA type-certificate noise database, then set
   `review_status = REVIEWED` with reviewer and date.
3. A3: supply engine type (and MTOW option where available) per airframe.
4. A4: add relative humidity (ERA5 2 m dewpoint and pressure-level humidity) or the OEJN METAR.
