# UV correction during component transforms

This fixes the native UV correction behavior before implementation in issue
#48. Keep the complete source suite, fixed tolerances, and all remaining gates.
This change covers the UV layers that the native asset can store. Other corner
attribute types and multiresolution data require their own later implementation.

When `correct_face_attributes` is true, copy the original face geometry and UV
layers before changing coordinates. Correct loop data for visible transform
vertices and their mirror destinations. Proportional data includes vertices
outside the influence radius. Hidden neighbouring faces still contribute their
incident corners. Preserve IDs, geometry topology, materials, seam flags, UV
layer order, active layer, selection, hidden state, vertex groups and weights.

Project each new corner position into the original face's 2D orthogonal basis.
Derive its normal from original geometry, never stored shading normals. Use the
pinned `interp_weights_poly_v2` mean-value coordinates, including float32 border
thresholds, point/segment shortcuts, double half-tangent arithmetic and float32
weight normalization. Interpolate each existing UV layer with the pinned
float32 multiply/add order. This permits extrapolation outside a face.

For a zero-area face, choose its actual radial neighbour with nonzero normal.
Prefer an edge with both vertices unselected. Copy the neighbour's original
data and project all corners of the zero-area face during setup. Use this
substitute for subsequent correction. If no substitute exists, derive the
orthogonal projection axis from the pinned automatic face tangent and its
orthogonal vector fallback. Preserve the mean-value function's zero results
when it cannot assign a nonzero total weight. Reject nonfinite output.

With `keep_connected: false`, leave each corrected corner independent. With
`keep_connected: true`, snapshot contiguous UV fans separately for each layer
and vertex before editing. Follow the actual radial-next relation in both
corner-edge directions. Two original UV values join when their squared
distance is strictly below `0.00001`. The seam flag alone does not split a
group. Different layers can have different groups. Disconnected coincident
vertices remain distinct.

Initial group weights use original geometric corner angles. Skip coincident
edge endpoints using the source epsilon. Normalize the weights, or use equal
weights when their total is zero. For moved vertices (squared displacement
greater than float epsilon), project original neighbours onto the original
vertex-normal plane. Use the pinned signed squared corner distance and `1e-8`
transition interval to reweight each original group. If all new weights are
zero, use the original weights. Merge corrected values and copy the result to
every corner in that group. Use original coordinates for all transform data
and current coordinates for other neighbours, as in the source.

Correct after mirror copies and before updating automatic shading normals.
Track faces whose UV payload changed in the normal changed-face receipt even
when their vertex coordinates did not change. Add optional
`attribute_faces` with the exact UV-changed face IDs. A UV-only change also
marks a generated asset edited. Preserve persist-on-success atomic behavior.

Tests must independently check projected affine UVs, triangles and n-gons,
multiple layers, connected fans, separate UV islands, disconnected vertices,
seams, nonmanifold traversal, degenerate substitutes, no-UV assets, mirrors,
replay, undo, saved reopen and failed saves. A finite sample cannot establish
all modelling or UV feature parity. Run all eighteen authored correction cases
through CLI and official MCP, followed by the unchanged complete source gate.
