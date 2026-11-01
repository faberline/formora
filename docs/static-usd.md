# Native static USD gate (#86)

Status at initial freeze: no product or device test had passed yet.
The contract below was frozen before exporter code. Current evidence is recorded
in `docs/verification/static-usd.md`; this document is not a live pass report.
Base: c67c23031cf305b4730702de689160a5c91abf06 (unmerged PR #81).
The editable mother file is Formora scene JSON. USD is a static projection.

## Frozen contract v1

CLI: `formora scene export --scene PATH --root ID --format usda --output NEW.usda`.
MCP: `scene_export` with `root`, `format` and `output`. Both use one Rust core.
Only the selected entity and all descendants are exported. No external ancestor is
allowed for the selected root. Root pivot remains its authored origin. A root at
identity with geometry resting on Z=0 has a bottom-centre pivot. Export does not
change source bytes, revision or undo history. Camera and light siblings outside
this subtree do not enter the asset. The stage is right-handed Z-up, metresPerUnit=1.
Apple imports into Y-up: test (x,y,z) -> (x,z,-y) with the independent asymmetric
witness. No implicit game-unit conversion is allowed.

Support explicit MeshAsset triangles and polygons, static Empty hierarchy,
right-handed winding, double-sided=false, subdivision=none. Export authored
points as point3f only when each conversion error is <=1e-6. Reject out-of-range
values. USD matrices are row-vector matrices; transpose Formora column-vector
local matrices. Preserve source IDs with collision-free hex prim identifiers,
source name/mesh/vertex/face IDs as custom data. Do not use human names as paths.
Preserve triangle and polygon order separately with exact source kind/ID arrays.
Resolve normals with the same explicit-corner > face > automatic rule as preview.
Export face-varying normals and complete UV layers (active layer named st; other
layers use collision-free names). Reject inconsistent UV coverage. Materials use
UsdPreviewSurface diffuseColor, opacity, roughness and metallic, with per-face
UsdGeomSubset bindings and an entity material fallback. No texture capability is
claimed. Material float conversion has the same <=1e-6 limit.

Reject builtin Geometry Cube/Plane (author explicit assets first), empty geometry,
isolated vertices or loose edges (not rendered), nonzero simulation time, doors,
annotations, nonempty editor/object contexts, skinning/weights/groups/seams/custom
integer attributes, mesh diagnostics, camera/light descendants, missing material,
missing reference, empty subtree, depth above 128, or data beyond the frozen budget.
Recipe/editor state is not a runtime USD feature: reject nonempty recipe/editing
rather than silently dropping it. Use explicit set_mesh_asset inputs for this gate.
All scene and mesh validation runs before output creation. All relevant source
IDs and native topology remain in the mother file. USD does not promise a Formora
round trip. Full mother-file save/reopen equality is checked separately.

UTF-8 strings use USD escaping (quote, backslash and control bytes). New-file-only
output: stage to a sibling temporary file, flush/sync, publish with a non-replacing
hard link, remove temporary file. Existing file/symlink is an error. Failure must
not publish a partial successful file. Return format, source revision/root, mesh,
vertex/face counts, bytes and SHA-256. Unknown format is an error, not inferred
from extension. Only `.usda` targets are accepted. No USDZ or GLB support is claimed.
Bounds: <=128 entity depth, <=4096 entities, <=200000 vertices, <=200000 faces,
<=800000 face corners, <=256 MiB output. These are v1 limits, not performance proof.

## Frozen independent inputs and checks

`baseline/static-usd/{crate,rock,workbench,radio}/create.json` are original recipes.
Run init, create, edit, inspect in fresh processes. Each edit moves vertex v0 and
changes the body material roughness. `expected.json` is independent arithmetic,
not exporter output. Four models use explicit triangles and visible material parts.
Dimensions are proposed authoring dimensions, not ASHFALL gameplay dimensions.
Band/grille/dial details can extend beyond the body. Model bounds must use actual
geometry; the advertised body size is not silently treated as full asset bounds.

`axis-witness.usda` and `axis-witness-expected.json` were written by hand before
exporter implementation. They fix winding, unequal axis lengths, translation,
hierarchy and the Apple axis mapping. All continuous comparisons <=1e-6; indices,
IDs, counts, hierarchy and process exit codes exact. Apple may duplicate vertices
for corners: compare complete triangle corner geometry/materials, not only counts.
Require actual Apple mesh buffers/material values and per-node transforms.
A bounding box or screenshot alone cannot pass geometry/material/hierarchy tests.
Controls must mutate axis, unit, material, missing geometry and parent relation,
and reject failure/missing process receipts. Retain the first failure.

Pinned upstream source bytes, SDK interface excerpts, compiler and capture method
are in `baseline/static-usd/source-pins.json`. SDK availability is source evidence,
not an actual old-OS/device test. Apple hardware tests must record actual OS,
SDK, hardware, tool digest, inputs, output, command, PID, wait and exit. Minimum
compile targets remain macOS14/iOS17; iOS execution remains unrun until performed.

Capacity workloads/clocks/three samples are fixed in `performance-contract.json`.
Keep old per-data 250ms core/2000ms pipeline and two-data 500/4000ms limits. Full
validation stays inside each clock. Small models cannot establish capacity pass.
GPU quality/startup and Apple load are separate checks. All required failures,
skips or unrun checks keep this gate incomplete. Old rotation/Windows CI failures,
source seals and milestone acceptance remain. No milestone is closed by this gate.

## Rebuild the four assets

Use the new candidate branch from PR #87. Its base PR #81 is not integrated.
Build with Rust 1.85 and `--features preview`. On hosts with a separate Homebrew
Cargo installation, put the chosen rustup toolchain's `bin` directory first on PATH;
`rustup run ... cargo clippy` alone can still select Homebrew's cargo-clippy.

For each ID `crate`, `rock`, `workbench`, `radio`, run these native commands with a
new scene and a new output path. `NAME` below is a shell variable for that ID.
The third operation is the explicit whole-model pivot correction. It retains the
original create/edit requests, vertices and material values. Final revision is3.

```sh
NAME=crate
./target/debug/formora scene init --scene "/tmp/$NAME.json"
./target/debug/formora scene apply --scene "/tmp/$NAME.json" --request "baseline/static-usd/$NAME/create.json"
./target/debug/formora scene apply --scene "/tmp/$NAME.json" --request "baseline/static-usd/$NAME/edit.json"
./target/debug/formora scene apply --scene "/tmp/$NAME.json" --request "baseline/static-usd-pivot/$NAME.json"
./target/debug/formora scene inspect --scene "/tmp/$NAME.json"
./target/debug/formora scene export --scene "/tmp/$NAME.json" --root "$NAME" --format usda --output "/tmp/$NAME.usda"
```

MCP uses `formora mcp --scene PATH`. Call `scene_apply` with exactly the same three
request objects, then `scene_inspect` and `scene_export`. The export arguments are
`{"root":"crate","format":"usda","output":"/tmp/crate.usda"}`. Output must be new.
Inspect/save/edit use the existing shared scene core. `scene_export` returns actual
root/revision/counts/bytes/SHA-256 and the complete-validation core duration.

Native multiview helper: `python3 tools/static_usd_native_views.py BINARY MOTHER NEW_DIR`.
It makes preview copies with cameras/lights. It does not change the mother.
Apple tool: compile `tools/apple-static-usd/Inspect.swift` with `xcrun swiftc`,
`-swift-version 5 -parse-as-library -target arm64-apple-macosx14.0`. Run its output
as `INSPECTOR MODEL.usda NEW_REPORT.json NEW_CAPTURE_DIR`. Actual GPU access is
required. Check buffers with `python3 tools/static_usd_apple_check.py REPORT MOTHER ROOT`.
Minimum iOS17 API typecheck is separate; iOS hardware execution remains unrun.

Textures, skinning, rigs, character animation, LOD, USDZ and a native Formora USD
importer are not implemented by this gate. ASHFALL still must choose its game-unit
conversion and adopt/independently test a pinned candidate. Its repository was not
modified. Native JSON is the editable source; USD is a static delivery projection.
