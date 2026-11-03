# CPU material projects

Status: CPU slice A is implemented on this branch. Functional CI is pending.
The Rust window/GPU slice B and Swift app integration are not implemented here.

The CLI and MCP use `material_project` in the Rust library.
This module validates a complete static polygon source, resolves project resources,
and samples an image at explicit texture-space UV coordinates.
It does not render a mesh or compute a camera pixel, ray hit, or interpolated surface UV.

## Fixed profiles

| Item | Accepted value |
| --- | --- |
| Project schema | `1` |
| Project profile | `formora-base-color-image-v1` |
| Source profile | `formora-static-polygons-bb025-v1` |
| Declared source producer | `bb025ce17432ba0419008d0cd794222127e7ff92` |
| Image | RGB8 PNG with no transparency, animation, or embedded color metadata |
| Color declaration | Explicit `srgb` |
| Filter | `nearest` |
| Address mode | `clamp_to_edge` |

The producer field is a declaration. It is not proof that the old program ran.
The complete pinned Rust scene and mesh types validate the source.
This includes native polygons, edges, UV layout, recipes, editing state,
integer attributes, vertex groups/weights, transform modes, and scene contexts.
The adapter keeps the exact source bytes. It does not save a serialized replacement.
Native optional fields retain their pinned defaults when read.
Missing normals remain missing. Unused vertices and all material slots remain present.

This profile permits only empty entities and mesh entities with asset geometry.
It requires time zero, empty doors/annotations, and no active camera.
Roots must be distinct top-level entities. Their descendants must equal all entities.
All and only referenced meshes and materials must be present.
Material references include unused non-null mesh slots.
Every texture binding must be used by at least one face.
Every image must be referenced by a binding.
An entity material overrides asset slots, as in the pinned native preview.
Every face using a bound material must contain its named UV layer.
The native validator checks UV corner counts, finite numbers, topology, contexts,
and all native references. A missing named layer returns `missing_uv` first.

The old main-only model importer remains separate.
It does not load this source profile. D25 is also outside this profile.
There is no source field removal, automatic profile upgrade, or native triangulation save.
This CPU slice adds no skeletal animation or game state interpretation.

## Project files

The [frozen schema bundle](../schemas/material-project/contracts.json) contains
`project`, `source`, `inspect_request`, `sample_request`, `import_request`, and `receipt`.
JSON Schema checks shape. Rust also checks hashes, paths, references, native validity,
resource closure, binding use, and the supported image subset.

[project.json](../tests/fixtures/texture/project.json) is a complete example.
It binds the unchanged Ashfall panel, image, `fixture_white` material, and `uv0` layer.
The image bindings live in this new descriptor.
The old native `Material` type still has no image field.
An old `Scene::load` call alone cannot load a texture project.

The caller supplies `expected_project_sha256` for the exact descriptor bytes.
Rust checks that hash before it trusts paths, profiles, roots, or payload hashes.
It checks raw scene and encoded PNG hashes, then uses those same verified byte buffers.
The source/profile declarations, color rules, and bindings are all bound by the descriptor hash.
Duplicate JSON keys and unknown descriptor/request fields fail.

Resolve resources from the descriptor directory, never the process working directory.
Paths use forward slashes and nonempty components.
Absolute paths, `.`/`..`, drive/UNC forms, backslashes, NUL, links,
and paths outside the project are errors.
Resource paths must be distinct and cannot use the output descriptor name `project.json`.
There is no resource search, download, or fallback image.
An existing project can move as a whole without changing its descriptor or resource bytes.

Import creates a new owned directory after validation.
It copies exact scene and PNG bytes, then writes the exact descriptor as `project.json`.
All files are synced before success. Existing output paths are never overwritten or deleted.
An I/O failure can leave an incomplete new directory.
The caller must adopt a saved result only after an `ok: true` import receipt.
Inspect and sample do not save or adopt a model.
No operation changes the open MCP scene, an active app model, or a game save.
The app host must keep its model storage separate from its save storage.

## Sampling and color

UV `(0,0)` is the bottom-left corner. Decoded PNG row zero is the top row.
For width `W` and height `H`, select:

```text
x = min(W-1, floor(clamp(u,0,1) * W))
y = min(H-1, floor((1-clamp(v,0,1)) * H))
```

Reject nonfinite coordinates. Finite coordinates outside the unit square clamp to its edge.
Queries identify an existing entity and source polygon or triangle.
They supply texture-space coordinates directly. They do not specify a location on the model.
The result includes the selected material/image, texel index, exact RGB8 with alpha 255,
and linear RGB with alpha one.
These are image texels. They do not multiply the native material's base color,
apply lighting/roughness/metallic, or represent a rendered surface color.

Convert normalized sRGB component `c` to `c/12.92` when `c <= 0.04045`.
Otherwise use `((c+0.055)/1.055)^2.4`.
This follows the [pinned W3C sRGB transfer function](https://www.w3.org/TR/2026/CRD-css-color-4-20261103/#predefined-sRGB).
It is not a full display color-management or PBR contract.

The fixture has no embedded color metadata. The descriptor must declare `srgb`.
Other color spaces and embedded profiles are explicit unsupported cases in this slice.
RGB8 keeps the first slice's alpha behavior unambiguous.
RGBA, grayscale, palette, 16-bit, transparency, and animated PNG require later profiles.

| UV | Expected RGBA8 |
| --- | --- |
| `(0.25,0.25)` | `[0,0,255,255]` |
| `(0.75,0.25)` | `[255,255,0,255]` |
| `(0.25,0.75)` | `[255,0,0,255]` |
| `(0.75,0.75)` | `[0,255,0,255]` |

The saturated fixture colors cannot detect a missing transfer function.
A separate pure gray sample checks that `128/255` maps to
`0.21586050011389926`, with absolute error at most `1e-12`.
The original fixture is not changed to add gray.
CLI and MCP use the same Rust sampler. Exact source bytes and RGB8 values are required.
This is CPU consistency, not GPU or native display acceptance.
Slice B must freeze its actual camera, interior sample pixels, output color settings,
and one-code-value output tolerance before an authorized run.

## CLI and MCP

Build the CPU executable without `preview`:

```sh
cargo build --locked --no-default-features
target/debug/formora material schema
target/debug/formora material inspect --request inspect.json
target/debug/formora material sample --request sample.json
target/debug/formora material import --request import.json
```

Use `--request -` to read JSON from standard input.
Every CLI operation returns a JSON receipt. Success exits `0`; failure exits `1`.
Bad CLI options or a missing request flag exit `64`.
An unreadable or malformed request file returns an `invalid_request` failure receipt.

An inspect request has `project` and `expected_project_sha256`.
An import request adds `output`, which must be a new directory.
A sample request adds a nonempty `samples` list:

```json
{
  "project": "tests/fixtures/texture/project.json",
  "expected_project_sha256": "21ed6a4ded954936347102b1b9d44c2c990aab7aaf0d21ebe1ea1ee911065f0e",
  "samples": [
    {"entity":"mesh", "face":{"kind":"polygon","id":"p0001"}, "uv":[0.25,0.25]}
  ]
}
```

Run this example from the frozen source checkout root.
The example hash binds the checked-in descriptor bytes.
Compute the hash from raw descriptor bytes, not a parsed/rewritten JSON object.
MCP names are `material_project_schema`, `material_inspect`, `material_sample`,
and `material_import`. Their request fields are the same as the CLI JSON fields.
They call the same Rust functions.

For structurally valid MCP arguments, failed operations return a failure receipt
as `structuredContent` and set `isError: true`.
Missing, wrongly typed, or unknown arguments return text with `isError: true`
and no `structuredContent`, before the operation starts.
Correctly typed arguments with an invalid hash string reach the core
and return an `invalid_request` receipt.

Success receipts state the operation, validated source/profile, source/image/project hashes,
roots, counts, and requested samples. Only import success has `saved_location`.
Failure receipts contain only version, `ok: false`, code, stage, message,
and an optional observed raw project hash. Success fields must be omitted, not set to null.
`validator_revision` hashes compiled-in source inputs, including the pinned compatibility source.
It is not a Git commit, executable hash, or reproducible-build attestation.
Record the delivered source archive and executable identity separately.

## Source provenance and verification

The [compatibility provenance](../compat/bb025/PROVENANCE.json) binds all 54 upstream
source files and the original Cargo manifest to exact SHA-256 values.
The Rust source files are copied unchanged from the exact producer revision.
The wrapper manifest changes only the package name and retains the library name.
This avoids a local package-name/version collision.
Default features are off. The dependency is excluded from the root workspace.
No GPU dependency is active in the CPU dependency graph.
The full upstream baseline/test datasets are not part of this dependency copy.
Their historical checks and failures remain separate; this slice does not claim to rerun them.

The Ashfall fixture manifest remains
`5e61b47734aa27c01dd61bf93a8897746c4e9fc964d0b2ce42ed12b985d71f6a`.
The original scene remains
`c8a790703dfaad4aa061667f29830b9877252afdd13a809c0d279f0539223b29`.
The PNG remains
`71676a057ca47df88bcaa37191d0be9c2ec46eae37f882cb4ecb01140fff8607`.
The old manifest and requirements are copied as provenance, not as a new execution result.
The new descriptor is a separate file with its own hash.

Pure memory tests check native source identity, original polygon/UV bytes, gray transfer,
quadrants, clamps, invalid hashes/profiles/paths/UV/image data, and failure receipts.
Real CLI/MCP tests check save/reopen, project relocation and nested resources,
missing images/UV, linked resources, descriptor tampering, existing output,
and preservation of an open scene/game save.
The official MCP client checks schema validity and the four quadrant samples.
Functional tests run in normal three-platform CI. They are not run as local pure units.

Passing this slice does not accept a Swift app, native window, image-rendered mesh,
original complete model set, rig, skinning, clip, socket, performance gate, or milestone.
