# Distance merge source registry

Issue #82, milestone 0.0. This document fixes source acceptance. It does not
add a Rust operation or accept a product feature.

The source is Blender 5.2.3, commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`. The admitted native binary hash
and immutable official manual snapshot remain unchanged.

`baseline/fixtures/mesh-merge-distance-complete-02.json` contains 2,412 cases.
The first 1,188 preserve every original draft assignment and parameter.
The retained 116 targeted cases include analytic pairs, normal setup, scalar
conversion, rejection and explicitly tagged native nonfinite probes.
Expanded rows add missing factor combinations and hidden-data interactions.

| Domain | Fixed coverage |
| --- | --- |
| Geometry | Eleven literal fixtures: loose pair, unequal triplet, chain, centroid tie, quad strip, concave face, nonmanifold fan, coincident disconnected faces, smooth open and smooth cyclic fans, plus a repeat-sensitive chain. |
| Parameters | All eight boolean combinations. Six ordinary distance levels. All nonempty omission sets, scalar coercion/bounds/invalid types, unknown keyword and native nonfinite probes. |
| Selection | Seven nonempty masks, all/alternating/none selection, no/forward/reverse typed history. |
| Context | Single data, two independent data in either active order, and active linked owner. A linked non-edit owner and an outside mesh are retained. |
| Frames | Identity, noncommuting hierarchy, nonuniform, negative, zero-axis and zero-parent scale. |
| Units | None, metric 0.01 and metric 100. |
| Normals | Ten automatic/custom presets, including smooth fans and source input clamp/int16 conversion. |
| Data | Two UV layers, active layer/order, material slots, smooth/seam/sharp flags, named signed/duplicate/provenance integers, group names and explicit zero weights. |

All 1,636 expanded assignments of two factors are present. Complete named
three-factor products cover geometry/options/distance, mode/selection/context
and options/normals/frame. The hidden mode/selection/context/history product
contains 252 added cases, plus the retained earlier hidden case. This is a
finite source acceptance registry. It is not every Cartesian combination or
every representable floating point input.
The repeat-sensitive chain has points at 0, 0.125 and 0.1875 with threshold 0.125.
One centroid pass must leave 0.0625 and 0.1875. A repeated pass collapses them to
0.125. Sixteen explicit owner/option cases therefore expose duplicate data
processing. The earlier2,319-case candidate01 was never sealed or executed;
its input, generator and preparation evidence remain retained.

Before complete native execution, commit the registry and all required code.
Create a separate immutable seal. The seal records that code commit, exact
source/script/input hashes, case count, binary identity and original limits.
The seal verifier checks the committed bytes. A diagnostic cannot substitute
for a sealed complete capture.
The historical source lock is copied byte-for-byte before sealing. Existing
baseline fields and artifact pins must remain equal. Later artifact additions
can extend the list without changing its frozen prefix.

Run every case in two fresh factory-startup native viewport processes.
Use the fixed window geometry to preserve the viewport context. Each process
must create the authored state, execute the source operator, save a real
native file, reopen it and capture the complete resulting state. Keep raw
JSON, gzip/native bytes, exact commands, PIDs, stdout/stderr hashes and actual
parent terminal waits. Missing, failed or timed-out receipts cannot pass.

Both captures must pass independent authored-input binding, source group
positions/removal analysis, strict complete state invariants and complete
after/reopen comparison. Their run, actual arguments, scene, before, after,
reloaded, result and save/open status fields must match each other. Each
native file has its own byte digest; native timestamps are not semantic state.
Every frozen case is required. None may be dropped, renamed or counted from
the successful subset.

Continuous comparisons stay at absolute 1e-6. Discrete values, order, flags,
packed integers and topology stay exact. Source input rejection, unchanged
completion, empty-data skips and native nonfinite probes remain separate.
Rejections/skips/native nonfinite observations are not numeric matches.
The approved singular-parent local-query policy remains `cannot_invert` with
raw local query, valid operation/world and no numeric local-query match.

Keep all failed attempts and reasons. A corrected harness requires a new
code seal and two fresh complete captures. Do not relax limits, remove a
failed case or edit bound inputs/code while a capture is live.

Functional source completion does not finish #82 alone. Before Rust distance
implementation, separately freeze capacity workloads, forms and three samples
per form. Class A is 10,201 vertices, 20,200 edges and 10,000 quads on the fixed
M1 Max. Per-data limits remain 250 ms core and 2,000 ms operation/save/fresh-read;
two-data limits remain 500/4,000 ms. Full validation stays inside the clocks.
Retain actual source results before opening the Rust distance issue.

Platform CI, dependency integration and independent acceptance remain required.
All 11 milestones stay open until their own complete gates pass.
