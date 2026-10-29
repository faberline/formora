# Explicit seeded random falloff

Issue #50 adds a versioned random sequence to the Rust transform core.
It depends on #48 / draft PR #49. Implementation candidate:
`047b5072c5398704da9da1c6fe73d96cadb233b9`.
The contract and source evidence were committed before implementation in
`735c56f`. No issue or milestone is accepted by this report.

Agents can set `proportional.random_algorithm` to `blender_5_2` or
`splitmix64_v1`. Both interfaces use the same Rust operation. The operation
reports an explicit algorithm with its preserved seed. A missing algorithm
keeps the existing SplitMix64 behavior and omits the new receipt field.
Blender mode requires a seed in `0..=4294967295`. Legacy mode keeps all 64
seed bits. Invalid combinations fail before any scene change is published.

For example, a transform can contain:

```json
{
  "entity": "target",
  "change": {"kind": "translate", "value": [0, 0, 1]},
  "proportional": {
    "radius": 1,
    "falloff": "random",
    "seed": 42,
    "random_algorithm": "blender_5_2"
  }
}
```

The source is Blender 5.2.3 LTS commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`. The ordinary `BLI_rng_new` path
uses a 48-bit integer state. The Rust port preserves seeding, wrapping,
integer conversion and f32 division. It preserves the rare rounding to 1.0.
It does not use the source's separate scrambled-seed path or the clock.

Each operation starts a new stream. Draws follow sorted stable vertex IDs.
Selected, hidden, unreachable and out-of-radius vertices consume no draws.
A vertex exactly on the radius consumes a draw with zero influence.
Connected and projected distances retain their existing rules.

## Source sequence and API checks

Two independent C++ processes compiled the complete, unmodified pinned
`BLI_rand.hh`. Dependency stubs supply only unrelated vector and span types.
The source header, compiler command, stubs, driver, binary, raw bytes and
hashes are retained in `baseline/reference/blender-5.2.3/random-falloff`.
The process IDs are 9427 and 9429. Their complete outputs are identical.

Rust matched all 1,089,536 checked f32 values bit for bit. This covers ten
seeds with 4,096 draws each, plus 1,048,576 draws from seed 42. Restarted and
interleaved streams match. The fixed distribution smoke limits also pass:
mean 0.4996914899, variance 0.0833874600, and lag-one correlation 0.0008140329.
Every one of the 256 bins meets the fixed 12% count limit. Negative tests
reject truncated, non-finite, out-of-range, constant and alternating data.
These finite checks do not establish general statistical quality.

The real CLI session and official MCP SDK pass 96 cases. An additional 48
one-shot CLI applications match the session receipts and saved geometry.
The checks cover source and legacy streams, seed width, stable order, hidden
and unreachable vertices, radius boundaries, distance modes, shared assets,
schema exposure, invalid requests, failed batches, undo, replay and fresh
process reload. Rust tests also verify that failed saves preserve memory
and undo state. Actual Rust 1.85 passes 225 tests. Python passes 84 tests.
Formatting and Clippy pass.

The production executable also passes an unseen source-RNG edit with all
repository reads denied. That probe includes the existing mirror/UV/world
query, shared ownership, stale requests, failed batches, undo and replay.
Native Metal renders the new random deformation: 18 changed vertices and
12,532 changed pixels. Fresh reload image bytes are identical. The original
mirror/UV Metal check also passes with 15 changed vertices and 14,302 changed
pixels. Six Euler parent/child world queries still match the source exactly.

## Original gates and remaining work

All 2,406 original raw transform results are byte-identical to PR #49's
validation-reuse candidate. There are 2,392 matching or stochastic support
checks and fourteen remaining failures. No source case, expected answer,
request mapping, comparer, threshold or support rule changed. The seven
all-axis rotation cases still fail through both interfaces.

All legacy local regressions pass: 162 generation, eight scale, 1,060
selection, 262 creation-context, 57 payload and 42 normal-query checks.
The general official MCP regression passes. The original release benchmark
driver is unchanged. All nine fixed 100×100 grid samples pass: core
218.710833–229.120208 ms, pipeline 387.250584–403.248000 ms. Limits remain
250 ms and 2,000 ms. All nine saved outputs match the retained two-process
Blender reference with exactly zero position and normal error. The 1e-6
comparison limit and previous failed samples remain unchanged.

The source operator uses whole clock seconds and exposes no seed parameter.
Its original random captures remain stochastic support checks. This work
verifies an explicit seeded generator and native consumption rules. It does
not accept every source operator sequence, mirrored source allocation,
distribution, mode, numeric domain or capacity. A source import must retain
the source vertex order for a per-vertex sequence comparison. All remaining
roadmap work stays required.

All previous 3,785 baseline pins are unchanged. Twenty new source/evidence
pins bring the total to 3,805. Structural validation passes. Strict baseline
acceptance still fails with 9,003 pending source entries and 31 pending
features. All eleven milestones remain open.

Required three-platform CI, dependency integration and independent acceptance
remain unrun. Earlier CI was refused before executing steps due to GitHub
billing limits. A current PR-head check must confirm the latest CI state.
Issue #50 remains open with `agy:doing`.

Evidence: `docs/evidence/random-falloff/manifest.json`.
Read-only integrity check: `python3 docs/evidence/random-falloff/check-evidence.py`.
The checker retains the fourteen failures and reports zero accepted milestones.
