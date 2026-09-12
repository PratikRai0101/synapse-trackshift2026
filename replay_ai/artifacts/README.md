# Runtime model artifacts

These checked-in defaults are **synthetic development artifacts**, not models fitted to
private F1 battery labels:

- `hmm-emissions.json` — ERS-mode emissions fitted on simulator-labelled telemetry.
- `lap-time-map.json` — empirical Level 3 map fitted on simulator-labelled laps.
- `hmm-split-report.json` and `lap-map-report.json` — event-disjoint evaluation reports.

Regenerate from `docs/AIBackend.md`. The replay HUD must describe the HMM output as an
ERS capability belief; public FastF1 data does not expose rival SOC.
