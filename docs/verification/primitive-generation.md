# Primitive generation verification

Compiler qualification correction: the historical local Rust 1.85 claim below was withdrawn after a child-tool PATH audit. Use the [actual minimum-version recheck](dependency-minimum-rust.md) for the exact pending candidate and its verified tools. The old records remain historical functional evidence. Required CI and integrated acceptance remain open.

Scope: [issue #34](https://github.com/faberline/formora/issues/34).
The [fixed contract](../contracts/primitive-generation.md) was committed as `e97f71d` before feature code.
This branch depends on [PR #33](https://github.com/faberline/formora/pull/33), which is not yet integrated.
No product milestone or complete primitive feature is accepted by these finite checks.

## Rust and interface checks

On macOS 26.5.2 arm64, Apple M1 Max, Rust 1.85.0:

- Rust format, Clippy with all features and targets, and all 85 Rust tests passed.
- Python comparison/collection tests: 33 passed.
- The [official MCP regression check](../evidence/primitive-generation/mcp-regression.json) passed.
- Native JSONL and MCP tests create the same geometry, reject huge requests without committing,
  mark manual edits, regenerate from saved parameters, save, reload and undo.
- Generated assets preserve shared entity references. Invalid creation IDs fail before generation.
- The strict full baseline check still exits 2. It reports 9,047 sources, 9,036 pending sources and 13 pending features.
  Product acceptance remains `unrun`.

The runtime generator is Rust arithmetic. It does not contain reference-file loading or invoke an upstream tool.
The [independent-runtime check](../evidence/primitive-generation/independent-runtime.json) copied the binary
into an empty temporary directory. A macOS sandbox denied all reads from the entire source repository.
A control read of an existing reference fixture failed with a permission error.
The restricted binary then generated four shapes with parameter values outside the fixed reference corpus.
Counts and saved parameters were queried from new processes. All passed.

## Actual generated results

The [generation report](../evidence/primitive-generation/cases/report.json) contains 54 checks:
20 original primitive cases and seven boundary geometry subchecks through each of CLI and official MCP SDK 2.3.0.
The adapter sends shape parameters. It never sends the reference vertices or faces to the runtime.
Every result is saved and queried again from a new process.

The existing comparer checks oriented topology, edges, per-corner UVs and normals, smooth flags,
transforms and bounds at the unchanged 1e-6 thresholds. Inputs and outputs are pinned by SHA-256.
All 54 checks passed. The runtime returns generation warnings after successful persistence;
these warnings match the stored asset diagnostics.

Cube scale is baked into its generated asset. The fixed source captures ignore that option for the other three shapes.
The adapter applies the captured object transform to an entity and checks its saved transform.
It does not claim acceptance of shared cursor, view alignment or edit-insertion behavior.

The seven boundary checks project source context captures onto geometry fields only.
No selection, material-role, origin or creation-context metadata are copied into a candidate.
The report explicitly keeps full context acceptance `unrun`.

Zero-size planes/grids retain coincident but distinct vertex IDs. Zero-size cubes match the source's unit-cube result.
Filled zero-radius circles use the already-fixed finite-zero UV fallback and emit `degenerate_default_uv`.
The two cases have 14 and 42 undefined upstream UV components. Their numeric UV-error values are null, not zero.

## Comparison regression

A new regression first failed: a geometry-only view of the zero-radius source reported `0.0` UV error,
even though no finite source UV component existed. The old report only used a null value when creation metadata was present.

The comparer now reports undefined counts and null numeric error independently of creation metadata.
It still rejects missing diagnostics and keeps all finite tolerances unchanged.
It does not emit a creation-attribute match claim for a geometry-only comparison.
All prior comparison tests continue to pass.

## Fixed performance samples

Run the release example `primitive_generation_bench`.
The [measured report](../evidence/primitive-generation/performance.json) records compiler, source and contract hashes.

| Sample and run | Generate | Create, regenerate, save and reload |
| --- | ---: | ---: |
| 100×100 grid, 1 | 57.82 ms | 276.08 ms |
| 100×100 grid, 2 | 36.75 ms | 274.68 ms |
| 100×100 grid, 3 | 36.62 ms | 270.13 ms |
| 4,096-point filled circle, 1 | 4.93 ms | 52.49 ms |
| 4,096-point filled circle, 2 | 4.89 ms | 51.08 ms |
| 4,096-point filled circle, 3 | 4.87 ms | 53.53 ms |
| Fixed per-run maximum | 500 ms | 2,000 ms |

All six runs passed. The existing [polygon](../evidence/primitive-generation/polygon-regression-performance.json)
and [triangle](../evidence/primitive-generation/triangle-regression-performance.json) samples also pass their original limits.
These finite CPU samples do not accept the full input domain or viewport performance.

## Native result evidence

The [Metal manifest](../evidence/primitive-generation/manifest.json) pins the exact executable, source, shader,
capture script and requests. It uses the same binary as the generation and independent-runtime reports.

The [initial capture](../evidence/primitive-generation/before.png) shows four Rust-generated assets.
Each has a separate pixel probe. Changing the four recipes gives the [regenerated capture](../evidence/primitive-generation/after-regenerate.png).
For each shape, a point outside its original visible region becomes filled. These individual checks passed.
A new-process [reload](../evidence/primitive-generation/reopened.png) is byte-identical.
The saved entity-to-asset references also remain unchanged. Codex inspected the output image.

An early cube-growth probe hit the neighboring plane instead of background. That assertion failed.
The point was moved above the plane and the full capture reran with the same background-to-surface assertions.
Only the corrected capture is stored as accepted finite evidence.

## Required gates still open

The dependency PR and the exact implementation candidate must pass all three-platform CI checks before integration.
GitHub previously refused to start jobs because recent account payments failed or the spending limit needs an increase.
The required checks are retained. Local results do not replace them.

Remaining work includes the other primitives, full numeric bounds and capacity evidence, shared creation context,
edit insertion and selection, parameter presets, loose-edge display/picking, native window input for this candidate,
Windows/Linux GPU checks and complete modeling acceptance. The original milestone scope remains unchanged.
