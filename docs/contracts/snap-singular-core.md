# Zero-scale snapping and unavailable local frame queries

Issue #73. Continue the full 0.0–1.0 goal. Depend on source draft PR #69 at
3e5347dcc53d809bd5b7fabc23b6d46a7c0aa870 and its unintegrated stack.
Freeze this contract, behavior tests and real performance inputs before code.
The user-approved rule is in snap-singular-local-matrix-policy.md and issue
#68, comment 6513201148. Do not ask for that approval again.

## Existing query behavior

Keep successful operations and all valid physical world results. A local
frame that cannot be evaluated as a finite matrix has an explicit error.
Use the existing objects::frames / world inspection channel. Represent its
matrix_local as null with matrix_local_error equal to cannot_invert.
Other frame fields, world_matrix and real world_vertices remain present.
The world query succeeds. This is an unavailable derived local query, not
a rejected operation or a numeric matrix replacement.

Use an optional typed local matrix and optional typed error. Omit the error
field for available matrices; their existing JSON arrays stay unchanged.
Preserve the old query shape when no object context requested frame details.
Do not add a new edit operation or require scene mutation to query results.
The library frame query also reports the same availability. Query calls must
not change files, memory, scene revision, undo or persisted transforms.

Separate parent/world lookup errors from local inverse/evaluation errors.
Keep errors for invalid entity IDs or invalid physical state. Evaluate actual
frames; never use fixture IDs, mode lists or source answers to choose a result.
Keep finite source results, including exact-zero inverse fallback matrices,
under the original checks. Do not declare all zero-scale frames unavailable.
Do not change stored transforms or snap behavior to avoid the bad getter.
The fourteen approved undefined mesh-axis input rejections remain unchanged.

## Complete product evidence

Run all 1,764 fixed authored cases through actual CLI and official MCP:
3,528 operation requests. Setup reads authored inputs only. No captured source
answer, expected output or reference path may influence operation execution.
Read actual saved channels/geometry, physical queries and genuine receipts.
Compare all physical results and every available local matrix to both native
captures with exact discrete behavior and unchanged 1e-6 continuous limits.
Require the twelve explicit unavailable after-state child queries separately.
They are not numeric local-matrix matches. No dropped case or hidden field.

Preserve the raw API responses that demonstrate null/error versus matrix
availability. Do not synthesize native NaN records from Rust results to pass
a source comparator. The physical and local-query channels have separate
validators. Bind receipt/frame/saved data to actual runtime responses.
Require reload in a fresh process, real shared users, raw active/inactive
channels, attributes, source zero results, undo/replay and recipe regeneration.

Test stale revisions/IDs, invalid parameters/ranges, budget and late batch
failure, and actual failed saves. Failure must preserve disk/memory/revision
and undo with no successful receipt. Successful operations remain committed
when a later read-only local query is unavailable. World queries still work.
Add source-read-denied unseen analytic frames with query error and valid
world geometry, and a native Metal before/after/reloaded rendering proof.

Retain every preceding required gate: actual Rust 1.85 tests and Clippy/fmt,
all Python tests, source comparisons, the 14,326 preceding actual CLI/MCP
requests, asset/RNG checks, approved fourteen undefined-axis errors, recipes,
source-denied proofs, failed-save behavior and native preview proofs.
Keep existing fixtures, expected values and limits unchanged. Freeze new
negative controls before code for false query errors, fake numeric fallbacks,
whole-world rejection, lost state/receipt data and source leakage.

## Before-code performance

Bind the unchanged original class-A grid SHA-256
8f29def12ade5467214e888fdcacec23b3d78ed4954e470207a00479ac149536:
10,201 vertices, 20,200 edges and 10,000 quads. Author any new zero-scale
frames as separate fixed inputs while retaining the exact base topology.
Freeze the native source adapter/results, input hashes, every form/sample,
release driver and limits before implementing the query change.

Use representative target-zero and parent-zero frames across all seven direct
operators and the four selected-to-cursor flag pairs: ten forms for each
of two frames, three samples per form, sixty new samples. Preserve actual
source status and local-query availability. Keep source getter errors separate
from timing/physical pass outcomes. Core and operation/save/fresh-reload clocks
include their complete required validation. Each sample must be at most
250 ms core and 2,000 ms pipeline on the recorded M1 Max with actual Rust 1.85.
No discarded warmup, selected best sample, changed timer or relaxed limit.

Also repeat all 177 retained required performance samples and their original
source comparisons/limits: ninety scene, twenty-four raw rotation, thirty
single mesh, nine mesh transform and twenty-four delta. Retain first failures,
all raw measurements and actual terminal exits. Use fresh output directories.

## Lifecycle

Bind every check to actual code, executable/library and fixed source hashes.
Publish a draft with exact local results and preserved failures. Platform CI,
dependency integration and independent Codex acceptance remain required.
Failed, skipped, missing and unrun required checks cannot pass. Keep catalog
reviews pending, complete_products empty and all eleven milestones open.
The independent mesh-merge work on codex/mesh-merge-core remains required;
its committed data-model work and before-code tests/workloads are preserved.
