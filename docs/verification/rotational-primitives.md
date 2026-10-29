# Rotational primitive verification

Compiler qualification correction: the historical local Rust 1.85 claim below was withdrawn after a child-tool PATH audit. Use the [actual minimum-version recheck](dependency-minimum-rust.md) for the exact pending candidate and its verified tools. The old records remain historical functional evidence. Required CI and integrated acceptance remain open.

Scope: [issue #36](https://github.com/faberline/formora/issues/36).
The fixed contract was committed as `2ad8cf3` before the implementation.
The implementation candidate is `b1dfd56`.
The dependency chain is PR #33, then PR #35, then this change.
No milestone or full modeling feature is accepted by these finite results.

## Local checks

On macOS 26.5.2 arm64, Apple M1 Max, Rust 1.85.0:

- Format and Clippy with all features and targets passed.
- All 90 Rust tests passed. Five new tests cover real topology, UVs, saved recipes,
  zero dimensions, fills, resource budgets, invalid requests, regeneration, persistence and undo.
- All 33 Python comparison and collection tests passed.
- The [official MCP regression check](../evidence/rotational-primitives/mcp-regression.json) passed.
- All [138 generation comparisons](../evidence/rotational-primitives/cases/report.json) passed.
  These are 47 original cases and 22 boundary geometry subchecks through each of CLI and official MCP SDK 2.3.0.
- The [57 existing polygon payload round trips](../evidence/rotational-primitives/polygon-payload-regression.json) passed.
  These are payload checks. They do not test procedural generation.
- The [independent runtime check](../evidence/rotational-primitives/independent-runtime.json) passed.
  It denied every source repository read and generated eight shapes from unseen parameter samples.
  A control read of an existing reference file failed with a permission error.

The comparison adapter sends shape parameters and the requested creation rotation.
It does not send reference vertices or faces to the runtime.
It applies the captured object transform to a scene entity, as in the prior checks.
The new process reload must return the same saved mesh data.
The existing exact oriented topology and 1e-6 numeric limits remain unchanged.
The largest measured normal error is less than 2e-7.
Boundary tests remain geometry-only checks. Full creation-context acceptance remains unrun.

The [local checks record](../evidence/rotational-primitives/local-checks.json) pins the executable,
source, tools, tests, contracts and workflow used for these results.

## Failed cases and correction

The [pre-correction report](../evidence/rotational-primitives/diagnostics/before-creation-frame-report.json)
records 136 passes and two failures. CLI and MCP both failed the placed UV sphere.
The failed candidate data are retained in that directory.
Earlier default-sphere and torus failures were also found during development.
They were not counted as accepted results.

The sphere must preserve single-precision rotation and seam-weld selection.
Its face and corner normals use separate precision rules.
The torus must wrap its rotation angle before matrix construction.
For the placed sphere, creation-frame trigonometry uses float inputs and float results,
then double products. Object-frame trigonometry uses double results.
An ideal scale-only transform loses this small frame difference and fails the fixed normal limit.

The Rust recipe now stores an optional `creation_rotation` for spheres, cylinders and cones.
It reproduces the conversion between those frames from the requested rotation.
It does not position an entity. Entity transforms still control placement.
The full suite was rerun after this correction. Every final comparison passed.
The original captures, comparison limits and comparison algorithm were not changed.
Source provenance and license notices are in [the generator guide](../rotational-primitives.md).

## Performance and native GPU

The [release performance record](../evidence/rotational-primitives/performance.json)
contains three runs each for the 128×64 sphere, 128×64 torus, 100×100 grid and 4,096-point circle.
Every run passed its fixed 500 ms generation and 2,000 ms create/regenerate/save/reload limits.
The largest measurements were 62.47 ms and 272.12 ms, respectively.
The existing [polygon](../evidence/rotational-primitives/polygon-regression-performance.json)
and [triangle](../evidence/rotational-primitives/triangle-regression-performance.json)
performance samples also passed their original limits.

The [Metal manifest](../evidence/rotational-primitives/gpu/manifest.json) records four isolated scenes.
Each scene contains one generated shape, a camera and a light.
Each shape is visible. Increasing its radius changes its pixels and increases its visible area.
Each fresh-process reload produces a byte-identical PNG.
The instance still references the same asset after regeneration.
The manifest pins the binary, complete source including shader, capture script, requests and output files.
Codex also inspected the sphere and torus output images.
This is finite rendering evidence. It is not full rendering-quality or viewport acceptance.

## Gates that remain open

The dependency chain and exact final candidate require all three-platform CI checks before integration.
Earlier runs were refused by GitHub because of account payments or spending limits.
Local passes do not replace unrun CI jobs.
The exact integrated candidate also requires independent Codex acceptance before issue closure.

The strict full-baseline check still exits 2. It reports 9,047 sources, 9,036 pending sources
and 13 pending features. Product acceptance remains unrun.
Icosphere, Suzanne, full numeric domains, general creation contexts, edit insertion and selection,
parameter presets, native window input, Windows/Linux GPU checks and full modeling acceptance remain open.
All 11 milestones retain their original scope.
