# Rust mesh component transform contract

Issue #48 implements the eight pending contracts introduced by #46 / PR #47.
The complete 1,203-case source suite remains the target. An early supported subset
is progress only. It cannot complete this issue or accept a feature or milestone.

## Shared operation and result

Use one Rust operation core for CLI and official MCP.
Locate the target through its entity and shared asset.
Compute the actual working basis, pivot centres, influence and changed component IDs.
Publish success receipts only after the complete batch is validated and saved.
Keep query/undo/save/reload, stable typed triangle/polygon IDs and instance ownership.
Unrelated entities, materials, UV layout, weights, seams, hidden and selection state remain correct.
Mark edited recipes. Never replace identity using position equality.

Support translate, rotate and resize with the fixed orientation, pivot, constraint,
custom matrix, parent, mirror, face-attribute and proportional options.
The adapter maps authored source request semantics to documented native parameters.
It may not derive an input vertex, normal, basis, pivot or influence from a measured answer.
RANDOM uses an explicit preserved/reported seed for agent replay.
Its source comparison retains the fixed support policy, not a false sequence match.

## Normals and rendering

Compute automatic face and corner normals from actual Rust geometry.
Handle flat and smooth faces, smooth fans, non-manifold/opposite-winding boundaries,
loose vertices, degenerate faces and mixed legacy triangles/polygons.
UV seams do not imply sharp normal edges.
Existing explicit normal payloads remain visible and queryable.
A read-only resolved-normal query must use the same precedence as rendering.
It may not rewrite the asset, its revision or history.
Transforms must update the geometry-dependent normals they invalidate.
Full custom-normal authoring remains a distinct required roadmap function.

## Fixed gates

- Execute all 1,203 source cases through each of CLI and official MCP: 2,406 cases.
- Keep the source comparer and componentwise 1e-6 position, normal and UV limits.
  Compare all 1,179 deterministic cases and separately check all 24 stochastic cases.
- Initial data come only from authored fixture values. The executable must work
  without Blender, Python, reference outputs or repository reads.
- Add independent geometric normal, mixed topology, shared instance, frame,
  pivot, influence, mirror, attribute, replay and failure tests.
- Invalid/stale requests, unsafe frames, over-budget operations, failed batches
  and failed saves must roll back without success receipts or undo entries.
- Retain all existing Rust/Python, MCP, 262 creation-context, 162 generation,
  eight scale, 1,060 selection, 57 payload, performance and native GPU gates.
- Use actual Rust 1.85 compiler child paths. Run the fixed M1 Max/macOS/release
  100×100 grid samples in `mesh-transform-baseline.md`: core <=250 ms and
  operation/save/reload <=2000 ms, three times for each basic operation.
- Native Metal must show real modifications, byte-identical fresh reload images
  and unchanged surface picking when markers are toggled.
- Keep exact executable/source/shader/input/query/receipt/output hashes and raw measurements.

Required three-platform CI, dependency integration and integrated independent
acceptance remain necessary. Failed, skipped and unrun gates cannot pass.
`agy:done` stays open until those gates pass.
Snapping, merge/split, other modes/data types, full numeric/capacity domains,
random sequence/distribution and full custom-normal editing remain on the full roadmap.
