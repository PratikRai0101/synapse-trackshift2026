# Car model

Drop a GLTF/GLB here as `car.glb` to replace the primitive open-wheel car.

## Sourcing

Real Formula 1 chassis geometry and team liveries are trademarked, so use a
**generic** open-wheel model and let the viewer tint the bodywork per team from
`driver_colors` in the telemetry stream (this is already how the built-in
primitive car works).

Candidates seen so far, all free-to-use generic open-wheel models:

| Model | License | Notes |
|---|---|---|
| F1 2022 Monopost (peterkissdesign / The Pixel Lab) | Royalty-free | Blender source + OBJ/GLTF, texture maps included |
| Formula 1 Car (dark_igorek) | CC-BY | GLB, ~330k tris, 24 MB |
| Generic F1 open-wheel (CGTrader) | Royalty-free | OBJ/FBX/BLEND/GLTF |

Check the license on the page before shipping, and record attribution here.

**Until a model is added, nothing breaks** — the primitive car is used.

## Requirements for the loader

- Y-up, +Z forward, origin on the ground between the wheels.
- Roughly 5.6 m long, 2 m wide.
- Bodywork should use a separate material so it can be tinted per team.

Wiring the loader up is a small change in `src/scene/carParts.ts`, where the
part list is defined.
