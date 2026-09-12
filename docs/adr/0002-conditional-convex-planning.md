---
status: proposed
---

# Separate conditional convex planning from nonlinear evaluation

Use frozen local speed/grip/thermal predictions and fixed candidate paths to build tractable convex deployment subproblems, then validate their consequences in a nonlinear plant. This trades a global coupled optimum for bounded computation, testable feasibility residuals and explicit model mismatch. A large KKT game or end-to-end RL policy is not on the 24-hour critical path; sequential convex refinements do not establish global convexity or real-world safety.
