# Blender 5.2.3 reference measurements

These files record upstream mesh output. They are test fixtures.
They are not Formora implementation code or product acceptance results.

Source: [Blender 5.2 Mesh Primitives manual](https://docs.blender.org/manual/en/5.2/modeling/meshes/primitives.html).
The archived manual has the CC-BY-SA 4.0 notice from Blender contributors.
The original page is preserved in `baseline/sources/blender-5.2-mesh-primitives.html`.

The reference executable is Blender 5.2.3 LTS, build `e13b728c6880`.
Its version, build data and executable hash are in `mesh-primitives/manifest.json`.
The adapter starts with factory settings. It removes the default objects before each run.
Inputs are in `baseline/fixtures/mesh-primitives.json`.
The adapter is `tools/blender_mesh_reference.py`.

`operator-properties.json` records the actual operator parameters from that build.
The mesh JSON files keep vertices, edges, oriented faces, normals, face-corner UVs,
shading flags, world matrices, bounds and derived triangles.
The comparison uses the oriented polygons. It does not require the same derived triangle numbering.

`reproduction-manifest.json` records a second fresh process.
`reproduction-comparison.json` records its comparison with the first process.
Some UV sphere face and edge indices differ between processes.
The oriented geometry, normals and UVs are equal under a bijective vertex map.
The comparison also handles distinct Suzanne vertices at the same position.
It must not weld them.

The primitive implementation and Suzanne data come from Blender contributors.
They are available under GPL-2.0-or-later.
See [the pinned upstream source](https://github.com/blender/blender/blob/v5.2.3/source/blender/bmesh/operators/bmo_primitive.cc)
and the included [GPL text](GPL-license.txt).
The Blender source can be obtained from that release tag.
The license notice here applies to the upstream reference data in this directory.
It does not change the license of other Formora files.

All ten feature contracts remain pending review.
The shared options, Edit Mode insertion, full valid parameter range, degenerate inputs,
rendering and performance need more contracts.
Formora execution and product acceptance remain `unrun`.

The later `mesh-contexts/` dataset adds 131 creation and lower-bound fixtures.
See `docs/verification/mesh-creation-contexts.md` for the capture and comparison rules.
Undefined UV values in two zero-radius circles are preserved as explicit tags.
They cannot pass a finite Formora comparison without the fixed zero fallback and diagnostic.
The first 57 input and output files remain unchanged.
