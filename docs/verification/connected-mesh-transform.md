# Connected mesh transform progress

Issue #48 and PR #49 remain incomplete. This change implements connected
proportional editing. It does not accept a feature, issue or milestone.

The Rust candidate is `34a32d7328f241bc9229c2e39357744d5ea46baa`.
The source and limits were fixed before implementation in
`docs/contracts/connected-mesh-transform.md`.

## Behavior

Connected distance propagates through visible polygon surfaces and along loose
edges. It can cross a face interior. It does not replace surface distance with
an edge-only shortest path. Hidden faces block surface shortcuts. Visible edges
can still supply a boundary path. Hidden edges and vertices block their paths.
Disconnected vertices remain unaffected, even when their positions coincide.

The algorithm uses the actual object's linear world frame. Non-uniform and
reflected scales affect distance. Translation does not. Connected distance takes
precedence over projected distance. Individual centres follow the originating
selected island. Vertex-mode isolated seeds supply their own centres. Other
modes retain the pinned source's no-island fallback.

The existing falloffs consume these actual distances. Random falloff preserves
its explicit replay seed. A work limit counts edge processing, face searches,
propagation attempts and scheduling. It uses `max_components * 64` with
saturating integer arithmetic. Arithmetic overflow and work-limit failure return
errors before any edited asset is published.

## Full source comparison

The focused check executes all 114 connected cases through CLI and official MCP.
All 228 comparisons pass. Focused success is not the complete transform gate.

The full unchanged suite executes 2,406 cases. It now matches 1,830 results:
1,818 completed transforms and 12 expected cancellations. There are 576 failed
comparisons. The full gate still returns exit 1.

Exactly the 228 connected comparisons changed from failed to matched. None of
the previous 1,602 matches regressed. Both interfaces produce identical raw
results for every case. Position, normal and UV limits remain `1e-6`.

Each interface still has these 288 failures:

| Failure | Cases per interface |
|---|---:|
| Normal orientation | 114 |
| Gimbal orientation | 114 |
| Face attribute correction | 18 |
| Safe singular frame behavior | 12 |
| Mirror | 6 |
| Local geometry numerical mismatch | 14 |
| Normal numerical mismatch | 6 |
| World position numerical mismatch | 4 |

Full requests, initial and final states, receipts and failures remain in
`docs/evidence/mesh-transform-core/connected-runtime/`. Its `analysis.json`
compares the current results with the complete first run. No failing case was
removed or weakened.

## Other verification

Formatting, Clippy, 146 Rust tests and 74 Python tests pass with actual Rust 1.85
compiler and rustdoc child paths. Independent geometric tests distinguish a
surface shortcut from a wire path. They cover hidden barriers, disconnected
coincident IDs, reflected non-uniform scale, translation independence,
projection precedence, centre inheritance, seeded replay, budget rejection,
arithmetic errors, save failure, undo and fresh load.

The official MCP regression and all 42 normal-query cases pass. Metadata remains
structurally valid. The strict baseline still exits 2, with 9,003 pending sources
and all 31 feature contracts pending. All 3,753 prior source pins are preserved.
There are now 3,755 pins.

A copied executable also runs with all source repository reads denied by the
macOS sandbox. An independent authored shape supplies no normal payloads. The
check verifies connected translation, rotation, reflected resize, shared asset
ownership, attributes, undo and fresh reload against geometric expectations.
It does not import any measured source geometry or normal.

Native Metal renders a 25-vertex authored grid. Connected editing changes 21
vertices and 21,341 pixels. The seed moves by the requested amount. The four
outer corners remain unchanged. A fresh process produces a byte-identical image.

The evidence index is
`docs/evidence/mesh-transform-core/connected-implementation-manifest.json`.
Isolation and GPU drivers are retained beside their results.

## Remaining acceptance

Complete normal and gimbal frames, UV correction, safe singular frames and
mirror correspondence. Resolve all numeric mismatches. Keep the full source
gate and its limits. Run the fixed release performance gates and all required
final regressions at the finished candidate. Required three-platform CI,
dependency integration and independent issue acceptance remain unrun.
Full numeric/capacity domains, random sequence/distribution and custom-normal
authoring remain on the complete roadmap. No milestone may close from this subset.
