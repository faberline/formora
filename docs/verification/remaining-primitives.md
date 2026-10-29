# Icosphere and Suzanne verification

Scope: issue #42. The fixed contract is commit `be84a8a`.
The implementation candidate is `3ea7ecd`.
The branch depends on PR #41 and its pending dependency chain.
These finite results do not accept a full feature or milestone.

The [evidence manifest](../evidence/remaining-primitives/manifest.json)
pins the exact executable, source, shader, requests, measurements and output data.
All product captures use the same Rust 1.85 executable.
The [local check record](../evidence/remaining-primitives/local/manifest.json)
retains Rust 1.85.0, Cargo 1.85.0, Clippy 0.1.85 and rustfmt 1.8.0-stable versions.
Absolute compiler paths and the matching PATH were used.
The driver checks versions and refuses source/input changes during execution.

## Actual local results

- Format and Clippy with all features and targets passed.
- All 107 Rust tests and 49 Python tests passed. No test was ignored.
- All [162 generation comparisons](../evidence/remaining-primitives/generation/report.json) passed.
  Each of CLI and official MCP executed all 57 original source cases and 24 boundary geometry subchecks.
  The ten newly generated original cases cover icosphere levels, radius, UV options, placement and Suzanne size.
- All [eight additional scale comparisons](../evidence/remaining-primitives/scale/report.json) passed.
  These add negative and zero-axis cases for both models through both interfaces.
  They strengthen the fixed suite. They do not remove or replace any of its 162 required comparisons.
- All [1,060 selection regressions](../evidence/remaining-primitives/selection/report.json) passed.
  The complete before/after data, outcomes, save/reload, undo and rejection checks remain required.
- All [57 payload regressions](../evidence/remaining-primitives/polygon-payload-regression.json) and the official MCP regression passed.

The existing oriented topology checks and 1e-6 numeric limits remain unchanged.
The frozen mesh and selection comparers were not changed.
The adapter sends primitive parameters and scene transforms.
It does not send source vertices or faces to the Rust generator.
Boundary and additional scale comparisons verify geometry only.
Full creation-context acceptance remains unrun.

The new Rust tests verify authored topology, UVs, symmetry and coincident vertex identity.
They check component estimates for every subdivision value from 1 through 10.
They generate additional levels, check Euler counts and reject over-budget requests before allocation.
They also verify stable IDs at zero dimensions, axis scaling, invalid parameters,
duplicate IDs, stale revisions, batch rollback, saved recipes, manual-edit flags,
shared instances, selection replacement and undo.
The Python tests check the official source Git blob, exact table reproduction
and rejection of changed source or measured geometry input.

## Source data and runtime isolation

The [source manifest](../evidence/remaining-primitives/source/manifest.json)
records the fixed Blender commit, official source paths, Git blobs and SHA-256 values.
The retained `bmo_primitive.cc` contains the original authored model and UV tables.
The pinned generator reproduces the Rust tables from that exact source.
They are not copied from measured reference mesh output.
Source notices, GPL identifiers and the existing GPL text are retained.
See [the generator guide](../remaining-primitives.md) for behavior and provenance.

The [isolated runtime report](../evidence/remaining-primitives/independent/report.json)
copies the executable outside the repository and denies every repository read.
A control read of an actual source fixture fails.
All ten primitive types then generate from unseen parameter inputs.
The new icosphere uses subdivision 4 and radius 0.875.
Suzanne uses size 1.75.
The full query output for each primitive is retained with its hash.
The runtime uses compiled Rust data and arithmetic.

## Fixed performance and Metal results

Measurements use Apple M1 Max, macOS 26.5.2 arm64 and release builds.
The [hardware record](../evidence/remaining-primitives/hardware.json) retains the actual model and OS build.
The [six new performance runs](../evidence/remaining-primitives/local/remaining_primitive_bench.stdout)
cover subdivision-6 icospheres and default Suzanne three times each.
The icosphere contains 10,242 vertices, 30,720 edges and 20,480 faces.
The requested changes are radius 1 to 1.5 and size 2 to 3.
Every run passed the unchanged 500 ms generation and 2,000 ms create/rebuild/save/reload limits.
Maximum generation time was 88.051 ms. Maximum pipeline time was 578.987 ms.
Raw monotonic start/end timestamps are retained.
All previous triangle, polygon and procedural-generation performance samples also passed their original limits.

The [native Metal manifest](../evidence/remaining-primitives/gpu/manifest.json)
contains one isolated scene for each new model.
Both models are visible. Increasing the requested radius or size increases their visible area.
Each fresh-process reload produces a byte-identical PNG.
The asset ID and entity references remain unchanged after rebuilding.
Codex inspected both output images.
These are finite visibility checks, not full rendering-quality or native window-input acceptance.

## Reproduce and remaining gates

Install `tools/requirements-mcp.txt` before SDK checks.
Use a new output directory for each run.

```sh
python3 tools/local_remaining_primitive_checks.py /absolute/rust-1.85-toolchain/bin /absolute/target /absolute/new-local-evidence
python3 tools/primitive_reference_smoke.py /absolute/target/debug/formora /absolute/new-generation-evidence
python3 tools/remaining_scale_regression.py /absolute/target/debug/formora /absolute/new-scale-evidence
python3 tools/selection_runtime_smoke.py /absolute/target/debug/formora /absolute/new-selection-evidence
python3 tools/remaining_primitive_gpu_evidence.py /absolute/target/debug/formora /absolute/new-gpu-evidence
python3 tools/primitive_independent.py /absolute/target/debug/formora /absolute/new-independent-evidence
```

The strict baseline still exits 2. It reports 9,047 sources, 9,026 pending sources
and all 23 catalog features pending acceptance.
The source pins, original cases and comparison limits remain fixed.
Full numeric domains and upper-range capacity remain unrun.
General creation contexts, edit insertion, presets, native window input,
Windows/Linux GPU and full modeling acceptance remain open.

Required three-platform CI, all dependency integration and independent acceptance
of the integrated candidate remain required before issue closure.
Earlier GitHub jobs could not start because of account billing or spending limits.
The final PR must retain its fresh CI result.
All 11 milestones retain their original complete scope.
