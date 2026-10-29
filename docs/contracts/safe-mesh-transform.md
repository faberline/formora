# Explicit source centres and singular object frames

This extends issue #48. Keep the unchanged 2,406-case gate, 1e-6 limits,
performance, integration and independent acceptance requirements.

Source `t_around_get` changes an explicitly overridden centre to BOUNDS mode
before orientation and individual-island setup. The source adapter must map
this to native `pivot: bounds` and the authored `center_override` point for
every requested source pivot. Do not change the native API's documented option
to retain individual centres when a native caller explicitly requests them.
Do not alter input geometry, measured outputs or fixed expected results.

Use the pinned `pseudoinverse_m3_m3` operation for the object's linear inverse.
Try the source's regular float32 adjugate/determinant order first. Only an exact
zero determinant selects its 4-by-4 SVD fallback. Embed the 3-by-3 matrix with
homogeneous unit entry. Use the pinned TNT-derived bidiagonal SVD and absolute
singular-value cutoff `1e-8`. A small nonzero determinant must not be truncated.
Keep the 200-step bound. Reject nonconvergence and nonfinite arithmetic before
publishing a scene change. A partially converged inverse cannot pass.

The local pivot and linear inverse have different source paths. For singular
object frames, derive the pivot with `invert_m4_m4_fallback`'s actual partial
Gauss elimination result, including its row order and double intermediate
steps. Do not replace this pivot matrix with the linear pseudo-inverse. Retain
the existing nonsingular native pivot behavior in this change.

Local orientation fills missing normalized axes with the source's cross or
projection rules and identity fallback. Individual normal orientation uses the
object's normalized columns without inventing nonzero axes. Geometric normal
orientation uses `invert_m3_m3`'s adjugate result on singular matrices, rather
than the operation's pseudo-inverse. Explicit singular custom working matrices
and unsafe Gimbal frames keep their existing rejection policy.

Independent tests must cover rank zero, one and two matrices, non-axis-aligned
rank loss, full-rank tiny scales, the distinct affine pivot path, missing local
axes, nonfinite arithmetic, convergence limits, actual zero-scale transforms,
shared ownership, attributes, hidden/selection state, undo and failed saves.
Run the centre-override and singular source cases through CLI and official MCP.
Then run all 2,406 cases. All remaining failures stay visible.

## Unresolved all-axis rotation source behavior

`constraints_rotation_impl` has no assignment for three true constraint flags.
Its caller declares `float3 axis_final` without a value. The pinned VecBase
default constructor supplies no initialization. The exposed release build flags
do not establish a zero-initialization guarantee. Existing source captures show
a cosine deformation for seven such requests, but that does not prove a
source-defined zero-axis rule. Keep these seven source cases and their failing
status. Do not change the frozen native three-axis rule or map them to a scale
operation merely to pass this finite sample. Further source/runtime evidence
and a faithful native operation mapping remain required.
