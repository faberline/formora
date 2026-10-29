# Connected proportional mesh transforms

This extends issue #48. Its full 2,406-case gate, unchanged 1e-6 limits, release
performance, integration and independent acceptance remain required.

Use the frozen `transform_convert_mesh_connectivity_distance` wave queues and
`geodesic_distance_propagate_across_triangle` from Blender commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`.
Propagate along loose edges and across visible polygon surfaces. An edge-only
shortest path is insufficient. Keep actual mesh identity and topology.

Distances use the actual object's linear world frame. They do not use world
translation. Connected distance takes precedence over view projection, as in
the pinned source. Hidden elements block propagation. Disconnected vertices
remain outside the influenced region.

Preserve the originating selected vertex during propagation. Individual pivots
inherit its actual selected island centre. Isolated selected vertices supply a
centre in vertex mode. Other modes retain the source's no-island fallback.
Apply the existing deterministic and explicitly seeded random falloffs to these
distances. Query receipts must report the actual weights and centres.

Use finite f32 arithmetic with the pinned operation order. Preserve the fallback
to direct edge distance when the surface estimate is invalid. Reject arithmetic
overflow. Bound propagation work by `max_components * 64`, with checked/saturating
count arithmetic. Exceeding the work budget must leave scene, disk, receipts and
undo unchanged.

Independent tests must distinguish surface distance from edge-only distance.
They must cover wire paths, disconnected coincident vertices, hidden barriers,
non-uniform and reflected object scales, translation independence, individual
centres, projection precedence, seeded replay and failure atomicity.
Run all 114 connected source cases through each interface as a focused diagnostic.
Then rerun the entire unchanged 2,406-case gate. Focused success alone cannot
accept the issue, a feature or a milestone.
