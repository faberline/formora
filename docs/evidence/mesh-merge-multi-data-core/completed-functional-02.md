# Completed retained functional checks

Refs #79 and #80. This report follows `completed-functional-01.md`.
All 16,374 retained interface records and all 1,687 retained asset checks
are now complete. This accepts no whole feature, issue or milestone.
The new 26,880-record multi-data matrix is still running.
Its complete raw audit is still unrun. All 207 retained timing samples and
their physical source comparisons are also unrun.

The effective Rust implementation remains
`0a5a3bed31b974fc5cee98155c3dc7113bf12a87`.
The frozen full-run tree remains
`bd13f3d424f2649b4b25c16305c4e5b0eb7f8542`.
No product, test, tool or frozen contract changed during these runs.
The default executable SHA-256 remains
`64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019`.
The preview executable SHA-256 remains
`518d5cb60791ccbd40c972e875807d836120aceadb4183c95e0647147bc00b65`.

## Retained interfaces and assets

The retained parent waited for all 13 children. Each child exited 0.
The official MCP SDK smoke check passed. It adds no numeric match count.
The previous archive contains the 2,048 single-data merge records and
3,584 delta records. This archive adds the remaining 10,742 raw records:

| Corpus | Records | Classification |
| --- | ---: | --- |
| Raw rotation | 4,992 | Original defined comparisons retained |
| Scene snap | 1,100 | 1,094 defined, four source cancellations, two atomic rejections |
| Single snap | 2,244 | 2,072 defined, 136 source cancellations, 36 atomic rejections |
| Mesh transform | 2,406 | Original 2,344 deterministic and 48 stochastic cases; 14 approved undefined-input rejections |

Separate audit processes rechecked all raw results, saved scenes, source
records and terminal receipts. Each audit exited 0. The transform source
outcomes remain 2,380 FINISHED, 12 CANCELLED and 14 human-approved rejections.
Rejections and cancellations do not count as numeric matches. The approved
three-axis rotation rejection does not weaken any defined-source check.

The seven asset families retain their original scopes: primitive 162,
scale eight, selection 1,060, creation 262, payload 57, normal 42 and RNG 96.
A separate audit checked all 1,687 raw results and rejected seven forged
results. These controls do not execute forged operations. Full numeric input
domains, full custom normals and payload generation remain outside these
bounded retained checks. Their broader product requirements remain open.

## Other retained gates

- All 12 small suites exited 0. These cover seven source-read denial suites
  and five recipe, action and input-rejection suites.
- The failed-save proof, one-shot RNG proof and exact Euler source proof
  exited 0. They retain their original 19, 48 and six checks.
- All five retained Metal suites exited 0. Original pixel thresholds and
  fresh-load byte checks remain unchanged. Six actual images were inspected.
  Filled surfaces and expected selection marks are visible. The single-data
  merge changes the edited face. The outside green triangle stays unchanged.

All adapted drivers keep their original assertions. Binding records show
the exact path, output, executable and source-head changes. Reversing those
bindings recovers the original scripts. The failed-save driver now renames
its empty recovery directory and preserves it. Its assertions are unchanged.
Original failed attempts and all source files remain available.

## Archive and pending gates

`completed-functional-02/archive-manifest.json` binds 12,869 lossless copies.
It records original and stored SHA-256 values. PNG and Python files remain
directly viewable. Other files can use lossless gzip. Empty source directories
are preserved and listed. Together, the two completed functional archives
contain all 16,374 retained interface records and 1,687 asset checks.

Six compiled timing drivers and their wrapper bindings are saved for later
use. Compilation is not timing acceptance. No timing sample was run by this
archive step. The original workloads, clocks and limits must remain intact.

The new 26,880-record matrix, full raw audit, 207 retained timing/source
samples, remaining native requirements, dependency integration, three-platform
CI and independent Codex acceptance remain required. CI has not passed.
Issues #79 and #80 remain open with `agy:doing`. All 11 milestones remain open.
