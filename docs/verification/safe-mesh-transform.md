# Singular mesh frame and source centre progress

Issue #48 and draft PR #49 remain incomplete. No feature or milestone is accepted.
The Rust candidate is `263fe1d7652e344e84ccb30a0d4e7c1ab5046def`.
Its executable SHA-256 is
`f9453a2634fe68afaf10430c34efafa3f87a570d24347327791264575cdcc771`.

The contract and primary source were fixed before implementation in
`docs/contracts/safe-mesh-transform.md`. A later contract extension fixed exact
rank certification before that part was implemented. The source remains pinned
to Blender commit `e13b728c6880d3084d9d57c30031ed5df8b39dee`.

## Behavior

An explicit source centre disables individual and active pivot setup before
orientation is derived. The adapter now requests native BOUNDS with that authored
world point. Direct native callers keep the documented individual-centre option.
No initial geometry, source result or transform value changes.

Object linear inversion uses the pinned ordinary float32 inverse first. An exact
zero determinant selects the four-dimensional SVD fallback. The fallback keeps
the source's absolute `1e-8` singular-value cutoff and 200-step bound. Arithmetic
overflow or failure to converge returns an error before an asset is published.
Small full-rank scales keep their ordinary inverse.

The source SVD produces false nonzero values for exact rank loss. An unchanged
C++ extraction confirms values near `2.47e-7` and `1.15e-7` for rank-one and
rank-two examples. The native core certifies the actual float32 input rank with
exact dyadic determinant arithmetic and exact two-term minors. It deflates only
nonexistent dimensions before applying the unchanged cutoff. It does not raise
the cutoff or drop a true small determinant. Independent Moore-Penrose identity
tests cover zero, one, two and non-axis-aligned rank loss.

Singular pivot conversion follows a different source path. It uses the actual
partial Gauss elimination matrix, with column-major order and double intermediate
steps. It does not reuse the linear pseudo-inverse. The unchanged C++ oracle
confirms the independent pivot example `[0, 1, 0]`.

Local orientation fills missing axes with the source's cross/projection and
identity fallbacks. Individual normal frames retain zero object columns.
Geometric normal orientation uses the ordinary inverse's adjugate when singular.
Explicit singular custom working frames and unsafe Gimbal frames still reject.
Existing nonsingular native pivot behavior remains in this change.

## Source comparison

All 42 centre-override and singular source cases run through CLI and official
MCP. All 84 comparisons pass. This focused result cannot accept the full issue.

The complete unchanged suite runs all 2,406 comparisons. It matches 2,314:
2,302 completed transforms and 12 expected cancellations. There are 92 failed
comparisons. The full gate still returns exit 1.

Exactly 36 comparisons improve: 24 singular-frame results and 12 centre-mapping
results. None of the previous 2,278 matches regresses. Both interfaces produce
byte-identical raw results. The comparer and all 1e-6 position, normal and UV
limits stay unchanged. The checker verifies every old/new request and setup.
Only the source's explicit-centre pivot mapping changes.

Each interface retains these 46 failures:

| Failure | Cases per interface |
|---|---:|
| Face attribute correction | 18 |
| Mirror | 6 |
| Local geometry numeric mismatch | 10 |
| Normal numeric mismatch | 6 |
| World position numeric mismatch | 6 |

Seven geometry cases have all three rotation constraint flags. The source does
not assign their temporary axis. Its default vector constructor does not supply
a value. The exposed build flags do not establish zero initialization. The
existing cosine-deformation captures do not prove a defined zero-axis rule.
These seven required cases remain failing. They are not skipped or mapped to a
scale operation. Faithful source/runtime evidence and operation mapping remain
required. The frozen native three-axis semantics remain intact.

Full requests, before/after states, receipts and failures are retained in
`docs/evidence/mesh-transform-core/safe-runtime/`. Source audit inputs, compiler
identity, commands and raw outputs are in `safe-source-audit/` beside it.

## Other verification

Formatting, Clippy, 185 Rust tests and 77 Python tests pass with actual Rust 1.85
compiler and rustdoc child paths. Fifteen new Rust tests check exact rank,
Moore-Penrose identities, tiny full-rank scales, separate normal and pivot
inverse paths, missing axes, convergence and arithmetic errors, real zero-scale
edits, parent rank loss, native centre semantics, attributes, shared ownership,
hidden state, stale requests, undo, failed batches and failed saves.

Official MCP regression and all 42 normal queries pass. Metadata is structurally
valid. The strict baseline exits 2. It still has 9,003 pending sources and all
31 feature contracts pending. All 3,764 prior artifact pins are preserved. There
are now 3,771 pins.

A copied executable runs with source repository reads denied by macOS. An unseen
mesh uses reflected scale `[-1.3, 0, 0.7]`. Independent geometric checks pass for
translation, rotation, reflected resize and the distinct affine centres.
Shared ownership, attributes, undo and fresh reload pass. Inputs contain authored
points and operation values, with no measured normals, axes or geometry.

Native Metal renders a surface with object scale `[1, 0, 1]`. The operation
requests `[0.3, 7, 0.6]`. The seed reaches `[0.3, 0, 0.6]`. The unrepresentable
Y component stays unchanged for every vertex. There are 15 changed vertices and
2,606 changed pixels. Outer corners stay fixed. A fresh process produces a
byte-identical image.

The evidence index is
`docs/evidence/mesh-transform-core/safe-implementation-manifest.json`.

## Remaining acceptance

Implement UV correction and mirror behavior. Resolve every numeric mismatch,
including the unresolved all-axis source path. Keep release performance, final
regression, three-platform CI, dependency integration and independent acceptance
gates. Full numeric/capacity domains, random sequence/distribution and custom
normal authoring remain on the full roadmap. No milestone may close from this subset.
