# Object and multi-edit direct snapping core

Freeze this contract before product implementation. This 0.2 slice depends
on issue #56 / PR #57. It covers exactly the other 550 unchanged authored
snap-menu cases: 440 OBJECT and 110 multi-object EDIT_MESH cases, IDs
snap_1086 through snap_1635. Run each through real CLI and official MCP:
1,100 new requests. Retain the existing 2,244 single-edit requests. These
finite cases do not accept any complete catalog feature or milestone.

## Persistent product state

Add typed persistent scene interaction state for object selection, active
object, edit objects, object iteration order, location/rotation locks,
parent-inverse matrices, skip-children and origins-only settings. These are
actual authored inputs. Query, save, reload, undo, rendering and play must
use the same state. Old scenes without it retain current behavior. Reject
unknown fields, duplicate IDs, missing entities, inconsistent edit/shared
asset membership, invalid affine matrices and non-finite values. Preserve
unrelated authored f64 values exactly when an operation does not write them.

Add a typed scene snap command that shares the existing seven action types
and persistent authoring cursor. Read topology, edit selection/history and
shared asset identity from actual scene data. Do not accept reference output
as preparation or operation input. Physical coordinates are metres, right
handed, Z-up. Keep the frozen f32 operation order and rounding rules.

Follow the fixed native source for all 550 cases. In object mode, apply
location and rotation locks, selected-parent offset suppression, active
unselected objects, empty selections, parent-relative target conversion,
rotation assignment and Euler conversion. In multi-edit mode, process each
unique mesh once using the actual source representative order. Compute the
common selected centre across edit objects. The source ignores cursor
rotation in edit mode. Origins-only must transform the actual shared mesh.
Skip-children must update actual parent-inverse state. Do not detach meshes
or substitute matrix overrides for authored transform channels.

The current reference rotation cases use XYZ Euler angles. Other authored
rotation domains remain required future coverage. If an unsupported domain
cannot be evaluated faithfully, reject it atomically and report it as
unsupported; do not silently convert it or mark it accepted.

## Results and failure behavior

Return a typed scene-snap receipt with the real command index, action,
status, cursor before/after, transformed objects, parent-inverse changes,
unique mesh edits and all shared users. Bind changed IDs to actual before
and after state. Missing active data for selected-to-active is an atomic
error. Source cancellations are explicit unchanged/cancelled results.
No receipt can convert a cancellation or rejection into a numeric pass.

Preserve topology, UVs, group weights, material/active slots, smooth/seam
flags, selection/history, hidden elements, sharing and unrelated objects.
Update automatic normals and primitive recipe edit flags for actual mesh
changes. All query/render paths use the same parent-inverse world frames.
Successful operations must survive fresh-process reload, undo and replay.
Stale revision, invalid input, missing data, budget exhaustion, failed save
and later failed commands leave scene, disk, revision, undo and receipts
unchanged. Apply component budgets across all unique affected mesh assets,
with checked arithmetic; include object traversal in a bounded object budget.

## Fixed validation gates

For all 1,100 requests bind initial state only to authored inputs, then
compare complete actual local/world geometry, resolved face/corner normals,
attributes, selection, object modes/selection/locks, authored channels,
basis/local/world/parent-inverse matrices and cursor against BOTH unchanged
native source captures. Retain the 1e-6 physical position and normal/UV/
rotation/matrix limits. Discrete data and sharing stay exact. Reject all
non-finite comparison values. Keep failures and raw results. Required tests
that fail, skip or do not run cannot pass. Do not change source fixture,
source captures or limits to fit the implementation.

Add focused Rust transaction tests and Python negative controls for wrong
iteration order, double shared edits, false locks/receipts, parent-inverse
omission, hidden output injection and source-input leakage. Verify actual
CLI and official MCP, save/reload, undo/replay, rollback and save failures.
Use a native repository-read-denied proof on unseen authored inputs. Show
real saved geometry in native Metal and retain identical fresh reload output.

Before implementation, fix these release performance cases on the same
M1 Max and timing method as mesh-snap-core. Every class uses all ten action/
flag forms, three samples each (90 new samples). Prepare inputs outside the
timer. Use the original 100x100 quad grid (10,201 vertices, 20,200 edges,
10,000 faces), all selected, last active vertex, median pivot, grid 0.75 m
and cursor (0.375,-0.625,0.875) m. Class A: one grid mesh object plus an
unselected empty child, origins-only and skip-children enabled, translated
object (0.25,-0.5,0.75), child location (1,2,3), XYZ zero rotation/unit scale.
Class B: two edit objects at translations (0,0,0) and (2,0,0) sharing one
grid asset, active first object. Class C: the same two edit objects with two
independent full grid assets. A/B core <=250 ms and operation/save/fresh
reload <=2,000 ms. C doubles the unique grid work: core <=500 ms and full
pipeline <=4,000 ms. Compare every saved output and frame to fresh native
source results. Keep all samples. No threshold reduction after measurement.

Retain all existing Rust/Python, 2,406 transform requests, 2,244 single snap
requests, source baselines, RNG/one-shot/isolation, primitive/selection/
creation/payload/normals, MCP, recipe, Euler frame, native Metal and fixed
30 snap plus nine transform performance gates. Use actual Rust 1.85 tools.
Required three-platform CI, integration and independent Codex acceptance
remain gates. Keep catalog review pending and complete_products empty.
All milestones remain open until their full original gates pass. Other data
modes, continuous target snapping, full parameter domains and capacity
remain required work under the same unlimited goal.
