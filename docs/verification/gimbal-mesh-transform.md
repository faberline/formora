# Stored rotation and Gimbal transform progress

Issue #48 and draft PR #49 remain incomplete. No feature or milestone is accepted.
The Rust candidate is `95de73958d8382965e9cd07983ce7b85a88434c4`.
Its executable SHA-256 is
`ccbed86911e56b09881d65c30a54fe496b86c4348ead7aa6445fa267cd3c3b75`.

The contract and primary source were fixed before implementation in commit
`ec2a8c5`. See `docs/contracts/gimbal-mesh-transform.md`.
The added rotation source comes from frozen Blender commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`.

## Stored rotation

`Transform.rotation` now accepts the existing x/y/z/w quaternion array or a
tagged Euler or axis-angle object. The field itself stores the chosen mode.
There is no second cached rotation value. Euler mode preserves all three
angles and all six rotation orders. Axis-angle preserves its axis and angle.
Queries, save/reload and undo retain the authored mode and full turns.
Legacy version-one scenes still use the same quaternion arrays.

One native conversion resolves physical rotation for mesh frames, preview and
door validation. Door animation replaces the stored value with its actual
interpolated quaternion. It cannot leave a stale Euler value beside it.
Nonfinite values, invalid quaternion lengths, zero axis-angle axes and unknown
or mixed object fields fail before a scene change.

## Gimbal frames

Euler Gimbal frames use the stored angle order. The first axis is local.
The second excludes the first angle. The last is a global coordinate axis.
Axis-angle uses its actual authored axis and the pinned rotation construction.
Quaternion mode follows the pinned parent-orientation fallback.

Parent world columns are normalized separately before matrix multiplication.
The result is not made orthogonal or normalized again. This matters when a
parent hierarchy produces shear. Constrained and unconstrained rotations keep
these actual Gimbal axes. Translation, resize, pivots, influence and receipts
continue through the shared native operation core.

The source adapter now supplies the actual authored XYZ Euler state. It does
not infer Euler angles from a quaternion or copy measured axes. The observer
resolves the actual queried native mode. The evidence checker verifies every
old/new request and setup. Only the rotation representation changes. Each new
physical quaternion matches its old authored equivalent within `1e-12`.
No source fixture, geometry input or transform request was replaced.

## Source comparison

The focused diagnostic runs all 114 GIMBAL source cases through CLI and official
MCP: 228 comparisons. It matches 226 and fails two. The remaining case in each
interface is `transform_0717`, a rotation with all three constraint flags set.
Focused success is not claimed.

The unchanged complete suite runs all 2,406 comparisons. It matches 2,278:
2,266 completed transforms and 12 expected cancellations. There are 128 failed
comparisons. The full gate still returns exit 1.

Exactly 226 comparisons changed from failed to matched. All new matches are
Gimbal cases. None of the previous 2,052 matches regressed. Both interfaces
produce byte-identical raw results. Position, normal and UV limits remain
`1e-6`. All failures remain in the evidence.

Each interface retains these 64 failures:

| Failure | Cases per interface |
|---|---:|
| Face attribute correction | 18 |
| Safe singular frame behavior | 12 |
| Mirror | 6 |
| Local geometry numeric mismatch | 16 |
| Normal numeric mismatch | 6 |
| World position numeric mismatch | 6 |

The raw requests, before/after states, receipts and analysis are in
`docs/evidence/mesh-transform-core/gimbal-runtime/`.

## Other verification

Formatting, Clippy, 170 Rust tests and 76 Python tests pass with actual Rust 1.85
compiler and rustdoc child paths. Twelve new Rust tests check six physical
rotation orders against independent sequential axis rotations. They also check
Gimbal axes, distinct authored modes, reflected and sheared parents, axis-angle,
quaternion fallback, validation, full-turn storage, rollback, failed saves,
undo/reload, doors, preview world matrices and actual surface picking.

Official MCP regression and all 42 normal queries pass. Metadata is still
structurally valid. The strict baseline exits 2. It has 9,003 pending sources
and all 31 feature contracts pending. All 3,762 prior artifact pins are
preserved. There are now 3,764 pins.

A copied executable also runs with source repository reads denied by macOS.
An unseen mesh uses ZXY Euler rotation under a reflected YZX parent. Independent
geometric checks pass for translation, rotation, reflected resize, shared asset
ownership, unchanged attributes, undo and fresh reload. The driver supplies
authored points and angles. It supplies no measured normals, axes or geometry.

Native Metal renders the actual stored Euler state and its Gimbal deformation.
There are 15 changed vertices and 26,438 changed pixels. Outer corners stay
fixed. Fresh-process reload produces a byte-identical image. Replacing the
Euler mode with its equivalent physical quaternion also produces the same
image. Raw inputs, queries, receipts, images and drivers are retained.

The evidence index is
`docs/evidence/mesh-transform-core/gimbal-implementation-manifest.json`.

## Remaining acceptance

Implement UV correction, safe singular frames and mirror behavior. Resolve all
numeric mismatches. Keep the fixed release performance, final regression,
three-platform CI, dependency integration and independent acceptance gates.
Full numeric/capacity domains, random sequence/distribution and custom-normal
authoring remain on the complete roadmap. No milestone may close from this subset.
