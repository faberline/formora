# Transform performance with complete validation

Implementation candidate: `08d370df5dca83c5d892b9a8411e60db9dddf621`.
This is bounded progress in draft PR #49. No issue or milestone is accepted.

Asset validation builds a graph of vertices, edges and faces to check editing
and seam IDs. Transform setup and automatic normals previously built another
equivalent graph immediately afterwards. The internal validation path now
returns its owned graph for that caller to use. Every validation check remains.
The normal algorithm and all arithmetic remain unchanged. No graph persists
across asset or selection changes.

Public validation retains its previous behavior for assets that do not need a
graph. Geometry, borders, UVs, normals, slots, recipes, diagnostics, groups,
weights, smooth faces, seams, selection, hidden state, history and active face
are still checked. Budget and finite-range checks remain. Final asset checks,
checks after each batch command and persist-on-success saves remain.

The contract was committed before implementation in
`d4a220bfe812cac8985ff6aba4612593a39b23dd`. The diagnostic profile retained in
`reuse-profile` measured about 47–49 ms for asset validation and 75–78 ms for
automatic normals on the fixed grid. Those component times locate repeated
work. They are not acceptance samples.

## Fixed performance gate

The original benchmark driver and input scene are byte-identical to the failed
baseline. No sample, input, limit or operation was removed. The previous nine
failed samples remain in `frame-performance`.

Actual Rust 1.85 release ran on the Apple M1 Max with macOS 26.5.2. The grid has
10,201 vertices, 20,200 edges and 10,000 quad faces. All vertices are selected.
The object frame is identity. Global direction, median pivot, the three basic
operation values and three repetitions follow the frozen contract. There is
no proportional influence, snapping or UV correction.

All nine samples passed. Core operation times were 224.219541–242.850041 ms,
below the unchanged 250 ms limit. Operation/save/fresh-reload times were
394.605333–435.172292 ms, below the unchanged 2,000 ms limit. Core timing includes
the validated atomic editor operation and actual receipt. Pipeline timing
includes the operation, save, fresh complete load and equality check. Input
preparation stays outside the timers.

The standalone driver links this candidate's actual release library with no
preview feature. Exact executable and library hashes, compiler commands, raw
monotonic timestamps, host identity, full scenes and receipts are retained.
The timing pass alone does not accept the operation or issue.

## Independent large-grid source comparison

Two independent frozen Blender processes captured the same three grid
operations. Process IDs were 3011 and 57484. Both use Blender 5.2.3 LTS, build
`e13b728c6880`, with the same fixed executable hash. Each had an initialized
viewport and the existing reference adapter. The input grid is the exact
authored benchmark input. It is not derived from a transformed output.

Complete source geometry, normals, world positions and selection results agree
between the two processes. The comparison checks every saved grid output from
all nine release samples. It checks stable vertex, edge and face identities,
positions, face normals and every corner normal. Each sample compares 180,603
numeric components. The position and normal errors are exactly zero. The fixed
1e-6 limit remains unchanged. Raw source states, capture drivers, comparison
driver and all hashes are retained. No measured value enters the Rust operation.

## Complete regressions and failure checks

Actual Rust 1.85 passed 216 tests. Python passed 80 tests. Formatting and Clippy
passed. New fault tests check invalid group names and weights, seam and smooth
IDs, slots, diagnostics, selection modes, unknown components, hidden/selected
overlap, duplicate history, active faces, UV layout, missing borders, invalid
vertices and invalid normal/UV payloads. Both transform setup and normal queries
return the original validation errors. Failed transforms preserve the supplied
scene. Successive edits derive normals from current positions and undo fully.

The complete 1,203-case transform suite ran through CLI and official MCP.
All 2,406 raw result files are byte-identical to the previous candidate. This
includes all receipts, native world queries, geometry, attributes, selection,
errors and preserved stochastic checks. There are 2,392 matches and fourteen
remaining failures. No input, source expectation, request, limit or comparer
changed. The known seven undefined all-axis rotation cases remain failing
through both interfaces. The fixed RANDOM support policy does not claim exact
sequence or distribution parity.

All final-candidate legacy suites passed: 162 generation, eight scale, 1,060
selection, 262 creation-context and 57 payload checks. General official MCP
regression and 42 normal queries passed. Six Euler parent/child world-frame
queries still match the frozen source exactly. SDK is 2.3.0. Protocol is
2025-11-25. All 3,785 source pins remain unchanged.

The copied binary passed the unseen mirror/UV/world-query test with all
repository reads denied. Shared ownership, hidden and coincident IDs, stale
requests, failed batches, undo, replay and fresh reload are checked. Actual
Metal rendering passed with 15 changed vertices and 14,302 changed pixels.
Fresh reload produces identical image bytes.

## Evidence and remaining work

`docs/evidence/mesh-transform-core/reuse-implementation-manifest.json` binds the
candidate, executable, source inputs and raw artifacts. The capture checker
verifies raw-result identity, all regression reports, native probes, both source
processes and all nine performance outputs. Evidence bytes are also checked
against the Git index and stored blobs before the evidence commit.

The required transform gate still fails on fourteen source comparisons.
Three-platform CI, dependency integration and independent acceptance remain
unrun. The full modelling and other milestone feature domains remain required.
Baseline metadata is structurally valid. Strict acceptance still returns exit
2 with 9,003 pending source entries and 31 pending features.

Earlier CI attempts were refused before execution due to GitHub account billing
limits. A head-specific CI record must confirm the latest state. Issue #48
stays open with `agy:doing`. PR #49 stays a draft. All milestones remain open.
Continue investigating the remaining source rotation behavior and the other
required feature domains. A failed or unrun gate cannot pass.
