# Automatic normal foundation for issue #48

This is one part of the open mesh transform issue. It does not complete that issue,
the modeling milestone, custom normal editing, or the full product roadmap.
The complete 1,203 transform cases remain required by
[`mesh-transform-core.md`](../contracts/mesh-transform-core.md).

## Behavior

`scene inspect --mesh-asset ID --normals` returns face and corner normals.
The official MCP `scene_inspect` tool accepts the same `normals: true` option.
Both use the shared Rust resolver. The raw asset remains in the response.
The query does not change the scene, its revision, saved bytes or undo history.

Preview uses stored corner normals first. A stored polygon normal is next.
Missing values use automatic normals from the actual geometry.
Surface picking does not compute shading normals. Selection markers do not alter
its geometry. Explicit zero corner normals still use the preview's existing
geometric fallback when a normalized shading vector cannot be formed.

The source has separate face and corner normal paths. Triangle and quad face
queries use their specialized cross products. Automatic corner calculation uses
Newell face normals. The distinction is retained for non-planar and degenerate
faces. Smooth fans use angle weights and the fixed source's f32 approximation.
Flat faces, wrong winding and non-manifold edges split mixed smooth fans.
The all-smooth point domain averages all faces incident on a vertex.
UV seams do not split shading fans. Triangle and polygon IDs remain typed.

Automatic calculations reject geometry or intermediate arithmetic outside their
finite f32 range. Raw asset queries still use the existing f64 geometry model.
This bounded range is not full numeric-domain acceptance.

## Inputs and gates

`baseline/fixtures/mesh-normals.json` contains 21 authored cases. They cover flat,
smooth and mixed shading, reversed winding, non-manifold edges, disconnected
fans, collinear corners, legacy triangles, coincident positions, non-planar
quads, a concave polygon, three scales, a sliver and the transform fixture's
initial geometry. `tools/generate_mesh_normal_cases.py` must reproduce this file.
The inputs were committed before capture. They contain no measured normals.

The source is Blender 5.2.3 LTS, build `e13b728c6880`.
Its executable SHA-256 is
`de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619`.
The capture uses CPU mesh calculations. It does not claim viewport transform
context coverage. Each record binds the authored positions, faces and smooth
flags. Its manifest binds the executable, adapter and fixture hashes.
Pinned algorithm sources and licenses are in
`docs/evidence/mesh-transform-core/normals/source/manifest.json`.

`tools/normal_runtime_smoke.py` runs each case through CLI and the official MCP
client. It compares every normal component with the fixed absolute limit of
`1e-6`. It also checks repeat queries, invalid targets, saved bytes, and undo.
The input asset has no normal payloads. The Rust executable receives no source
result. Comparator tests must reject wrong values, missing data, duplicate IDs,
changed authored geometry, stale hashes and incomplete captures.

`tests/normals.rs` uses independent geometric expectations. With the preview
feature, it also checks actual render vertex normals and unchanged surface hits.
`tools/normal_gpu_evidence.py` requires native Metal. It first changes only the
smooth flags, then edits actual positions. Both image changes must exceed 500
pixels at 640×480. A fresh process must produce an identical saved-scene image.

## Commands

Use actual Rust 1.85 compiler and rustdoc child paths when building.
Use the locked MCP requirements for the Python runtime check.

```sh
cargo fmt --all --check
cargo clippy --locked --all-features --all-targets -- -D warnings
cargo test --locked --all-features --all-targets
python3 -m unittest discover -s tools/tests -v
python3 tools/normal_runtime_smoke.py /absolute/formora /absolute/new-output
python3 tools/normal_gpu_evidence.py /absolute/formora /absolute/new-gpu-output
```

All original primitive, selection, creation-context, performance and GPU gates
remain required for issue #48. Failed, skipped and unrun jobs cannot pass.
Three-platform CI, integration and independent acceptance remain required.

## Recorded local results

Rust source candidate `5b8cbadd419cde91f8f5518dfe9790493047c0de`
passed formatting, Clippy and 125 Rust tests with actual Rust 1.85 child tools.
The initial Python suite passed 68 tests. The final comparer adds an authored
asset identity check and passes 69 tests. Rust source and the executable did
not change between these checks.

All 42 final CLI/MCP normal queries pass. Their maximum component error is zero.
The final comparer rejects a changed input asset even when its normals match.
The original 162 generation, eight scale, 1,060 selection, 262 creation-context
and 57 payload cases also pass. Their complete raw records remain under
`docs/evidence/mesh-transform-core/normals/local/`.

The native Metal normal sample changes 20,305 pixels from smooth to flat shading.
The geometry edit changes 19,009 pixels. Its fresh reload is byte-identical.
All eight original Metal samples and both original repository-read-denied
execution checks pass with the same executable.

The initial verification manifest binds the earlier comparer and baseline lock.
The final verification manifest separately binds the stricter comparer, its
69-test Python run, the unchanged Rust source, and all final source pins.
The strict baseline still exits 2: 9,003 sources and all 31 feature contracts
remain pending. No product transform, issue or milestone is accepted here.
