# Complete multi-data runtime execution

Refs #79 and #80. All issues and milestones remain open.
This report proves full runtime execution. It does not accept the complete
interface evidence gate, an issue or a milestone.

The actual parent waited for process 5100. That process exited 0.
Both required interfaces completed all 13,440 authored cases.
The runtime report contains 26,880 unique interface/case pairs and no failed
record. Each interface has 9,088 completed source comparisons and 4,352
explicit enum rejections. Rejections do not count as numeric matches.

The frozen runtime tree is
`bd13f3d424f2649b4b25c16305c4e5b0eb7f8542`.
All 216 registered input files still have their recorded hashes.
The actual executable SHA-256 is unchanged:
`64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019`.
The effective Rust implementation remains
`0a5a3bed31b974fc5cee98155c3dc7113bf12a87`.
Only documentation and completed evidence were added during the run.

`full-runtime-terminal-01/` preserves the full runtime report, actual start
and terminal receipts, and parent stdout/stderr. Large files use lossless
gzip. The seal report binds original and stored hashes. Originals remain
outside the repository. The seal checks coverage, classification, the actual
parent wait result, executable identity and every registered input hash.
It does not replace the separate raw-record audit.

The separate audit has started as actual process 43142. It must recheck every
raw request, reply, saved scene, source comparison, physical query, scale-lock
query and MCP process receipt. Its required scope is 26,880 records and
860,160 bound calls. It has no accepted terminal result at this snapshot.
The full 30 corruption controls are also still unrun at this snapshot.

The queued controller waits for these two checks before running the 207
retained timing samples and their physical source comparisons. Original
workloads, counts, clocks, validation and limits remain unchanged.
The [completed retained functional checks](completed-functional-02.md)
remain separate evidence. Their passing results cannot replace these gates.

Required platform CI, dependency integration and independent Codex acceptance
remain unpassed or unrun. No failed, skipped or unrun required gate passes.
All 11 milestones remain open. This snapshot makes no product acceptance claim.
