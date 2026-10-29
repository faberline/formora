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
are now complete as local gates. The final results below do not grant
three-platform, integration or independent Codex acceptance.

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

The complete 4,992 new CLI/MCP requests passed on the same binary. Every case
compares raw modes/channels/locks, actual Rust frames and cursor matrices,
geometry, normals, attributes and real receipts against both fixed native
captures. Each new request has an actual fresh-process reload check. The
retained 5,750 request gate also passed: 1,100 object/multi-edit snaps,
2,244 single-mesh snaps and 2,406 transforms. Cancellations and expected atomic
rejections remain distinct. The 14 approved undefined-source rotation cases
are explicit rejections and are not numeric source matches.

All 1,591 retained primitive/scale/selection/creation/payload/normal checks,
96 RNG checks and official MCP smoke passed. All 48 one-shot RNG cases and
all six retained Euler-order frame checks passed. Both raw scene-snap and
legacy mesh-snap recipe proofs passed, including rollback, undo/replay,
regeneration and reload. Six native source-read-denied proofs passed. The new
27-call proof uses unseen nonunit channels, analytic physical rotation and
parent conversion, actual child inverse changes and complete fresh reload.

The new native Metal scene changed 25 real shared vertices and 20,350 pixels.
It preserves the selected surface and child's world frames through actual
geometry compensation and parent-inverse changes. Stored nonunit quaternion
channels and inactive data remain intact. Fresh reload PNGs are byte-identical.
Both retained RNG/mirror Metal proofs also passed, changing 12,532 and 14,302
pixels respectively with identical reload PNGs. The before/after new images
were visually inspected. Opening the after image in the app returned queued.

## Fixed performance and preserved preparation failure

All final 153 release samples passed the original time limits and fresh
source comparisons. Inputs, raw saved scenes, receipts, monotonic intervals,
compiler/library hashes, controller receipts and source results are retained.
The original one-process method writes outside the watched checkout on the
same filesystem. No priority, host setting, grid, case or limit was changed.

| Gate | Samples | Maximum core / full pipeline (ms) | Original limits (ms) |
|---|---:|---:|---:|
| Raw rotation modes | 24 | 139.497292 / 364.165 | 250 / 2,000 |
| Retained scene classes | 90 | 295.215125 / 583.332208 | A/B: 250 / 2,000; C: 500 / 4,000 |
| Retained single snaps | 30 | 249.506792 / 407.804791 | 250 / 2,000 |
| Retained transforms | 9 | 229.908 / 440.53675 | 250 / 2,000 |

The first 24 raw-mode timings passed, but source input binding failed. The
prepared Rust child state omitted the native child's four-dimensional UI flag
(true in the already frozen capture). The strict checker rejected the trial
before accepting any output. All 24 original raw samples and the original
driver remain under performance/diagnostics/raw-01 with an unaccepted
disposition. The second driver maps that existing native child flag explicitly.
Product code, source capture, geometry, physical transforms, actions, timing
intervals, sample counts and limits are unchanged. All 24 cases were rerun;
none was selected from the invalid preparation trial. The final checker is
unchanged and compares both initial and final raw state.

All three final performance directories were renamed losslessly into this
evidence folder after their comparisons completed. Every file hash was checked
before and after each rename. No raw sample was deleted.

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

The final evidence auditor rechecks complete raw artifacts, authored-only
setup, both native references and real receipts. This local audit is not
independent product acceptance. Keep every failed sample and source capture.
Three-platform CI, integration and independent acceptance remain required.

PR #61 is draft at c425d470c78825412f182d39ae658f7c323c118c above draft PR #59.
Its push 40951169057 and PR 40951283364 CI runs failed before all six jobs
could start. GitHub reported account payments/spending-limit restrictions.
Three-platform CI, integration and independent Codex acceptance remain
required. No complete feature or milestone is accepted. The original unlimited
goal remains active for all eleven milestones.
