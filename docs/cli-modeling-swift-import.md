# Rust CLI modeling and Swift model import

Status: adopted direction; first static-main schema and CPU CLI/MCP implementation on this branch.
CLI/MCP functional validation in CI is pending. Swift app hosts and legacy profiles remain unimplemented.

## Priority

Formora first completes Blender-style modeling through its Rust CLI.
Agents use the CLI and MCP through the same Rust operations.
Each operation needs a defined input, an inspectable result, and tests.
Models must remain editable after save and reopen.
The fixed Blender baseline remains the source for modeling behavior.

The GitHub milestones remain the roadmap.
This priority does not close a milestone or accept unfinished features.
Broad engine replacement, new Rust window work, and full app performance work
do not lead this modeling slice.
Their existing requirements and failure records remain valid.

## Ownership

| Part | Owner |
| --- | --- |
| Model creation, topology, attributes, transforms, validation, and files | Formora Rust core |
| Agent commands and machine-readable results | Formora Rust CLI and MCP |
| File selection, import progress, model information, and human controls | Each app's Swift interface |
| Import validation, owned model data, and game state | Each app's Rust core |
| Rendering host and the Swift to Rust call boundary | A separate app integration task |

Swift passes an import request to Rust.
Swift must not copy modeling algorithms or scene validation into its UI.
Rust returns a versioned result that Swift can display.
This does not require a full UI rewrite in one change.

## What exists

The default main branch has native scene JSON, Rust scene operations, and CLI/MCP entry points.
It does not yet have this shared model package or import adapter.

The separate frozen integration candidate at
`d25a2a7ed7c16fa8d61f70e9c2f65926e962303d` adds CPU inspection and static USDA export.
That candidate is not the default main branch.
An export command is not an import implementation.
It does not prove that any Swift app can load the output.

The three consumers reported these current boundaries:

| App | Current gap |
| --- | --- |
| Ashfall | SwiftUI and a Rust game bridge exist. The model is not packaged or loaded by the app. The crate still uses a placeholder. |
| Vortex | A Swift process bridge and Rust city service exist. The fixed 56-model catalog is not a general file importer. |
| FF Modern | Rust loads native scene JSON and an app-specific model index at startup. There is no Swift app host or file import entry. |

These are source inventories, not completed Swift import tests.
GLB, OBJ, USDZ, and general USD import are not claimed as supported.

The new package is independent of each app's existing file wrapper and catalog.
In Vortex, it is not a `{scene, manifest}` city Presentation.
It does not supply or invent a CityScene, city provenance, revision, or targets.
It is not input to the fixed 56-model catalog loader.
Model IDs, filenames, roots, and mesh counts do not inherit that catalog's rules.

## First shared package

The editable source is Formora native scene JSON.
A display export is optional. It must not replace the editable source.
The first package has a manifest and `model.scene.json`.
This package is the first static profile implemented on this branch.

The first CPU slice on this branch implements `formora model schema` and
`formora model import --manifest PATH --expected-manifest-sha256 HASH --output NEW_DIRECTORY`.
MCP exposes the same Rust core as `model_package_schema` and `model_import`.
The frozen review files are [manifest](../schemas/model-package/manifest.schema.json),
[request](../schemas/model-package/import-request.schema.json), and
[receipt](../schemas/model-package/receipt.schema.json).
These commands are not yet on the default main branch.

| Manifest field | Contract |
| --- | --- |
| `manifest_schema_version` | Integer `1`. Reject unknown versions. |
| `scene_file` | Relative package path to `model.scene.json`. |
| `scene_sha256` | SHA-256 of the exact source file bytes. |
| `scene_schema_version` | Must match the native scene's supported schema. The current schema is `1`. |
| `scene_profile` | Named field and capability contract. A schema number alone does not prove compatibility. |
| `producer_commit` | Exact Formora producer revision for this unreleased profile. Rust still validates the file. |
| `roots` | Explicit model root entity IDs. Rust checks the referenced hierarchy and assets. |
| `meters_per_unit` | Explicit positive finite scale. Do not infer it from a catalog or a renderer. |
| `up_axis` | `Z` for this first source profile. |
| `coordinate_system` | `right_handed` for this first source profile. |
| `capabilities` | State the material, geometry, and animation features used by the source. |
| `display_exports` | Optional files with explicit format, relative path, SHA-256, and supported scope. |

Swift supplies `expected_manifest_sha256`, the hash of the exact manifest file bytes.
Rust checks those same bytes before it trusts roots, units, profile, or payload hashes.
Hash the raw file. Do not parse and serialize it again before hashing.
The manifest then binds the exact scene and any listed display file bytes.
The scene hash alone does not bind units, roots, or the profile.
Reject a changed manifest or payload before saving any imported data.

Native scene JSON does not itself declare all of this unit metadata.
The package author must supply it.
Rust checks the declaration before an app adopts the model.
Rust also checks that the declared profile and capabilities match the actual source fields.
Do not accept a newer scene only because its schema number is still `1`.

## First source profile

`formora-static-triangles-main-v1` is the proposed first import profile.
Its initial producer compatibility set contains only
`5761e683b01bb82e5efc3cfc931e40a3cc55a8c2`.
This is a declared producer revision, not proof that a program ran.
New producer revisions need an explicit compatibility entry and tests.
This profile does not ask an app to downgrade its existing Rust dependency.
A separate helper can validate it while the app keeps its current game core.

The profile follows that revision's
[mesh](https://github.com/faberline/formora/blob/5761e683b01bb82e5efc3cfc931e40a3cc55a8c2/src/mesh.rs)
and [scene](https://github.com/faberline/formora/blob/5761e683b01bb82e5efc3cfc931e40a3cc55a8c2/src/scene.rs)
field definitions:

| Value | Allowed fields and values |
| --- | --- |
| Scene | `schema_version`, `revision`, `time_seconds`, `entities`, `materials`, `mesh_assets`, `doors`, `active_camera`, `annotations`. |
| Entity | `name`, `parent`, `transform`, `content`. Only `empty` or mesh content with asset geometry. |
| Transform | `translation`, `rotation`, `scale`. Rotation is an x/y/z/w quaternion array. |
| Asset geometry | `kind` equal to `asset`, and mesh asset `id`. |
| Mesh asset | `vertices`, `triangles`, `material_slots`. Keep every vertex, including unused vertices. |
| Triangle | `vertices`, `uv_layers`, `corner_normals`, `material_slot`. |
| Material | `base_color`, `roughness`, `metallic`. |

Reject unknown fields at every level.
Use the pinned Rust definitions and validation rules for types, defaults, and numeric constraints.
The package must contain at least one referenced mesh with a triangle.
The profile allows these capability names only:
`triangle_meshes`, `hierarchy`, `corner_uvs`, `corner_normals`, `solid_color_materials`.
Declare the exact features used by the source, and verify that declaration against the source.
`triangle_meshes` is required by this profile.
Use `hierarchy` when an entity has a non-null parent.
Use `corner_uvs` when a triangle has nonempty UV layers.
Use `corner_normals` when a triangle has non-null corner normals.
Use `solid_color_materials` when the material map is nonempty.
This is an allowlist, not a request to add missing fields to a model.

The D25 source profile is separate and is not supported by this first import adapter.
Its frozen producer revision remains
`d25a2a7ed7c16fa8d61f70e9c2f65926e962303d`.
D25 adds fields such as triangle `corner_colors`, source polygons, edges, and editing data.
It also has different transform and scene context fields.
Main cannot load that data through its strict older native types.
Reject a D25 package as an unsupported profile in this first slice.
Do not strip fields, colors, normals, or topology to make it fit the main profile.
The D25 loader and all original 56-model evidence remain unchanged and separate.
This first profile does not inherit that evidence or accept all 56 models.
Ashfall's existing crate has producer pin
`bb025ce17432ba0419008d0cd794222127e7ff92` and source polygon data.
It is also outside this first profile.
Its full source profile needs a separate field definition and compatibility tests
before the crate can pass the new importer.
Keep it as an unchanged negative case for the first profile.

## Model content closure

`roots` is a nonempty list of distinct, existing top-level entity IDs.
Each root has `parent: null`.
Keep the manifest root order in the receipt.
The selected entity set is the union of those roots and all their descendants.
The scene must contain exactly that entity set.
Reject other entities rather than dropping them during import.

Every parent reference must stay inside the selected entity set.
Roots may share mesh assets or materials.
The selected mesh asset set contains every asset referenced by a selected mesh entity.
The scene must contain exactly that mesh asset set.
The selected material set includes every non-null entity material and every non-null
material slot in those mesh assets, even if a triangle does not use that slot.
The scene must contain exactly that material set.
Rust checks every vertex, triangle, slot, and hierarchy reference.
Reject missing, extra, cyclic, or out-of-set references.
Do not rename entities to `model` or require one mesh per package.

This static profile requires `time_seconds: 0`, empty `doors`,
`active_camera: null`, and empty `annotations`.
Camera and light entities, authoring context, object context, and animation state are rejected.
They are not silently removed or converted into app state.
Keep the original model file bytes, IDs, transforms, revision, and supported attributes.
Save and reopen the owned model package independently of a city or game save.
FF's existing asset library has mesh assets but no root entities.
Its adapter must author a new package with explicit roots and the required resource set.
It must not edit the original library to add those roots.
The original mesh values, corner data, and complete material slots stay unchanged in that new package.

## Scale and axis

The first main profile requires explicit `meters_per_unit: 1.0`, `up_axis: "Z"`,
and `coordinate_system: "right_handed"`.
It uses the native main coordinate convention.
Missing or unknown scale is an error.
Use an explicitly measured external model for the first positive case.
Do not infer physical scale from Vortex's old normalized mesh units or instance dimensions.
That old catalog has no package-level physical scale declaration.
It must not be relabeled as metres without evidence.

Vortex's east/north/height coordinates already use right-handed Z-up metres.
The first slice needs no axis conversion there.
Rust stores the source declaration and any later explicit world conversion separately.
It does not rewrite source vertices to match a game footprint.
FF's two-metre grid and per-axis footprint scaling are app projection rules.
Ashfall's game grid is not yet established as metres.
Neither is proof of a source model's physical scale.

Keep source IDs, hierarchy, polygon topology, transforms, and corner attributes.
Keep native numeric precision, including signed zero where the source uses it.
Do not replace source polygons with preview triangles in the saved model.
Do not silently normalize dimensions, axes, or origins.
If an app needs a different world scale, its Rust adapter records that conversion.
Game catalog keys and footprint rules stay in each app's adapter.

The first slice uses the source features that Rust can validate and preserve.
It must reject requested features that it cannot preserve.
Do not silently drop textures, rig data, animation, or unknown attributes.
A static USDA display file can be a later validated output of the existing export candidate.
It is not a promise of USDA import, a selected Apple renderer, or Swift display support.
This first validator requires `display_exports` to be absent or empty.
It returns `unsupported_feature` for nonempty display exports rather than claiming to validate USD.

## First app slice

1. Swift selects a package and sends its manifest path and `expected_manifest_sha256` to Rust.
2. Rust checks raw manifest bytes, payload hashes, producer/profile, schema, roots, units, references, and capabilities.
3. Rust stages and validates owned data before it changes the active model.
4. Rust returns an import receipt. Swift shows the receipt and model information.
5. A later display task shows the imported model through an explicit Swift/Rust host contract.

On failure, keep the current model, scene, and game save unchanged.
An import's saved result location holds owned model data only.
It is not a game save location.
In Ashfall, keep autosave, manual slots, backups, and legacy save files under the existing Swift save flow.
Do not treat a file-picker result or a success log as a completed import.
Do not pass large geometry arrays through the file-picker UI contract.
The choice of C ABI or a Rust process bridge belongs to each app's host task.
Both choices must use the same Rust validation rules and receipt fields.
The first Vortex slice uses an independent Rust helper through its Process bridge.
It does not add fake model actions to CityHostAction or reuse a city command Receipt.
It must not mutate CityWorld, city provenance, or the game save.
Ashfall's game Engine loader and game C ABI are also not model import APIs.
The first slice does not expand that game ABI or reuse a game response as a model receipt.
FF's current ArtLibrary loader is not the shared package validator.
It can fill normals in derived display data, but must not save that data as the untouched imported source.
The shared CPU validator must work without `preview`, winit, a GPU, or the `formora-live` module.

The proposed receipt includes:

- `receipt_schema_version`, `ok`, `manifest_sha256`, and `scene_sha256`.
- Validated `scene_profile`, declared `producer_commit`, and the validator's exact revision.
- The adopted root IDs, in manifest order.
- Source units, axis declaration, model counts, and the saved result location on success.
- An explicit conversion or loss report. A required loss is an error in this first slice.
- A structured error code and message on failure.

The receipt has separate success and failure forms, selected by `ok`.
`ok: true` requires the complete validated fields and a successfully saved owned package.
`ok: false` requires an error code, message, and validation stage.
It may include observed manifest or scene hashes that Rust actually obtained.
If the manifest is missing, cannot be parsed, or has the wrong hash,
validated profile, producer, adopted roots, validated scene hash, and saved location
must be absent or null.
Do not copy untrusted manifest declarations into those validated result fields.
A hash that could not be read is also absent or null.
A failed import never reports adopted data or a successful save.
`validator_revision` identifies compiled-in validator and core source inputs as `sha256:HEX`.
It is not a Git commit, binary hash, or reproducible-build attestation.
The CLI exits `0` for a saved package and `1` for a failure receipt.
CLI usage errors exit `64` and do not constitute model validation.
MCP returns the same receipt as structured content, with `isError: true` on import failure.

Minimum error cases are unsupported format or schema, hash mismatch, invalid scene,
unsupported profile or producer, missing resource or entity reference,
invalid content closure, unsupported scene state, unknown units, and unsupported feature.
For hash mismatch, identify whether the manifest, scene, or display file changed.
The schema files list the implemented error codes and stages for this first profile.
Existing game command strings are not import receipts.
The output directory is reserved with an exclusive create after input validation.
The source bytes are saved first, then the manifest. Both files are synced before success.
The caller must not adopt a directory until it receives the success receipt.
An I/O failure can retain an incomplete new directory for inspection.
The importer never removes that directory or deletes an existing model to retry.

## Acceptance before expansion

Use one existing model per app first.
Use it as a positive case only if its full data matches the first profile.
Ashfall's crate is a candidate, not a promise that the main profile can load it.
Vortex uses a measured external model outside its fixed catalog.
FF keeps its catalog metadata in its Rust adapter.
FF's shelter is a candidate for a new package with an explicit root.
Keep its catalog key and footprint outside the shared source model contract.
If an existing model uses D25-only fields, keep it unchanged as a rejection case.
Author a separate first-profile fixture instead of reducing that model's data.
A simple fixture proves only the first-profile helper slice.
It does not resolve an app's dependency on its existing models.
Those models still need their full source profiles and successful positive import cases.
Do not substitute a simpler new model for an app's original acceptance set.

Test successful import, save and reopen, model information, and explicit failure cases.
Check full source values and required attributes, not only counts or a screenshot.
Prove that each failed import leaves the prior model and game save unchanged.
Test a manifest change to roots or units with unchanged scene bytes.
The old expected manifest hash must fail that import.
Test extra entities, unused assets, cross-set references, and unsupported D25 fields.
Test a source with missing normals without changing those source fields during import.
If display needs generated normals, test that only the derived display data changes.
Swift import, display, and the original app performance gates are separate results.

The next work is CI validation of this slice, then independent use by the three consumers.
Their existing polygon/color models still need complete compatible source profiles.
Continue modeling operations against the fixed Blender baseline.
No Swift display host or game ABI is implemented by this CLI slice.

Keep all previous evidence.
The original Vortex 56-model result and the extra streetblock result retain their bounded scope.
FF's latest 76-state GPU program exited successfully, but its independent image review is pending.
No full FF performance or whole engine migration acceptance follows from this direction change.
