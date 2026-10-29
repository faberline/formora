# Explicit rejection of undefined source rotation

Issue #52 implements the human-approved policy for a Blender 5.2.3 source
defect. It depends on #48 and #50 / draft PR #51. Implementation candidate:
`0e992339d70b2fb61457b20665e746698f2a95ca`.
The policy and exact error were committed before implementation in
`a051bc20bbd9af22dcb1b2b07f7e9f07478b033c`.

Rotation with three true constraint flags now returns an explicit error.
It previously used a native axis extension while the source left its axis
uninitialized. The shared Rust operation rejects the input before frame or
geometry work. It keeps all-false, single-axis and plane rotations valid.
Translation and resize retain their existing behavior. The restriction and
the unconstrained alternative appear in the machine-readable agent schema.

The source defect is recorded in
`docs/defects/blender-5.2.3-all-axis-rotation.md`. The record includes the
fixed source commit, executable hash, caller, vector constructor, wrapper,
both callbacks, flag values and original case IDs. An unchanged C++ callback
probe tests all eight masks with initialized sentinel data. It never reads
uninitialized memory. Raw native instructions confirm the unwritten stack
axis and both callbacks' return before their output stores.

## Complete original request suite

All 1,203 original requests ran through both CLI and official MCP.
All 2,406 checks passed under the approved policy:

- 2,344 checks compare defined deterministic source cases.
- 48 checks retain the fixed stochastic support rules.
- 14 checks require the exact rejection for the seven source defect cases.

The fourteen rejection records contain the actual error, absent success
result, complete before/after scene, world queries and saved-file hashes.
The scene and disk bytes are identical across each rejection. Each record
explicitly disclaims a numerical source match. Negative checker tests reject
a wrong error, a success result, a changed scene, a changed request and a
policy error on a defined source case. Untyped boolean masks also fail.

The other 2,392 raw result files are byte-identical to the previous RNG
candidate. No source input, reference capture, request mapping, numerical
limit or stochastic support rule changed. The seven source cases remain
in the fixture. Their previous fourteen failures remain retained.

The archive stores the fourteen changed results. An explicit per-file index
links the 2,392 unchanged captured results to the already committed identical
bytes. Every link records the SHA-256, Git blob and parent commit. Capture
bytes were checked against that committed content before reuse. All raw
results remain available. The checker verifies every linked file again.

## Local regression and atomicity

Actual Rust 1.85 passes 229 tests. Python passes 90 tests. Formatting and
Clippy pass. Direct Rust tests cover angles, orientations, pivots, empty
selection and all three requested axes. They verify valid masks and the
unchanged three-axis behavior of translation and resize. A failed batch
preserves an existing undo entry. Saved rejection tests keep exact file
bytes and restore the prior valid scene through undo.

The 96 seeded-RNG CLI/session/MCP cases pass. They now also reject the bad
rotation alone and after a valid command inside a batch. Undo still restores
the prior valid scene. An additional 48 one-shot CLI applications verify
the same rejection and unchanged saved bytes. Schema exposure passes.

All old regression suites pass: 162 generation, eight scale, 1,060 selection,
262 creation-context, 57 payload, 42 normal queries and general official MCP.
All six Euler parent/child world queries still match the source exactly.
Repository-denied native execution verifies the new rejection, batch rollback,
retained undo and replay alongside the existing mirror/UV/RNG checks.

Both actual Metal checks pass. Source-RNG deformation changes 18 vertices
and 12,532 pixels. The legacy mirror/UV case changes 15 vertices and 14,302
pixels. Each fresh reload produces identical image bytes.

The original release benchmark program, input, limits and nine samples remain.
All samples pass: core 225.567167–236.662958 ms; operation/save/fresh reload
385.541708–478.651292 ms. Limits remain 250 and 2,000 ms. All nine saved
grids match the retained two-process Blender reference with exactly zero
position and normal error. The 1e-6 comparison limit remains unchanged.

## Acceptance boundary

The complete original transform request gate now passes with separate
defined-source, stochastic-support and explicit-rejection counts. This
does not accept a complete feature or milestone. Numeric domains, capacity,
other operations/data/modes, complete custom normal and RNG operator work,
snapping and the remaining roadmap domains still require their own proof.

All previous 3,805 baseline pins are unchanged. Two source provenance pins
bring the total to 3,807. Structural validation passes. Strict baseline
acceptance still fails with 9,003 pending source entries and 31 pending
features. All eleven milestones remain open.

Required three-platform CI, dependency integration and independent acceptance
remain unrun. Prior CI was refused before execution because of GitHub billing
limits. The final PR-head state must be checked separately. Issues #48 and
#52 remain open with `agy:doing`.

Evidence: `docs/evidence/undefined-rotation/manifest.json`.
Read-only check: `python3 docs/evidence/undefined-rotation/check-evidence.py`.
