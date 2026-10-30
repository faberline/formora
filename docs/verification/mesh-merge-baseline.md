# Vertex merge: local native source baseline

Issue #70 continues the complete 0.0–1.0 goal. This source baseline passes
its local checks. No Rust product implementation or milestone is accepted.
The parent is draft PR #67 at dcc7a293145575851660ba6690e4bf36a2b42f8f.
This branch is independent of draft PR #69 and its pending zero-scale policy.

## Fixed inputs and native capture

Commit 70900f7b81e0c4eadb5c9f2482175a9513efcce1 froze the contract,
1,024 authored inputs, strict native adapter, comparator, source manifest
and eight analytic controls. Commit a54c320270f02b1a9dacfe5eda49b6a64d97cdad
bound the native launcher and forty pilot cases. No source answers informed
the authored inputs. The later two checker corrections are described below.

Use Blender 5.2.3, build e13b728c6880, full source commit
e13b728c6880d3084d9d57c30031ed5df8b39dee and executable SHA-256
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
The source manifest binds 32 exact source files and their Git blobs/SHA-256.
Source includes the editor operator, BMesh weld/collapse, interpolation,
CustomData, deformation groups and operator definitions. Existing selection
flush source is already pinned through the historical baseline lock.

The strict pilot completed forty cases in native viewport process 45574,
actual terminal exit 0. Two independent complete native viewport processes,
50701 and 52091, each completed all 1,024 original cases with actual exit 0.
Their complete comparison passes every raw field at the fixed 1e-6 continuous
limit and exact discrete equality. No background process replaces a viewport.

The cases cover five merge methods, both UV settings, ten topology regions,
all seven component-mode masks, empty/single selections, four nonsingular
frames and forward/reverse vertex history. Both selected objects share one
actual edit mesh and retain distinct world frames and an unselected child.
Actual topology, two UV layers, group weights including explicit zeros,
materials, smooth/seam flags, normals, selection/history and source tags
are captured and checked. Initial data is bound to authored inputs. Independent
checks cover mean/cursor/history locations and connected edge collapse counts.

Results remain separate: 920 cases change the geometry record, 88 retain it,
and 16 empty FIRST/LAST requests receive a native enum rejection. No enum
rejection or unchanged geometry is counted as a numeric geometry mutation.

Native welding can interpolate the integer capture tag to the value of an
unselected vertex. Case merge_0008 has duplicate inherited tag 3, while all
fifty surviving native vertices remain present. The adapter indexes every
native component by iteration order and records inherited tags separately.
It neither overwrites duplicate tags nor modifies native data to repair them.
Temporary mesh normal queries verify the same native face/vertex order.

## Preserved checker failures

The first pilot check failed at merge_0835 after 22 cases. Its reused snap
selection oracle treated the seed domain as the final selected edge set.
Pinned BM_mesh_select_mode_flush_ex also flushes selected vertices up to
edges when VERT is enabled. The corrected oracle derives that mixed-mode
selection from authored endpoints and keeps the full exact initial binding.

The second pilot check failed at merge_0923 after 32 cases. Its collapse
oracle used the mean of unique vertices. Pinned bmo_collapse_exec adds both
endpoints of every selected edge, so a shared vertex contributes once per
incident edge. The corrected mean follows that source rule.

Both original checker versions and both first failure reports are retained.
Commit 4fc8c1af3f2a1d17b70c8f96c3dd774ee8df557e fixed the corrected checker
and two regression controls before the complete captures. The third pilot
check passed all forty cases. No capture adapter, authored input, required
case, numeric limit or Rust product source changed to resolve either failure.
The contract's collapse component means are edge-endpoint means.

Before any capture, one preparation test guessed the existing UV layer names
incorrectly. It was corrected to the actual pinned UVMap/DetailUV names.
The authored mesh was unchanged. One guessed source filename returned 404;
the exact pinned directory identified bmesh_operators.cc, whose Git blob was
then verified. These preparation errors are recorded and grant no acceptance.

## Verification and catalog

All 215 Python tests pass, including ten preparation controls and fifteen
actual native controls. Actual Rust 1.85 passes all 28 baseline tests. Source
comparison verifies every stored/raw gzip hash, native identity, RNA, script,
authored input, source manifest/file, historical lock and terminal receipt.
Both capture provenances still pass after appending twelve source pins.
The original 7,183 pins remain unchanged; the lock now contains 7,195 pins.

Only the exact bpy.ops.mesh.merge manual anchor is assigned to mesh.merge.
The broader manual page, remove-doubles anchor and other page sections remain
pending. The feature case keeps full-domain/capacity/product work explicit.
No claim is made that the live manual contents were reread successfully:
the web fetch returned 402 and the pinned manual raw fetch returned 403.
The source/operator/RNA/native evidence establishes this bounded operator
baseline. It does not complete the full official-manual inventory review.

Metadata is structurally valid with no problems. Strict readiness exits 2.
All 39 features and 8,993 sources remain pending. complete_products is empty.
The new source comparison is required by the three-platform workflow.
No Rust product files, existing source artifacts or acceptance limits changed.

## Reproduce and continue

Use Python 3.12 with tools/requirements-mcp.txt installed. From the repository
root, run the following with a new output path:

```sh
python tools/compare_mesh_merge_reference.py --suite baseline/fixtures/mesh-merge.json --first docs/evidence/mesh-merge-baseline/native-01 --second docs/evidence/mesh-merge-baseline/native-02 --receipts docs/evidence/mesh-merge-baseline/native-processes.json --output /private/tmp/formora-merge-source-new.json
python -m unittest discover -s tools/tests -v
cargo test --locked --all-features --test baseline
```

The captured command lines and actual exit receipts are in native-processes.json.
The before-capture plan and correction records bind the exact setup history.
The evidence manifest excludes itself and hashes every other retained file.

Next freeze a separate Rust contract and actual performance inputs before
implementation. Require shared CLI/official MCP execution, real saved topology
and attributes, receipts, physical queries/preview, reload, undo/replay,
atomic errors, recipes, source-independent proof and unchanged retained gates.
Keep the full parameter/data/capacity domains in scope. Three-platform CI,
stack integration and independent Codex acceptance remain required. No failed,
skipped or unrun check can pass. All eleven milestones remain open.
