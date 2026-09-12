# GRID//OPS — development specification

Version 1.0 · 12 September 2026 · Proposed design; implementation and results pending

**Purpose:** decide whether an electrical-energy commitment is worth making against a rival whose current capability is uncertain, while accounting for the subsequent race and the ego car's physical limits.

This package is the corrected planning baseline. It supersedes the two pasted execution roadmaps and conflicting implementation details in the earlier proposals. Earlier research notes remain useful evidence. It does **not** assert that the user has approved every design choice, that code exists, or that experimental claims have been demonstrated.

## Read this first

We are building an engineer-facing decision-support engine and a closed-loop experimental simulator. Public telemetry supplies observations and contextual calibration; it does not reveal either car's true battery condition. In the demonstrator, own-car measurements come from the simulator, rival internal state remains hidden from the controller, and only the evaluator can inspect truth.

The full design spans execution, lap/tactics, remaining race and component lifecycle. The 24-hour delivery implements a smaller, complete experimental system with the same interfaces. A configured lifecycle penalty is called **season-informed**, not a solved season MPC. A fixed-budget scenario evaluator is called **scenario planning**, not POMCP or a Nash-equilibrium solver.

## Reading routes

| Reader / decision | Read |
|---|---|
| Both developers: what are we building? | [PRD](01-prd.md), [architecture](02-architecture.md), [build plan](06-build-plan.md) |
| Dynamics/control developer | [models and algorithms](03-models-and-algorithms.md), [contracts](04-data-and-contracts.md), [verification](05-validation-and-experiments.md) |
| Inference/evaluation developer | [contracts](04-data-and-contracts.md), [verification](05-validation-and-experiments.md), [backlog](07-engineering-backlog.md) |
| Research/pitch lead | [novelty and experiments](08-research-and-novelty.md), [pitch guide](09-pitch-guide.md), [references](10-references.md) |
| A fresh development session | [developer handoff](12-developer-handoff.md), then its selected backlog slice |
| Terminology | [domain glossary](../../CONTEXT.md), [technical glossary](11-glossary.md) |

Supporting artifacts: [architecture diagram source](architecture.mmd), [chronological architecture block diagrams](13-chronological-architecture-block-diagram.md), [example run manifest](templates/run-manifest.example.json), [example ruleset contract](templates/ruleset.example.json), and [architectural decisions](../adr/0001-truth-observation-separation.md).

## The product in one sentence

**GRID//OPS compares physically achievable energy strategies across plausible rival responses, recommends a justified commitment or retention of the reference strategy, and records the evidence behind that decision.**

## Delivery boundaries

| Tier | Intended capability | Honest claim |
|---|---|---|
| Required experimental build | Action-responsive simulation, constrained energy planning, persistent rival beliefs, multi-lap value, thermal/tyre effects, reproducible comparisons, evidence-driven interface | Working research demonstrator, if acceptance tests pass |
| Optional within the event | Strategic energy feints, synthetic season dynamic program, richer battery circuit, compact policy learning | Implemented extensions only when independently tested |
| Research follow-up | Strong learned baselines, independently developed plant, larger evaluation, formal analysis of a restricted model | Candidate paper contribution; no publication guarantee |
| Authorized team integration | Identified vehicle maps, own-car telemetry, operational validation with engineers | Future integration proposal, not present capability |

## Non-negotiables

1. No hidden rival truth, future samples, or test outcomes enter the deployed controller.
2. No synthetic state is displayed as measured F1 telemetry.
3. No solver-status flag substitutes for checking physical and rule residuals.
4. No thermal/wear proxy is reported as identified battery lifetime or measured tyre loss.
5. No guaranteed wins, guaranteed safe overtakes, FIA certification or unmeasured Haas lap-time gains.
6. No paper supplies authority to disregard the current event ruleset.
7. No external publication or issue creation is implied by these local documents.

## Open decisions and prerequisites

Confirm organizer reuse rules, actual submission requirements, reference event, dataset permissions, available machine and final team ownership at kickoff. The proposed test seam is a complete episode driven through the same decision interface as the dashboard. The asynchronous review question and the proposed backlog remain review items; they do not block producing these documents.

Working assumptions: two capable developers; CPU and optional GPU; a 24-hour event; public data; one circuit geometry and a two-car tactical focus. Schedule times are relative to event start. No absolute deadline is inferred from the older conversation.

## Development status

At preparation time the workspace contains research notes and an earlier illustrative HTML interface, not a verified simulator, controller, experiment suite or dependency lockfile. This package adds specifications only. Metrics and latency limits elsewhere are **targets**, never results.
