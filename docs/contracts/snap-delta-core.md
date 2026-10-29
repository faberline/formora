# Persistent delta transforms and direct-snap Rust core

Freeze this contract and added performance inputs before product edits.
Depend on issue #64 / draft PR #65 at
393cebdf58d589f5de093a088f74b3018ea6196f and issue #62 / draft PR #63.
Implement all unchanged 1,792 delta-source cases through actual CLI and
official MCP: 3,584 new product requests. Continue the unlimited 0.0–1.0 goal.
This bounded slice does not accept complete delta, snapping or catalog parity.

## Saved and physical state

Add typed saved delta translation, Euler rotation, W/X/Y/Z quaternion and
scale channels to the actual object transform. Follow the normal object's
rotation mode and Euler order. Do not add a second conflicting active mode.
Preserve raw active and inactive values, nonunit quaternion magnitude/sign and
unrelated f64 data. Validate dimensions, ownership, finite fields, unknown
fields and supported finite physical arithmetic before publication.
Default/omitted delta state is identity and preserves old serialized behavior.
Legacy unit-quaternion validation remains unchanged.

Use the source order: delta rotation times normal rotation, componentwise
delta times normal scale, normal plus delta location, then actual parent /
parent-inverse world composition. Normalize a physical quaternion copy only.
The source AXIS_ANGLE public path has no active delta axis-angle property;
exposed inactive Euler/quaternion fields must not change its physical pose.
Do not claim native/internal-data compatibility beyond these fixed cases.

All physical queries, mesh frames, preview, play, creation context, snapping
and transforms must use the same complete saved transform core. Do not bake
an evaluated matrix into authored state or normalize saved raw channels.
Both authored f32 and legacy f64 precision remain explicit. Preserve existing
zero/negative scale behavior and error boundaries. Do not globally reject
previous valid scenes to hide an unsupported inverse domain.

## Transactions and direct snaps

Both interfaces use the same Rust implementation and typed real receipts.
All seven existing direct operators must use the actual delta-composed frames.
Respect the source's protected normal-channel setter: a direct snap may leave
delta channels intact even when its resulting physical orientation differs
from the cursor. Do not subtract a delta rotation merely to force that pose.
Location changes use actual evaluated world position and source parent space.
All independent location and W/X/Y/Z locks preserve their actual channels.

Keep delta channels unchanged through direct snaps. Bind normal/delta/frame
query results and changed IDs to actual saved entities/assets. Preserve real
shared data, selection/edit owners, topology, UV order/coordinates, materials,
smooth/seam flags, normals, groups and cursor. Origins-only and skip-children
must compensate actual geometry/parent inverses as the source does.
Report actual object/asset/cursor before and after state and real changes.
Keep old receipt compatibility; do not claim unmodified data changed.

Require complete scene validation and existing object/unique-asset budgets
before revision, receipt, undo or disk publication. Stale revision, late failed
commands, unknown IDs/fields, invalid membership, nonfinite/range input,
budget failure and failed save leave all state unchanged. Successful results
survive fresh-process reload, undo and replay. Preserve recipe regeneration
and actual geometry-edit versus cursor-only recipe behavior.

## Fixed product checks

Run all 3,584 new requests from authored inputs only. Compare every real
before/after stored delta/normal channel, mode/lock, basis/local/world/parent
inverse matrix, local/world vertex, normal, attribute, cursor and actual receipt
against BOTH unchanged native captures. Discrete fields remain exact;
continuous positions in metres, channels, matrices, normals and UV use maximum
absolute error 1e-6 per component. Reject nonfinite results. Keep cancellation
and expected atomic rejection separate from numerical matches. Each request
must have a real fresh-process reload check. Preserve all raw failures.

Add analytic identity, noncommuting quarter-turn, mirrored delta scale and
raw signed/nonunit quaternion controls. Negative controls must reject omitted
translation, reversed delta multiplication, duplicated scale, silent raw
normalization/sign folding, changed inactive data, false locks/receipts,
double shared edits, stale world/cursor frames and source-output input leaks.
Require unseen source-read-denied native operations, real rollback, failed save,
undo/replay, recipe regeneration and actual native Metal geometry/pixel changes
with byte-identical fresh-reload PNGs. Do not use a browser as native proof.

Before code, freeze 24 added release samples on the same M1 Max. Reuse the
exact existing class-A 100x100 quad grid: 10,201 vertices, 20,200 edges,
10,000 faces; all selected, last vertex active, median pivot, 0.75 m grid.
One mesh target plus unselected empty child; origins-only and skip-children
true; target location (0.25,-0.5,0.75), child (1,2,3), unit normal scales,
no parent. Cursor location is (0.375,-0.625,0.875) m. Selected-to-cursor has
offset false and rotation true. Use all eight paired object/cursor modes and
regular raw channels from generate_snap_rotation_cases.channels. Target delta
uses generate_snap_delta_cases.delta('combined'); child delta uses its fixed
authored child role. Lock X true/Y/Z/W false and target four-dimensional flag
true. Child rotation XYZ zero, all locks and four-dimensional flag explicitly
false. Run three samples per mode. Freeze the exact grid/mode/delta bytes and
native adapter before capture or implementation. Compare all saved initial
and final geometry, channels, attributes and frames to fresh fixed-source
grid results. Native source input binding must pass before accepting samples.

Keep the original one-process timing method: prepare outside timers, complete
validation inside Editor.apply and save/reload pipeline, output outside the
watched checkout on the same filesystem. Core <=250 ms and complete operation /
save / fresh reload <=2,000 ms. No dropped warmups, selected samples, workload
or limit changes after measurement. Preserve every trial and raw saved scene.
Lossless gzip after timing may archive exact scene bytes; retain raw/stored
hashes and reconstruct exact bytes before any fresh reload or comparison.

Retain all previous 10,742 CLI/MCP snap/transform requests, all Rust/Python,
asset/selection/creation/payload/normal, RNG/one-shot/MCP, native isolation,
recipe, Euler and Metal checks, and all fixed 153 release samples. Use actual
Rust 1.85. Three-platform CI, dependency integration and independent Codex
acceptance remain required. Failed, skipped and unrun required checks cannot
pass. Keep catalog review pending, complete_products empty and milestones
open. Singular domains, continuous snapping, other data modes, full parameter
ranges and capacity remain in the unchanged goal. The approved undefined
mesh-axis rejection does not authorize rejecting valid object delta modes.
