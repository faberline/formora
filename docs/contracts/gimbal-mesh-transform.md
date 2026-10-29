# Stored rotation state and gimbal mesh transforms

This extends issue #48. Keep all 1,203 source cases per interface, all fixed
1e-6 limits, performance, final regression, integration and independent gates.
Focused checks cannot accept this issue, any feature or a milestone.

Store the actual rotation representation as the single scene authority.
`Transform.rotation` accepts the existing x/y/z/w unit-quaternion array, or a
tagged object. An Euler object has `kind: euler`, `angles: [x,y,z]` in radians
and `order: xyz|xzy|yxz|yzx|zxy|zyx` (default xyz). An axis-angle object has
`kind: axis_angle`, `axis: [x,y,z]` and `radians`. Retain the chosen representation,
full angles and order through queries, editing, undo and saved scene reload.
Reject nonfinite values and invalid quaternion length. Axis-angle requires a
nonzero axis. Unknown or mixed object fields and unknown orders must fail.
Legacy version-one scenes keep their quaternion-array representation.

Resolve physical orientation through one shared native quaternion conversion.
Preview, mesh authoring frames and door consistency checks must consume it.
Door animation explicitly replaces authored rotation with its actual interpolated
quaternion. It must not leave stale Euler or axis-angle state behind. Preserve
all existing door, picking, playback and save behavior.

The source adapter supplies actual authored Euler angles, quantized to the
source's stored float values. It may not copy a measured basis or recover Euler
angles from a quaternion. Its world-position observer must consume the actual
queried native representation with the same physical quaternion conversion.

Use `eulO_to_mat3` and `eulO_to_gimbal_axis` from frozen Blender commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`. Preserve all six rotation orders and
float32 output steps. The first gimbal axis is the first local rotation axis.
The second excludes the first angle. The last is its global coordinate axis.
Axis-angle follows `axis_angle_to_gimbal_axis`, including its authored axis.
If a parent exists, normalize its world columns separately and multiply the
local gimbal matrix. Do not orthogonalize this result or substitute local axes.
Quaternion mode follows the pinned PARENT fallback. Do not invent Euler state.

Use these actual axes in translation, rotation and resize. Keep constraints,
pivots, proportional influence, shared identity and success-only receipts.
Reject unsafe frames and nonfinite intermediate arithmetic before publishing
geometry, disk, receipts or undo. Safe singular transforms and full numeric
domains remain required in the complete roadmap and issue's remaining gates.

Independent tests must cover six distinct orders, equivalent physical poses
with different authored modes, stored full turns, parent/reflected scale,
quaternion fallback, axis-angle, scene validation, rollback, doors, preview,
undo and save/reload. Run all GIMBAL source cases through CLI and official MCP,
then rerun the complete unchanged suite. Preserve all failures and prior matches.
