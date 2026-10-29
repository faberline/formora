# Primitive creation context verification

Scope: issue #44. The fixed contract is commit `b5d9631`.
The implementation candidate is `c289c5b77afa979f8bc0986fe9e234151fbf5b07`.
It depends on PR #43, PR #41 and their pending dependency chain.
This evidence does not accept a full feature or milestone.

The [evidence manifest](../evidence/creation-contexts/manifest.json) pins the executable,
Rust source, shader, tools, requests, receipts, measurements and output files.
All captures use executable SHA-256
`7311bc72ab6d0aabde61c352208dda416d5ad423aa732d96e390d3cd4fb41501`.
The actual minimum toolchain is Rust 1.85.0, Cargo 1.85.0, Clippy 0.1.85 and rustfmt 1.8.0-stable.
Absolute child-tool paths and the matching PATH are pinned.
The [local record](../evidence/creation-contexts/local/manifest.json) retains the logs and complete source/test/tool hashes.

## Actual local results

- Format and Clippy with all features and targets passed.
- All 116 Rust tests and 49 Python tests passed. None was ignored.
- All [262 creation-context comparisons](../evidence/creation-contexts/contexts/report.json) passed.
  CLI and the official MCP SDK each execute all 131 authored source cases.
  Each interface covers 91 new objects and 40 insertions.
  Every case also edits a real new vertex, undoes that edit, undoes creation,
  repeats creation and reloads the saved result in a fresh process.
  CLI additionally repeats each case through the one-shot command route.
- All [162 generation regressions](../evidence/creation-contexts/generation/report.json),
  [eight scale regressions](../evidence/creation-contexts/scale/report.json),
  [1,060 selection regressions](../evidence/creation-contexts/selection/report.json),
  [57 payload regressions](../evidence/creation-contexts/polygon-payload-regression/report.json)
  and the existing MCP regression passed.

The unchanged comparers verify oriented topology and fixed 1e-6 numeric limits.
Creation checks include local/world positions, face and corner normals, smooth flags,
UV values, layer order and active layer, material slots and active index,
selection flags and existing/new component identity.
Receipts are actual saved operation results.
The adapter checks each receipt against the actual before/after component sets.
It uses only authored parameters, context and seed input.
It never sends expected newly generated geometry or selection answers to Rust.
Capture drivers refuse changed source, adapter, reference inputs or executables during execution.

The Rust tests add parent world transforms, shared asset ownership,
legacy triangle and implicit edge identity, prefix collision, combined budget rejection,
singular target rejection, batch rollback, ordered receipts, persisted contexts,
frame-preserving rebuilds, save failures and undo.
A preview test hides component markers while retaining selection flags and identical surface hits.

## Failure evidence and source arithmetic

The [first capture](../evidence/creation-contexts/failed-first-capture/report.json)
failed 16 comparisons. All 16 failed raw outputs are retained beside its report.
The first report also lists its successful cases; those earlier successful raw files are not retained.
This failed candidate is not acceptance evidence.

The fixes retain the original comparer and thresholds.
Cone and cylinder cap UVs use the transformed face orientation.
Collapsed caps classify a zero normal before applying the finite source fallback.
Torus insertion uses the frozen source's 4x4 inverse and pairwise multiplication order.
Its actual Eigen revision uses an ARM reciprocal estimate followed by two refinement steps.
The Rust implementation reproduces that arithmetic with scalar operations.
Research with a different Eigen release and the Python Matrix inversion route did not
match the compiled creation path. Those experimental routes were not retained in the product.

The [source manifest](../evidence/creation-contexts/source/manifest.json) records exact
Blender and Eigen revisions, primary source URLs, Blender Git blobs and SHA-256 hashes.
The Eigen dependency is taken from Blender's pinned `versions.cmake`.
Original notices and the complete MPL-2.0 text are retained.
The runtime performs no Blender, Python or repository fixture reads.

## Performance and native output

The [hardware record](../evidence/creation-contexts/hardware.json) identifies Apple M1 Max,
macOS 26.5.2 build 25F84 and arm64. Performance samples use release builds.
The [six new runs](../evidence/creation-contexts/local/creation_context_bench.stdout)
create a 100×100 grid and insert the same grid into a cube three times each.
Every grid contributes 10,201 vertices, 20,200 edges and 10,000 polygons.
The worst core time is 178.802 ms against 500 ms.
The worst operation/save/reload time is 344.211 ms against 2,000 ms.
Raw monotonic timestamps, receipts and equality checks are retained.
All previous triangle, polygon, generation and remaining-primitive performance runs passed.
All [30 selection performance runs](../evidence/creation-contexts/selection-performance/report.json)
also passed their original 100/2,000 ms limits.

The [native Metal evidence](../evidence/creation-contexts/gpu/manifest.json)
shows cursor placement, view placement and insertion into a rotated shared asset.
Each scene has visible geometry. A real edit changes more than 500 pixels.
Fresh process reload produces a byte-identical PNG.
The old vertices remain unchanged when only inserted vertices are edited.
All three prior selection GPU scenes and both prior model GPU scenes also passed.
These offscreen Metal checks do not accept native window input or other platforms.

The [isolated context run](../evidence/creation-contexts/independent/report.json)
copies the executable outside the repository and denies every repository read.
A control read of Cargo.toml fails.
Unseen cube/view and cone/insertion inputs then create, select, undo and reload successfully.
Full saved queries and receipts are retained.
The [ten existing isolated generator cases](../evidence/creation-contexts/generators-independent/report.json)
also pass with repository reads denied.

## Reproduction and remaining gates

Use the actual Rust 1.85 toolchain directory and matching RUSTUP_HOME/CARGO_HOME.
The local driver pins rustc, rustdoc and PATH, and verifies their exact versions.

```sh
python3 tools/local_creation_context_checks.py /absolute/rust-1.85/bin /absolute/target /absolute/new-local-evidence
PYTHONPATH=/absolute/mcp-sdk python3 tools/creation_context_runtime.py /absolute/target/debug/formora /absolute/new-context-evidence
PYTHONPATH=/absolute/mcp-sdk python3 tools/primitive_reference_smoke.py /absolute/target/debug/formora /absolute/new-generation-evidence
PYTHONPATH=/absolute/mcp-sdk python3 tools/remaining_scale_regression.py /absolute/target/debug/formora /absolute/new-scale-evidence
PYTHONPATH=/absolute/mcp-sdk python3 tools/selection_runtime_smoke.py /absolute/target/debug/formora /absolute/new-selection-evidence
python3 tools/polygon_reference_smoke.py /absolute/target/debug/formora /absolute/new-payload-evidence
python3 tools/creation_context_gpu_evidence.py /absolute/target/debug/formora /absolute/new-gpu-evidence
python3 tools/creation_context_independent.py /absolute/target/debug/formora /absolute/new-isolated-evidence
```

Run `selection_performance` in release with a new output directory argument.
Native GPU and sandbox isolation need normal macOS process access.
The strict baseline still exits 2: 9,047 sources, 9,026 pending sources and all 23 features pending.
Source pins, cases, comparison limits and performance gates remain fixed.
Full numeric domains/capacity, other modes, preset management, general modeling,
native window input and Windows/Linux GPU acceptance remain open.
Required three-platform CI, dependency integration and integrated independent acceptance remain unrun.
No failed, skipped or unrun gate is a pass. Issue #44 and all milestones remain open.
