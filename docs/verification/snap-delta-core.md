# Delta core: local implementation evidence

Issue #66 is OPEN with agy:doing under milestone 0.2. The unlimited 0.0–1.0
goal continues. Contract d3a3857232a9bc4de12180235894c488a0a1f518 fixes all
1,792 source cases through real CLI and official MCP: 3,584 new requests.
It retains every previous gate and adds 24 fixed release samples.

Commit 643862e5bfc795356df2024e804484b927a25526 freezes the unchanged class-A
grid bytes, eight normal/cursor rotation modes, combined target delta, child
delta, all channel flags and native capture/check programs before Rust edits.
The exact grid SHA-256 is
8f29def12ade5467214e888fdcacec23b3d78ed4954e470207a00479ac149536.
The original workload and 250 ms core / 2,000 ms pipeline limits remain fixed.

Native Blender process 72828 completed all eight modes with terminal exit 0.
It uses the fixed 5.2.3 executable SHA-256
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
All eight source checks passed: exact authored geometry and normal/delta raw
channels, independent initial world frames/vertices, topology/attributes,
unchanged deltas/cursor and actual child world preservation through changed
parent inverses. The child's four-dimensional flag is explicitly false in
both frozen inputs and native setup. Every stored/raw gzip hash was checked.
The source captures, controller receipts and checks are under
docs/evidence/snap-delta-core/performance.

No product Rust source changed before these captures. At capture time all
product implementation and verification remained unrun. Source preparation
is not a product pass. No feature or milestone is accepted.

## Rust candidate and initial checks

The candidate saves typed delta translation, Euler, W/X/Y/Z quaternion and
scale in actual transforms. Default identity preserves old serialized scenes;
signed zero and nondefault inactive values remain saved. The common f32/f64
frame core applies delta rotation before normal rotation, multiplies scales
and adds translation. Protected direct snaps retain their real delta channels.
The whole scene rejects an overflowing new physical delta frame before
publication. Old normal unit-quaternion validation remains unchanged.

All 271 actual Rust 1.85 all-feature tests passed with none ignored. All 190
Python tests passed. Format, Clippy with warnings denied and debug build
passed. Eight new Rust tests cover identity serialization, signed zero,
noncommuting rotations, negative scale, signed/nonunit raw delta data,
inactive axis-angle data, late rollback, f64 overflow, actual direct setters,
real receipts and undo/replay. Ten added Python controls use actual saved
product output and verify source input isolation, delta signs/normalization,
inactive values, frame consistency and real transform receipts.

The first 18-case pilot passed all 36 actual CLI/MCP requests against both
complete native references, with fresh process reloads. This pilot uses debug
binary 0991a4dc3e253894f535ccf3b653f4b3d38827a2400addbbe2d14b99727e87c4
before the added f64 overflow guard. The subsequent tested debug binary is
bd666398596d8a9ec61d8e12db62df53bd7c2aa53ba5492ceba65ab4ea655bef.
The pilot is a diagnostic and cannot pass the complete 3,584-request gate.
The two suites share one runtime driver with explicit authored setup,
snapshot and source comparison functions. Original rotation defaults and
required counts are unchanged. The workflow adds the complete delta gate.

Preserved development failures include a complete Transform literal missing
its new identity field, a new test using the revision-only method instead of
the typed-outcome method, and a negative snapshot control whose actual
scene/query mismatch was rejected earlier than the test expected. The tests
now use the complete identity literal, actual typed outcomes and both existing
consistency guards. No source fixture, comparison threshold or required gate
was changed. Their original logs remain under diagnostics.

The complete new 3,584 requests and retained 10,742 requests passed on the
subsequent binary above: 14,326 actual CLI/MCP requests. Every declared input
hash was rechecked, including retained reports that do not emit an unchanged
flag. Cancellations and expected atomic rejections remain separate. The
14 approved undefined-source mesh-axis cases remain explicit rejections.

All 1,591 retained asset checks, 96 RNG checks, official MCP smoke, 48 fresh
one-shot RNG cases and six exact Euler-order frame checks passed. All six
retained source-read-denied suites and the new 29-call unseen delta suite
passed. All three recipe proofs and four native Metal proofs passed. The new
Metal proof changes 25 vertices / 20,083 pixels and preserves actual surface /
child world frames. It keeps raw delta channels and has byte-identical fresh
reload PNGs. Its before/after images were viewed.

Additional native proofs passed all seven direct actions against analytic
delta-composed points, thirteen atomic invalid inputs and finite inactive f64
preservation. An actual failed save preserves memory/revision, original disk
bytes and the undo stack. Recovery, real receipts, undo/replay and fresh
reload pass. The first failed-save harness stopped after the rollback checks
because the existing serializer omits an empty mesh_assets map. Its original
driver/data/logs remain; the corrected empty-map check passed in a new run.
One retained standalone RNG driver initially refused its old fixed output
folder before starting native operations. That failure remains preserved.
Only its output path changed for the successful fresh native replay.

## Fixed performance and preserved failed trials

The 24 added delta samples passed both original time limits and full native
source comparisons. Maximum core is 133.431208 ms and maximum pipeline is
397.655708 ms, within the fixed 250 / 2,000 ms limits.

The first complete retained 90-sample run failed ten class-A core samples.
The largest failing class-A core time is 302.011166 ms against 250 ms.
Every pipeline sample passed. All ninety samples, exact scenes, receipts,
controller results and host observations remain retained and unaccepted.
The before snapshot reports 0% CPU idle; the older passing reference run's
before snapshot reports 53.94% idle. This is observed host contention, not
proof that code cannot contribute. No threshold, input, timer, priority,
host setting or other process was changed. Failed timings cannot pass.

The complete failed trial is archived losslessly under performance /
diagnostics/retained-90-01. Its index binds original and compressed bytes.
Every raw scene is reconstructed and rehashed before native reads. The
existing comparator's explicit diagnostic mode is used only to check source
results of the failed trial; its required_full_gate_passed stays false.
The first trial will not be counted as a passing performance run.

One complete fresh 90-sample experiment passed using the unchanged executable,
source, workload, timers and limits. No samples were combined across trials.
Its before snapshot reports 59.78% CPU idle. All ninety strict native source
comparisons passed without the diagnostic flag. The first trial stays failed.
No host settings, priorities or other processes were changed. Observed host
conditions differ; this does not establish a universal timing guarantee.

The first retained 39-sample group had one 268.973625 ms single-snap core
sample against 250 ms. Its saved scene bytes equal both sibling samples in
the same form. All first-group pipeline and nine transform samples passed.
The complete failed group remains unaccepted and preserved. One registered
full 39-sample repeat passed every original sample. It keeps all three samples
per form and all nine transforms, with the same executable, input and limits.
It selects no samples from the first group. No root cause is claimed for the
single wall-time outlier.

All final 177 samples passed both original timing and native result gates:

| Gate | Samples | Maximum core / pipeline (ms) | Original limits (ms) |
|---|---:|---:|---:|
| Added delta modes | 24 | 133.431208 / 397.655708 | 250 / 2,000 |
| Retained scene classes | 90 | 293.168125 / 600.453417 | A/B: 250 / 2,000; C: 500 / 4,000 |
| Retained raw rotation modes | 24 | 159.031250 / 360.901000 | 250 / 2,000 |
| Retained single snaps | 30 | 243.847625 / 745.562792 | 250 / 2,000 |
| Retained transforms | 9 | 240.459916 / 406.394791 | 250 / 2,000 |

The retained A/B maximum core is 225.967083 ms; the table's 293.168125 ms
belongs to class C. All 129 timings from the two unaccepted whole trials remain
preserved, including their eleven actual over-limit rows. Failed rows never
become passes. The exact scene bytes are losslessly archived only after
timing. Archive indices bind raw and stored hashes. Reconstruction verifies
every byte before a native query. No original data was dropped.

The first numeric diagnostic command omitted the installed MCP SDK path and
failed on import. Its restore had already verified all archived hashes; no
numeric comparison ran. The corrected environment ran the unchanged existing
diagnostic comparator. It deliberately exits 1 with required_full_gate_passed
false while recording all ninety source matches. Its diagnostic result is
not used as a required performance pass. Fresh full repeats use strict gates.

The full API evidence auditor rechecked all 14,326 complete raw request
artifacts, exact authored setup, both source captures, real frames and typed
receipts. It derives delta and normal snapshots from actual stored scenes and
actual queries. This is a local evidence audit, not independent acceptance.
The full product and milestone acceptance remain pending. Three-platform CI,
dependency integration and independent Codex acceptance also remain required.
Catalog review and all milestones stay open.

The final local evidence audit passed at implementation e16eab6471f32aa85c2bbba867e6fd4e09ead640.
It rechecked all 332 archived scenes and all 736 archived files against both
raw and stored hashes. All first failed trial rows remain failed. It confirms
the 271 Rust tests, 190 Python tests, 14,326 complete requests and 177 final
source-matched performance samples without granting product acceptance.

Parent PR #65 remains draft at 393cebdf58d589f5de093a088f74b3018ea6196f.
Its push 40967417693 and PR 40967460108 CI failed before all six jobs started.
GitHub annotations report account payment/spending-limit restrictions.
Keep all milestones open and every original scope/criterion intact.
