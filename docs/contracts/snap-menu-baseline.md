# Direct snapping baseline

Freeze the complete relevant source and authored inputs before reference
capture. Use Blender 5.2.3 LTS build `e13b728c6880`, source commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`, and manual commit
`4a3be8f9ed3b66b24913e0a0d491d3429a70ea08`.
Keep all existing inventory IDs, source pins and evidence unchanged.

## Required source family

Capture all seven direct operators: selected to grid, cursor and active;
cursor to grid, selected, active and world origin. Retain every RNA property,
default, array length, range and enum value. Selected-to-cursor includes all
four offset/rotation combinations. It must not be represented by a single
translation demonstration.

The authored suite has 1,672 cases. It covers mesh vertex/edge/face/combined
selection, empty and hidden selection, all five pivots, identity, rotated,
reflected, parented and singular frames, exact and adjacent half-grid values,
duplicate positions with separate IDs, three grid spacings, metric/imperial
unit scales, active and missing history, unselected active faces, object mode,
multi-object editing, linked data, selected/unselected children, transform
locks, skip-child and origin-only settings. Every input is authored without
reading a reference answer. A setup failure cannot be silently skipped.

Continuous transform snapping, target search/projection, pose/curve/other
data modes, tracking bundles, full parameter domains and capacity remain
required roadmap work. This finite baseline does not accept those functions
or a complete direct-snapping feature. The GUI-only exclusion cannot exclude
a snapping outcome. Seven pending catalog entries are not seven completed
features.

## Fixed capture and comparison

Run every case in two independent native Blender viewport processes.
Use different process IDs and the same fixed executable hash. Refuse existing
output directories. Keep captures atomic and verify input hashes before and
after capture. Preserve failures and cancellations as distinct outcomes.
Retain the complete actual operator request and raw error. A failed setup or
non-finite result is a failed capture, not an accepted empty outcome.

Query complete local/world geometry, directed faces, edge identities, face
and corner normals, smooth flags, materials, all UV layers/order/active layer,
groups/weights, selection/hidden state, history, active face, mesh sharing,
object frames and parents, locks, selected/active objects, cursor location
and rotation, pivot, view and unit/grid settings. Snap-to-origin must include
its actual rotation behavior. Changes to object origins must preserve the
source's actual data and world-space consequences.
Object frames include parent inverse, local/basis matrices and delta transforms.
Retain raw source scene units and explicit physical-metre positions. The
physical factor is one for unit system NONE and `unit_scale_length` otherwise.
No measured snap result may determine that input conversion or grid size.

Independently bind each initial mesh, selection, object/parent frame and
setting to the authored input. Compare every deterministic result across
both processes. Match IDs, oriented topology and discrete state exactly.
Local/world positions use a maximum absolute error of 1e-6 metres per
component. Normals, UVs, rotations and matrices use 1e-6 per component.
Reject non-finite values, missing fields and changed inputs or pins.

Add analytic checks for identity-frame grid rounding and cursor-to-origin.
Include negative tests that corrupt a vertex, UV, normal, cursor, frame,
selection, sharing identity, status, parameter or provenance hash. Each must
be rejected. Do not adjust a criterion after seeing an implementation result.
Source defects need evidence and explicit handling; they are not numerical
passes. The existing all-axis rotation policy applies only to its exact
documented input boundary.

## Later Rust product gates

CLI and official MCP must use one Rust operation core. Agent requests must
locate actual entities/assets and return real changed identities, effective
grid/pivot/target, cursor/object changes and sharing consequences. No reference
answer may be passed as an input. Saved projects, undo, replay, revisions,
recipes and unrelated attributes must remain correct. Invalid/stale requests,
exceeded budgets, failed batches and failed saves must be atomic. Keep the
valid no-change and cancellation outcomes explicit.

Retain all existing Rust/Python, source comparison, seeded RNG, MCP,
repository-denied, native Metal and fixed transform performance gates.
Use actual Rust 1.85 child paths. For each of the ten direct-operation/flag
forms, run three release samples on the existing M1 Max with a 100×100 quad
grid, all vertices selected, identity frame, median pivot, active last vertex,
grid spacing 0.75 and cursor `(0.375,-0.625,0.875)`. Preserve all 10,201
vertices, 20,200 edges, 10,000 faces and stable IDs. Core <=250 ms;
operation/save/fresh-reload <=2,000 ms. Prepare input outside the timers.
Retain all samples and compare their actual outputs to the frozen source.

Required three-platform CI, dependency integration and independent acceptance
remain necessary. Failed, skipped and unrun checks cannot pass. Catalog review
stays pending and `complete_products` stays empty. No milestone closes until
its complete original scope and evidence pass.
