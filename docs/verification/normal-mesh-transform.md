# Geometric normal transform progress

Issue #48 and draft PR #49 remain incomplete. No feature or milestone is accepted.
The Rust candidate is `3befda13bc356444056f5c6ffeabd1b800cc3ac5`.
Its executable SHA-256 is
`fb5b3ace6fe80ec210bd52a665cbbff18e121560cf9fb523bd1bf16a0d84299c`.

The contract and primary source were fixed before implementation in commits
`f64ed61` and `c171cc4`. See `docs/contracts/normal-mesh-transform.md`.
The additional source files come from frozen Blender commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`.

## Behavior

The Rust core derives normal orientation from actual geometry and persistent
selection. It uses geometric face and angle-weighted vertex normals. Shading
payloads and smooth flags cannot redirect these geometric normals. Incident
hidden faces still contribute to vertex geometry normals.

Active selection follows the pinned vertex, edge and face rules. The active
face takes precedence over the last face history record. Complete contiguous
vertex history supplies reverse ordering. Other cases use actual selected
faces, a triangle, an edge or vertex pair, one vertex, or a larger vertex set.
Boundary winding, explicit edge endpoint order, triangle/quad/ngon tangents and
degenerate fallbacks come from the pinned source.

Face and vertex frames use the inverse-transpose object frame. Edge frames use
the forward frame and then remove the component along the transformed edge.
Individual NORMAL transforms use a separate frame for each selected island.
Connected proportional vertices inherit their origin island's centre and frame.
Receipts include the common `basis_world` and the actual per-influenced-vertex
`component_basis_local` matrices for this individual mode.

All calculations run before publishing the asset. Invalid arithmetic, failed
batches and failed saves leave the scene, disk and undo unchanged. Actual
geometry changes still update automatic normals and edited recipe state.

## Source comparison

The focused diagnostic executes all 117 NORMAL source cases through CLI and
official MCP: 234 comparisons. It matches 222 and fails 12. In each interface,
two world-position numeric cases, one rotation numeric case and three singular
object frame cases still fail. Focused success is not claimed.

The complete unchanged suite executes all 2,406 comparisons. It matches 2,052:
2,040 completed transforms and 12 expected cancellations. There are 354 failed
comparisons. The full gate still returns exit 1.

Exactly 222 comparisons changed from failed to matched. All new matches are
normal orientation. None of the previous 1,830 matches regressed. CLI and official
MCP produce byte-identical raw results for each case. Position, normal and UV
limits remain `1e-6`. Every failure remains in the evidence.

Each interface retains these 177 failures:

| Failure | Cases per interface |
|---|---:|
| Gimbal orientation | 114 |
| Face attribute correction | 18 |
| Safe singular frame behavior | 12 |
| Mirror | 6 |
| Local geometry numeric mismatch | 15 |
| Normal numeric mismatch | 6 |
| World position numeric mismatch | 6 |

The raw comparison data and analysis are in
`docs/evidence/mesh-transform-core/orientation-runtime/`.

## Other verification

Formatting, Clippy, 158 Rust tests and 74 Python tests pass with actual Rust 1.85
compiler and rustdoc child paths. Twelve new independent tests cover geometric
normal derivation, hidden incident faces, shading independence, active history,
inverse-transpose under reflected nonuniform scale, wire and coincident
fallbacks, individual tangent frames, connected inheritance, triangle/ngon and
typed legacy faces, larger vertex sets, undo, save/reload and failure atomicity.

Official MCP regression and all 42 normal queries pass. Metadata remains
structurally valid. The strict baseline exits 2. It still has 9,003 pending
sources and all 31 feature contracts pending. All 3,755 prior artifact pins are
preserved. There are now 3,762 pins.

A copied executable also runs with source repository reads denied by macOS.
An unseen tilted rectangle supplies only authored points, topology and attributes.
Geometric expectations independently check normal translation, constrained
rotation and individual reflected resize. Shared ownership, unchanged attributes,
undo and fresh reload pass. Inputs include no measured normals or geometry.

Native Metal renders a tilted 25-vertex grid. The geometric normal transform
moves the seed to `[0.72, 0, 0.96]`. It changes 21 vertices and 23,288 pixels.
Outer corners stay fixed. Fresh-process reload produces a byte-identical image.

The evidence index is
`docs/evidence/mesh-transform-core/orientation-implementation-manifest.json`.
Isolation and GPU capture drivers are stored beside their results.

## Remaining acceptance

Implement gimbal orientation, UV correction, singular frames and mirror behavior.
Resolve all numeric mismatches, including the three remaining normal-frame
numeric cases. Then run the fixed release performance, final regression,
three-platform CI, dependency integration and independent acceptance gates.
Full numeric/capacity domains, random sequence/distribution and custom-normal
authoring remain on the complete roadmap. No milestone may close from this subset.
