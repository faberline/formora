# Stored rotation channels and direct-snap Rust core

Freeze this contract before product implementation. This bounded 0.2 slice
depends on issue #60 / PR #61 at c425d470c78825412f182d39ae658f7c323c118c,
and issue #58 / PR #59. It implements the unchanged 2,496 rotation-source
cases through real CLI and official MCP: 4,992 new requests. It does not
accept a complete rotation, snapping, catalog feature or milestone.

## Persistent representations

Support the eight fixed modes XYZ, XZY, YXZ, YZX, ZXY, ZYX, QUATERNION and
AXIS_ANGLE for authored object and cursor rotation. Preserve the actual
stored Euler, quaternion and axis-angle channels, including inactive ones.
Store mode and channels as typed scene data, with an explicit quaternion
component order. Do not store output matrices as replacement authored data.
Queries and previews must resolve the same actual saved rotation state.

Keep existing legacy unit-quaternion arrays, authored Euler/axis-angle input,
old authoring cursor arrays and their validation/serialized behavior. Add an
explicit typed representation for source raw channels. Partly locked source
quaternions or axes may be nonunit. Keep those stored values unchanged and
evaluate a physical normalized copy using the pinned source arithmetic.
This does not relax the existing legacy unit-quaternion validation.

Keep existing rotation_mode defaults. Avoid duplicate conflicting active
states. Validate mode, array dimensions, IDs, finite values, inactive channels
and ownership. An operation that needs f32 values must reject values outside
its supported finite source arithmetic atomically. Do not silently clip,
convert an unsupported representation or remove a required source case.
Keep unrelated untouched f64 values exact. Reject unknown fields.

Persist X/Y/Z rotation locks, the W/angle lock and the four-dimensional UI
flag. Follow the actual protected setter. The UI flag must not invent an
extra numerical restriction. Apply locks to raw source channels in their
correct order. The angle occupies the W/angle position for axis-angle.
Same-mode unparented assignments and parent-space conversions follow their
distinct actual source branches. Preserve quaternion sign and inactive data.

## Shared operations and results

CLI and official MCP must call the same Rust core. All seven direct snap
actions must use the physical cursor orientation and preserve source cursor
mode/channel behavior. Mesh editing still ignores cursor rotation where the
fixed source does. Cursor-to-origin clears the actual active physical
orientation according to its authored mode. A cursor-only operation must
preserve real objects, geometry, sharing and unrelated channels.

Return real typed receipts for actual object/cursor changes and raw channel
before/after state. Bind changed IDs to saved entities and shared assets.
Keep old receipt arrays/fields for legacy states and add explicit typed
orientation information when needed. A receipt must not claim a changed
channel, entity or asset that the transaction did not change.

Use the same source-order f32 rotation, normalization, matrix composition,
parent-inverse and evaluated dependency behavior in queries, snap operations,
rendering and play. Preserve topology, all UV layers/order, material and smooth/
seam data, group weights, selection/history, actual edit owners, shared users
and child compensation. Physical positions remain right-handed, Z-up metres.

Retain full scene validation before publishing a revision, receipt, undo
entry or disk state. Stale revision, unsupported/nonfinite input, invalid
membership, budgets, late failed commands and failed saves leave all of them
unchanged. Apply existing object and aggregate unique-asset component budgets.
Successful changes survive fresh-process reload, undo and replay. Preserve
recipe behavior for actual geometry edits and cursor-only operations.

## Fixed verification

Run all 4,992 new requests from authored inputs only. Compare every real
before/after raw channel, mode, lock, basis/local/world/parent-inverse matrix,
physical local/world vertex, normal, attribute, cursor, result and receipt
against BOTH unchanged native captures. Discrete values stay exact. Use the
original maximum absolute 1e-6 per-component position/channel/matrix/normal/UV
limits. Reject nonfinite values. Record cancellation/rejection separately from
a numerical pass. Keep raw evidence and all failed runs.

Add focused Rust transaction tests, analytic zero/quarter-turn and raw-sign
controls, and negative controls for wrong modes, W/X/Y/Z mapping, unintended
normalization, double shared edits, false locks/receipts, stale matrices and
reference-input leakage. Verify real CLI/MCP, source-read-denied unseen input,
fresh reload, undo/replay, rollback, failed save and recipe regeneration.
Show actual raw-channel geometry consequences in native Metal. Keep identical
fresh-process reload PNGs. Do not use a browser substitute for native proof.

Before code, freeze 24 added release samples on the same M1 Max: the existing
100x100 quad grid (10,201 vertices, 20,200 edges, 10,000 faces), all selected,
last vertex active, median pivot and 0.75 m grid. Use class A from scene-snap:
one mesh object plus unselected empty child, origins-only and skip-children
enabled, object translation (0.25,-0.5,0.75), child location (1,2,3), unit scale,
no parent. Run selected-to-cursor with offset false, rotation true. Use each
of the eight modes for both object and cursor, the regular raw channel values
from generate_snap_rotation_cases.channels, lock X true/Y/Z/W false and the
four-dimensional flag true. Cursor location is (0.375,-0.625,0.875) m. Run
three samples per mode, in the original single-native-process method, with
output outside the watched checkout on the same filesystem. Prepare inputs
outside timers. Core <=250 ms; operation/save/fresh reload <=2,000 ms. Keep
every sample and compare all saved geometry, attributes and frames to fresh
fixed-source grid results. Keep full validation inside the original timers.
No threshold or workload change after measurement.

Retain all 5,750 previous snap/transform CLI/MCP requests, all Rust/Python,
primitive/selection/creation/payload/normal suites, RNG and fresh-process RNG,
official MCP, native source/isolation/Metal/recipe/Euler checks, and all fixed
90+30+9 release samples. Use actual Rust 1.85 paths. Required three-platform
CI, dependency integration and independent Codex acceptance remain gates.
Failed, skipped and unrun required checks cannot pass. Keep catalog review
pending and complete_products empty. Every milestone stays open until its
complete original scope passes. Delta transforms, singular-parent domains,
other data modes, continuous snapping, full parameter domains and capacity
remain work under the same unlimited goal. The exact approved undefined
mesh-axis rejection policy is unchanged and cannot reject these valid modes.
