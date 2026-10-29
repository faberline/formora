# Native mesh transform API

This document fixes the agent API before its implementation. It supplements
`mesh-transform-core.md`. That contract's full 1,203 source cases, fixed 1e-6
limits, performance limits and independent acceptance remain required.
An initial implementation is progress only. Unsupported options must fail
explicitly. They must not silently fall back or complete issue #48.

`transform_mesh` takes one `transform` object. It locates a mesh through `entity`.
All instances keep that shared asset. It changes visible selected vertices.
It preserves IDs, topology, selection, hidden state and unrelated attributes.
It updates automatic normals after the geometry changes and marks recipes edited.

`change` has one of three tagged forms:

- `{"kind":"translate","value":[x,y,z]}` uses metres in the working basis.
- `{"kind":"rotate","radians":a,"axis":"x|y|z"}` uses a right-handed angle.
- `{"kind":"resize","value":[x,y,z]}` uses dimensionless factors.

`orientation` defaults to `{"kind":"global"}`. Other kinds are `local`, `parent`,
`cursor`, `view`, `normal`, `gimbal`, and `custom`. A custom orientation supplies
`matrix` as row-major numbers, with its working axes in the columns. The core
must derive all other bases from actual scene or mesh state. Matrices must have
finite f32 values and an invertible working frame. Singular object frames require
the fixed source's separately verified safe inverse behavior before support.

`pivot` defaults to `median`. It also accepts `bounds`, `cursor`, `active` and
`individual`. Active uses actual persistent selection history and active face.
Individual centres use selected connected edge/face islands. Isolated selected
vertices use their own position. Centres and arithmetic follow the pinned source.

`constraint_axis` is a three-boolean mask. All false means unconstrained.
Translation masks displacement components in the working basis. Resize leaves
unconstrained factors at one. Rotation uses a single constrained axis, or the
normal of a constrained plane. Three true leaves the requested rotation axis.
The source EXEC translation input already contains final values. Its adapter
must therefore omit the native translation mask. This is an authored request
mapping. It must not use measured positions or bases.

`proportional` is optional. It contains a positive finite `radius`, a `falloff`
(`smooth`, `sphere`, `root`, `sharp`, `linear`, `constant`, `random` or
`inverse_square`), and `connected` and `projected` booleans. Projected distances
use the actual authoring view. Connected distances require the verified source
surface propagation algorithm, not an edge-only approximation. Random requires
an explicit `seed`. The core must preserve and report it for repeatable replay.
Source random comparison retains the fixed support policy. Full source sequence
and distribution parity remain unrun.

`mirror` optionally supplies `axis` and `topology`. `correct_face_attributes`
defaults to false. `keep_connected` defaults to true. These options require
their actual implementation. A request for an unsupported option fails.
`max_components` defaults to 1,000,000. Count vertices, resolved edges, faces and
face corners before transformation. Reject a zero or exceeded budget.

A successful saved batch returns `transforms` receipts. Each receipt contains
the command index, target entity, shared asset, instance IDs, actual world basis,
world pivot, local per-vertex centres, influence weights, changed typed component
IDs and preserved random seed. Receipts must not survive failed batches or saves.
No selected visible vertices is an explicit error. It leaves the scene unchanged.
The source adapter may recognize that specific error as its expected cancellation.

No operation may receive measured reference geometry, normals, bases, centres or
influences as inputs. Invalid and stale requests, unsafe frames, budget failures,
batch failures and save failures must leave disk, memory and undo unchanged.
