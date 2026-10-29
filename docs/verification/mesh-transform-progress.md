# Mesh transform progress for issue #48

Issue #48 is incomplete. PR #49 must stay a draft. No feature, issue or milestone
is accepted by this evidence.

The implementation candidate is `19d2470b9d7891d81c27906ca99358bc7f01b327`.
Its executable SHA-256 is
`74eed79df6e27580de2dee4d06d0045bf3ace02b800d499d7a2c8c8ef2915dcd`.
The native request contract is `docs/contracts/mesh-transform-native-api.md`.
The full acceptance contract remains `docs/contracts/mesh-transform-core.md`.

## Implemented paths

`transform_mesh` now changes real shared mesh geometry through CLI and official
MCP. It supports translation, rotation and resize. It calculates global, local,
parent, cursor, view and custom working frames from actual scene data.
Median, bounds, cursor, active and individual centres are calculated in Rust.
Individual centres use selected edge or face groups. Vertex identity remains
separate from position equality.

The core calculates Euclidean and view-projected proportional weights.
A balanced point tree finds the closest selected point. Seven deterministic
falloffs and an explicitly seeded random falloff are implemented. Random replay
preserves and reports the seed. Connected surface propagation is not implemented.

Receipts report actual frames, centres, weights, changed typed components and
shared instances. They are returned after a valid batch is saved. Failed requests,
stale revisions, invalid frames, budget failures, failed batches and failed saves
leave the scene and undo history unchanged. Geometry edits update automatic
normals and mark primitive recipes edited.

These are implemented paths, not full feature claims. The source comparison
below still fails. Source request mapping is based on the pinned source code.
Numeric EXEC move and scale arrays enable all three source axes. Nested Python
matrix arrays use column-major source storage. `use_accurate` initializes mouse
input only when an input event exists. This suite has no such event.

## Complete first source run

`tools/transform_runtime_smoke.py` executes all 1,203 authored cases through each
of CLI and official MCP. It uses only authored initial geometry and parameters.
It does not send measured source positions, normals, bases, centres or influences
to Rust. It validates both complete source captures before product comparison.

All 2,406 requests ran. Both interfaces produced identical raw results for every
case. There are 1,602 matched results: 1,590 completed transforms and 12 expected
cancellations. There are 804 failed comparisons. The required gate returns exit
1 and records `required_full_gate_passed: false`.

Each interface has the following 402 failures:

| Failure | Cases per interface |
|---|---:|
| Normal orientation is not implemented | 114 |
| Gimbal orientation is not implemented | 114 |
| Connected proportional editing is not implemented | 114 |
| Face attribute correction is not implemented | 18 |
| Safe singular frame behavior is not implemented | 12 |
| Mirror is not implemented | 6 |
| Local geometry differs numerically | 14 |
| Normals differ numerically | 6 |
| World positions differ numerically | 4 |

The fixed component limits remain `1e-6` for positions, normals and UVs.
No failed case was removed or reclassified as passed. Unsupported options return
errors. They do not silently use another operation. A specific empty-selection
error can match a source cancellation. Other errors cannot use that route.

Raw requests, initial state, final state, receipts, failures and hashes are in
`docs/evidence/mesh-transform-core/first-runtime/`. `analysis.json` records the
failure groups. The complete report is `report.json`.

## Other local checks

Actual Rust 1.85 compiler and rustdoc child paths were used. Formatting, Clippy,
136 Rust tests and 74 Python tests pass. The tests cover shared asset ownership,
unrelated data, typed face IDs, native axis constraints, independent geometric
centres and falloffs, replay, undo, fresh load and failure atomicity.

The existing local checks pass with this executable:

- 42 automatic normal queries;
- 162 primitive generation cases and eight scale cases;
- 1,060 selection cases;
- 262 creation contexts;
- 57 reference payload cases;
- official MCP regression;
- eight existing native Metal samples;
- repository-read-denied generation and create/append execution.

New native Metal samples execute all three transform kinds. Translation changes
43,460 pixels, rotation changes 36,375 pixels, and resize changes 20,920 pixels.
Each fresh-process reload image is byte-identical. A standalone Rust 1.85 probe
links the same built library. It verifies that selection markers add render
vertices but leave the surface hit position and distance unchanged.
The probe, its build command, library hashes, requests and images are under
`docs/evidence/mesh-transform-core/gpu/`.

The metadata check passes. The strict baseline still exits 2. There are 9,003
pending sources and all 31 feature contracts remain pending. All 3,748 previous
artifact pins are preserved. The total is now 3,753 pins.

## Required next work

Implement connected proportional editing with the pinned surface propagation
algorithm. An edge-only shortest-path replacement is insufficient. Then complete
normal and gimbal frames, face attribute correction, safe singular frames and
mirror correspondence. Resolve every numeric mismatch. Rerun the full unchanged
2,406-case gate after these changes.

Repository-read-denied execution of the new transform operation remains unrun.
The fixed release performance gates, required three-platform CI, dependency
integration and independent issue acceptance remain unrun. Full numeric domains,
random sequence/distribution and custom-normal authoring remain on the roadmap.
Passing the current subset cannot close this issue or a milestone.
