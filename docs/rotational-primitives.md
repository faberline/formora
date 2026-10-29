# Rotational mesh generation

Issue #36 extends the saved Rust primitive recipes with `uv_sphere`, `cylinder`,
`cone` and `torus`. CLI and MCP use the same `create_mesh_primitive` and
`regenerate_mesh_primitive` commands. A resource budget is checked before allocation.
This work depends on PRs #33 and #35. It is not integrated or accepted.

The sphere takes `radius`, `segments`, `ring_count`, `scale` and `calc_uvs`.
The cylinder takes `radius`, `depth`, `vertices`, `end_fill_type`, `scale` and `calc_uvs`.
The cone uses `radius1` and `radius2` instead of one radius.
`end_fill_type` accepts `nothing`, `ngon` and `trifan`.
Scale is baked into local positions. Entity transforms place an instance in the scene.
These three recipes also accept `creation_rotation`, an XYZ Euler rotation in radians.
It gives the orientation of the creation frame. It preserves the reference build's
conversion between the rounded creation frame and rounded object frame.
It does not move an entity. World placement still uses the entity transform.
This is an input parameter. The test adapter sends the requested source rotation,
not a matrix inferred from reference vertices.

The torus takes `major_segments`, `minor_segments` and `generate_uvs`.
Its `major_minor` mode uses `major_radius` and `minor_radius`.
Its `ext_int` mode uses `abso_major_rad` and `abso_minor_rad`.
The latter radius difference is clamped to zero when the inner radius is larger.
Each recipe retains the requested parameters. Regeneration replaces the asset data
and retains asset identity. Existing instances keep their shared reference.

Zero-radius spheres retain one vertex. Conics with both radii zero retain two
vertices and one edge. Tori retain all vertices and face corners, even when
positions coincide. A collapsed face has no derived triangles.

Face normals and corner normals are separate data. The reference build uses
different precision for them. The generator preserves these precision rules.
Sphere meridians use repeated single-precision rotation. A deterministic spatial
partition selects seam samples. A direct ideal circle gives different normals.
The torus wraps its rotation angle in single precision before it makes a matrix.

The fixed quality contract is [rotational-primitives.md](contracts/rotational-primitives.md).
The complete 138-check comparison must pass. A failed case remains a failure.
The full creation context, all numeric domains and full modeling parity remain unrun.

## Source and license

The behavior research used the installed Blender 5.2.3 LTS build `e13b728c6880`.
The matching source commit is `e13b728c6880d3084d9d57c30031ed5df8b39dee`.
These are the relevant official source files:

- [BMesh primitive construction](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/bmesh/operators/bmo_primitive.cc).
- [Duplicate selection and welding](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/bmesh/operators/bmo_removedoubles.cc).
- [Spatial partition and duplicate clusters](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/blenlib/BLI_kdtree.hh).
- [Fraction and angle arithmetic](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/blenlib/intern/math_rotation_c.cc).
- [Primitive creation frames](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/editors/object/object_add.cc).
- [Matrix conversion arithmetic](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/source/blender/blenlib/intern/math_matrix_c.cc).
- [Torus construction](https://github.com/blender/blender/blob/e13b728c6880d3084d9d57c30031ed5df8b39dee/scripts/startup/bl_operators/add_mesh_torus.py).

The derived Rust module `src/mesh/primitives/rotational.rs` retains the Blender
Authors copyright notice and GPL-2.0-or-later license identifier.
The [GPL text](../baseline/reference/blender-5.2.3/GPL-license.txt) is included.
This notice does not assign a new license to unrelated files.
Runtime generation uses Rust arithmetic. It does not read the source repository,
reference vertex arrays, Blender, Python or an external geometry process.
