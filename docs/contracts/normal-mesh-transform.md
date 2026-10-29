# Normal orientation for mesh transforms

This extends issue #48. The complete unchanged 2,406-case gate, componentwise
1e-6 limits, performance, integration and independent acceptance remain required.
A focused result cannot accept the issue, a feature or a milestone.

Derive the basis from actual geometry, topology, persistent selection flags,
selection history, active face and object frame. Never accept a measured normal,
tangent or basis as a substitute for these inputs. Stored shading normals and
face smoothing do not override BMesh geometric orientation normals.

Follow `getTransformOrientation_ex`, `ED_getTransformOrientationMatrix`,
`createSpaceNormal` and `createSpaceNormalTangent` at the frozen Blender commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`. The existing source archive includes
these functions and BMesh vertex normal accumulation. The new archive pins
face normals, triangle/quad/ngon tangents, active selection and vector helpers.
Keep their float32 arithmetic order and degenerate fallbacks.

Support active vertex, edge and face orientation. Active normal selection uses
the source's temporary selection record with no previous record. Otherwise use
selected faces first, then three vertices, an edge or vertex pair, one vertex,
or the sum of more than three selected vertex normals. Preserve reverse history
ordering when it supplies the complete requested contiguous domain. Use actual
boundary winding and authored explicit edge endpoints. Coincident vertices
retain separate identity. Hidden faces may contribute to geometric vertex
normals; only visible selected components choose the orientation.

Use inverse-transpose for face and vertex orientation. Edge orientation uses
the forward object frame and then removes the normal's component along the
transformed edge. Normalize both vectors and construct orthogonal axes. A zero
plane falls back to the vertex construction. A zero or collinear construction
falls back to identity. Reject nonfinite intermediate arithmetic before a
geometry, disk, receipt or undo change. Keep the existing component budget.

Independent tests must cover vertex and edge fallback, history/active-face
precedence, multi-face tangent choice, triangle and ngon geometry, disconnected
or coincident identity, shading-normal independence, reflected/nonuniform
object frames and save/undo/reload/failure atomicity. Run all source NORMAL
cases through CLI and official MCP. Then rerun all 2,406 source comparisons.
All remaining failures must remain visible with their unchanged limits.

For individual NORMAL orientation, use the source's per-island axis matrices.
Derive them by summing active-element geometric normals and tangents within the
actual selected edge/face groups. Use the source's tangent or dominant-axis
fallback. Ungrouped vertices use their own geometric normal frame. Connected
proportional vertices inherit the originating island's centre and axis matrix.
Keep distinct source translation, rotation and resize multiplication orders.
Report these derived local matrices per influenced vertex as
`component_basis_local`, while `basis_world` remains the common display frame.
No per-vertex direction may come from a reference result.
