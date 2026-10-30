# Direct snapping with zero scale: source baseline

Issue #68. Depend on draft PR #67 at
dcc7a293145575851660ba6690e4bf36a2b42f8f. Continue the full 0.0–1.0 goal.
Freeze this contract, inputs and capture program before native capture.
This baseline does not accept product behavior, a feature or a milestone.

Use Blender 5.2.3, build e13b728c6880, source commit
e13b728c6880d3084d9d57c30031ed5df8b39dee and executable SHA-256
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
Bind reused sources and their Git blobs and hashes in a new source manifest.
Do not change existing fixtures, source pins, evidence or limits.

## Authored coverage

Create exactly 1,764 cases without reading measured answers:

- 1,120 object cases: seven nonempty zero-axis masks, two affected roles
  (target normal scale or parent normal scale), eight rotation modes and
  ten operator forms. The forms are all four selected-to-cursor flag pairs
  and each of the other six direct operators.
- 84 mesh-edit cases: seven masks, the two roles and the six selected
  operator forms (grid, active and four cursor flag pairs).
- 112 object origin/child controls: seven target normal scale masks,
  all four origins-only / skip-children settings and four cursor flag pairs.
- 448 delta-scale cases: seven masks, two affected roles, eight modes
  and four selected-to-cursor flag pairs. Normal scale stays nonzero.

Use the existing authored mesh, real UVs, groups, materials, seams, smooth
flags, selection, sharing and unselected child. Keep secondary scale nonzero.
Target-scale cases use the unparented frame, regular active rotations and
combined deltas. Parent-scale cases use the rotated parent frame, identity
active target rotations and translation deltas. This isolates exact zero
axes before each operation. Preserve all raw active and inactive channels.
Use all seven masks, not a zero determinant tolerance. Signed negative
nonzero components remain in the authored target/parent frames.

## Source behavior and checks

The pinned 3x3 inverse writes the adjugate before testing the determinant.
On exact zero it returns false and leaves the adjugate. The direct snapping
callers use that result. The pinned Eigen 4x4 inverse instead writes a zero
matrix on failure. Do not assume the two fallbacks are interchangeable.
Do not apply a blanket singular-input rejection.

Capture two separate native viewport processes with different process IDs.
No background replacement is allowed. Refuse existing output or staging.
Retain staging on failure. Store exact JSON with lossless gzip and raw/stored
hashes. Bind every setup script, authored input, source file/manifest,
baseline lock, actual RNA, process identity, platform and terminal exit.

Bind initial normal/delta channels, locks, selection, settings and geometry
to authored inputs. Independently compose initial basis/world matrices and
world vertices. Check channel-to-basis, parent-to-world and world-to-vertex
consistency before and after. Read the actual matrix_local getter too.
For a singular parent it uses the source 4x4 inverse; it must not be replaced
by parent_inverse times basis. Check its zero result where the actual parent
matrix has an exact zero column. Retain and compare the raw getter in both
processes for other cases; do not claim an independent inverse oracle there.

Compare every captured field across processes. Discrete fields are exact.
Finite positions, channels, normals, UVs and matrices have maximum absolute
error 1e-6 per component. Do not loosen this limit after capture. Preserve
operator FINISHED, CANCELLED and ERROR separately. An unexpected error,
nonfinite output, setup failure, missing case or nonzero terminal exit fails
the complete baseline. Do not remove cases after seeing results.

Add analytic zero-axis and adjugate controls and negative controls for changed
zero masks, deltas, raw inactive channels, matrix_local, world matrices,
geometry, sharing, hashes, duplicate processes and missing/failed receipts.
If the source has an additional undefined result, preserve its failure and
seek a separate policy decision. The approved 14 mesh-axis rejection cases
do not authorize a new rejection policy.

## Remaining gates

Write a separate before-code Rust contract after the baseline passes.
Require both CLI and official MCP, actual saved data and receipts, reload,
undo/replay, atomic failure, source-independent checks, native previews,
unchanged retained gates and performance limits frozen before product code.
Platform CI, stack integration and independent Codex acceptance stay required.
Failed, skipped and unrun checks do not pass. Keep all milestones open.
Near-singular ranges, pose data, other data modes, continuous snapping,
capacity and every other product domain remain in the full goal.
