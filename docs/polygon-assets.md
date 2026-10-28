# Polygon topology and preview tessellation

[Issue #32](https://github.com/faberline/formora/issues/32) extends the [shared mesh asset](mesh-assets.md).
The Rust core stores source polygons and edges. It does not replace a polygon with its preview triangles.
Primitive generation and the full modeling milestone remain pending.

## Stored data

The existing `vertices`, `triangles` and `material_slots` fields remain valid.
Three optional fields extend an asset:

- `edges`: a map from stable edge ID to two different vertex IDs. Only one edge can connect a given pair. Endpoint order is preserved but has no topological direction.
- `polygons`: a map from stable face ID to a polygon record. A polygon has at least three different vertex IDs in boundary order. Its boundary edges must exist.
- `uv_layout`: an ordered `layers` list and an optional `active` layer name. A polygon with UV data needs this layout. Every polygon must have the same layer names. With a layout present, legacy triangles must also match it.

Each polygon has `vertices`, `uv_layers`, `corner_normals`, `normal`, `smooth` and `material_slot`.
Each UV layer contains one `[u,v]` pair per face corner. Optional corner normals also match that count.
A normal is a unit vector or a zero vector. Values are finite. Layer names contain 1–128 UTF-8 bytes.
A material slot has the same meaning as a triangle slot.

Edge, face and vertex IDs each have their own namespace. They use the existing scene ID rule.
Unused vertices, loose edges, coincident positions and edges shared by more than two faces are valid.
The core preserves these data. Loose edges do not yet have native drawing or picking support.
A face can share edges with other faces. A face cannot repeat a vertex ID within its boundary.

Normals and smooth flags are saved caller data. Moving vertices preserves them.
This work does not generate new smooth normals. The preview uses supplied corner normals,
then the face normal, then a geometric triangle normal. It stores UVs without drawing textures.

## Agent operations

Use the existing `set_mesh_asset`, `set_mesh_vertices` and `delete_mesh_asset` commands.
Revision checks, atomic saving, undo and shared instances use the same Rust scene core.
A triangle-only saved asset still loads. Empty new maps are omitted when saved.
Older binaries reject nonempty new fields.

A read-only query can include polygon tessellation:

```json
{"mesh_asset":"panel","tessellate":true}
```

Call `scene_inspect` through MCP with those arguments. The CLI form is:

```sh
formora scene inspect --scene PATH --mesh-asset panel --tessellate
```

`tessellate` requires a mesh asset query. The response includes the saved `mesh_asset` and `tessellation`.
Each derived triangle has a polygon ID and three original face-corner indices.
These indices select the matching source vertex, normal and UV value.
The response lists only polygon-derived triangles. Legacy explicit triangles remain in `mesh_asset.triangles`.

## Preview rules

The Rust tessellator projects each face to its dominant plane. It preserves winding and clips ears
from a simple concave boundary. Drawing and ray picking use those same derived triangles.
A notch remains empty. Nonplanar faces use this projection as a preview surface choice.
This is not a claim of matching Blender's internal diagonal choices for every nonplanar face.

Projection coordinates are normalized by the face extent. Geometric predicates use `1e-12` in that space.
Consecutive coincident positions and boundary points on a straight edge can be omitted from the derived triangles.
The source face and all its attributes remain saved. The query reports `collapsed_polygon_corners`.
A fully collapsed or collinear face yields no triangles and reports `degenerate_polygon`.

A self-intersecting projection fails with the polygon ID. A failed query returns no partial tessellation.
A failed render does not create a PNG or overwrite an existing PNG. Stored data and undo remain intact.
These errors let an agent repair geometry. They do not silently delete an authored face.

See the [fixed contract](contracts/polygon-assets.md) and [verification record](verification/polygon-assets.md).
