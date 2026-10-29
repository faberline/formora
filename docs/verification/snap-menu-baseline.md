# Direct snapping source baseline

This is finite source evidence for issue #54 and milestone 0.0.
It does not accept Rust snapping, a complete feature, or a milestone.
The [contract](../contracts/snap-menu-baseline.md) and 1,672 authored requests
were committed before the native captures. The final capture adapter is
commit `224d399`; the original authored source freeze is `ba35fb4`.

## Source and capture

The source is Blender 5.2.3 LTS build `e13b728c6880`, full source commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`.
The manual commit is `4a3be8f9ed3b66b24913e0a0d491d3429a70ea08`.
The executable SHA-256 is
`de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619`.
Use the recorded build report as the authoritative executable pin.
The [primary manifest](../../baseline/sources/snap-menu/manifest.json)
retains the source and manual objects. The
[supporting manifest](../../baseline/sources/snap-menu/supporting-manifest.json)
adds fixed unit conversion, RNA matrix access and singular inversion code.
Existing source objects and pins remain unchanged.

Two native viewport processes, PIDs 23778 and 24985, each ran all 1,672 cases.
Both controller waits ended with exit zero. Each adapter verified the fixed
build, refused an existing output folder, checked all four input hashes
before and after capture, and published its folder by atomic rename.
The [first manifest](../../baseline/reference/blender-5.2.3/snap-menu/manifest.json)
and [repeat manifest](../../baseline/reference/blender-5.2.3/snap-menu-repeat/manifest.json)
retain every request, raw outcome and complete before/after state.
The original absolute input paths are provenance. Verification binds their
repository-relative suffixes and hashes so another checkout can check them.

| Direct operator | Cases per process | FINISHED | CANCELLED | ERROR |
| --- | ---: | ---: | ---: | ---: |
| Selected to grid | 178 | 178 | 0 | 0 |
| Selected to cursor | 928 | 928 | 0 | 0 |
| Selected to active | 98 | 79 | 0 | 19 |
| Cursor to grid | 82 | 82 | 0 | 0 |
| Cursor to selected | 230 | 179 | 51 | 0 |
| Cursor to active | 98 | 79 | 19 | 0 |
| Cursor to origin | 58 | 58 | 0 | 0 |

The 19 errors retain the exact `No active element found!` report.
The source cancels selected-to-active when it cannot find an active element;
the Python API exposes its error report as a RuntimeError.
Cursor-to-active cancels without that error report.
Cursor-to-selected cancels for empty effective selection.
All 89 non-FINISHED results per process preserve the entire recorded state.
They are explicit negative or no-change outcomes, not skipped operations,
successful numeric matches, or product acceptance.

## Verification rules and findings

The [comparison report](../../baseline/reference/blender-5.2.3/snap-menu-reproduction.json)
checks all 3,344 captures and 358 independent analytic cases.
Initial meshes, UVs, materials, weights, winding, selection closure, hidden
state, history, active faces, object poses/parents, locks, shared data,
cursor, view and grid/unit settings are bound to the authored fixture.
The two actual outcomes must agree. Unknown errors or cancellations fail.
Every raw result has its own hash. The complete source and result family
is included in the baseline lock.

IDs, topology and discrete state match exactly. Continuous components use
the contract's fixed limits: positions within 1e-6 physical metres, and
normals, UVs, rotations and matrices within 1e-6 per component.
Raw scene coordinates and physical coordinates are both retained.
For unit system NONE the physical factor is one; otherwise it is
`unit_scale_length`. The conversion does not read a measured snap answer.

Grid rounding follows the pinned float expression
`grid * floorf(0.5f + coordinate / grid)`. Negative half values round toward
positive infinity. The intermediate float sum also matters for the adjacent
half-grid inputs. Unit scales come from the fixed unit source: metre for
metric, foot for imperial, and one raw scene unit for NONE.
Cursor-to-origin clears both location and rotation.

World-coordinate consistency uses the actual Mathutils rule: each float
product rounds before a double sum, which then rounds to a float result.
The checker uses that defined expression rather than increasing a tolerance.
For a singular parent, the source inverse explicitly returns a zero matrix.
Its RNA local-matrix getter therefore returns zero while the child's basis
matrix still holds its authored pose. Both fields remain distinct in evidence.

Ten added Python tests cover the complete source pair and reject corrupted
positions, UVs, normals, materials, groups, winding, selection, hidden state,
history, cursor, frames, parent inverse, local matrix, sharing, settings,
flags, parameters, status, non-finite values, missing fields and provenance.
They also check fixed tolerances, negative half rounding and linked users.

## Diagnostic history

The [diagnostic record](../evidence/snap-menu-baseline/diagnostics/history.json)
preserves two capture-harness errors, without counting them as passes.
An initial setup loop appended vertex groups while iterating a shared group
list. A native process sample proved the loop. Only the verified task-owned
PID 72532 was stopped, with terminal exit -15. Freezing group names and
checking existing definitions fixed setup without changing the fixture.

The next complete pair read stale Mesh data from a linked object that stayed
in OBJECT mode while its shared data was being edited. Both original full
captures remain in task-local diagnostic folders. Their complete manifests
and a representative raw result are retained in the evidence directory.
The final adapter reads live data using `Mesh.is_editmode` for every user.
The final pair now has identical local geometry for all users of shared data.
Object mode and mesh edit mode are recorded separately.

## Remaining acceptance

Local regression commands, full logs, actual tool versions and unchanged
input hashes are in the [local record](../evidence/snap-menu-baseline/local/manifest.json).
All 229 Rust tests and 100 Python tests pass on actual Rust 1.85.0.
Formatting, all-target Clippy, the retained MCP regression and structural
metadata checks pass. Strict readiness still exits two, as expected for an
incomplete baseline. No Rust product source, product test or dependency
changed relative to PR #53 in this source-baseline branch.
The workflow adds the recorded snapping comparison on all three desktop
runners. A local result does not replace those required CI results.

The catalog has 38 pending features and 8,994 pending source entries.
All 9,047 inventory identities remain present; `complete_products` is empty.
Strict baseline readiness remains false. No issue or milestone is accepted
by these finite source results.

Rust CLI/MCP snapping, atomic failures, receipts, undo/replay, shared assets,
save/reload, native preview, fixed release performance, dependency integration
and independent acceptance remain unrun for this new family.
Continuous transform target snapping, other data modes, full parameter
domains and capacity also remain required roadmap work.
The separate approved all-axis rotation rejection policy stays unchanged.
