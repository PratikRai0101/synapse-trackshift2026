"""GRID//OPS — Pit-Wall Command Center.

Run with::

    .venv/bin/streamlit run app.py

The dashboard reads the same engine the CLI uses. Every panel is tagged with
whether it is *implemented*, *configured* or *not implemented*, and it never
displays a synthetic value as if it were measured.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from gridops.contracts.ruleset import default_ruleset
from gridops.contracts.state import BatteryParams, VehicleParams
from gridops.decision.pmp import guidance
from gridops.decision.zone_mpc import EnergyZone, ZoneMPC
from gridops.evaluation.batch import build_controller
from gridops.evaluation.calibration import calibrate
from gridops.evaluation.runner import EpisodeConfig, EpisodeRunner
from gridops.race_value.lap_map import LapMapConfig, RaceValueMap, default_terminal_value
from gridops.race_value.season import SeasonConfig, SeasonLifecycle
from gridops.simulation.rivals import RivalPolicy
from gridops.simulation.track import synthetic_circuit
from gridops.simulation.tyres import default_tyre_params

st.set_page_config(page_title="GRID//OPS Pit Wall", layout="wide", page_icon="🏁")

STATUS_BADGE = {
    "implemented": ("IMPLEMENTED", "#00d26a"),
    "configured": ("CONFIGURED", "#ffb800"),
    "partial": ("PARTIAL", "#ffb800"),
    "not_implemented": ("NOT IMPLEMENTED", "#ff4848"),
}


def badge(kind: str) -> str:
    label, colour = STATUS_BADGE.get(kind, ("UNKNOWN", "#9a9aa8"))
    return (
        f"<span style='border:1px solid {colour};color:{colour};border-radius:999px;"
        f"padding:1px 9px;font-size:10px;letter-spacing:.06em'>{label}</span>"
    )


@st.cache_resource(show_spinner="Calibrating rival model from paired rollouts…")
def calibration():
    battery, vehicle = BatteryParams(), VehicleParams()
    return calibrate(
        synthetic_circuit(), vehicle, battery, tyre_params=default_tyre_params()
    )


def make_runner() -> EpisodeRunner:
    battery, vehicle = BatteryParams(), VehicleParams()
    return EpisodeRunner(
        track=synthetic_circuit(),
        vehicle=vehicle,
        battery=battery,
        terminal_value=default_terminal_value(battery),
        config=EpisodeConfig(
            duration_s=25.0, dt_s=0.05, replan_interval_s=1.0, decision_budget_s=0.1,
            rival_progress_m=8.0,
        ),
        tyre_params=default_tyre_params(),
        rules=default_ruleset(),
    )


def run_episode(controller_name: str, policy: str, seed: int) -> dict:
    runner = make_runner()
    controller = build_controller(controller_name, runner, seed, calibration())
    report = runner.run(controller, rival_policy=RivalPolicy(policy), seed=seed)
    return {
        "summary": report.summary(),
        "decisions": report.decisions,
        "trace": pd.DataFrame(report.trace),
    }


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
st.sidebar.title("🏁 GRID//OPS")
st.sidebar.caption("Pit-Wall Command Center")
controller_name = st.sidebar.selectbox(
    "Controller",
    ["m_hmm40", "m_hmm", "m", "stationary", "posterior_mean", "convex", "reference"],
    help="m_hmm40 uses the 40-state (mode × reserve) belief",
)
policy = st.sidebar.selectbox(
    "Rival policy",
    [p.value for p in RivalPolicy],
    index=2,
)
seed = st.sidebar.slider("Seed", 1, 20, 1)
run_clicked = st.sidebar.button("Run episode", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "All physical parameters are **synthetic**. Revealed rival state is "
    "**hidden simulator truth**, never a measurement. Energy values are "
    "**model estimates**."
)

if run_clicked or "result" not in st.session_state:
    with st.spinner("Running closed-loop episode…"):
        st.session_state.result = run_episode(controller_name, policy, seed)
        st.session_state.label = f"{controller_name} vs {policy} (seed {seed})"

result = st.session_state.result
summary = result["summary"]
trace: pd.DataFrame = result["trace"]

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("Pit-Wall Command Center")
st.caption(st.session_state.label)

cols = st.columns(6)
cards = [
    ("final gap", f"{summary.get('final_gap_m', float('nan')):.2f} m"),
    ("energy spent", f"{(summary.get('ego_energy_spent_j') or 0)/1e6:.3f} MJ"),
    ("passes", summary.get("pass_events", "n/a")),
    ("catch-ups", summary.get("catch_up_events", "n/a")),
    ("contacts", summary.get("contacts", "n/a")),
    ("decisions", summary.get("decisions", "n/a")),
]
for col, (label, value) in zip(cols, cards):
    col.metric(label, value)

st.markdown("---")

tabs = st.tabs(
    [
        "L4 · Season",
        "L3 · Race",
        "L2 · Tactical",
        "L1 · Execution",
        "B0 · Features",
        "B5 · Simulation",
        "Batch results",
        "Architecture status",
    ]
)

# -- L4 --------------------------------------------------------------------
with tabs[0]:
    st.subheader("L4 — Season lifecycle manager")
    st.markdown(badge("implemented") + " synthetic finite-horizon DP, not a calibrated championship model", unsafe_allow_html=True)
    cfg = SeasonConfig(n_events=24)
    season = SeasonLifecycle(cfg)
    outcome = season.solve()
    a, b, c = st.columns(3)
    a.metric("season value (synthetic points)", f"{outcome.value:.1f}")
    b.metric("replacements", len(outcome.replacement_events))
    c.metric("marginal stress price", f"{outcome.marginal_stress_price:.3f}")
    st.caption(
        "The marginal stress price is the only quantity handed down to L3. It is a "
        "synthetic local price, not a measured battery-life cost."
    )

# -- L3 --------------------------------------------------------------------
with tabs[1]:
    st.subheader("L3 — Full-race strategy and stint manager")
    st.markdown(
        badge("implemented") + " energy value recursion &nbsp; "
        + badge("implemented") + " neural lap-time surrogate &nbsp; "
        + badge("not_implemented") + " mid-race pit-window optimisation",
        unsafe_allow_html=True,
    )
    battery = BatteryParams()
    race_value = RaceValueMap(
        default_terminal_value(battery), LapMapConfig(laps=20, n_energy_levels=61)
    )
    energies = np.linspace(0.3e6, 3.9e6, 40)
    frame = pd.DataFrame(
        {
            "usable MJ": energies / 1e6,
            "value, 2 laps left": [race_value.value(e, 2) for e in energies],
            "value, 10 laps left": [race_value.value(e, 10) for e in energies],
            "value, 20 laps left": [race_value.value(e, 20) for e in energies],
        }
    ).set_index("usable MJ")
    st.line_chart(frame)
    laps = np.arange(1, 21)
    targets = [race_value.deploy_target(2.5e6, int(l)) / 1e3 for l in laps]
    st.line_chart(pd.DataFrame({"deploy target kW": targets}, index=laps))
    st.caption(
        "Value map is a finite-horizon DP over usable energy; the terminal reserve "
        "is priced once. The lap-time map is a small MLP fitted to plant laps and "
        "refuses out-of-range queries."
    )

# -- L2 --------------------------------------------------------------------
with tabs[2]:
    st.subheader("L2 — Tactical planner and opponent inference")
    st.markdown(
        badge("implemented") + " 40-state (mode × reserve) HMM &nbsp; "
        + badge("implemented") + " conditional convex planner &nbsp; "
        + badge("implemented") + " POMCP scenario search &nbsp; "
        + badge("implemented") + " contact supervisor",
        unsafe_allow_html=True,
    )
    decisions = result["decisions"]
    table = pd.DataFrame(
        [
            {
                "t s": d["time_s"],
                "action": d["family"],
                "status": d["status"],
                "gap m": d["gap_m"],
                "P kW": d["p_k_dc_w"] / 1000.0,
                "strong mass": (d.get("belief") or {}).get("strong_rival_mass"),
                "reasons": ",".join(d["reason_codes"]),
            }
            for d in decisions
        ]
    )
    st.dataframe(table, use_container_width=True, height=320)

    belief_rows = [
        d["belief"]["policy_mass"] | {"t s": d["time_s"]}
        for d in decisions
        if d.get("belief") and d["belief"].get("policy_mass")
    ]
    if belief_rows:
        belief_frame = pd.DataFrame(belief_rows).set_index("t s")
        st.markdown("**Belief over rival response policy** (mode-marginal of the 40-state filter)")
        st.area_chart(belief_frame)

    st.markdown("**What the controller declined to do**")
    retained = [d for d in decisions if d["status"] == "RETAIN_REFERENCE"]
    st.write(
        f"{len(retained)} of {len(decisions)} decisions retained the reference. "
        "Retaining is a valid outcome, not a solver failure."
    )
    st.caption(
        "Rival state is never observed. The belief is over response policies; "
        "there is no displayed rival state-of-charge."
    )

# -- L1 --------------------------------------------------------------------
with tabs[3]:
    st.subheader("L1 — Fast execution and driver guidance")
    st.markdown(
        badge("implemented") + " zone MPC (LP) &nbsp; "
        + badge("implemented") + " PMP costate cues &nbsp; "
        + badge("not_implemented") + " 100 Hz onboard deployment rate",
        unsafe_allow_html=True,
    )
    battery = BatteryParams()
    race_value = RaceValueMap(
        default_terminal_value(battery), LapMapConfig(laps=20, n_energy_levels=61)
    )
    plan = guidance(
        speed_mps=80.0, mass_kg=798.0, race_value=race_value,
        usable_energy_j=2.4e6, laps_remaining=10,
    )
    a, b, c, d = st.columns(4)
    a.metric("PMP cue", plan.cue)
    b.metric("λ_kin", f"{plan.lambda_kin:.2e}")
    c.metric("λ_b", f"{plan.lambda_b:.2e}")
    d.metric("λ_kin / λ_b", f"{plan.ratio:.2f}")
    st.caption(plan.guidance)

    zone = EnergyZone(
        e_kin_low_j=0.5 * 798.0 * 70.0**2,
        e_kin_high_j=0.5 * 798.0 * 88.0**2,
        e_bat_low_j=1.0e6,
        e_bat_high_j=3.0e6,
    )
    from gridops.simulation.plant import initial_state

    mpc = ZoneMPC(synthetic_circuit(), VehicleParams(), battery, horizon_m=300.0)
    zone_plan = mpc.solve(0.0, 80.0, initial_state(battery).battery, zone)
    st.write(
        f"Zone MPC: status **{zone_plan.status}**, DCP **{zone_plan.is_dcp}**, "
        f"solve **{zone_plan.solve_time_s*1000:.1f} ms**, "
        f"{len(zone_plan.p_k_dc_w)} steps"
    )
    if zone_plan.accepted:
        st.line_chart(
            pd.DataFrame(
                {"deploy kW": zone_plan.p_k_dc_w / 1000.0,
                 "speed m/s": zone_plan.speed_mps[:-1]},
            )
        )
    st.caption(
        "The cue is derived from the same first-order conditions as the "
        "minimum-lap-time literature, applied to this reduced model. It is "
        "advisory: the system proposes no car actuation."
    )

# -- B0 --------------------------------------------------------------------
with tabs[4]:
    st.subheader("Block 0 — Causal feature extraction")
    st.markdown(badge("implemented") + " rolling baselines and the super-clipping proxy", unsafe_allow_html=True)
    if not trace.empty:
        lag = trace[["t", "gap"]].copy()
        lag["gap lag m"] = lag["gap"].shift(4)
        lag["gap delta m"] = lag["gap"].diff(4)
        st.line_chart(lag.set_index("t")[["gap", "gap lag m"]])
    st.caption(
        "The super-clipping fraction is a declared **proxy**: reduced speed at full "
        "throttle does not by itself establish that MGU-K recovery caused it. The "
        "interpretation is the HMM's job."
    )

# -- B5 --------------------------------------------------------------------
with tabs[5]:
    st.subheader("Block 5 — Closed-loop simulation and feedback")
    st.markdown(badge("implemented") + " two-car plant, reactive rival, trace recorded", unsafe_allow_html=True)
    if not trace.empty:
        st.line_chart(trace.set_index("t")[["gap"]])
        st.line_chart(trace.set_index("t")[["ego_v", "rival_v"]])
        st.line_chart(trace.set_index("t")[["p_k_w"]].assign(**{"deploy kW": trace["p_k_w"] / 1000.0})[["deploy kW"]])
        st.line_chart(trace.set_index("t")[["energy_j"]].assign(**{"usable MJ": trace["energy_j"] / 1e6})[["usable MJ"]])
        if "tyre_temp_k" in trace and trace["tyre_temp_k"].notna().any():
            st.line_chart(trace.set_index("t")[["tyre_temp_k"]])
    else:
        st.info("No trace recorded for this run.")

# -- Batch -----------------------------------------------------------------
with tabs[6]:
    st.subheader("Frozen batch and claim ledger")
    bundle_path = Path("artifacts/pitch_bundle.json")
    if bundle_path.exists():
        bundle = json.loads(bundle_path.read_text())
        for split, aggregate in bundle.get("aggregate_by_split", {}).items():
            st.markdown(f"**{split} split**")
            st.dataframe(pd.DataFrame(aggregate), use_container_width=True)
        st.markdown("**Claim ledger**")
        for claim in bundle.get("claim_ledger", []) + bundle.get("split_claims", []):
            colour = {"supported": "🟢", "not met": "🟠"}.get(claim["status"], "🔴")
            st.markdown(f"{colour} **[{claim['status']}]** {claim['claim']} — _{claim['evidence']}_")
        st.markdown("**Limitations**")
        for item in bundle.get("limitations", []):
            st.markdown(f"- {item}")
    else:
        st.info("Run `gridops.cli report …` to generate `artifacts/pitch_bundle.json`.")

# -- Architecture status ---------------------------------------------------
with tabs[7]:
    st.subheader("Architecture status — what is real")
    st.dataframe(
        pd.DataFrame(
            [
                {"block": "0 · feature extraction", "state": "implemented", "note": "rolling baselines, super-clipping proxy"},
                {"block": "1 · L4 season lifecycle", "state": "partial", "note": "synthetic DP + stress price; no calibration"},
                {"block": "2 · L3 race / lap maps", "state": "partial", "note": "DP value map + neural lap surrogate; no pit optimisation"},
                {"block": "3A · 40-state HMM", "state": "implemented", "note": "factored mode × reserve"},
                {"block": "3B · SOCP + POMCP", "state": "partial", "note": "SOCP and POMCP yes; Duhr g-g split-accel no"},
                {"block": "4A · zone MPC", "state": "implemented", "note": "LP, solves in ms"},
                {"block": "4B · PMP cues", "state": "implemented", "note": "four switching regimes from costates"},
                {"block": "5 · closed loop", "state": "implemented", "note": "two-car plant, reactive rival"},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "No car actuation, no ECU integration, no FIA certification, and no claim "
        "about real-race lap time or points."
    )
