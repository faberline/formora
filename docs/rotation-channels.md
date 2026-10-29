# Raw rotation channels

Objects can store their rotation mode and all rotation channels. This includes
inactive channels. The active mode controls the physical pose.

Use `rotation.kind = "channels"` in an entity transform:

```json
{
  "translation": [0, 0, 0],
  "rotation": {
    "kind": "channels",
    "channels": {
      "mode": "quaternion",
      "euler": [0, 0, 0],
      "quaternion_wxyz": [0.8, -0.5, 0, 0.6],
      "axis_angle": [0, 0, 1, 0]
    }
  },
  "scale": [1, 1, 1],
  "precision": "f32"
}
```

Modes are `xyz`, `xzy`, `yxz`, `yzx`, `zxy`, `zyx`, `quaternion` and
`axis_angle`. Euler angles and axis-angle angles use radians. The quaternion
array is W/X/Y/Z. The axis-angle array is angle/X/Y/Z.

The example quaternion is not unit length. The stored channels stay raw.
Evaluation normalizes a copy. The old quaternion array format stays X/Y/Z/W
and still requires unit length. A legacy quaternion snap that produces nonunit
channels changes to the explicit channels format. Its receipt contains that
actual change. An unchanged inactive channel keeps its original value.

Set `lock_rotation` to the X/Y/Z mask in `object_context.states`. Use
`lock_rotation_w` for quaternion W or the axis-angle angle. The
`lock_rotations_4d` flag is saved too. The direct snap setter applies each
channel lock. It does not add another restriction from the UI flag.

A cursor can use `authoring_context.cursor_orientation` with the same channel
object. Keep `cursor_rotation` equal to its stored `euler` array. These are
the same Euler channels, even while another mode is active. Conflicting values
are rejected. Omitting `cursor_orientation` keeps the old XYZ cursor behavior.

The seven existing scene snap actions share this state through CLI and MCP.
`cursor_to_center` clears the active physical rotation. It preserves the mode
and inactive channels. Mesh edit snapping ignores cursor rotation where the
fixed source does. Object changes and cursor changes have actual before/after
receipts. A scene inspection includes `cursor_matrix` when the explicit cursor
orientation is present. This is the Rust evaluation, not a client estimate.

Unknown fields and nonfinite channels are rejected. Source arithmetic must
fit finite f32 values where the operation requires it. Invalid requests do
not publish partial changes. Full source/API, performance, native, three-platform
CI, integration and independent acceptance gates remain required. This work
does not accept a complete rotation or snapping feature.
