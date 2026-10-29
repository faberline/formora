# Nonidentity delta snapping: local source evidence

Issue #64 extends milestone 0.0 under the unchanged unlimited 0.0–1.0 goal.
Commit aa32b6b0f4b31703750088fdb5eab63e3c35a23c froze the contract, 1,792
authored inputs, source manifest, native adapter, comparator and six analytic
controls before native capture. The parent is draft PR #63 at
7779cf8fac799dc9aa1e94ed064df80799039b01. No product Rust files changed.

## Fixed native results

Two independent native Blender 5.2.3 viewport processes completed all 1,792
cases each. Process IDs are 54018 and 55401. Both actual terminal exits are
zero. Both use build e13b728c6880, full source commit
e13b728c6880d3084d9d57c30031ed5df8b39dee and executable SHA-256
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
The actual controller receipts, child logs, commands and hashes are retained.
The separate 18-case pilot used process 51760 and terminal exit 0. It is a
diagnostic, not the complete baseline.

Cases cover eight rotation modes, isolated translation/rotation/reflected
scale and combined deltas, nonsingular parent frames, all sixteen channel
lock masks, location locks, origin/child options, cursor and mesh editing.
Initial normal and delta channels are bound exactly to authored f32 inputs.
Independent matrix composition follows delta rotation before normal rotation,
componentwise scale multiplication and location addition. Physical frames,
real shared geometry, parent inverses, raw channels, normals, UVs, groups,
material/seam/smooth data and actual operator results are checked.

Actual RNA confirms that delta axis-angle is not exposed by the fixed source.
The pinned RNA file places that definition inside #if 0. Axis-angle cases
preserve exposed inactive delta Euler and quaternion values while the actual
internal delta axis/angle stays at its fresh object default. No native memory
was written. Other internal data domains remain in the full product scope.

The first complete comparison passed all 1,792 cases against both captures.
All operations returned FINISHED; no cancellation or error counted as a
numeric pass. Both gzip and exact raw JSON hashes remain bound to manifests.
Terminal receipts bind each manifest and exact historical baseline lock.
The original 7,181 pins remain unchanged. Two appended fixture/manifest pins
bring the lock to 7,183. All 22 reused source files have exact SHA-256 and Git
blob checks. Baseline criteria remain unchanged.

The final comparison also passed from the workflow's relative CLI paths using
actual Python 3.12.11. Its report binds the final comparator bytes and actual
terminal receipts. All 180 Python tests passed, including 28 new analytic /
native negative controls. The complete suite keeps every previous test.
Baseline metadata is structurally valid with no problems; strict readiness
exits 2. All 38 features and 8,994 sources remain pending. Both products remain
incomplete. The prior two rotation-capture provenances also still validate
against the appended lock. Product source files remain unchanged from PR #63.

## Preserved checker failure

The first initial-state and self-consistency scan exited 1 at delta_snap_0403,
after-state secondary vertex v000022. The old helper used Python sum for three
rounded products before adding translation. Python's compensated sum differed
from the fixed C++ sequential double accumulator at a float halfway boundary:
Y was 0.5250000953674316 instead of native 0.5250000357627869.

The new local helper follows mathutils_Vector.cc column_vector_multiplication:
four f32 products, accumulated in source order in double, then converted to
f32. This gives the actual native value. The exact zero-tolerance world-vertex
self-check remains exact. The fixed 1e-6 source comparison limit is unchanged.
The original comparator, raw captures, first failure and logs are preserved.
No capture, authored input, product code, case or limit changed. A focused
regression control protects the exact halfway result. Relative CLI paths also
resolve to their actual checkout before provenance checks.

The first full Python command omitted the already installed official MCP SDK
from PYTHONPATH. Two existing runtime test modules failed to import mcp;
163 tests were reported with two import errors. Its exact logs remain saved.
The retry uses the existing SDK path and changes no test or product code.
The workflow now installs its already required MCP package before unit tests,
because those tests import the real runtime adapters. Previously that install
was after the tests. No package version or dependency criterion changed.

## Acceptance boundary

The workflow requires this complete source comparison on all three platforms.
No three-platform CI success, dependency integration or independent Codex
acceptance is claimed. Parent PR #63 push 40965331828 and PR 40965365412
failed before all six jobs started because GitHub reported account payment /
spending-limit restrictions. No billing, runner or workflow limit was changed.

This source baseline does not implement Rust delta transforms. A separate
before-code implementation contract must cover every case through real CLI
and official MCP, persistence, actual physical frames, typed receipts,
atomicity, reload, undo/replay, recipes, native Metal and fixed performance.
All previous required gates remain. The approved undefined mesh-axis
rejection policy remains limited to its exact defect boundary.

Catalog review stays pending, complete_products stays empty and all eleven
milestones stay open. Singular transforms, wider parameter ranges, other
data modes, continuous snapping and capacity remain required work.
