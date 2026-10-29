# Mesh transform reference baseline

Scope: issue #46, part of #14 and milestone 0.0.
This branch depends on PR #45 and its pending dependency chain.
It adds eight pending contracts. It does not implement Rust component transforms.

## Fixed sources and inputs

The reference remains Blender 5.2.3 LTS, build `e13b728c6880`.
Its executable SHA-256 remains
`de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619`.
Core source commit is `e13b728c6880d3084d9d57c30031ed5df8b39dee`.
The official manual's `blender-v5.2-release` branch was resolved to
`4a3be8f9ed3b66b24913e0a0d491d3429a70ea08`.
HTML requests failed. The official repository content API supplied the exact source files at that commit.
The [source manifest](../../baseline/sources/mesh-transform/manifest.json) records files,
official URLs, Git blobs and SHA-256 hashes. The Blender Manual contributor attribution,
original CC BY-SA 4.0 license and core GPL notices are retained.

The initial authoring contract and input were committed as `5a2c935` before capture.
The final expanded input and viewport adapter were committed as `4dbef10` before both final captures.
All initial 1,191 requests remain. Twelve explicit rotation-axis requests were appended.
The input also explicitly fixes the active material index.
No source result was used to generate these authored inputs.

The fixture has 20 vertices, 21 edges and six quads.
It includes a raised grid, a disconnected face, a wire, an isolated point at another
depth and hidden geometry. Two UV layers, two materials, active indices, smooth
flags, seams and weights are authored explicitly.
Custom integer attributes retain vertex, edge and face identity.
Coordinate coincidence never defines an identity.

Eight contracts cover translate, rotate, resize, orientation, pivot, falloff,
connected influence and projected influence.
The cases include all three selection domains, seven built-in orientations,
five pivots, eight axis masks, explicit orientation matrices, parent frames,
nonuniform/reflected/singular object scales, value boundaries, mirror settings,
center overrides, precision mode and face-attribute correction.
All 85 observed operator parameter definitions remain in the reference data.
The [parameter coverage report](../evidence/mesh-transform-baseline/parameter-coverage.json)
lists explicit inputs and every omitted or deferred option.
It does not count omitted/default settings as complete coverage.

## Actual reference execution

Both complete captures and the check report are retained:

- [First manifest](../../baseline/reference/blender-5.2.3/mesh-transform/manifest.json).
- [Second manifest](../../baseline/reference/blender-5.2.3/mesh-transform-repeat/manifest.json).
- [Reference check report](../../baseline/reference/blender-5.2.3/mesh-transform-reproduction.json).

The two final processes have distinct IDs and the same pinned executable hash.
Each executes all 1,203 requests in an initialized native window.
Each contains 1,197 FINISHED and six CANCELLED outcomes.
The cancelled cases are empty or entirely hidden geometry.
They preserve the complete state. They are actual unchanged outcomes, not skipped tests.

Every result retains requested parameters, context, complete before/after logical
geometry, world positions, face/corner normals, object and parent matrices,
cursor/view state, selection, hidden flags, history, active face, groups,
UV values/order/active layer, materials/active index, seams and smooth flags.
The adapter refuses existing output directories and changed input/adapter files.
It publishes a result directory only after all requested captures complete.

The 1,179 deterministic cases reproduce within the fixed componentwise 1e-6
position, normal and UV limits. IDs and oriented topology are compared exactly.
All initial geometry and attributes are bound to authored JSON.
Selection closure is checked independently, including additional selections that
a simple seed-inclusion test would miss.
Object/parent matrices are checked from authored poses.
World positions are checked against actual local coordinates and matrices.
View matrices are checked against both the captured quaternion and authored angles.
There are 92 independent basic/proportional analytic checks across both processes.
These do not imply that every case has a separate mathematical oracle.

The 24 RANDOM cases have a different rule fixed before their capture.
The pinned source seeds this mode from whole clock seconds and exposes no operator seed.
Two independent random outputs need not have identical coordinates.
Both outputs instead pass 960 vertex path/support checks and 288 face-normal
checks against their actual geometry. Selected vertices retain full influence.
Connected influence cannot cross disconnected topology.
Normals must be finite and zero or unit length. Preserved fields remain exact.
This does not accept RNG sequences, distributions or full numeric domains.

## Findings and negative checks

The first background pilot changed view rotation but retained an old view matrix.
A real viewport update needs a native GPU context; invoking it in background mode crashed.
Those pilots are not acceptance evidence.
The final adapter requires a native window and updates the matrices in that region.
Its dedicated factory-startup process closes itself only after publishing complete output.
It saves no source scene.

Independent arithmetic checks also caught two source-interface details.
Numeric EXEC translation values are final orientation-space values; the source does
not simply clip that vector to an interactive axis mask.
An unconstrained viewport rotation flips its selected axis, including numeric EXEC requests.
Both behaviors are recorded in the pinned core source.
The oracle follows those defined semantics without changing the numeric limits.

An additional connected-influence assertion initially required bit-identical float positions.
The source's parent-frame rotation leaves up to 1.49e-7 local rounding drift on some
disconnected points. The check now applies the already fixed 1e-6 position limit.
Negative tests still reject actual influence on disconnected geometry.
The [initial oracle failures](../evidence/mesh-transform-baseline/initial-oracle-failures.json)
remain diagnostic history, not passed gates.

Fifteen new Python tests reject changed authored geometry, topology, UVs, materials,
weights, seams, extra initial selection, stale views, false world/parent frames,
wrong analytic results, invalid random paths, wrong normal/UV comparisons,
changed hashes/builds/adapters, reused processes, unknown statuses, non-finite
values, partial suites and weakened tolerances.
They also check the complete valid source pair and exact authored-suite regeneration.

## Local checks, CI and open scope

The [local record](../evidence/mesh-transform-baseline/local/manifest.json) pins
actual Rust 1.85.0, Cargo 1.85.0, Clippy 0.1.85 and rustfmt 1.8.0-stable.
It runs all 116 Rust tests and 64 Python tests, format, all-target Clippy,
both source comparison suites, metadata checks and the existing MCP regression.
Its logs and full input hashes determine the actual result; this document alone does not prove it.

All 9,047 original source IDs and every previous artifact pin remain.
There are 31 pending feature contracts and 9,003 pending sources.
`complete_products` remains empty.
Strict mode must still exit 2 with structurally valid data and no problems.
No feature was marked accepted and no milestone was closed.

CI now requires the transform reference check, all 262 existing creation-context
executions through CLI/MCP, and the existing macOS create/append isolation test.
Every prior workflow step remains required.
Adding these steps does not show that any remote job has executed.

Snapping, auto-merge/split, other modes/data targets, multi-object editing,
full numeric/capacity domains, random sequence/distribution checks, native
product input, three-platform CI and integrated independent acceptance remain open.
The [fixed contract](../contracts/mesh-transform-baseline.md) retains later Rust
performance and native output gates. They remain unrun.

## Reproduction

Use a fresh output directory for each capture.
The pinned source adapter needs a native window; background mode is rejected.

```sh
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup --window-geometry 0 0 1024 768 --python tools/blender_transform_reference.py -- --suite baseline/fixtures/mesh-transform.json --output /absolute/new-reference
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup --window-geometry 0 0 1024 768 --python tools/blender_transform_reference.py -- --suite baseline/fixtures/mesh-transform.json --output /absolute/new-repeat
python3 tools/compare_transform_reference.py baseline/fixtures/mesh-transform.json /absolute/new-reference /absolute/new-repeat /absolute/new-report.json
python3 tools/local_transform_baseline_checks.py /absolute/rust-1.85/bin /absolute/target /absolute/new-local-evidence
```

The local driver pins compiler child paths and PATH. Supply matching
RUSTUP_HOME/CARGO_HOME and the SDK path needed by the existing MCP regression.
