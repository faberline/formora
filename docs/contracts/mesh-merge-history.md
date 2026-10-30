# Merge history keeps the original overlap flags

Issue 72. Keep the original source cases, timing inputs, clocks and limits.
The new controls do not replace or weaken an earlier gate.

The pinned BM_select_history_merge_from_targetmap first marks each original
history component. It then maps the entries. During deduplication, a mapped
entry survives only if its destination had an original history flag. It
clears that flag after keeping the first entry. A removed-only history does
not create a new entry on a survivor absent from the original history.

Apply this rule separately to typed vertices, edges and faces. Keep the
first mapped entry once when the actual destination was in original
history. A valid explicit FIRST/LAST endpoint keeps its existing entry.
Disconnected collapse components keep only their own original flags.
Active-face mapping is independent of this history overlap rule.

The fixed large grid has only v010200 in initial history. CENTER/CURSOR
and COLLAPSE remove that vertex, so native after-history is empty.
FIRST/LAST preserve that endpoint and its entry. The native snapshots and
the unchanged marking source are retained as evidence.

Before repair, five independent controls execute: two pass and three fail.
Keep these failures. Repair the core and run every required source, real
CLI/MCP and performance gate again. The first thirty timings passed limits
but their source comparison failed on history. That combined gate does not
pass. The earlier 2,048-request corpus also failed verification because
sparse-path reapplication removed a required contract during the run.
Keep that complete failed run. Fix the full input inventory before rerun.
