# Vertex merge: source baseline

Issue #70. Continue the full 0.0–1.0 goal. Depend on draft PR #67 at
dcc7a293145575851660ba6690e4bf36a2b42f8f. This work is independent of
draft PR #69 and its pending zero-scale policy. Do not change that policy.
Freeze this contract, authored cases and capture tools before native capture.
No Rust product code changes belong to this baseline.

Use Blender 5.2.3, build e13b728c6880, source commit
e13b728c6880d3084d9d57c30031ed5df8b39dee, executable SHA-256
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
Pin the editor operator, BMesh merge/weld and data interpolation sources.
Bind exact Git blobs and SHA-256. Preserve prior source bytes and limits.

## Authored cases

Create exactly 1,024 cases without measured answers:

- 800 vertex cases: five methods, two UV settings, ten topology selections,
  four nonsingular object frames and forward/reverse vertex history.
- 144 other-domain cases: CENTER, CURSOR and COLLAPSE, two UV settings,
  six nonempty selection-mode masks other than VERT, and four frames.
- 80 boundary cases: five methods, two UV settings, empty/single selection
  and four frames. Record unavailable FIRST/LAST enum rejection separately.

The methods are CENTER, CURSOR, COLLAPSE, FIRST and LAST. Frames are identity,
rotated/nonuniform, reflected and parented. The fixed 52-vertex authored
selection mesh includes grid faces, tetrahedron, isolated vertices, wire,
bow-tie, nonmanifold edge, inconsistent winding, interior faces, closed poles,
an n-gon and a hidden face. Use real two-layer UVs, group weights, materials,
smooth/seam flags and selection history. Keep all hidden geometry present.
The ten vertex selections cover grid edge, grid diagonal, tetrahedron,
isolated, wire, bow-tie, nonmanifold, winding, interior and n-gon regions.

Use two selected objects sharing one real mesh and one unselected child.
The active target owns the edit mesh. Preserve distinct object world frames.
Both shared users must report identical live mesh data after one source
operation. Do not run a shared data block twice. No zero-scale frame enters
this independent suite. Other parameter/data domains remain in the full goal.

## Native identity and results

Capture in two separate native viewport processes. Refuse existing output
and staging directories. Retain staging on failure. Record actual process
IDs, command lines, binary and script/input/source hashes, actual RNA and
terminal exits. Keep exact JSON with optional lossless gzip and raw/stored
hashes. Bind the historical baseline lock without changing old pins.

Snapshot every native vertex, edge, face and loop. Use native iteration
indices as snapshot identity. Separately record the actual integer capture
tag values. Welding can copy or interpolate tags. Duplicate tags must never
overwrite geometry entries. Do not mutate native data to repair identity.
Record topology, local/world positions, UVs and layer order, normals, group
names/weights, materials, flags, selection/history and active elements.

Bind all initial geometry, channels and settings to authored inputs.
Independently derive initial basis/world matrices and physical vertices.
Validate complete topology and attribute coverage before and after. Check
shared-data equality and unchanged object/cursor/settings state.

For CENTER and CURSOR, nonempty selected vertices become one vertex at the
authored mean or cursor converted into the target frame. FIRST/LAST preserve
the selected history endpoint position. Check resulting vertex counts and
survivor coordinates independently. COLLAPSE joins connected selected edge
components at their means; disconnected isolated vertices stay separate.
Unselected vertices stay unchanged unless the native topology operation
explicitly consumes them. Preserve zero weights and inactive UV layers.

An empty FIRST/LAST request can be unavailable through the context-sensitive
enum. If native Python rejects that enum, retain the exact error text and
require unchanged state. Otherwise require FINISHED and unchanged state.
Only that authored boundary permits this enum rejection. All other errors,
nonfinite values, missing fields/cases or nonzero terminal exits fail.
Never count an enum rejection or no-op as a numeric geometry match.

Compare every captured field in both processes. Discrete values remain exact.
Continuous positions, normals, UVs, weights, channels and matrices use maximum
absolute error 1e-6 per component. Do not remove a case or loosen limits
after capture. Add analytic and actual-native negative controls for wrong
merge locations, history endpoints, UV behavior, topology, source tags,
shared data, hashes, missing cases and failed/missing terminal receipts.

## Later Rust gates

After the complete source baseline passes, freeze a separate before-code
product contract. Both CLI and official MCP must use the same operation core.
Require actual saved topology and attributes, physical query/preview data,
typed receipts, fresh-process reload, undo/replay, atomic errors, recipes,
source-independent checks and performance workloads fixed before product code.
Retain prior required gates. Three-platform CI, dependency integration and
independent Codex acceptance remain required. A failed, skipped or unrun
required check cannot pass. Keep catalog reviews pending, complete_products
empty and every milestone open until the full acceptance rules are met.
