# Icosphere and Suzanne generation

Scope: issue #42. These generators use the shared Rust primitive commands.
Their public kinds are `ico_sphere` and `monkey`.
CLI and MCP use the same core, resource budget, saved recipe and rebuild behavior.

```json
{
  "expected_revision": 0,
  "commands": [
    {
      "operation": "create_mesh_primitive",
      "id": "ball",
      "primitive": {"kind": "ico_sphere", "subdivisions": 3, "radius": 1.25}
    },
    {
      "operation": "create_mesh_primitive",
      "id": "head",
      "primitive": {"kind": "monkey", "size": 2.0}
    }
  ]
}
```

Apply this request through `scene_apply` or the CLI `scene apply` command.
Use tool discovery or `scene schema` for all fields and defaults.
Both generators support `calc_uvs` and `creation_rotation`.
The icosphere also supports an authored local `scale`.
Entity transforms control final scene placement.
The fixed upstream monkey operator ignores the generic scale option.
The Rust monkey generator uses its effective `size` parameter.
Scale its scene entity when scene-level scaling is required.

The icosphere accepts subdivisions 1 through 10.
For `n = 2^(subdivisions-1)`, it has `10*n*n+2` vertices, `30*n*n` edges,
`20*n*n` triangular faces and `60*n*n` face corners.
The resource count is `120*n*n+2`.
The default generation budget is 1,000,000 components.
A request that exceeds its budget fails before geometry allocation.
The generator preserves the requested subdivision value.
It does not reduce it to fit a smaller budget.
An explicit larger budget allows a larger requested mesh.
Full upper-range geometry and capacity acceptance remain unrun.

The icosphere starts from the authored 12-point source table.
It splits original edges in source order with single-precision arithmetic.
It projects edge points, then builds and projects the internal face rows.
Per-corner UVs interpolate the authored UV chart.
Shared edge points keep one logical ID across faces.
Zero radius retains topology and distinct IDs.

Suzanne uses the authored 271-point half-model and 250 source face rows.
It mirrors those points with the fixed center-line reuse rule.
The result has 507 vertices, 1,005 edges, 500 polygons and 1,968 face corners.
Its default UVs come from the authored source chart.
Zero size preserves these IDs and topology.
Coincident authored vertices remain distinct.

Rebuilding preserves the asset ID and all entity references.
It replaces the asset data, including editing state, as specified by the shared recipe contract.
Undo restores the previous asset and selection.
Manual vertex edits mark the recipe as edited.
Rebuilding without new parameters uses the saved recipe.

## Source provenance

The fixed source commit is Blender 5.2.3 LTS
`e13b728c6880d3084d9d57c30031ed5df8b39dee`.
The [source manifest](evidence/remaining-primitives/source/manifest.json)
records official URLs, Git blob IDs and SHA-256 values.
It also retains the exact source bytes used for tables and behavior research.

`tools/generate_legacy_primitive_tables.py` accepts only the pinned `bmo_primitive.cc` bytes.
It generates `src/mesh/primitives/legacy_tables.rs` from the original authored tables.
It never reads measured reference geometry.
The Python tests check the official Git blob ID, byte-for-byte reproduction and rejection of changed input.
The derived Rust modules retain Blender Authors notices and GPL-2.0-or-later identifiers.
The [GPL text](../baseline/reference/blender-5.2.3/GPL-license.txt) remains included.
This notice does not assign a new license to unrelated files.

The production executable uses compiled Rust data and arithmetic.
It does not call Blender or Python and does not load reference answers.

## Remaining acceptance

Finite source comparisons do not accept the whole primitive feature or modeling milestone.
Full numeric domains and capacity, general creation contexts, edit insertion, presets,
native window input and Windows/Linux GPU checks remain open.
Required three-platform CI, dependency integration and independent acceptance remain required.
