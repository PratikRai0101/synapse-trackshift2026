---
status: proposed
---

# Separate simulated truth from controller evidence

The simulation and evaluator retain hidden rival state, while every deployable controller receives the same causal observation interface. This costs explicit serialization and leakage tests, but avoids a scientifically invalid shortcut in which a controller appears to infer information it was actually given. Privileged comparators are separate, labelled controller adapters; historical replay never silently becomes an action-responsive race.
