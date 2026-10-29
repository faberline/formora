# Raw rotation snap core: source preparation

Issue #62 is OPEN with agy:doing under milestone 0.2. This is work in
progress. The Rust candidate below is not product acceptance.

Before-code contract b6aff74d93ac72420368d34f828b6717ac591180 fixes all
2,496 native rotation cases through both real product interfaces, all prior
gates, and 24 added release samples. Commit 6516cf91 freezes the original
class-A grid bytes, eight raw rotation settings and native capture adapter.

Native Blender process 55824 completed all eight large-grid modes, terminal
exit 0. It used fixed executable de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
All eight source checks passed: exact authored local geometry/channels,
independently evaluated initial world frames/vertices, preserved topology,
unchanged cursor, and actual child world preservation with changed stored
parent inverse. Every raw and gzip hash and all capture inputs were checked.

Source files, terminal receipts and checks are in
docs/evidence/snap-rotation-core/performance. The 24 Rust performance samples
are UNRUN. The full 4,992-request gate and required retained product suites
remain UNRUN for this slice.

## Rust candidate and local checks

The candidate adds explicit stored active/inactive rotation channels, W/angle
locks, the saved four-dimensional UI flag, raw cursor orientation and actual
cursor matrix queries. Source setters preserve quaternion sign and locked
channels. Evaluation normalizes a copy. Legacy unit-quaternion validity is
unchanged. A legacy snap that produces nonunit raw channels promotes its actual
stored result to the explicit channel representation. It does not normalize
the saved channels to force legacy validity.

CLI/MCP and preview frames share the core. Both scene-snap and single-mesh
cursor paths have actual before/after raw cursor receipts. New raw cursor
orientations must have a finite evaluable physical matrix before publication.
Old serialized states and receipts omit the added optional/default fields.

At debug binary SHA-256
093b46f00749eddde3930d4aa5377315a553bafb878807f8ecb8f42db37e54fa:

- 263 actual Rust 1.85 all-feature tests passed, none ignored.
- 152 Python tests passed. Twelve new controls use actual retained product
  output to reject wrong raw modes/order/sign/normalization, false locks,
  stale matrices and false receipts. Authored setup cannot read source output.
- Clippy with warnings denied, format, debug build and release library passed.
- A 136-case pilot through both actual interfaces passed all 272 operations.
  It covers mode conversions, scaled parent frames, protected quaternion/axis
  channels, boundaries, cursor clearing and mesh editing. Raw data and complete
  before/after queries are retained. This is not the full 4,992-request gate.

New Rust cases test raw quarter-turn geometry, shared asset preservation,
nonunit channels after locks, undo/replay, legacy promotion, W locks, raw axis
locks, cursor origin across all modes, disabled rotation, atomic late/stale/
range errors, invalid inactive data, pinned zero-quaternion behavior and the
single-mesh cursor path. The former legacy-quaternion rejection is now an
actual physical-pose/serialization success test. Existing budget/context
negative cases remain. Required source fixtures and limits are unchanged.

Preserved development failures include: a shell PATH quoting error before
Cargo ran; the obsolete quaternion-rejection assertion; new test fixtures with
the wrong polygon material field; and a range-test setup that used a valid
F64 object pose rather than an invalid source cursor. These were corrected
without changing a source capture or acceptance limit. Their original logs
remain in diagnostics. All final checks above have actual terminal exit 0.

Next run the full frozen request set, native isolation/Metal/recipe proofs,
all retained gates and all 24+90+30+9 fixed release samples. Keep every failed
sample and all source captures unchanged. Integration and independent
acceptance remain required.

PR #61 is draft at c425d470c78825412f182d39ae658f7c323c118c above draft PR #59.
Its push 40951169057 and PR 40951283364 CI runs failed before all six jobs
could start. GitHub reported account payments/spending-limit restrictions.
Three-platform CI, integration and independent Codex acceptance remain
required. No complete feature or milestone is accepted. The original unlimited
goal remains active for all eleven milestones.
