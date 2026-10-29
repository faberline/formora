# Delta transforms

An object can save a second set of transform channels in `transform.delta`.
The default is identity. Old scenes can omit it.

```json
{
  "translation": [0.125, -0.25, 0.375],
  "euler": [0.17, -0.11, 0.29],
  "quaternion_wxyz": [-1.0, 1.0, 1.0, -1.0],
  "scale": [1.2, 0.75, 1.1]
}
```

The normal object rotation mode selects the active delta rotation channels.
Euler uses `euler` in the same axis order as the normal rotation. Quaternion
uses `quaternion_wxyz` in W, X, Y, Z order. Axis-angle keeps both exposed delta
rotation arrays inactive, as the fixed source public interface does.

Saved quaternion channels can be nonunit. Evaluation normalizes a copy.
It preserves the saved sign and inactive channels. The old normal quaternion
array still requires unit length.

The physical frame applies delta rotation after normal rotation. It multiplies
normal and delta scale on each axis. It adds normal and delta translation.
Parent and parent-inverse frames then give the world frame.

CLI and MCP use the same saved transform and physical frame. Direct snaps
keep delta channels intact. Protected setters change normal channels only.
A source snap can therefore leave a physical orientation that differs from
the cursor. Object queries return the actual saved channels and world frame.

Use a complete typed delta object. Each array must have its stated length.
All channels must be finite, including inactive ones. Unknown fields fail.
Operations that need source f32 arithmetic reject values outside its finite
range before publishing a scene change.
