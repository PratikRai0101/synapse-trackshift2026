# GRID//OPS development reference audit

12 September 2026. Bounded follow-up to `outputs/research-evidence.md` and `outputs/four-horizon-review-and-build-plan.md`. Primary institutional records and official documentation only; no paid access, installations, code execution, or broad literature review.

## Salazar: bibliography verified

Mauro Salazar, Camillo Balerna, Philipp Elbert, Fernando P. Grando, and Christopher H. Onder. **“Real-Time Control Algorithms for a Hybrid Electric Race Car Using a Two-Level Model Predictive Control Scheme.”** *IEEE Transactions on Vehicular Technology*, **66**(12), 10911–10922, December 2017. DOI: [10.1109/TVT.2017.2729623](https://doi.org/10.1109/TVT.2017.2729623); [IEEE document 7986999](https://ieeexplore.ieee.org/document/7986999/).

The [TU/e institutional record](https://research.tue.nl/en/publications/real-time-control-algorithms-for-a-hybrid-electric-race-car-using/) verifies DOI, issue, pages, and published status. Its author metadata omits two middle initials; the [ETH project bibliography](https://idsc.ethz.ch/research-guzzella-onder/research-projects/Formula1.html) supplies Grando’s P. and Onder’s H. IEEE’s page did not expose substantive text during this audit.

TU/e’s abstract supports a convex upper-level planner and a zone-MPC lower-level **linear program**. It reports millisecond-scale lower-level iterations and simulator validation. That is a reported result for that controller, not a measured GRID//OPS latency or a timing guarantee for four horizons, opponent rollouts, or added thermal/tyre dynamics.

## Neumann: manuscript and publication status distinguished

**“Hierarchical Co-Design for Multi-Race Strategy Optimization in Formula 1.”** Authors, in order: Marc-Philippe Neumann, Raphael Habermacher, Giona Fieni, Alberto Cerofolini, Gioele Zardini, Christopher H. Onder. The [MIT author bibliography](https://zardini.mit.edu/publications/) confirms all six and lists the **29th IEEE International Conference on Intelligent Transportation Systems (ITSC), 2026, in press**.

ETH’s [Research Collection author listing](https://www.research-collection.ethz.ch/items/60cad51f-a346-4222-b954-5b4faf48f6f5) classifies the work as a **2025 working paper**. The [ETH project page](https://idsc.ethz.ch/research-guzzella-onder/research-projects/Formula1.html) still says submitted to ITSC 2026. These records are not synchronized: cite “2025 working paper; ITSC 2026 in press according to the authors,” without claiming a verified publisher version of record.

MIT links this [ETH manuscript](https://www.research-collection.ethz.ch/server/api/core/bitstreams/7e6b5a19-6bec-4544-b403-04262777d6cc/content). Its [indexed PDF extract](https://www.research-collection.ethz.ch/bitstreams/7e6b5a19-6bec-4544-b403-04262777d6cc/download) corroborates title and author order, but direct full-PDF retrieval failed. **No numbered revision, revision date, final proceedings DOI/pages, or manuscript-to-proceedings equivalence was verified.** Preserve the linked bitstream identifier as the inspected reference; do not invent “v1.” The author abstract establishes seasonal performance/wear/replacement planning as prior art, not reproducible implementation details or GRID//OPS performance.

## Conditional convex implementation implications

- **DCP gate:** [CVXPY’s DCP guide](https://www.cvxpy.org/tutorial/dcp/index.html) requires a convex minimization objective (or concave maximization), affine equalities, and correctly oriented convex inequalities. Check `problem.is_dcp()`. General products of optimized states/controls do not satisfy these rules; a failed check can also reflect an unsuitable expression of a convex function.
- **OSQP:** Its [official problem definition](https://osqp.org/docs/) accepts a positive-semidefinite quadratic objective with linear bounds `l <= A*x <= u`. “QP-only” includes LPs as a special case. It does not directly accept general second-order-cone constraints.
- **Clarabel:** Its [official overview](https://clarabel.org/stable/) supports quadratic objectives with conic constraints; [supported cones](https://clarabel.org/stable/api_cone_types/) include `||x||₂ <= t`. Use it when the retained convex envelope requires SOC constraints.
- **Selection:** [CVXPY solver documentation](https://www.cvxpy.org/tutorial/solvers/index.html) describes OSQP for QPs and Clarabel for SOCPs, explicit `solver=cp.OSQP`/`cp.CLARABEL`, and `cp.installed_solvers()`. Verify available versions before implementation.

Design inference: freeze scenario/thermal/wear coefficients per solve, enumerate discrete tactics externally, verify DCP and solver compatibility, then validate trajectories in the nonlinear plant. Freezing coefficients alone does not prove convexity or global optimality of the coupled problem.

No paper-linked code release was verified for either paper; treat code as unavailable for build planning, not proven nonexistent. Nothing was reproduced. Benchmark complete decision latency—including compilation, estimation, rollouts, and validation—plus tail latency, failures, residuals, and fallback behavior. Solver documentation and warm-start examples establish no GRID//OPS runtime.
