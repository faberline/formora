# Fixed-seed random falloff sequences

This is additional 0.2 work after the transform core in #48 / draft PR #49.
It does not replace the original 1,203-case transform gate or its fourteen
remaining failures. No feature or milestone is accepted by this finite suite.

## Source and API

Use Blender 5.2.3 LTS source commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee`.
Pin the complete `BLI_rand.hh`, `rand.cc`, and `transform_convert.cc` files.
Retain every existing source pin and inventory identity.

Add optional `proportional.random_algorithm` with values `splitmix64_v1`
and `blender_5_2`. An omitted field keeps the existing SplitMix64 sequence,
64-bit seed behavior, request serialization and receipt bytes unchanged.
An explicit algorithm is reported in the operation receipt. Reject unknown
algorithms, an algorithm on a non-random falloff, a missing random seed, and
a Blender seed above `u32::MAX`. Do not truncate seeds or use the clock.
Both agent interfaces use the same Rust core.

For `blender_5_2`, port the source's ordinary `seed`, `step`, `get_int32`,
and `get_float` path used by `BLI_rng_new` / `BLI_rng_get_float`.
Do not use the separate scrambled `seed_random` path. Preserve the source's
integer widths, wrapping, cast to f32 and division order. The source's float
rounding can produce 1.0; do not clamp, resample or change that result.

Each operation starts a fresh sequence from its explicit seed. Consume one
draw per visible, unselected, reachable vertex inside or exactly on the
radius. Visit canonical stable vertex IDs in sorted order. Selected, hidden,
unreachable and out-of-radius vertices consume no draws. A radius-boundary
vertex consumes a draw even though its linear distance ratio is zero.
Multiply the draw by the existing f32 distance ratio. Connected and projected
distance rules, mirror ordering, geometry, UVs and normals remain unchanged.

The source calculates factors in its raw mesh vertex order; its sorted index
map does not reorder that storage. Canonical IDs provide Formora's stable
order. A source import must preserve that order to claim per-vertex sequence
agreement. Clock-seeded source operator captures remain stochastic support
checks. They do not become deterministic comparisons.

## Gates fixed before implementation

- Compile an independent C++ oracle using the complete pinned, unmodified
  `BLI_rand.hh`. Dependency stubs may supply unrelated vector/span types only.
  Keep compiler commands, stubs, driver, raw outputs and hashes.
- Compare exact f32 bits for 4,096 draws for each seed in
  `[0, 1, 2, 42, 65535, 65536, 1234567, 2147483647, 2147483648, 4294967295]`.
  Check reproducible restart and interleaved independent generator instances.
- Inspect 1,048,576 source draws from seed 42. Keep the complete raw f32 bits.
  Require finite values in [0,1], mean within 0.002 of 0.5, variance within
  0.001 of 1/12, absolute lag-one correlation below 0.01, and all 256 histogram
  bins within 12% of the expected count. These fixed smoke limits do not
  establish general statistical quality or cryptographic safety.
- Test actual editor geometry and influence receipts. Cover skipped vertices,
  zero-ratio draw consumption, sorted IDs, connected/projected distance,
  explicit legacy mode, full-width legacy seeds, rejection, rollback, undo,
  save/reload and replay. No expected output may become a product input.
- Exercise the new option through CLI and the official MCP SDK. Check exact
  geometry, receipt metadata, schema exposure, failed batches and saved state.
- Run actual Rust 1.85 tests, Python tests, formatting and Clippy. Keep every
  original source input, comparator, tolerance, random support rule and gate.
  Run all 2,406 original transform requests and require byte-identical raw
  results relative to PR #49's validation-reuse candidate. Retain all failures.
- Retain the legacy regression suites, native repository-denied execution,
  Metal modification/reload checks and the fixed release performance gate.
  A new option is not a waiver for those checks.

Required three-platform CI, dependency integration and independent acceptance
remain necessary. Failed, skipped and unrun checks cannot pass. The issue
stays open; `agy:done` requires its complete implementation gates first.
All eleven milestones and the full feature roadmap remain unchanged.
