# AI Motorsport Intelligence Replay

This repository contains two copies of the F1 race replay application:

- [`replay/`](replay/) — the untouched replay baseline.
- [`replay_ai/`](replay_ai/) — the canonical AI Motorsport Intelligence implementation.

All active model, simulation, training, evaluation, and dashboard development belongs in
`replay_ai/`. The retired experimental engine and its documentation remain available in
Git history and are intentionally not part of the current product.

See [`replay_ai/README.md`](replay_ai/README.md) and
[`replay_ai/docs/AIBackend.md`](replay_ai/docs/AIBackend.md) for setup and current model
capabilities.
