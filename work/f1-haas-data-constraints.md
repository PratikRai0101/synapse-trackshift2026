# F1 2026 energy/overtake decision support: practical evidence

As of **2026-09-11**. Independent research; no delegation. Primary sources only. This bounded note distinguishes regulation text, explanatory announcements, documented public data, and proposed modelling choices. It does not certify regulatory compliance. The user's reported HMM claims are evaluated here; the paper itself was not independently reviewed in this sidecar.

## 1. Controlling editions and technical constraints

The [FIA championship regulations index](https://www.fia.com/regulation/category/110), checked 2026-09-11, lists:

- **[Section C, Technical, Issue 20, 5 August 2026](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_20_-_2026-08-05.pdf)**. Use the cover/footer date; search metadata inconsistently says 3 August.
- **[Section B, Sporting, Issue 08, 5 August 2026](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_08_-_2026-08-05_7.pdf)**; cover records WMSC approval 3 August.

These supersede the 2024/2025 launch-era versions. Later-season event instructions and referenced FIA documents can supply additional parameters; do not treat the general PDFs as an exhaustive event configuration.

### Technical rule facts: Section C

| Article | Verified constraint |
|---|---|
| C5.2.7 | Absolute ERS-K electrical DC power ≤350 kW: deployment **and recovery**. |
| C5.2.8(i–ii) | Speed-dependent deployment caps below, additionally subject to B7.2. |
| C5.2.8(iii–iv) | Specified race/sprint sectors during power-limited periods: 250 kW below 310 km/h, then normal taper; separate low-grip curves reference FIA-F1-DOC-111. |
| C5.2.9 | Maximum-minus-minimum ES state of charge ≤4 MJ on track. This is a permitted energy swing, not proof of total battery capacity. |
| C5.2.10 | Recharge measured at CU-K HV DC bus ≤8.5 MJ/lap; conditional reduction to 7 MJ; qualifying reductions; conditional additional ≤0.5 MJ. Low-grip safety-car laps have no recharge limit. |
| C5.2.11 | MGU-K mechanical torque magnitude ≤500 Nm, referenced to crankshaft speed. |
| C5.18.5 | Relative rotational speed between any two MGU-K parts ≤60,000 rpm. |
| C5.2.2, .14 | Lap accounting changes at pit-lane entry; separate DC measurements cover ES and CU-K energy flow. |

For speed `v` in km/h and power in kW, mathematical restatement of C5.2.7–8:

| Speed range | Normal maximum | Overtake maximum |
|---|---:|---:|
| v < 340 | min(350, 1800 − 5v) | min(350, 7100 − 20v) |
| 340 ≤ v < 345 | 6900 − 20v | min(350, 7100 − 20v) |
| 345 ≤ v < 355 | 0 | min(350, 7100 − 20v) |
| v ≥ 355 | 0 | 0 |

Thus the unmodified normal envelope starts tapering above 290 km/h; Overtake retains 350 kW through 337.5 km/h. These are maximum envelopes, not observed deployment traces or a guarantee that stored energy is available.

**Unresolved detail:** C5.2.10(ii) extracted text contains both “5” and “4” MJ in tracked changes. B7.2.1(c) explicitly allows up to twelve qualifying-limit events, at most four below 5 MJ. Do not quote the exact amended floor until the rendered page is checked. The energy-flow diagram also needs visual verification before asserting an independent per-lap deployment allowance.

### Eligibility and human control

Section B, B7.2.1–4: the FIA supplies the **Detection Gap**, Detection Line, Activation Line, recharge allowances and sector overrides. Race/sprint activation requires a gap **less than** that event's Detection Gap at the Detection Line; eligibility takes effect at the Activation Line. Practice/qualifying differs. Electronic notification governs use; manual failure handling requires Race Director permission. Overtake is disabled for low grip, safety-car deployment and start/resumption, with prescribed re-enabling conditions; the Race Director can disable it for safety. Consequently, “within one second anywhere” is an inadequate rules engine. B7.1 separately governs driver-commanded active aero and its permitted zones. B1.8.1 requires the driver to drive alone and unaided. [Sporting text, 2026-08-05](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_08_-_2026-08-05_7.pdf).

C8.5.3 prohibits team-to-car telemetry except specified marshalling/handshake exceptions. C8.6.1–3 governs ECU-generated driver signals and deliberate driver input; voice radio is distinguished. C5.12 additionally constrains power-demand changes and Boost. [Technical text, 2026-08-05](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_20_-_2026-08-05.pdf).

**Architecture implication:** propose an engineer-facing recommendation system with an auditable event rules configuration. An autonomous controller, arbitrary remote mode write, or new cockpit prompt needs its own technical review. A human reviewer alone does not establish compliance.

## 2. Corrections to the reported HMM assumptions

| Reported claim | Correction / appropriate baseline treatment |
|---|---|
| “Unlimited regeneration” | False as a general 2026 constraint: distinguish instantaneous recovery power, lap recharge accounting, battery headroom and the narrow low-grip safety-car exception above. |
| Exact continuous “50/50” | The [FIA launch announcement, 2024-06-06](https://www.fia.com/news/new-era-competition-fia-showcases-future-focused-formula-1-regulations-2026-and-beyond) describes a shift toward a 50/50 power distribution. It is explanatory launch language, not an instantaneous equality constraint. Current speed/energy caps alone preclude assuming equal power continuously. Do not equate peak power share with lap energy share. |
| Energy low at SOC “ceiling” | Under conventional SOC, the ceiling means high stored charge and little charging headroom; the floor means little discharge reserve. Reverse wording only if the paper explicitly defines a depletion variable. |
| Same starting fuel for every car; depletion determined by lap | Unverified simplifying assumptions, not facts from the reviewed sources. Public schemas do not reveal starting fuel or fuel flow. Treat initial fuel and burn as uncertain, policy-dependent latent quantities; no numerical 2026 starting-fuel limit is asserted here. |
| Active aero from speed residual is “observed” | A residual is observed; its aero interpretation is inferred. It can also reflect slipstream, wind, grade, fuel mass, throttle, tyres, gearing or electrical power. Retain a probabilistic latent state and test identifiability. |
| FastF1 provides native 10 Hz telemetry | Unsupported. The [maintainer's 2022-09-15 answer](https://github.com/theOehrly/Fast-F1/discussions/258) explicitly distinguishes upsampling from measurement frequency. A 10 Hz analysis grid cannot create independent observations. |

The HMM can remain a **baseline for latent tactical regimes**, with posterior uncertainty and sensitivity analyses. It cannot validate SOC accuracy against its own pseudo-labels or promote inferred modes to sensor truth.

## 3. Public telemetry: available versus missing

Official **project** documentation is primary for these libraries; neither library is an official FIA/team telemetry entitlement. Documentation/source below checked 2026-09-11; live pages may change.

**FastF1:** [project repository](https://github.com/theOehrly/Fast-F1), [parser and embedded API documentation](https://raw.githubusercontent.com/theOehrly/Fast-F1/master/fastf1/_api.py), [Telemetry implementation/documentation](https://raw.githubusercontent.com/theOehrly/Fast-F1/master/fastf1/core.py). Car/position channels include speed, RPM, gear, throttle, brake, DRS, timestamps and X/Y/Z; timing includes laps, sectors, pits, gaps, tyres, weather and race-control information. Current `TELEMETRY_FREQUENCY` defaults to `"original"`. Even that merges timestamps and interpolates missing channel values; integer frequencies explicitly resample. Prefer unmerged channels for sampling audits. Exact native cadence and live-access contract remain unresolved pending final source inspection. The hosted docs returned access errors; upstream source is the fallback.

**OpenF1:** [API reference](https://openf1.org/docs/) documents car data and approximate position at about **3.7 Hz**; intervals about **4 seconds**. Car fields: `brake`, `date`, `driver_number`, `drs`, `meeting_key`, `n_gear`, `rpm`, `session_key`, `speed`, `throttle`. Brake is **0/100 pressed status**, not pressure. Location is approximate X/Y/Z and explicitly lacks reliable left/right lateral placement. Other endpoints cover laps, pits, stints, weather, race control and team-radio recordings. Its DRS mapping contains uncertain values; no verified mapping here establishes 2026 front/rear active-aero state or Overtake activation.

Neither inspected schema documents **own/opponent SOC, ERS electrical deployment/recovery power, battery temperatures, fuel mass/flow, brake pressure, or precise lane geometry**. This is a schema-level finding, not a claim that such signals cannot exist in private team/FIA data.

**Access/cost:** [OpenF1 access and FAQ](https://openf1.org/), checked 2026-09-11: historical sessions since 2023, free without authentication; community limits 3 requests/s and 30/min. Sponsor live access costs **€9.90/month**, 6 requests/s and 60/min, with REST/MQTT/WebSocket. Advertised typical delay is about 3 s, not an SLA. “Live” spans 30 minutes before through 30 minutes after a session. Published tiers are for personal use; the site directs other uses to licensing discussions. Do not assume a Haas commercial deployment is covered by a hackathon data subscription. No account was created or purchase made.

## 4. Haas-specific evidence and pitch

- **Mphasis relationship is real:** Haas announced its multi-year **Official Digital Partner** agreement on **2024-11-21**, naming real-time data analysis, predictive modelling, performance optimisation and operational efficiency. This supports the topic's relevance, not an assertion that Haas lacks these capabilities. [Haas announcement](https://www.haasf1team.com/news/moneygram-haas-f1-team-welcomes-mphasis-partnership).
- **2026 PU supplier is Ferrari:** Haas's **2024-07-16** announcement extends Ferrari power units through the end of **2028** and describes continuity into the 2026 rules as part of development. [Haas supplier announcement](https://www.haasf1team.com/news/partnership-extended-between-moneygram-haas-f1-team-and-scuderia-ferrari). Do not imply Toyota branding makes Toyota the 2026 engine supplier.

**Proposed positioning, not an internal Haas requirement:** “An uncertainty-aware energy and overtaking adviser that helps engineers compare attack, defend and recharge options, explains which constraints bind, and preserves battery reserve across the next sequence of straights.” Align with the published Mphasis analytics/efficiency remit. Do not invent lap-time gains, points targets, compute budgets, private workflow deficiencies or access to Ferrari maps.

**Credible demonstration boundary:** historical public replay plus explicitly synthetic energy ground truth; a constrained simulator/state estimator; uncertain opponent intent; short-horizon alternative plans; source-linked explanations. Evaluate held-out events, calibration, decision regret, solver latency and reserve violations in simulation. Separate measured outcomes from counterfactual estimates. Team-data validation would require agreed own-car energy/PU signals and independently verified event configuration; public replay alone cannot establish real energy optimisation gains.

## 5. Remaining checks and organizer scope

Unresolved: rendered qualifying-floor amendment and energy-flow diagram; circuit-specific FIA messages and supporting documents including FIA-F1-DOC-034/-058/-111; exact native FastF1 cadence/live entitlement; validated 2026 DRS/active-aero mapping; private-data availability. No blanket legality, causal-identification or commercial-data licence claim is made.

The organizer-hosted [TrackShift Devpost page](https://trackshift.devpost.com/) inspected here describes **2025**. Its [updates page](https://trackshift.devpost.com/updates) has an indexed 2026 notice, but 2026 rules were not verified. Do not reuse 2025 eligibility, deadlines, submission formats or prize conditions as 2026 rules. No sign-in or upload was attempted.
