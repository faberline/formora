# Vertex integer interpolation continuation for issue 72

Keep the original merge contract, all source captures, fixed workloads,
timers, limits and before-code tests unchanged. The exact-zero query policy
was approved later and is implemented separately by issue 73. This isolated
work remains based on the frozen nonsingular merge corpus.

Port the pinned CustomData_bmesh_interp default equal weights and
layerInterp_propInt callback. The contributor order includes the survivor
first, followed by actual removed vertex IDs in source mesh order. Accumulate
each i32 value converted to f32, multiplied by the f32 reciprocal count, with
separate f32 multiply/add rounding. Round the final sum halfway away from zero.

Attribute values never identify components. Duplicate values on different
IDs stay distinct. Modify only the survivor values in vertex integer layers.
Keep contributor IDs, unrelated IDs and all other domains unchanged. A
singleton keeps its original i32 value without a needless f32 round trip.
Reject empty, duplicate or missing contributor IDs and a mismatched first ID.
Reject a derived value outside the i32 domain before writing any layer.
Failure in a later layer must leave every earlier layer unchanged.

Freeze tests before this helper is implemented. A pre-code compile failure
for the missing API executes zero tests and is not a passing result. The full
merge kernel, CLI/MCP command, receipts, topology/UV/group handling, 1,024
source cases, complete numeric domains, 30 new timings and all retained gates
remain required. This helper alone cannot complete issue 72 or any milestone.
