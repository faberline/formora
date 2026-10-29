# Single edit-mesh direct snapping

This implements the bounded 0.2 slice in issue #56.
The [contract](../contracts/mesh-snap-core.md) was committed as
`0fbcc4538125c328daf72ec8123c5a745a1ccf9c` before product implementation.
The implementation is `f3403dc720a6b6e2f26d86af61ad10e9ccdc7f86`.
It depends on issue #54 / PR #55 and the fixed Blender 5.2.3 source baseline.
No complete feature or milestone is accepted here.

## Product behavior

One typed `snap_mesh` command serves the CLI, native session and official MCP.
It reads an actual entity, its shared mesh, persistent selection, hidden state,
history, active face and cursor. Seven actions implement selected-to-grid,
cursor or active; and cursor-to-grid, selection, active or origin.
Grid spacing is in physical metres. All five source pivots remain explicit.
Selected-to-cursor retains both offset and rotation request flags. The source
ignores its rotation flag in mesh edit mode, so the selection rotation flag
in the receipt remains false. Cursor rotation has separate before/after fields.
Cursor-to-origin clears its actual location and rotation.

Receipts identify real changed vertices, incident edges/faces, the entity,
asset, all shared users, effective grid/pivot/target, cursor changes and status.
Missing active data rejects selected-to-active atomically. Cursor-to-active
or cursor-to-selection can return an explicit unchanged cancellation.
Cancelled transactions retain the existing editor revision/undo semantics;
their receipt says cancelled and contains no changed geometry or cursor.
Invalid requests return no successful receipt and preserve disk, scene,
revision and undo history. Save failure and a late batch error also roll back.

The core retains source float order and negative-half grid rounding.
It uses the direct source's ordinary 3x3 adjugate for a zero determinant.
It does not substitute the safe transform inverse or singular 4x4 zero inverse.
Topology identities, winding, UVs, materials, weights, seams, smooth flags,
selection/history, object frames and shared ownership remain intact.
Geometry edits update automatic normals and mark primitive recipes edited.
Cursor-only actions preserve those recipes. Actual undo, replay, regeneration
and saved fresh reload are recorded in the recipe check.

## Complete bounded execution

The [full report](../evidence/mesh-snap-core/full/report.json) retains all
1,122 covered cases through each interface: 2,244 real requests.
The complete input set, binary and source hashes stayed unchanged during
that final run. Both frozen native Blender processes are checked for every
actual result. Test setup uses authored inputs, never measured answers.

There are 2,072 defined FINISHED comparisons, 136 explicit cancellations and
36 expected atomic missing-active rejections. The last two categories are
not numeric successes. Every initial state is bound to authored geometry,
selection, attributes, parent poses and cursor settings. Final local/world
positions use the fixed 1e-6 metre component limit. Normals, UVs, rotations
and matrices keep the fixed 1e-6 component limit. Discrete state stays exact.

The other 550 object/multi-edit cases remain required and unrun by this core.
Other data modes, continuous target snapping, full domains and capacity also
remain required. All seven catalog entries stay pending.

## Corrections and retained failures

Strict input tests first caught unknown fields on parameter-free actions.
Empty struct variants now reject those fields before dispatch.
The initial runtime pilot also exposed a setup error for a hidden-only seed.
The adapter now applies the authored source selection-flush rule before
Rust validates editing state. The unchanged source states still bind setup.

The first complete finite run passed all 2,244 fixed requests. A separate
repository-denied unseen-input test then found an unrelated rotation change.
Moving the cursor rounded `[0.17,0.23,0.41]` to f32 even though the operation
only changed location. Both the failing native calls and a failing Rust
test are retained. The fix writes rotation only for cursor-to-origin.
Receipts compare the actual authored before/after fields independently.
The unseen-input test now passes with the original rotation values intact.
The old finite outputs are byte-identical to the corrected complete run;
their original report and exact shared-storage hashes remain diagnostic history.

A subsequent complete rerun stopped with ENOSPC while writing evidence.
A concurrent legacy run also stopped at initialization without retaining
that initializer's exact error. Both terminal failures and partial files are
retained. Neither was accepted as a pass. The cap guard rejected external
cache deletion, so this session deleted no cache or evidence files.
All 30 earlier performance scenes were losslessly archived and checked
byte-for-byte; their raw copies also remain. Space later became available.
Both complete suites were then rerun from the beginning and passed.
No authored case, required outcome or numerical limit was removed or weakened.

## Local evidence

- Actual Rust 1.85.0: 238 Rust tests, 108 Python tests, format and all-target
  Clippy pass. The added business checks cover strict inputs, rounding,
  shared/hidden identity, cursor preservation, stale/budget/batch failures,
  save failure, undo/replay, receipts and corrupted reference results.
- The original 2,406 transform requests pass: 2,344 defined deterministic
  checks, 48 stochastic support checks and the 14 separately approved
  all-axis rejection checks. The rejection policy remains unchanged.
- Retained checks pass: 162 primitives, eight scale cases, 1,060 selections,
  262 creation contexts, 57 payloads, 42 normal queries, 96 seeded RNG API
  cases, 48 one-shot seeded RNG cases and the official MCP smoke check.
- Six Euler-order parent/world queries remain exact. All retained native
  primitive, selection, creation and rotation/RNG isolation checks pass.
- The new unseen native isolation check denies every repository read and
  proves analytic geometry/normals, shared data, rejection, undo/replay,
  cursor preservation and fresh reload. Its process wait and fresh process
  both end with exit zero.
- Native Metal renders the actual new snap result. It changes 24 vertices
  and 29,269 pixels, preserves attributes, and produces identical fresh-reload
  PNGs. The retained source-RNG and legacy mirror/UV Metal checks also pass.

## Fixed performance

All ten direct operation/flag forms have three release samples on the M1 Max.
They retain 10,201 vertices, 20,200 edges, 10,000 faces, identity frame, median
pivot, last active vertex, 0.75 metre grid and the specified cursor.
Input preparation stays outside the timers. Every sample saves and freshly
loads the actual output. All 30 outputs match the independently captured
native source geometry and normals at the unchanged limits.

The final core range is 150.360292–223.801208 ms, below 250 ms for every sample.
Operation/save/fresh reload is 298.572375–392.319750 ms, below 2,000 ms.
The retained nine transform samples also pass at 226.587333–234.729542 ms
core and 392.758125–409.989417 ms pipeline. All nine source position and
normal comparisons have zero maximum error.

## Acceptance remains open

The [evidence manifest](../evidence/mesh-snap-core/manifest.json) and
[checker](../evidence/mesh-snap-core/check-evidence.py) bind the recorded files
and final candidate. Three-platform CI, dependency integration and independent
Codex acceptance remain required. A failed, skipped or unrun gate cannot pass.
The source inventory retains all 9,047 IDs, with 8,994 pending sources and
38 pending features. All 7,170 previous pins remain intact; three extra active
selection source pins bring the total to 7,173. Strict readiness stays false,
`complete_products` stays empty, and no milestone closes.
