# Single edit-mesh direct snapping core

This 0.2 issue depends on issue #54 / PR #55. Freeze this contract before
Rust implementation. It covers the 1,122 authored cases whose mode is
EDIT_MESH and whose multi_object flag is false in the unchanged snap suite.
Every selected case must run through both the command line and official MCP.
The other 550 object/multi-edit cases remain required work and must be
reported as unrun. This bounded core does not accept any whole feature.

## Agent operation

Add one typed `snap_mesh` command to the existing transactional command
core. The request identifies an actual entity with a shared mesh asset and
persistent edit selection. Seven actions correspond to the fixed direct
source operators. Grid actions take a finite positive physical spacing in
metres. Selected-to-cursor carries both offset and rotation flags. Its edit
mesh behavior must follow the source, which ignores the rotation flag.
All five pivots remain explicit. Reject unknown request fields.

Read the cursor from the persistent authoring context. Query actual topology,
selection, hidden flags, history and active face. Do not accept a supplied
answer, supplied active-element position or reference geometry as a result.
Only authored mesh/pose/selection/environment data may prepare a test scene.
Coordinates remain right-handed, Z-up, physical metres. Source-unit conversion
in test setup must derive only from authored units, never measured output.

Preserve vertex/edge/face identities and winding, duplicate-position vertices,
all UV layers/order/active layer, materials/active slot, groups/weights,
seams/smooth flags, hidden and selected elements, history, active face,
entity/parent frames, unrelated objects, and shared asset identity.
Update automatic normals after geometry changes. Mark edited primitive
recipes only for actual geometry edits. Shared users must see one actual
asset. Avoid detaching a copy to conceal a sharing consequence.

Retain the fixed source float expression and its operation order for grid
rounding, object-space conversion, centres and singular 3x3 inversion.
The source singular 3x3 routine retains the adjugate when its determinant
is zero. This differs from both the safe transform inverse and the singular
4x4 zero inverse. Do not substitute either implementation.
Active mesh centres follow actual BMesh history and selected active-face
rules. Cursor-to-selected uses bounds only for the bounds pivot and the
median otherwise. Selected-to-cursor uses the source's active fallback rule.
Cursor-to-origin clears cursor location and rotation.

## Outcomes and atomicity

Return a real typed receipt through the common command and MCP result.
It includes command index, entity, asset, all shared users, actual changed
identities, effective world grid/pivot/target, cursor change and explicit
finished or cancelled status. Do not manufacture success for missing active
elements. Preserve the fixed source distinction: selected-to-active rejects
missing active data; cursor-to-active and cursor-to-selected can return an
explicit unchanged/cancelled result. A cancellation is not a numeric success.

Reject invalid entity/asset/edit state, non-finite or non-positive spacing,
out-of-range finite casts, unknown fields, exhausted component budgets,
stale revisions, malformed batches and failed saves atomically. They must
leave scene, revision, undo, disk and receipts unchanged. A later invalid
command must roll back an earlier snap in the same batch. Successful edits
must survive save/fresh reload, undo and replay. Old saved scenes must load.
Keep the existing all-axis rotation rejection and seeded RNG behavior.

## Fixed evidence gates

Run all 1,122 covered cases through each interface: 2,244 real requests.
Bind setup independently to authored data. Compare full actual local/world
geometry, resolved face/corner normals, attributes, selection, frames and
cursor against each frozen source process. Use the original 1e-6 physical
metre position limit and 1e-6 normal/UV/rotation/matrix component limits.
IDs and discrete fields stay exact. Retain every failure and raw result.
Reject non-finite values. No required failed, skipped or unrun test can pass.

Add focused Rust transaction tests and meaningful Python negative controls
for incorrect rounding, active centres, mutation, false receipts and source
input leakage. Verify actual CLI and official MCP, save/reload, undo/replay,
rollback, stale/budget/save failures, shared users and unrelated attributes.
Run a native repository-read-denied operation so runtime data cannot come
from the source repository. Show actual saved geometry with native Metal,
then fresh-reload the same scene and retain matching proof.

Retain all previous Rust/Python, original source comparisons, all 2,406
transform requests, seeded RNG, primitive/selection/creation/payload/normal,
MCP, source-isolation, Metal and fixed transform performance checks.
Use the actual Rust 1.85 child tool paths, not just a version label.

For all ten operation/flag forms, retain three release samples on the fixed
M1 Max. Use the original 100x100 quad grid: 10,201 vertices, 20,200 edges,
10,000 faces, all selected, identity frame, median pivot, active last vertex,
world grid 0.75 m, cursor (0.375,-0.625,0.875) m. Prepare inputs outside the
timers. Core <=250 ms; operation/save/fresh reload <=2,000 ms. Compare every
actual output to the fixed source. Keep all samples. Do not lower limits.

Required three-platform CI, dependency integration and independent Codex
acceptance remain gates. Keep catalog review pending and complete_products
empty. No milestone closes from this bounded work. Track the other 550 cases,
other data modes, continuous target snapping, full domains and capacity as
remaining required work under the original milestones.
