# Rust selection implementation contract

Scope: issue #40. Dependencies: PRs #33, #35, #37 and #39.
The task branch combines their pending changes. This does not integrate them into main.
All existing acceptance gates remain required.

## Fixed behavior

Implement all ten functions in the selection baseline through one Rust core.
Run all 530 authored inputs through each of CLI and the official MCP client.
Compare actual before/after data, including the complete component sets, mode,
ordered history, active face, hidden state, UV layer order, groups and unrelated attributes.
Do not send reference selection flags to the runtime.
Keep the 480 completed, 30 unchanged and 20 rejected source outcomes distinct.
All 1,060 interface comparisons must pass. No skipped or unrun request is a pass.

Mesh editing state belongs to the shared asset. Existing instances keep their reference.
Use typed face references to distinguish polygons from legacy triangles with the same name.
Provide stable derived edge IDs for legacy triangles without rewriting authored geometry.
Expose that topology through the shared inspector. Queries must not change saved files.
Persist optional editing state, group names, weights and seam flags in schema 1.
Absent fields preserve old files and old output. Reject duplicate IDs and invalid references.

Manual seed editing must start from authored IDs and compute its own consistent flags.
Selection must preserve positions, topology, UVs, materials, smoothing, seams and weights.
Errors must leave disk, memory and undo history unchanged, including a failing multi-command batch.
Successful selection supports save/reload and undo. Return per-command operation outcomes
only after the batch is saved. Keep ordinary revision and generation diagnostics compatible.
Regeneration retains asset/instance identity and replaces the asset data as already specified.

## Fixed checks

Keep the frozen reference comparer, all old source pins and all numeric/performance limits.
Retain the 138 primitive comparisons, 57 payload checks and existing MCP regressions.
Use Rust 1.85 format, Clippy, full Rust tests and full Python tests.
Add meaningful checks for legacy identity, duplicate requests, stale revisions,
failed persistence, rollback, history, groups with zero weights and shared references.

Apply the exact 100×100 grid, authored attribute rules and parameter matrix in the baseline.
Measure every function/conversion three times in release on Apple M1 Max/macOS.
Core selection must take at most 100 ms. Select/save/reload must take at most 2,000 ms.
Keep nonnegative monotonic measurements and raw evidence. Do not increase these limits.

Use the actual Metal preview to show vertex markers, selected edges and selected faces.
Hide the specified components. Selection overlays must not change authored materials,
geometry, or surface picking. Save/reload must give identical output.

## Remaining gates

Record exact source, executable, shader, requests, measured outputs and hashes.
All dependency integrations, required three-platform CI and independent acceptance of
the integrated candidate remain required before issue closure.
The fixed finite suite does not accept full numeric domains, multi-object operations,
screen-space tools, UV synchronization or full modeling parity. Their original scope remains open.
No milestone can close from these partial results.
