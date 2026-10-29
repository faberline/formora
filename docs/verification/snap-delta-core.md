# Delta core: frozen source preparation

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

The complete new 3,584 requests, retained 10,742 requests, native/recipe/RNG /
Metal gates, 24 added plus 153 retained release samples, three-platform CI,
dependency integration and independent Codex acceptance remain required and
unrun for the current candidate. Catalog review and all milestones stay open.

Parent PR #65 remains draft at 393cebdf58d589f5de093a088f74b3018ea6196f.
Its push 40967417693 and PR 40967460108 CI failed before all six jobs started.
GitHub annotations report account payment/spending-limit restrictions.
Keep all milestones open and every original scope/criterion intact.
