# GRID//OPS — chronological architecture (block diagrams)

Status: derived from the corrected development package (v1.0). Diagram only — it adds no
requirements and no results. Where the specification says "target" or "proposed", the
diagram keeps that status.

This file shows **how the system runs in time**, from authorization through a single
decision tick, through episode termination, batch comparison, presentation and the claim
gates. Each section is one block diagram with a short legend.

Rendered copies (dark theme, SVG + 2× PNG) live in [diagrams/](diagrams/) — open
[diagrams/index.html](diagrams/index.html) to browse them all. The Mermaid source below is
the single source of truth; regenerate the rendered copies if the diagrams change.

## Diagram index

| # | Diagram | Question it answers |
|---|---|---|
| 1 | [Master chronology](#1-master-chronology) | What are the phases, in order, and where does the loop close? |
| 2 | [Phase 0–1: authorization and startup](#2-phase-01-authorization-and-startup) | What must be frozen before the first action? |
| 3 | [Phase 2: one closed-loop decision tick](#3-phase-2-one-closed-loop-decision-tick) | What happens inside one decision? |
| 4 | [Runtime sequence](#4-runtime-sequence) | Who calls whom, and when is data available? |
| 5 | [Four-horizon cascade H4→H1](#5-four-horizon-cascade-h4h1) | How do the planning horizons couple? |
| 6 | [Information separation / trust boundary](#6-information-separation--trust-boundary) | What can the controller never see? |
| 7 | [Event and memory chronology](#7-event-and-memory-chronology) | What resets, what persists, what widens? |
| 8 | [Decision outcomes and fallback](#8-decision-outcomes-and-fallback) | How does a recommendation get accepted or refused? |
| 9 | [Phase 3: termination and scoring](#9-phase-3-termination-and-scoring) | Who scores the episode and against what truth? |
| 10 | [Phase 4: experiment batch chronology](#10-phase-4-experiment-batch-chronology) | How does frozen comparison work? |
| 11 | [Phase 5: records to engineer interface](#11-phase-5-records-to-engineer-interface) | How does a display stay traceable? |
| 12 | [Build chronology T+0→T+24](#12-build-chronology-t0t24) | What is built when, and which gate blocks what? |
| 13 | [Module block map](#13-module-block-map) | Which code module owns which block? |
| 14 | [Claim release gates](#14-claim-release-gates) | What evidence unlocks which sentence? |

---

## 1. Master chronology

Top-level phase order. Phase 0 and Phase 1 run once. Phase 2 is the repeating episode
loop. Phases 3–5 run after the episode. Truth (red) never enters the controller (green).

```mermaid
flowchart TD
    classDef phase fill:#0b3d5c,stroke:#7fd1ff,color:#eaf6ff;
    classDef truth fill:#5c1a1a,stroke:#ff9a9a,color:#ffecec;
    classDef ctrl fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef eval fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef store fill:#2a1240,stroke:#c9a3ff,color:#f6ecff;
    classDef gate fill:#3d1a2a,stroke:#ff9ad5,color:#ffeaf6;

    subgraph P0["PHASE 0 — Kickoff and authorization (once)"]
        direction LR
        K1["Verify organizer rules<br/>reuse · AI assist · licences · submission"]
        K2["Choose one circuit geometry<br/>two-car scope · horizon · metric"]
        K3["Record machine, deps, roles<br/>freeze dependency policy"]
        K1 --> K2 --> K3
    end

    subgraph P1["PHASE 1 — Startup and configuration (once per run)"]
        direction TB
        S1["Resolve versioned scenario<br/>track · rules · parameters · seeds"]
        S2["Resolve parameter provenance<br/>synthetic / fitted / paper / verified_rule"]
        S3["Load controller-allowed artifacts only<br/>truth seeds in a separate run context"]
        S4["Validate track closure, units<br/>initial-state bounds, ruleset completeness"]
        S5["Build reference pace/energy maps<br/>+ candidate cache over validity domain"]
        S6["Initialize fast-state priors<br/>no previous-race SOC as truth"]
        S7["Append immutable run manifest<br/>before the first action"]
        S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7
    end

    subgraph P2["PHASE 2 — Closed-loop episode (repeats every decision tick)"]
        direction TB
        L1["Plant advances to next<br/>sensor / event / control time"]
        L2["Observation adapter publishes<br/>only available_at &lt;= now"]
        L3["Event ledger applies<br/>tyre set · rules mode · weather · penalty"]
        L4["Belief and context update<br/>propagate, then correct"]
        L5["Race value H3/H4<br/>targets + continuation cost"]
        L6["Candidate set + convex profiles H2"]
        L7["Bounded reactive-scenario evaluation"]
        L8["Commitment + feasibility supervisor"]
        L9["Execute first control interval H1"]
        L1 --> L2 --> L3 --> L4 --> L5 --> L6 --> L7 --> L8 --> L9 --> L1
    end

    subgraph P3["PHASE 3 — Termination and scoring"]
        direction LR
        T1["Privileged evaluator inspects truth"]
        T2["Metrics + failure table + record freeze"]
        T1 --> T2
    end

    subgraph P4["PHASE 4 — Frozen experiment batch"]
        direction LR
        B1["Paired seeds, matched resources"]
        B2["Baselines B0/B1/B2/B3/M/O + ablations"]
        B3["Complete results incl. failures"]
        B1 --> B2 --> B3
    end

    subgraph P5["PHASE 5 — Records to engineer interface"]
        direction LR
        U1["Immutable decision records"]
        U2["Traceable presentation + demo replay"]
        U1 --> U2
    end

    G0["G0 — units, hidden-info and one scenario agreed"]
    G5["G5 — replayable demo + reproducible bundle"]

    P0 --> G0 --> P1 --> P2 --> P3 --> P4 --> P5 --> G5
    P3 -. "aggregate only" .-> U2

    class P0,P1,P2,P3,P4,P5 phase
    class L1 truth
    class L2,L3,L4,L5,L6,L7,L8,L9 ctrl
    class T1 eval
    class T2,B1,B2,B3,U1,U2 store
    class G0,G5 gate
```

**Reading the loop:** only `L1` (the nonlinear plant) holds hidden rival truth. Everything
from `L2` to `L9` runs on permitted evidence. The transition `L9 → L1` closes the physical
loop; the integrity of that arrow is the whole design.

---

## 2. Phase 0–1: authorization and startup

The startup workflow is strictly ordered because each step can invalidate the next. An
unknown in `S2` or `S4` disables affected modes rather than defaulting.

```mermaid
flowchart LR
    classDef input fill:#132a3d,stroke:#7fd1ff,color:#eaf6ff;
    classDef proc fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef block fill:#5c1a1a,stroke:#ff9a9a,color:#ffecec;
    classDef art fill:#2a1240,stroke:#c9a3ff,color:#f6ecff;

    IN1["Organizer rubric<br/>reuse · AI · licence"] --> D0{"Rules reusable?"}
    D0 -- no --> STOP1["Stop<br/>do not submit affected artifact"]
    D0 -- yes --> P0A["Select reference circuit<br/>+ event identity"]

    P0A --> P1A["Resolve provenance per parameter<br/>value · unit · source · valid range"]
    P1A --> P1B["Load allowed controller artifacts"]
    P1B --> P1C["Separate evaluator truth context<br/>plant seeds · hidden rival state"]
    P1C --> VAL{"Track closed?<br/>units consistent?<br/>bounds valid?<br/>ruleset complete?"}
    VAL -- no --> BLK["Disable affected mode<br/>record UNKNOWN, never silently default"]
    VAL -- yes --> MAP["Build H3 lap map + H2 candidate cache<br/>known-answer numerical tests"]
    MAP --> PRI["Initialize fast-state priors<br/>shrink sparse driver history"]
    PRI --> MAN["Write run manifest<br/>code hash · seeds · versions · caps"]
    MAN --> RUN["Episode may start"]

    class IN1 input
    class P0A,P1A,P1B,P1C,MAP,PRI,MAN,RUN proc
    class STOP1,BLK block
    class D0,VAL input
```

**Artifacts produced:** scenario JSON, ruleset JSON (nulls for unverified fields), parameter
provenance ledger, run manifest, reference maps, candidate cache, initial-state priors.

---

## 3. Phase 2: one closed-loop decision tick

The canonical eleven-step cycle from the architecture spec, drawn as blocks. The dashed
return is the physical closed loop; the solid left column is the information path.

```mermaid
flowchart TD
    classDef phys fill:#5c1a1a,stroke:#ff9a9a,color:#ffecec;
    classDef obs fill:#132a3d,stroke:#7fd1ff,color:#eaf6ff;
    classDef ctrl fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef plan fill:#1a3d2e,stroke:#8ff0c4,color:#eaffff;
    classDef sup fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef stop fill:#3d1a2a,stroke:#ff9ad5,color:#ffeaf6;

    T0(["t = decision time"]) --> S1["1 · Integrate plant to next<br/>sensor / event / control time<br/>using previously accepted actions"]
    S1 --> S2["2 · Publish observations with<br/>available_at &lt;= t<br/>keep sampled_at and missingness"]
    S2 --> S3["3 · Apply event records<br/>tyre-set change · rules authorization<br/>weather · component identity · penalty"]
    S3 --> S4["4 · Propagate rival hypotheses<br/>through elapsed time, then<br/>update on newly available evidence"]
    S4 --> S5["5 · Query remaining-race value<br/>reachable reserve band + lap budget<br/>replan H3 if old target unreachable"]
    S5 --> S6["6 · Generate bounded candidate set<br/>reference · attack now · attack later<br/>defend · conserve · optional probe"]
    S6 --> S7["7 · Compute or reuse conditional<br/>convex profiles; reject stale cache<br/>and out-of-domain profiles"]
    S7 --> S8["8 · Roll out each candidate against<br/>reactive rival hypotheses;<br/>same first action across indistinguishable futures"]
    S8 --> S9["9 · Rank vs reference using criterion<br/>+ continuation cost; keep mean,<br/>downside and failure explanations"]
    S9 --> STEP10["10 · Commitment rule + feasibility<br/>supervisor → plan with expiry,<br/>or FALLBACK / UNAVAILABLE"]
    STEP10 --> STEP11["11 · Execute only the first control interval<br/>record saturation; next cycle starts<br/>from the actual resulting state"]
    STEP11 -->|next tick| T0

    S1 -. "plant truth stays here" .-> EPRIV["Privileged evaluator<br/>truth has no return path"]
    S2 -. "permitted evidence only" .-> S4
    S4 -. "belief" .-> S8
    S5 -. "targets" .-> S7

    class S1 phys
    class S2 obs
    class S3,S4,S5 ctrl
    class S6,S7 plan
    class S8,S9 ctrl
    class STEP10 sup
    class STEP11 phys
    class EPRIV stop
    class T0 obs
```

**Non-negotiable inside this tick**

- The controller cannot read the plant object, rival SOC, rival policy label or future samples.
- A rollout policy obeys the same observation contract as the deployed controller.
- The plan is the latest valid one only after a fresh feasibility check; expiry is explicit.
- Saturation and rejection are recorded, never hidden by clipping.

---

## 4. Runtime sequence

Same cycle as a sequence diagram, showing ownership and information timing. Note that the
evaluator receives truth in a separate, privileged channel.

```mermaid
sequenceDiagram
    autonumber
    participant Plant as Nonlinear plant (truth)
    participant Obs as Observation adapter
    participant Ledger as Event ledger
    participant Belief as Belief and context
    participant Value as Race value H3/H4
    participant Plan as Convex planner H2
    participant Eval as Scenario evaluator
    participant Sup as Commitment supervisor
    participant Exec as Execution tracker H1
    participant Rec as Records
    participant EPriv as Privileged evaluator

    Note over Plant,EPriv: Startup: manifest frozen before first action

    loop Every decision tick
        Exec->>Plant: advance(accepted actions, dt)
        Plant-->>Obs: raw sensors + exogenous events
        Plant-->>EPriv: hidden truth (private, no return path)
        Obs->>Belief: frame with sampled_at / available_at / masks
        Ledger->>Belief: tyre set, rules mode, weather, penalty
        Belief->>Belief: propagate over dt, then correct
        Belief->>Value: query reachable resource/context state
        Value-->>Belief: continuation cost, reserve band, targets
        Belief->>Plan: belief + context + energy targets
        Plan->>Plan: DCP check, solve, residual + trust-region report
        Plan-->>Eval: candidate speed/power/path profiles
        Belief-->>Eval: hypothesis set + response policies
        Eval->>Eval: paired rollouts, shared first action
        Eval-->>Sup: ranked candidates + downside + failures
        Sup->>Sup: commitment margin, reserve floor, no-progress guard
        alt candidate clears margin and feasibility
            Sup-->>Exec: RECOMMEND plan + validity interval
        else no candidate clears margin
            Sup-->>Exec: RETAIN_REFERENCE
        else solver/data/model problem
            Sup-->>Exec: FALLBACK (rechecked reference)
        else no valid model-feasible state
            Sup-->>Exec: UNAVAILABLE
        end
        Sup->>Rec: immutable decision record
        Exec->>Plant: applied first control interval
        Plant-->>Exec: measured saturation and feedback
    end

    Plant-->>EPriv: final outcome
    EPriv->>Rec: metrics, pass classification, failure table
    Rec-->>Rec: frozen bundle
```

---

## 5. Four-horizon cascade H4→H1

Four rates, not four competing weighted scores. Downward arrows carry **compatible resource
targets and costs**; upward arrows carry **feasibility feedback**. Any lower layer can
reject an upper target.

```mermaid
flowchart TB
    classDef h4 fill:#2a1240,stroke:#c9a3ff,color:#f6ecff;
    classDef h3 fill:#0b3d5c,stroke:#7fd1ff,color:#eaf6ff;
    classDef h2 fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef h1 fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef io fill:#132a3d,stroke:#9fd0ff,color:#eaf6ff;

    subgraph H4["H4 — Lifecycle / season (before event)"]
        direction LR
        H4A["Configured marginal stress value<br/>optional tiny synthetic DP"]
        H4B["Component constraints<br/>+ time-equivalent stress price"]
        H4A --> H4B
    end

    subgraph H3["H3 — Remaining race (lap boundary / major event)"]
        direction LR
        H3A["Finite lap-map allocation<br/>restricted pit alternatives"]
        H3B["Lap energy budget<br/>reachable reserve band<br/>continuation-cost map"]
        H3A --> H3B
    end

    subgraph H2["H2 — Lap / tactical windows (nominal 1 s or new evidence)"]
        direction LR
        H2A["Conditional convex<br/>deployment profiles"]
        H2B["Bounded reactive-scenario<br/>evaluation"]
        H2C["Selected speed/power/path refs<br/>validity interval + alternatives"]
        H2A --> H2B --> H2C
    end

    subgraph H1["H1 — Execution (50–100 ms; plant at 20 ms integration)"]
        direction LR
        H1A["Feasibility projection<br/>and tracking"]
        H1B["Simulated actuator request"]
        H1A --> H1B
    end

    H4B -->|"stress price + component constraints"| H3A
    H3B -->|"lap budget + reserve band + continuation value"| H2A
    H2C -->|"power/speed/path refs + validity interval"| H1A

    H1B -. "tracking error · saturation · thermal/grip limits" .-> H2C
    H2C -. "reachable energy interval · target infeasible" .-> H3B
    H3B -. "conflicting lifecycle target · achieved pace" .-> H4B

    NOTE["H1 is not called MPC unless it optimizes a horizon.<br/>H4 is season-informed, not a solved season MPC,<br/>while its input is a configured price."]
    H4 ~~~ NOTE

    class H4A,H4B h4
    class H3A,H3B h3
    class H2A,H2B,H2C h2
    class H1A,H1B h1
    class NOTE io
```

**Rate table (proposed starting configuration, subject to profiling)**

| Horizon | Update | Exchanges down | Exchanges up |
|---|---|---|---|
| H4 lifecycle | before event / component change | stress price, component constraints | stress exposure, performance trade-offs |
| H3 remaining race | lap boundary / major event | lap budget, reserve band, continuation cost | achieved pace, reachable targets |
| H2 lap/tactical | nominal 1 s / fresh evidence | profile refs, validity interval, alternatives | tracking residuals, revised hypotheses |
| H1 execution | 50–100 ms / 20 ms integration | simulated actuator request | saturation, thermal/grip limits, infeasibility |

---

## 6. Information separation / trust boundary

The single most important architectural constraint (ADR-0001). The evaluator may compare
beliefs with truth **after** the run; during action selection there is no return path.

```mermaid
flowchart LR
    classDef truth fill:#5c1a1a,stroke:#ff9a9a,color:#ffecec;
    classDef permit fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef forbid fill:#3d1a2a,stroke:#ff9ad5,color:#ffeaf6;
    classDef obs fill:#132a3d,stroke:#7fd1ff,color:#eaf6ff;

    subgraph TRUTH["Evaluator-only truth"]
        direction TB
        TR1["True rival SOC / temperature / SOH"]
        TR2["Rival private policy params + memory"]
        TR3["Future samples and exogenous schedule"]
        TR4["Test labels and privileged outcomes"]
    end

    subgraph PUB["Permitted public evidence"]
        direction TB
        PB1["Timing, stint, compound<br/>weather, race-control"]
        PB2["Public speed / throttle / brake status"]
        PB3["Own simulated measurements<br/>with uncertainty + provenance"]
        PB4["Verified track geometry<br/>and verified event permissions"]
    end

    subgraph CTRL["Deployable controller (DecisionInput only)"]
        direction TB
        C1["Ego state<br/>speed, estimated SOC/temp, constraints"]
        C2["Opponent observation frames only"]
        C3["Track and event context"]
        C4["Reachable resource targets"]
        C5["Versions: models, ruleset, candidate library"]
    end

    TRUTH -.->|"blocked during action selection"| BARRIER["Trust boundary<br/>no hidden truth<br/>no future samples"]
    BARRIER -.->|"post-run only"| SCORE["Evaluator scoring<br/>belief vs truth, calibration"]
    PUB --> OBSADP["Observation adapter<br/>assemble + timestamp"]
    OBSADP --> CTRL

    CTRL -->|"immutable decision records"| SCORE

    X1["EXPLICITLY PROHIBITED in DecisionInput<br/>true rival SOC/current/temperature<br/>policy-family label · future telemetry<br/>RNG state revealing opponent futures<br/>test labels · privileged counterfactuals"]
    C2 -.-> X1

    class TR1,TR2,TR3,TR4 truth
    class PB1,PB2,PB3,PB4 permit
    class C1,C2,C3,C4,C5 permit
    class OBSADP obs
    class SCORE obs
    class BARRIER forbid
    class X1 forbid
```

**Leakage tests that enforce this boundary:** mutate hidden rival state under fixed permitted
input (immediate action must not change); replace future telemetry (current features must not
change); ensure overlapping windows are not double-counted; ensure rollout controllers cannot
read sampled latent state; ensure cache keys never encode an evaluation label.

---

## 7. Event and memory chronology

Persistence is event-aware. Three memories move independently: fast race belief, driver/car
context, and the component/tyre ledger.

```mermaid
flowchart LR
    classDef ev fill:#0b3d5c,stroke:#7fd1ff,color:#eaf6ff;
    classDef fast fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef ctx fill:#2a1240,stroke:#c9a3ff,color:#f6ecff;
    classDef comp fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;

    N["Normal observation"] --> N1["Bayesian propagate then update"]
    N --> N2["Gradual contextual update<br/>on permitted data"]
    N --> N3["Accumulate declared evidence"]

    M["Missing observations"] --> M1["Predict forward, widen uncertainty"]
    M --> M2["No fabricated evidence"]
    M --> M3["Preserve last verified identity"]

    TY["New tyre set"] --> TY1["Reset relevant wear/temperature prior"]
    TY --> TY2["Preserve, with context change"]
    TY --> TY3["New set identity; old set kept in history"]

    SS["New session"] --> SS1["Fresh SOC/temperature priors"]
    SS --> SS2["Shrink or reuse compatible learned params"]
    SS --> SS3["Preserve only supported continuity"]

    BR["Confirmed battery replacement"] --> BR1["Reinitialize battery-health prior"]
    BR --> BR2["No automatic driver reset"]
    BR --> BR3["New component identity + evidence"]

    GP["Grid penalty"] --> GP1["Update order implications"]
    GP --> GP2["No implied aggression change"]
    GP --> GP3["Record reason; no automatic SOH deduction"]

    CW["Changed car / weather behavior"] --> CW1["Increase model uncertainty"]
    CW --> CW2["Forget, shrink, or change-point reset"]
    CW --> CW3["Retain provenance, not false precision"]

    N1 --> FAST["Fast race belief"]
    M1 --> FAST
    TY1 --> FAST
    SS1 --> FAST
    BR1 --> FAST
    GP1 --> FAST
    CW1 --> FAST

    N2 --> CTX2["Driver/car context"]
    SS2 --> CTX2
    CW2 --> CTX2

    N3 --> COMP2["Component / tyre ledger"]
    TY3 --> COMP2
    SS3 --> COMP2
    BR3 --> COMP2
    GP3 --> COMP2

    RULE["Rule: battery state and driver behavior are not the same object.<br/>Never restore a previous race's SOC as current truth."]
    COMP2 ~~~ RULE
    FAST ~~~ RULE

    class N,M,TY,SS,BR,GP,CW ev
    class FAST,N1,M1,TY1,SS1,BR1,GP1,CW1 fast
    class CTX2,N2,SS2,CW2 ctx
    class COMP2,N3,TY3,SS3,BR3,GP3 comp
    class RULE ev
```

---

## 8. Decision outcomes and fallback

A recommendation is a **commitment**, not a status flag. `FALLBACK` (technical) and
`RETAIN_REFERENCE` (strategic abstention) must never be conflated.

```mermaid
flowchart TD
    classDef calc fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef sup fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef ok fill:#0b3d5c,stroke:#7fd1ff,color:#eaf6ff;
    classDef warn fill:#3d1a2a,stroke:#ff9ad5,color:#ffeaf6;
    classDef fail fill:#5c1a1a,stroke:#ff9a9a,color:#ffecec;

    CAND["Candidate families<br/>reference · attack now · attack later<br/>defend · conserve · optional probe"] --> J["Paired cost J_H(a, theta)<br/>vs feasible reference a0"]
    J --> G["Estimated paired improvement<br/>G-hat(a, theta)"]
    G --> L["Worst-case lower bound<br/>L(a) = min_theta G-hat - epsilon_a"]
    L --> DEC{"L(a) &gt; commitment margin?<br/>and modeled-feasible?<br/>and reserve floor held?<br/>and no-progress guard clear?"}

    DEC -- yes --> REC["RECOMMEND<br/>plan + validity interval<br/>+ alternatives + reason codes"]
    DEC -- no, margin not cleared --> RET["RETAIN_REFERENCE<br/>strategic abstention<br/>not a solver failure"]
    DEC -- solver/data/model issue --> FB["FALLBACK<br/>current-state-checked reference<br/>report the technical issue"]
    DEC -- no valid state/action --> UN["UNAVAILABLE<br/>record failure or prescribed<br/>safe-termination behavior"]

    HB{"Plan switching<br/>within min hold period?"}
    REC --> HB
    HB -- yes and still feasible --> HOLD["Keep current plan<br/>until hold expires"]
    HB -- no, or limit/expiry overrides --> REC2["Switch plan"]
    HOLD --> EXE["Execute first control interval"]
    REC2 --> EXE
    RET --> EXE
    FB --> EXE
    UN --> EXE

    EXTRA["Multiple reasons may apply.<br/>Do not collapse to a single word.<br/>Suggested codes: GAIN_SURVIVES_SCENARIOS,<br/>AMBIGUOUS_CAPABILITY, INSUFFICIENT_RESERVE,<br/>THERMAL_LIMIT, GRIP_LIMIT, ELIGIBILITY_UNKNOWN,<br/>INPUT_STALE, SOLVER_TIMEOUT, NO_FEASIBLE_REFERENCE,<br/>MODEL_OUT_OF_DOMAIN"]
    DEC ~~~ EXTRA

    class CAND,J,G,L calc
    class DEC,HB sup
    class REC,REC2,HOLD ok
    class RET,FB warn
    class UN fail
    class EXE calc
    class EXTRA warn
```

---

## 9. Phase 3: termination and scoring

The evaluator is the only component that sees truth. It scores calibration, not just outcome,
and it keeps failures.

```mermaid
flowchart LR
    classDef truth fill:#5c1a1a,stroke:#ff9a9a,color:#ffecec;
    classDef eval fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef store fill:#2a1240,stroke:#c9a3ff,color:#f6ecff;

    END(["Episode ends<br/>horizon reached or prescribed stop"]) --> R1["Collect decision records"]
    END --> R2["Collect plant truth"]
    END --> R3["Collect event ledger"]

    R1 --> SC["Evaluator"]
    R2 --> SC
    R3 --> SC

    SC --> M1["Primary: total episode /<br/>finish-time cost, paired"]
    SC --> M2["Secondary: attack expenditure,<br/>unsuccessful attack rate,<br/>missed opportunity, regret"]
    SC --> M3["Physical: constraint violations,<br/>saturation, terminal reserve,<br/>max temperature, tyre wear proxy"]
    SC --> M4["Calibration: forecast error/coverage,<br/>latent calibration only where truth exists"]
    SC --> M5["Reliability: fallback/unavailable rate,<br/>plan oscillation, latency tails"]
    SC --> M6["Geometry: completed pass requires<br/>footprints + containment + persistence"]
    SC --> M7["Failures: timeouts and infeasible<br/>episodes retained, never dropped"]

    M1 --> REPORT["Frozen report + failure table"]
    M2 --> REPORT
    M3 --> REPORT
    M4 --> REPORT
    M5 --> REPORT
    M6 --> REPORT
    M7 --> REPORT

    class END,R2 truth
    class SC,M1,M2,M3,M4,M5,M6,M7 eval
    class R1,R3,REPORT store
```

**Pass classification rule:** no contact and no track exit, ego rear clears rival front by a
configured margin, and the new order persists for a configured interval. Without the
geometric model, every output is labelled **catch-up only**.

---

## 10. Phase 4: experiment batch chronology

Frozen comparison. The same physical plant and observation contract for every method; only
the decision adapter changes.

```mermaid
flowchart TD
    classDef freeze fill:#0b3d5c,stroke:#7fd1ff,color:#eaf6ff;
    classDef run fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef ctrl fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef out fill:#2a1240,stroke:#c9a3ff,color:#f6ecff;

    F1["Freeze scenario families S1–S5<br/>metric definitions + pass definition"] --> F2["Freeze splits<br/>development / calibration / test"]
    F2 --> F3["Freeze candidate, rollout, iteration<br/>and wall-clock caps"]
    F3 --> F4["Freeze terminal conditions and<br/>commitment margin (tuned on allowed split)"]

    F4 --> SEEDS["Paired seeds and matched initial resources"]
    SEEDS --> ISOLATE["Isolate random streams so one controller's<br/>extra rollouts cannot change the plant's draws"]

    ISOLATE --> RUNS["Run controller adapters on identical episodes"]
    RUNS --> B0["B0 budget-aware heuristic"]
    RUNS --> B1["B1 competitor-unaware convex planner"]
    RUNS --> B2["B2 posterior-mean scenario planner"]
    RUNS --> BM["M ambiguity-aware commitment (main test)"]
    RUNS --> B3["B3 optional CVaR / minimax-regret"]
    RUNS --> BO["O evaluator-only privileged diagnostic"]

    B0 --> ABL["Ablation matrix<br/>full M − continuation value<br/>− worst-case margin − belief update<br/>− probe − thermal/tyre limits"]
    B1 --> ABL
    B2 --> ABL
    BM --> ABL
    B3 --> ABL
    BO --> ABL

    ABL --> RES["Complete result table"]
    RES --> R1["Per-family paired differences<br/>median / mean"]
    RES --> R2["Uncertainty intervals<br/>bootstrap at episode/event cluster"]
    RES --> R3["Failure penalties applied<br/>before tests are unseen"]
    RES --> R4["Compute and calibration effects<br/>reported alongside outcomes"]

    R1 --> FREEZE["Frozen result bundle"]
    R2 --> FREEZE
    R3 --> FREEZE
    R4 --> FREEZE

    class F1,F2,F3,F4 freeze
    class SEEDS,ISOLATE,RUNS,ABL run
    class B0,B1,B2,BM,B3,BO ctrl
    class RES,R1,R2,R3,R4,FREEZE out
```

**Baseline roles (do not collapse them)**

| ID | Controller | What it isolates |
|---|---|---|
| B0 | Budget-aware heuristic | practical minimum comparator |
| B1 | Convex planner, competitor-unaware | value of interaction modelling |
| B2 | Posterior-mean scenario planner | ambiguity-aware commitment vs better search |
| M | Ambiguity-aware commitment | main method under test |
| B3 | CVaR / minimax regret | whether a risk criterion explains benefit |
| O | Privileged best feasible candidate | information-gap diagnostic, not deployable |

---

## 11. Phase 5: records to engineer interface

Presentation is a **projection** of immutable records. It cannot recompute or create results.

```mermaid
flowchart LR
    classDef rec fill:#2a1240,stroke:#c9a3ff,color:#f6ecff;
    classDef view fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef guard fill:#3d1a2a,stroke:#ff9ad5,color:#ffeaf6;

    REC1["Decision records<br/>status · action family · plan<br/>reference_id · alternatives"]
    REC2["Belief summary<br/>capability forecast + spread<br/>evidence freshness"]
    REC3["Resource forecast<br/>own energy/thermal/tyre<br/>units + uncertainty"]
    REC4["Constraint report<br/>residuals · limiting constraints<br/>prediction-model validity"]
    REC5["Runtime<br/>estimation · compile · solve<br/>rollout · verification · total"]
    REC6["Trace<br/>input IDs · versions · scenario-set<br/>criterion · error-margin provenance"]

    REC1 --> UI["Engineer-facing interface"]
    REC2 --> UI
    REC3 --> UI
    REC4 --> UI
    REC5 --> UI
    REC6 --> UI

    UI --> V1["Run mode and clock/freshness"]
    UI --> V2["Primary recommendation + reference"]
    UI --> V3["Uncertainty and binding constraints"]
    UI --> V4["Energy/power/temperature traces"]
    UI --> V5["Experiment comparison"]
    UI --> V6["Optional track view<br/>only after geometry verified"]

    V1 --> DEMO["Demo replay + pitch evidence"]
    V2 --> DEMO
    V3 --> DEMO
    V4 --> DEMO
    V5 --> DEMO
    V6 --> DEMO

    GUARD["Display missing/unavailable; never synthesize.<br/>Replayed records show exactly their recorded<br/>recommendations, not recomputed ones.<br/>No rival 'mind gauge'.<br/>Scenario interventions branch to a new run."]
    UI ~~~ GUARD

    class REC1,REC2,REC3,REC4,REC5,REC6 rec
    class UI,V1,V2,V3,V4,V5,V6,DEMO view
    class GUARD guard
```

---

## 12. Build chronology T+0→T+24

Parallel lanes and integration gates from the two-person build plan. The vertical milestones
(`V1`–`V8`) are the required evidence; the gates (`G0`–`G5`) block progress.

```mermaid
flowchart TD
    classDef gate fill:#3d1a2a,stroke:#ff9ad5,color:#ffeaf6;
    classDef laneA fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef laneB fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef joint fill:#0b3d5c,stroke:#7fd1ff,color:#eaf6ff;

    T0["T+0–2<br/>A: state/control contracts, simple plant<br/>B: run manifest, observation contract,<br/>deterministic runner, sample audit"] --> G0{"G0 — units, hidden info,<br/>one complete scenario agreed"}
    G0 -- fail --> G0F["Stop adding scope<br/>resolve contracts first"]

    G0 -- pass --> T1["T+2–6<br/>A: battery/accounting, grip, baseline driver<br/>B: reactive rivals, sensor masks,<br/>tyre/context state, baseline reports"]
    T1 --> G1{"G1 — full episode; different actions<br/>change outcome; no UI dependency"}
    G1 -- fail --> G1F["Work jointly on the episode<br/>and accounting"]

    G1 -- pass --> T2["T+6–10<br/>A: conditional convex profiles, supervisor<br/>B: persistent belief, causal features,<br/>leakage tests"]
    T2 --> G2{"G2 — decision record connects observations<br/>to a feasible executed profile"}
    G2 -- fail --> G2F["Retain tested reference; reduce grid<br/>and candidate complexity"]

    G2 -- pass --> T3["T+10–14<br/>A: race continuation maps, checked paths<br/>B: bounded scenario evaluator,<br/>paired baselines, ambiguity cases"]
    T3 --> G3{"G3 — attack/defer/defend change<br/>multi-lap outcomes; pass claims gated"}
    G3 -- geometry fails --> G3F["Report catch-up / opportunity,<br/>not completed passes"]

    G3 -- pass --> T4["T+14–18<br/>A: thermal/tyre integration, mismatch, latency<br/>B: frozen method selection, held-out batches,<br/>optional feint only if stable"]
    T4 --> G4{"G4 — all required mechanisms integrated;<br/>benchmark + failure table generated"}
    G4 -- budget fails --> G4F["Drop optional RL, season DP,<br/>feints; disclose smaller counts"]

    G4 -- pass --> T5["T+18–21<br/>A: reliability, worker cutoff, packaging<br/>B: record-driven interface, pitch evidence"]
    T5 --> G5{"G5 — replayable demo and<br/>reproducible result bundle"}
    G5 -- timing fails --> G5F["Offline accelerated demo with measured<br/>latency; no real-time claim"]

    G5 -- pass --> T6["T+21–24<br/>fix blockers; rehearse; submission<br/>freeze with buffer"]
    T6 --> SUB["Submission bundle"]

    class G0,G1,G2,G3,G4,G5 gate
    class T0,T1,T2,T3,T4,T5 laneA
    class G0F,G1F,G2F,G3F,G4F,G5F laneB
    class T6,SUB joint
```

**Required vertical milestones:** (1) reproducible episode + manifest; (2) a
resource-constrained action changes speed, energy and later ability; (3) convex controller
shows residuals; (4) belief controller acts only on causal observations; (5) comparison
includes a reacting opponent and multi-lap value; (6) thermal/tyre changes alter feasible
choices and geometry is checked where claimed; (7) paired batch exports all results and
failures; (8) interface reads frozen evidence.

---

## 13. Module block map

Implementation mapping to the proposed layout, with current status from the engine
foundation. Module names below are the ownership boundaries, not network services.

```mermaid
flowchart TB
    classDef done fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef open fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef missing fill:#5c1a1a,stroke:#ff9a9a,color:#ffecec;

    subgraph CFG["configs/"]
        C1["scenario_synthetic.json<br/>ruleset + scenario"]
    end

    subgraph CONTRACTS["gridops/contracts/"]
        CT1["units"]
        CT2["provenance"]
        CT3["state / params"]
        CT4["records"]
        CT5["DecisionInput"]
    end

    subgraph SIM["gridops/simulation/"]
        SM1["plant — longitudinal,<br/>grip envelope, corner cap, tracker"]
        SM2["battery — one-resistance<br/>electrothermal, signed accounting"]
        SM3["track — fixed-path synthetic circuit"]
        SM4["rivals — reactive policy families"]
        SM5["tyres / thermal<br/>NOT PRESENT"]
    end

    subgraph DEC["gridops/decision/"]
        DC1["belief — particle filter,<br/>credible set, mixing"]
        DC2["tactical — cheap surrogate<br/>calibration open"]
        DC3["planning — conditional convex<br/>CVXPY + Clarabel"]
        DC4["pomcp — history-tree search"]
        DC5["commitment — pricing, reserve floor,<br/>no-progress guard, ledger"]
    end

    subgraph RV["gridops/race_value/"]
        RV1["lap_map — monotone terminal<br/>resource value, reserve band"]
    end

    subgraph EVA["gridops/evaluation/"]
        EV1["controllers — reference, B_stat,<br/>B_mean, convex, M"]
        EV2["runner — deterministic episode,<br/>public-only DecisionInput"]
    end

    subgraph ADP["adapters/ — NOT CREATED"]
        AD1["public replay adapter<br/>FastF1/OpenF1 with available_at"]
        AD2["record-driven presentation"]
    end

    CLI["gridops/cli.py<br/>validate-config · run · benchmark"]

    CFG --> CONTRACTS
    CONTRACTS --> SIM
    CONTRACTS --> DEC
    CONTRACTS --> EVA
    SIM --> RV
    DEC --> EVA
    RV --> EVA
    EVA --> CLI
    SIM -. "geometry model needed<br/>before pass claims" .-> AD1
    EVA -. "records" .-> AD2

    class C1 done
    class CT1,CT2,CT3,CT4,CT5 done
    class SM1,SM2,SM3,SM4 done
    class SM5 missing
    class DC1,DC2 open
    class DC3,DC4,DC5 done
    class RV1 done
    class EV1,EV2 done
    class AD1,AD2 missing
    class CLI done
```

**Known open item (single most important):** belief calibration is not converged. The
surrogate closure scale in `decision/tactical.py` does not match the plant's observed
closure, so the controller's action distribution is dominated by the fixed probe schedule.
The G3 gate requires that against a conserving rival the credible set becomes
weak-dominated and M commits `attack_now`, while against a matching rival it retains.

---

## 14. Claim release gates

Each claim is unlocked only by its required evidence. Passing one level does not imply the
next. This is the chronology of what may honestly be said, in order.

```mermaid
flowchart TD
    classDef ok fill:#123d1e,stroke:#8ff0a4,color:#eafff0;
    classDef need fill:#3d2a12,stroke:#ffd08a,color:#fff6e6;
    classDef no fill:#5c1a1a,stroke:#ff9a9a,color:#ffecec;

    E1["1 · Implementation correctness<br/>unit/sign, numerical, contract tests"] --> C1["Working simulation"]
    E2["2 · Model validity within assumptions<br/>conservation, limiting cases, geometry, convergence"] --> C2["Completed simulated pass"]
    E3["3 · Closed-loop decision value<br/>matched controllers in reactive simulation"] --> C3["Competitor-aware decisions"]
    E4["4 · Robustness<br/>different plant, sensors, opponent policies"] --> C4["Improved benchmark result"]
    E5["5 · Observable-data relevance<br/>causal forecasting on held-out public telemetry"] --> C5["Public-data forecast relevance"]
    E6["6 · External validity<br/>independent/identified plant, authorized team evidence"] --> C6["Haas race gain / FIA certification"]
    E7["Identified ageing model + external evidence"] --> C7["Battery-life improvement"]
    E8["Closest-work comparison + reproducible contribution"] --> C8["Publishable novelty"]

    C2 --> NEEDGEO["Requires geometric separation<br/>and persistence tests"]
    C4 --> NEEDBATCH["Requires frozen test batch with<br/>paired outcomes and failures"]
    C5 --> NEEDCAUSAL["Requires causal held-out forecasts"]
    C6 --> NONE1["Unavailable in core build"]
    C7 --> NONE1
    C8 --> NONE2["Unproven"]

    class E1,E2,E3,E4,E5,E6,E7,E8 ok
    class C1,C2,C3,C4,C5,C6,C7,C8 need
    class NEEDGEO,NEEDBATCH,NEEDCAUSAL need
    class NONE1,NONE2 no
```

**Standing non-negotiables (apply at every phase):** no hidden rival truth or future samples
in the deployed controller; no synthetic state shown as measured F1 telemetry; no
solver-status flag substituting for physical and rule residuals; no thermal/wear proxy
reported as identified lifetime or measured loss; no guaranteed wins, safe overtakes, FIA
certification or unmeasured lap-time gains; no paper overriding the current event ruleset;
no external publication implied by these diagrams.

---

## Companion sources

- [PRD](01-prd.md) · [architecture](02-architecture.md) · [models](03-models-and-algorithms.md)
- [contracts](04-data-and-contracts.md) · [validation](05-validation-and-experiments.md) · [build plan](06-build-plan.md)
- [backlog](07-engineering-backlog.md) · [developer handoff](12-developer-handoff.md)
- [Mermaid source](architecture.mmd) · [ADR-0001 truth/observation separation](../adr/0001-truth-observation-separation.md)
- Domain vocabulary: [CONTEXT.md](../../CONTEXT.md) · engine status: [gridops/README.md](../../gridops/README.md)
