# Merge persistence and actual change receipts

Issue 72. Keep the original merge source cases, tests, limits and contracts.

Explicit FIRST/LAST welding does not copy a rounded position into the
survivor. Preserve its actual stored f64 coordinates, and the unrelated
coordinates, bit for bit. This operation needs no coordinate arithmetic
for the explicit endpoint. The selected-to-center/cursor and edge collapse
means retain their existing source f32 arithmetic.

A surviving edge changes geometrically when either endpoint moves, even
when its persistent ID and endpoint IDs stay the same. A surviving face
changes geometrically when one of its corners moves. Receipts must report
these real changes, alongside stored topology, attribute and flag changes.
Created and removed components stay separate from changed survivors.

The pinned editmesh_tools.cc skips a mesh only when totvertsel is zero.
A successful collapse with selected vertices but no selected edges still
clears selected geometry and history when vertex mode is absent. It keeps
the actual geometry. The receipt must include the changed vertex flags.

Freeze three behavioral controls before repair. Keep the real first three
failures. These controls supplement the source corpus; they do not replace
any source, CLI/MCP, performance, integration or acceptance gate.
