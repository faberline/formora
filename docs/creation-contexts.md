# Primitive creation contexts

Issue #44 adds three commands to the shared Rust operation core.
CLI and MCP use the same commands and return the same receipts.

`set_authoring_context` saves the cursor location, cursor rotation and view rotation.
Angles are XYZ Euler radians. Coordinates are metres.
The context is optional. An absent context uses zero location and rotation.

`create_mesh_object` requires the entity ID, asset ID, name and primitive parameters.
It creates one editable asset and one scene entity.
`append_mesh_primitive` requires an existing mesh entity and a new ID prefix.
It inserts into that entity's shared asset. It never welds coincident vertices.
The operation preserves existing entities, references and authored attributes.
New IDs use the requested prefix. A conflicting ID rejects the entire batch.

```json
{
  "expected_revision": 0,
  "commands": [
    {"operation":"set_authoring_context","context":{
      "cursor_location":[2,-1,3],"cursor_rotation":[0.2,-0.4,0.6],"view_rotation":[0.35,-0.25,0.6]
    }},
    {"operation":"create_mesh_object","creation":{
      "id":"room-part","asset":"room-part-mesh","name":"Room part",
      "primitive":{"kind":"cube","size":2},"placement":{"align":"cursor"}
    }}
  ]
}
```

Placement accepts `world`, `cursor` or `view` alignment.
Explicit location overrides cursor location.
For the C primitives, explicit rotation overrides alignment.
Torus follows the fixed Python source: an unset rotation uses world alignment.
With explicit rotation and cursor/view alignment, Torus uses the context rotation.
Monkey view alignment subtracts π/2 from its X angle.
The low-level `creation_rotation` must be zero when a high-level placement is used.
This prevents two competing placement systems in one request.

Each saved operation returns a creation receipt.
It contains the command index, entity, asset and actual new vertex, edge and typed face IDs.
Receipts are returned only after the complete batch is saved.
The receipt IDs and before/after queries let agents locate the new geometry.
New geometry is selected and immediately editable.
`preview_selection` controls visible markers. New objects default to false.
Insertions default to true. Selection queries retain the actual flags in both cases.

Insertion converts world coordinates into the target's local coordinates.
It includes parent transforms. A singular target rejects the operation.
The merged component budget is checked before generation.
Creation recipes retain their local frame for later regeneration.
Insertion marks an existing recipe as edited.
Rebuilding clears component editing state, as for the existing primitive API.

The source-specific UV rules are retained.
C primitives initialize existing faces when the first UV layer is added.
Torus initializes those old face corners to zero.
Generated UVs use the existing active layer. Other new layer values are zero.
Torus uses the existing active material index. C primitives use slot zero.
Negative and collapsed scales retain the fixed source's cap classification.

The [source manifest](evidence/creation-contexts/source/manifest.json) pins Blender
`e13b728c6880d3084d9d57c30031ed5df8b39dee` and its actual Eigen dependency
`8a1083e9bf41b91fdea6546681f806154efdc25a`.
The Eigen inverse translation is retained in a separate MPL-2.0 Rust file.
Upstream notices and the complete MPL text are stored beside the source manifest.
The scalar implementation reproduces the ARM reciprocal estimate and two refinement steps.
It does not call Blender, Python or a reference fixture at runtime.

The [fixed contract](contracts/primitive-creation-contexts.md) defines the acceptance gates.
Finite creation-context coverage does not complete general modeling or any milestone.
