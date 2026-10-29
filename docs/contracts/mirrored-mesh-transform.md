# Mirrored component transforms

This extends issue #48 before implementation. Keep the complete 2,406-case
source gate and its fixed limits. Mirror support alone cannot accept the issue.

Use the actual authored mesh positions, topology, selection and hidden flags.
The optional mirror axis is in mesh-local space. Use float32 arithmetic and the
pinned source threshold `0.00002`. A spatial match requires squared distance
strictly below the squared threshold. Hidden vertices cannot be sources or
destinations. Without proportional editing, only selected vertices initiate
the mirror cache. Cache assignments are reciprocal and use stable component
order. Equal-distance spatial ties use the lowest stable vertex ID in the
native API. Source tie parity is not established by this policy.

Topology mode uses the pinned unsigned 32-bit wrapping connectivity hashes.
Initialize hashes with edge degrees. Accumulate previous neighbour hashes times
the pass number in stable edge order. The pinned hash comparator compares
addresses, not pointed-to hash values. On the verified platform it preserves
the array order; its transition count must not be replaced by a corrected
unique-value count. The final hash/index pairs are sorted by hash. A group of
two forms a pair; a singleton is a self-match; larger groups are unmatched.
Self-matches are removed by the mirror cache. Check the literal comparator with
a standalone primary-source probe. Cross-platform parity remains unrun.

The sum of visible selected coordinates chooses the source half-space. A zero
sum chooses the positive side. Allow the source epsilon across that plane.
Each destination has one source. Do not create mirror dependency cycles.
Destinations are not transformed a second time. After transforming source
vertices, set their original near-plane axis coordinates to zero. This strict
plane test also applies to visible proportional data outside the radius. Then
copy each source result to its destination and negate the mirror coordinate.
Do not reflect displacement alone or use world coordinates for pairing.

Receipts add optional `mirror_sources` (destination ID to source ID) and
`mirror_plane_vertices` (source IDs clamped to the plane). The normal influence
map retains positive transform weights. Mirrored destinations inherit their
source's positive weight and retain their own derived centre. Plane clamps can
change a vertex with zero proportional weight; their IDs remain explicit in
the separate field. Changed component IDs describe the final published asset,
including copies and clamps. No duplicate or hidden component may appear.

Use a balanced spatial search. Bound hash/search work by 64 times the component
budget. Exhaustion, invalid requests, stale revisions, later batch errors and
failed saves leave disk, scene and undo unchanged. Preserve IDs, shared asset
ownership, UVs, groups, selection and hidden state. Recompute automatic normals
only after the final geometry is ready.

Tests must include all axes, both half-spaces, both selected sides, hidden
partners, the strict plane threshold, asymmetric topology pairs, ambiguous
topology groups, proportional copies/clamps, actual save/reopen, undo and
rollback. Run all twelve authored mirror-context cases through CLI and official
MCP, then run the full source suite without changing its expected data.
