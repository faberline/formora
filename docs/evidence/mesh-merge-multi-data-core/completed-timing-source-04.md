# Complete retained timing and source evidence

Refs #79 and #80. All 207 retained timings and all 207 physical source
comparisons now pass. No issue or milestone is accepted by this report.

The recovery parent waited for each actual child. Its six stages exited 0.
The 177-sample source controller also waited for all five actual children.
The final 30-sample source comparison exited 0. All recorded input hashes
remain unchanged. The original 1e-6 continuous limits and exact discrete
comparisons remain intact. Every saved output is checked against the fixed
native source and independent authored input.

The first timing attempt failed on sandbox-denied host probes before three
groups could run. Those failures remain failures. The already-passed 39
samples are retained. The recovery runs only the pending 168 samples.
It keeps every original workload, sample, clock, validation and limit.
The original `top` and `sysctl` probes run with host-read permission.
The actual hardware remains Apple M1 Max. No probe or sample is skipped.

The table shows the slowest measured sample in each group. Values are in ms.
Scene A and B use one grid. Scene C uses two grids. Each class-A grid has
10,201 vertices, 20,200 edges and 10,000 quads.

| Group | Samples | Core max | Core limit | Save/reload max | Save/reload limit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Scene A | 30 | 126.250958 | 250 | 280.361708 | 2,000 |
| Scene B | 30 | 125.251542 | 250 | 277.595041 | 2,000 |
| Scene C | 30 | 255.479084 | 500 | 557.611167 | 4,000 |
| Rotation | 24 | 132.122917 | 250 | 304.492708 | 2,000 |
| Delta | 24 | 129.042709 | 250 | 291.583166 | 2,000 |
| Single snap | 30 | 213.904833 | 250 | 368.190458 | 2,000 |
| Transform | 9 | 221.750208 | 250 | 376.542084 | 2,000 |
| Single-data merge | 30 | 158.190167 | 250 | 179.505000 | 2,000 |

`completed-timing-source-04/` preserves 816 lossless files. These include all
timed scenes, receipts, queries, timing reports, physical source checks,
actual process receipts, host data and exact driver bindings. It also lists
and preserves the failed attempts' empty directories. Every original remains
available. Stored hashes, decompressed hashes and original hashes have been
checked separately. Large raw files can use lossless gzip.

The effective Rust implementation remains
`0a5a3bed31b974fc5cee98155c3dc7113bf12a87`.
The executable SHA-256 remains
`64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019`.
The frozen runtime tree remains
`bd13f3d424f2649b4b25c16305c4e5b0eb7f8542`.
Only evidence and documentation were added during the long runs.

The new two-data merge capacity proof is separate. Its original 30 samples
already pass the unchanged 500/4,000 ms limits on this implementation.
This report does not add 30 to the retained 207 count.

[Full CLI/MCP raw evidence](completed-full-runtime-03.md) and
[retained functional evidence](completed-functional-02.md) remain separate
completed gates. Platform CI, dependency integration and independent Codex
acceptance still apply. No failed, skipped or unrun required gate passes.
All 11 milestones remain open.
