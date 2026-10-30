# Preserve unaffected UV data and remove duplicate merge work

Issue 72. Keep all source cases, original workloads, clocks, validation,
sample counts, limits and earlier failures. No new acceptance exception.

UV math uses the pinned f32 operations on the loops it actually uses.
Unmodified loops retain their stored f64 values exactly. This includes an
unselected triangle in a different region, even when its finite UV values
are outside f32 range. Do not convert every unselected loop to f32 merely
because another selected region uses the same named layer. A touched value
that cannot fit the required arithmetic must still fail atomically.

Freeze four analytic tests before repair. They use a six-sided face split,
an untouched stored triangle, negative integer data, repeated tag values on
distinct vertices, zero weights, two UV layers, shared users, noncommuting
parent/owner frames, real world queries, undo and serialized reload. Keep
the first failed native runs, including the actual OS read-denial controls.

The complete 2,048-request repaired-history API gate passed. All thirty
large-grid physical results match source. The combined timing/source gate
still fails because the second full timing trial exceeds the fixed limit.
Keep every sample. Do not retry an unchanged implementation to select a
better trial, drop a sample, reduce validation or change a limit.

Remove the duplicate immutable asset copy inside the private weld kernel.
Read the original through an immutable borrow while editing its private
candidate. Keep the existing atomic publication boundary and complete
input/result validation. Do not move work outside any frozen clock.

A face cannot survive welding when all of its mapped corners contain fewer
than three distinct vertex IDs. When no face can survive, no loop-data
output survives either. Avoid building those discarded face/UV records.
When any face can survive, compute the complete source UV contributions
before pruning degenerate faces, including contributions from faces that
will later be removed. Component identity never comes from attribute data.
This is a general topology rule; it cannot depend on a fixture ID or size.

Run the complete source, CLI/MCP, analytic, timing and retained gates on the
repaired implementation. Prior passes at a different library do not pass
it. Independent Codex acceptance and all milestones remain unpassed.
