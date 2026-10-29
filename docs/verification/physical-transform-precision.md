# Physical transform precision progress for issue #48

Implementation candidate: `4d7bc95bf988442cc95885ed4518d8ecd37e04fd`.
This is bounded progress in draft PR #49. No issue or milestone is accepted.

The Rust core now uses one physical matrix builder. Mesh creation, component
transforms, geometric frames, preview and picking consume it. The scene stores
one authored `precision`: `f64` by default, or explicit `f32`. Default precision
is omitted from saved JSON. Existing high-precision preview and picking tests
retain their original assertions and limits. Euler angles, order, axis-angle
and quaternion representation remain actual saved state.

The fixed Blender adapter requests `f32` uniformly for every object profile and
parent. It does not choose precision from a measured answer or failing case.
Its transform requests, authored geometry and expected outputs are unchanged.
Single-precision frames use the pinned rotation and scale rules and balanced
parent products. Default frames keep double-precision composition.

The source's local pivot first tries its pinned Eigen four-dimensional inverse.
The core reuses the Rust port already verified for mesh creation. It retains
the ARM reciprocal estimate and two refinements. A rejected inverse falls back
to the separately verified partial Gauss result. The operation's linear inverse
is unchanged. Default nonsingular native pivots retain their previous rule.

The new read-only query is `scene inspect --entity ID --world`. MCP accepts
`scene_inspect` with `entity` and `world: true`. It returns the actual row-major
world matrix. Meshes also return world vertices with stable IDs. Built-in cube
and plane corners use `builtin_v000000` onwards. Invalid option combinations
fail. Queries preserve scene, disk, revision and undo.

In `f32` mode the observed point path matches the pinned Python vector query:
float32 products, double accumulation, then a float32 result. Core vector
operations keep their separate float32 order. The comparer observes the actual
native query. It no longer reconstructs world coordinates with Python double
quaternion arithmetic. Raw captures retain both complete native world queries.

## Source and functional evidence

The precision contract precedes implementation. Five new pins bind the object,
SIMD, Python matrix/vector sources and their manifest. All 3,780 previous pins
remain intact. There are now 3,785 pins.

Six independently authored parent/child Euler scenes match the actual frozen
Blender binary exactly. Every world-matrix and world-point component matches
without tolerance. The source probe also exposes the different Python matrix
accumulation path. The observed parent frames match balanced float32 products.
No measured matrix, normal or vertex enters a product operation.

Actual Rust 1.85.0 passed 213 tests. Python passed 80 tests. Formatting and Clippy
passed. New tests cover six Euler orders, both precision modes, quaternion and
axis-angle frames, balanced cancellation, point accumulation, reflected parent
frames, zero scale, shared instances, query purity, built-in shapes, invalid
options, serialization, undo, saved reload, overflow and failed saves.

The final candidate passed all existing functional regression suites: 162
generation, eight scale, 1,060 selection, 262 creation-context and 57 payload
checks. The general official MCP regression and 42 normal queries passed.
SDK version is 2.3.0. Protocol version is 2025-11-25.

The complete transform gate ran all 1,203 cases through CLI and official MCP.
It matched 2,392 of 2,406 checks. This is 30 improvements and zero regressions
from the previous mirror/UV candidate. There are 2,380 completed outcomes and
12 expected cancellations. The fixed stochastic support policy remains in use.
It does not claim exact RNG sequence or distribution parity. All 1e-6 limits,
source cases and expected outputs remain unchanged. Raw results are identical
between interfaces. The 15 previously failing defined cases passed a separate
30-check diagnostic through both interfaces.

Fourteen checks still fail. They are the same seven source requests with all
three rotation constraint flags, repeated through both interfaces. The pinned
source does not initialize their rotation axis. The existing native axis rule
and all seven failing cases remain intact. A finite cosine-deformation sample
cannot establish a source-defined rule.

## Native and performance evidence

The copied native binary passed an unseen f32 scene with repository reads
denied. It checks a local Y mirror, reflected nonuniform scale, two UV layers,
plane clamps, the actual world query, distinct coincident IDs, hidden vertices,
shared ownership, stale revisions, failed batches, undo, replay and fresh reload.

Actual Apple M1 Max Metal rendering passed an f32 mirrored grid with UV
correction. Fifteen vertices and 14,302 pixels changed. Fresh reload produced
identical image bytes. The native query observes the same single-precision
surface state. This is rendered-scene evidence, not complete material parity.

The frozen release performance gate was measured for the first time. The
100-by-100 quad grid has 10,201 vertices, 20,200 edges and 10,000 faces. All
vertices are selected. The identity frame, global direction, median pivot,
three operation values and three repetitions follow the existing contract.
The standalone driver links the actual Rust 1.85 release library from this
candidate. It has no preview feature. Input preparation is outside the timers.
Core timing includes the validated atomic operation and its actual receipt.
Pipeline timing includes the operation, save, fresh complete load and equality
check. Raw monotonic timestamps, host identity, build commands, exact executable
and library hashes, full scenes, receipts and driver source are retained.

**The performance gate failed.** All nine core runs exceeded 250 ms. Core times
were 269.346166–278.49525 ms. Pipeline times were 431.822292–456.405292 ms, within
the separate 2,000 ms limit. IDs, topology, selection, receipts and complete
reloaded scenes were checked. Independent source-position comparison for this
large grid remains unrun. These timings do not accept the operation or issue.
The 250 ms and 2,000 ms limits remain fixed. Do not rerun unchanged code to select
a faster sample. Reduce the core cost and repeat the complete performance gate.

## Evidence and remaining work

`docs/evidence/mesh-transform-core/frame-implementation-manifest.json` binds
the final candidate, executable, source inputs and raw artifacts. Its checker
verifies all captures, the unchanged source gate, existing regression suites,
native probes, source pins and the failed performance gate. Staged evidence
bytes are also checked against the Git index and stored blobs.

Baseline metadata remains structurally valid. Strict acceptance still returns
exit 2. There are 9,003 pending source entries and 31 pending features. Required
three-platform CI, dependency integration and independent acceptance remain
unrun. Earlier GitHub CI attempts were refused before execution due to account
billing limits. A head-specific CI record must confirm the latest state.

Issue #48 stays open with `agy:doing`. PR #49 stays a draft. All milestones stay
open. Continue with core performance, the remaining undefined source behavior
and the other required feature domains. No failed or unrun gate is a pass.
