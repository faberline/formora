# Mesh selection through agents

Scope: issue #40. The shared Rust core serves CLI and MCP.
These ten finite contracts do not accept full modeling parity.

`select_mesh` operates on one shared asset. Every instance sees its saved editing state.
The selector kinds are `mode`, `non_manifold`, `loose`, `interior_faces`,
`faces_by_sides`, `poles` and `ungrouped`.
Mode options also provide expansion, contraction and combined mode masks.
Use `scene schema` or MCP tool discovery for all fields and defaults.

```json
{
  "expected_revision": 1,
  "commands": [
    {
      "operation": "select_mesh",
      "id": "surface",
      "selector": {"kind": "loose", "extend": false}
    }
  ]
}
```

Apply this request with `formora scene apply --scene scene.json --request request.json`.
MCP uses the same request in `scene_apply`.
A saved response contains the revision and one selection receipt per selector command.
Each receipt has `command_index`, `mesh_asset` and `outcome`.
`completed` and `unchanged` are distinct outcomes.
Receipts are returned only after a successful save.
An error rolls back the whole batch and preserves undo history.

Use `formora scene inspect --scene scene.json --mesh-asset surface --selection-topology`
to query stable component IDs. MCP uses `scene_inspect` with `selection_topology: true`.
This query does not write the scene.
Explicit edge IDs are preserved.
Legacy triangle boundaries receive deterministic derived edge IDs.
Coincident vertices retain distinct IDs.
Faces use typed references such as `{"kind":"polygon","id":"face"}` or
`{"kind":"triangle","id":"face"}`. Their names can match without aliasing.

`set_mesh_editing` sets an optional asset editing state.
It contains a nonempty domain mask, selected and hidden component sets,
an ordered selection history and an optional active face.
The core computes lower component flags and mode consistency from authored IDs.
It rejects duplicate IDs, unknown references, selected hidden components,
duplicate history entries and history entries that are not selected.
An active face can remain unselected after an operation.
Set `editing` to null to remove the state.
Old schema 1 scenes need no new fields.

Assets can store ordered `vertex_groups`, optional `vertex_weights`,
`edge_seams` and `smooth_triangles`.
A missing weight layer differs from an allocated empty layer.
A zero weight still counts as group membership.
Unknown groups, vertices, seam edges and nonfinite or out-of-range weights are rejected.
Selection preserves positions, topology, UVs, materials and unrelated attributes.

The preview shows selected vertex markers, selected edges and a selected face tint.
Hidden faces and faces incident to hidden vertices or edges are omitted.
Markers are generated render data. They do not alter authored materials or surface picking.
Surface picking respects hidden geometry.
The preview can omit a hidden crossing polygon without changing strict tessellation queries.

## Source and license

The fixed source is Blender 5.2.3 LTS commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`.
The official `v5.2.3` tag was checked against that commit.
Behavior research used these source files:

- [Edit-mesh selection](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/editors/mesh/editmesh_select.cc)
- [BMesh selection marking](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/bmesh/intern/bmesh_marking.cc)
- [BMesh topology queries](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/bmesh/intern/bmesh_query.cc)

The derived operations, interior cost and topology flag modules retain the Blender
Authors notices and GPL-2.0-or-later identifiers.
The [GPL text](../baseline/reference/blender-5.2.3/GPL-license.txt) is included.
This notice does not assign a new license to unrelated files.
The runtime computes selection in Rust. It does not load reference answers or call Blender or Python.

## Remaining scope

Full numeric domains, general multi-object editing, screen-space tools and UV synchronization remain open.
The interior selector uses finite double-precision area and angle costs.
It rejects an undefined cost for a degenerate non-manifold group atomically.
That input is outside the frozen finite suite. It remains a parity limitation.
Native window input and Windows/Linux GPU checks remain unrun.
Integration, three-platform CI and independent acceptance remain required.
