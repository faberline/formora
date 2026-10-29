# Rust primitive generation

The core can generate planes, cubes, grids and circles from parameters.
It creates real editable vertices, edges, polygons, face-corner normals and default UVs.
Runtime generation uses Rust arithmetic. It does not read reference assets or call Blender or Python.
This is the finite scope in [issue #34](https://github.com/faberline/formora/issues/34).
The other primitive types and complete modeling acceptance remain in the roadmap.

## Create and regenerate

Use `scene_apply` through MCP or `formora scene apply --scene PATH --request FILE`.
A batch still requires the current `expected_revision`.

```json
{
  "expected_revision": 0,
  "commands": [
    {"operation":"create_mesh_primitive","id":"box","primitive":{"kind":"cube","size":2}},
    {"operation":"create_mesh_primitive","id":"surface","primitive":{"kind":"grid","x_subdivisions":3,"y_subdivisions":5}}
  ]
}
```

Creation fails if the asset ID already exists. Use a mesh entity with `{"kind":"asset","id":"box"}` geometry to show it.
More than one entity can use the generated asset.

`regenerate_mesh_primitive` replaces an existing asset using its saved recipe:

```json
{"operation":"regenerate_mesh_primitive","id":"box"}
```

It can also take a new `primitive` and an optional `max_components` budget.
A raw imported asset needs explicit primitive parameters the first time it is regenerated.
The asset ID and entity references stay intact. Identical parameters produce identical component IDs and geometry.
Topology changes can give those component IDs different meanings.

Regeneration replaces the whole asset. It replaces direct geometry edits, UV edits and asset material slots.
Entity material overrides remain. Undo restores the previous asset.
These rules are explicit so an agent can choose between a local edit and a complete rebuild.

## Parameters

| Kind | Defaults and fields |
| --- | --- |
| `plane` | `size: 2`, `calc_uvs: true` |
| `cube` | `size: 2`, `scale: [1,1,1]`, `calc_uvs: true` |
| `grid` | `size: 2`, `x_subdivisions: 10`, `y_subdivisions: 10`, `calc_uvs: true` |
| `circle` | `radius: 1`, `vertices: 32`, `fill_type: "nothing"`, `calc_uvs: true` |

Dimensions range from 0 to 999999995904 metres. Cube scale components range from -999999995904 to 999999995904.
Counts are integers. Grid subdivision counts range from 1 to 10,000,000. Circle vertex count ranges from 3 to 10,000,000.
Circle fill values are `nothing`, `ngon` and `trifan`. A default circle has only edges. Loose-edge drawing remains pending.
Grid subdivisions count face spans. A 3 by 5 grid has 24 vertices and 15 faces.
Geometry parameters use the source tool's float32 coordinate precision.
Full upper-domain precision and capacity validation remain pending.

Cube `scale` is baked into local geometry. It is separate from the entity transform.
The fixed upstream captures bake this option for cubes but ignore it for these other three primitives.
Entity transforms still control placement of every shape. Full shared align/cursor/view/append behavior is not accepted here.

The fixed upstream version makes a unit cube when `size` is 0. Formora preserves that result.
A zero-size plane or grid keeps distinct vertex IDs at coincident positions.
A zero-radius circle keeps its topology. Its filled default UVs are undefined upstream.
Formora uses the already-fixed finite-zero UV fallback and emits `degenerate_default_uv`.
Finite UV values retain the original 1e-6 comparison threshold.

## Saved recipe and diagnostics

Inspect a generated asset with `scene_inspect` and `{"mesh_asset":"box"}`.
`recipe` stores resolved primitive parameters, the component budget and `edited`.
A manual vertex edit sets `edited: true`. A successful regeneration sets it back to false.
Other asset data are defined in [mesh assets](mesh-assets.md) and [polygon assets](polygon-assets.md).

Warnings from the last generation remain in the asset's `diagnostics` list.
A successful create or regenerate also returns warnings after the scene has been saved:

```json
{"revision":1,"generation_diagnostics":{"circle_asset":["degenerate_default_uv"]}}
```

The warning map contains affected assets still present at the end of the batch.
It is omitted when empty. Failed batches return errors and preserve memory, disk and undo state.
A warning does not turn an undefined upstream value into a numeric comparison pass.

## Resource budget

Generation estimates vertices + edges + polygons + face corners before allocating geometry.
`max_components` defaults to 1,000,000. An agent can supply a different budget.
The operation fails with the estimated count when it exceeds the budget.
It does not silently lower subdivisions. A saved recipe retains the budget for later regeneration.

See the [fixed contract](contracts/primitive-generation.md) and [verification record](verification/primitive-generation.md).
