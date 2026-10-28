# Shared mesh assets

A mesh asset stores triangle data in Rust. It can also store [source polygons and edges](polygon-assets.md). More than one entity can use the same asset.
An agent can replace the asset or change vertices by ID. These changes affect all its instances.

This is the bounded foundation in [issue #30](https://github.com/faberline/formora/issues/30).
It does not complete the modeling milestone. The [polygon extension](polygon-assets.md) adds topology.
[Primitive generation](primitive-generation.md) now covers four shapes. Complete modeling remains pending.

## Data

Scene schema 1 now has an optional `mesh_assets` map. An empty map is omitted when saved.
Existing room scenes still load. Older binaries reject scenes that use the new field or geometry type.

Each asset has:

- `vertices`: a map from stable vertex ID to `[x, y, z]` in metres.
- `triangles`: a map from stable triangle ID to three vertex IDs, in winding order.
- `material_slots`: an ordered list of scene material IDs or `null`.

Each triangle has:

- `vertices`: exactly three different IDs. Their positions may coincide.
- `uv_layers`: named sets of three `[u, v]` values. Values belong to face corners. Adjacent triangles can have different UV values at the same vertex.
- `corner_normals`: three unit normals, three zero normals, a mix of these, or `null`. A zero normal uses the geometric face normal in the preview.
- `material_slot`: a zero-based slot index, or `null` for the default material.

IDs use the scene ID rule: 1–128 ASCII letters, digits, hyphens or underscores.
All stored numbers must be finite. UV layer names must contain 1–128 UTF-8 bytes.
Empty assets and vertices without triangles are valid. The preview draws triangle surfaces.
Zero-area triangles remain stored. They add no visible area and cannot be picked.

The original triangle buffer remains valid. Optional polygon, edge and UV layout fields
are defined in the [polygon extension](polygon-assets.md). Vertex selections, texture images,
and generated smooth normals remain pending. Normals and UVs are caller data.
Moving a vertex preserves these values. The agent must replace them when needed.

## Commands

Use `scene_apply` through MCP, or `formora scene apply --scene PATH --request FILE`.
Both use the same commands and require `expected_revision`.

- `set_mesh_asset`: `id` and `asset`. Adds an asset or replaces the whole asset.
- `set_mesh_vertices`: `id` and `positions`. Changes existing vertex positions by ID. The map must not be empty.
- `delete_mesh_asset`: `id`. Fails while an entity still refers to that asset.

To use the asset, create a mesh entity with this content:

```json
{"kind":"mesh","geometry":{"kind":"asset","id":"shared"},"material":null}
```

An entity material overrides all triangle material slots. A null entity material uses each triangle's slot.
An unbound slot uses the default preview material. UV values are stored but textures are not drawn yet.

To inspect an asset, use `scene_inspect` with `{"mesh_asset":"shared"}`.
The CLI form is `formora scene inspect --scene PATH --mesh-asset shared`.
Specify either an entity or an asset in one query.

A successful batch is saved before the reply. Invalid commands preserve the scene and undo history.
Undo applies to the full batch. Each command must leave a valid scene.
Delete referring entities before deleting their asset in the same batch.

## Checks

The [fixed contract](contracts/mesh-assets.md) predates implementation.
The [verification record](verification/mesh-assets.md) records its evidence and remaining work.
The fixed Blender plane and cube data test storage and coordinate conversion.
They do not test primitive generation or full upstream feature parity.

Generated assets can store a primitive `recipe` and generation `diagnostics`. See [generation](primitive-generation.md).
