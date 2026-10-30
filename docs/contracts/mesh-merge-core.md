# Persistent Rust vertex merge

Issue #72. Continue the complete 0.0–1.0 goal. Depend on draft PR #71 at
74a4fc5b852be620e3a1fd9329aa6e73a01e52e1 and its unintegrated stack.
Freeze this contract and actual performance inputs before product changes.
The local source baseline passes all 1,024 cases in native processes 50701
and 52091. This does not accept a feature, milestone, CI or integration.
Do not adopt the pending zero-scale policy from issue #68.

## Operation and data

Add the typed scene command `merge_mesh` with a `merge` request containing
`entity`, `method`, `uvs` (default false) and the existing default component
budget. Methods are center, cursor, collapse, first and last. The existing
CLI and official MCP use this one core. The request reads the actual entity,
physical frame and persistent asset selection/history. It cannot take a
source answer, output topology or reference path as an operation parameter.

Operate on the entity's real shared mesh once. All users see the same asset.
Preserve object transforms, cursor, other assets and unrelated scene data.
Keep current f32 source arithmetic for these operations while preserving raw
unaffected f64 fields. Validate results before publication. No blanket
singular-transform rejection or new source-defect policy is authorized here.
Use existing source-derived inverse behavior and keep overflow errors atomic.

Implement the pinned BMesh rules, including nonadjacent repeated face corner
splits, degenerate face/edge removal, duplicate edges/faces, survivor mappings,
oriented loops and selection-history remapping. Keep loose geometry and
hidden components. Support existing triangle and polygon asset forms.
Preserve UV layer order/active layer, loop UVs, group names/weights including
explicit zeros, materials, seam/smooth flags and applicable normal data.
Do not retain a stale normal cache after geometry changes.

CENTER uses the selected vertex mean. CURSOR uses the actual cursor in the
owner's frame. FIRST/LAST use the selected vertex history endpoint. COLLAPSE
uses each selected connected edge component and counts both endpoints of
every edge in its mean. Isolated vertices outside selected edges remain.
Apply source UV behavior separately: center/cursor bounding-box face data,
first/last target face data, and collapse UV-connected components.

Store real signed i32 attributes needed by the source cases. Add an optional
`integer_attributes` mesh record with `vertices`, `edges`, `polygons` and
`triangles` layer maps. Each named layer maps actual component IDs to i32 values.
Reject duplicate keys, empty layer names, unknown component IDs and incomplete
layer coverage. Preserve inherited/interpolated values independently from
component identity. Source capture tag layers are real integer attribute data;
duplicate values must not merge otherwise distinct components.
Missing integer data defaults to None and stays omitted in old saved JSON.
Primitive insertion must give new components explicit zero defaults in
existing integer layers. Recipe regeneration creates fresh recipe data.
Other attribute kinds remain required full-product work; do not silently
replace existing UV, normal or group fields with the new integer container.

Return a typed merge receipt, including command index, owner/asset/shared
users, method/UV setting, explicit status/reason, before/after counts, actual
removed/created/changed components and real source-to-survivor mappings.
Map history and active faces to surviving components. Receipts must describe
the saved result. No fabricated fixture-derived receipt is permitted.
Add merge receipts to edit results only when nonempty, preserving old empty
result serialization. Mark the primitive recipe edited when data changes.
Distinguish changed, unchanged and unavailable-history outcomes.
Empty FIRST/LAST source enum rejection is an explicit atomic product error,
with no success receipt. Do not turn it into a numeric geometry pass.

## Complete local product checks

Run all 1,024 authored cases through real CLI and official MCP (2,048 merge
requests). Build setup only from authored inputs and existing source-derived
selection rules. Never read captured answers during setup or execution.
Read actual saved topology/attributes, physical query frames and actual
receipts. Normalize snapshot identity using persistent data and receipt
lineage, while comparing real stored integer values separately.
Compare to both native captures with exact discrete behavior and unchanged
1e-6 continuous limits. Keep all 920 changed-geometry, 88 unchanged-geometry
and 16 source enum rejection cases. No removed or skipped required case.

Verify fresh-process reload, real shared users, selection/history, both UV
layers, zero weights, actual automatic normals and complete attribute coverage.
Require no-op/error behavior, stale IDs/revisions, late batch failure,
unknown parameters, finite-range/overflow/budget failures and failed saves
to preserve disk, memory, revision and undo state. Success must support actual
undo/replay and recipe regeneration. Preserve original failed checks and logs.

Add unseen analytic inputs under native source-read denial, including a
negative integer attribute, a duplicate integer value on distinct vertices,
noncommuting frames, connected/disconnected components, explicit normals,
both existing face storage forms and a real shared asset. Do not substitute
stored fixtures for the native core. Require a native Metal before/after
topology proof with fresh reload and byte-identical saved/reloaded rendering.

Retain all previous required Rust, Python, source and actual CLI/MCP suites.
This includes the complete 14,326 preceding interface cases, existing asset
checks, RNG behavior, approved 14 undefined mesh-axis rejections, source-denied
proofs, recipes, failed-save behavior and native previews. The prior source
fixtures and acceptance criteria remain unchanged. Add corruption controls
for topology, UVs, integer values, history, source leakage, identity, receipts,
reload, missing cases and failed/missing terminal outcomes.

## Before-code performance

Freeze independently authored workload JSON, native capture adapter, actual
source results and timing driver before implementing the merge core.
Use the original class-A 101-by-101 grid (10,201 vertices, 20,200 edges,
10,000 quads), its existing exact input hash and immutable topology.
Bind the unchanged base scene SHA-256
8f29def12ade5467214e888fdcacec23b3d78ed4954e470207a00479ac149536.
Author a separate merge scene from that base before code. Keep every vertex,
edge and oriented polygon; only add the declared attributes, shared user and
explicit operation context/frame. Record both scene hashes without claiming
the new attributed scene is byte-identical to the unchanged base file.
Select all vertices, keep last-vertex history active, use the identity frame,
both UV settings and all five methods. Preserve two real UV layers, signed
integer values, zero/nonzero group weights and a real shared user.

Run ten forms with three complete measured samples each: 30 new timings.
No discarded warmup or best-of selection. Record one fresh fixed native
source capture for every form, including complete geometry/attributes.
Keep preparation outside the clock. Each release-core clock includes its
complete required input/result validation. Each pipeline clock includes the
operation, real save and fresh load/validation. Do not move validation out
of a timer after a failure. Use actual Rust 1.85 on the recorded M1 Max host.
Each core sample must be at most 250 ms; each pipeline at most 2,000 ms.
Source comparison uses unchanged numeric/discrete limits. Retain every failed
timing and its host observations. Do not mix selected samples across trials.

Also retain all preceding required performance forms, input hashes, source
comparisons and limits: 90 scene, 24 raw rotation, 30 single-mesh, nine mesh
transform and 24 delta samples (177 retained samples). An earlier accepted
build does not pass this new implementation. Native captures, real exits,
raw timings and result hashes remain required. No CI/QA acceptance follows
from local timing success alone.

## Publication and acceptance

Freeze the tests and contract before implementation. Keep evidence bound to
the actual executable/library/source revisions. Publish a draft with exact
local checks, preserved failures and remaining gates. Three-platform CI,
dependency integration and independent Codex acceptance are required before
completion. Failed, missing, skipped and unrun checks cannot pass.
Catalog review stays pending and complete_products stays empty. Keep all
eleven milestones open. Full numeric/data/capacity domains, multiple independent
edit meshes and all other product functions remain in the original goal.
