# Mirror and UV correction progress for issue #48

Implementation candidate: `32bd336d8dd708b5dc59c7fdb82c414a08d0adaf`.
This is bounded progress in draft PR #49. It does not accept an issue or milestone.

The Rust core now supports spatial and topology mirror pairing on one local
axis. It copies the transformed source position and locks original near-plane
vertices to the mirror plane. Hidden vertices remain excluded. Mirror receipts
identify actual copy sources and plane clamps.

UV correction uses original face geometry. It projects new corners and applies
the pinned mean-value interpolation. It handles every stored UV layer, separate
UV fans, original angle weights, moved-corner weights and zero-area substitutes.
Correction follows mirror copies. Automatic shading normals update afterwards.
Receipts identify UV-changed faces, including changes without vertex motion.

The fixed contracts precede implementation. The mirror contract was committed
in `f367904c6eb98c8994895a33cdd906d47837beb1`. The UV contract and further pinned
primary sources were committed in `6acc56c10cc31958ccb415ed5cb6672e6fec655b`.
The source manifest records eight primary files at the frozen Blender commit.
The lock now has 3,780 pins. The previous 3,771 pins remain intact.

The pinned topology hash comparator compares addresses. The standalone C++
probe retains its literal function body. On this Mac, `[9,1,9,2,2,1]` stays in
that order. The Rust pass counter retains the observed transition count.
The final hash groups still use actual hash values. Source tie behavior and
cross-platform comparator behavior remain unverified. The native spatial tie
rule is stable vertex ID order. The probe does not establish broader parity.

## Checks

Actual Rust 1.85.0 passed 205 tests. Python passed 79 tests. Formatting and
Clippy passed. New tests cover all mirror axes, both source sides, hidden
partners, strict plane thresholds, topology ambiguity, proportional copies,
affine UVs, triangles, n-gons, separate layers, connected fans, seams,
nonmanifold fans, hidden neighbours, degenerate substitutes, mirror ordering,
UV-only receipts, overflow, undo, saved reopen, failed batches and failed saves.

Thirty fixed mirror-context and UV cases passed both interfaces. These 60
checks are diagnostics. They cannot replace the complete source gate.

The complete gate ran all 1,203 cases through the command line and the official
MCP SDK. It matched 2,362 of 2,406 checks. These include 2,350 completed cases and
12 expected cancellations. There are 44 failures. This is 48 improvements and
zero regressions from the previous safe-inverse candidate. Native requests,
authored setup, source cases and expected results are unchanged. All seven
source cases with an undefined all-axis rotation value remain failing.

Each interface has ten geometry mismatches, six normal mismatches and six world
position mismatches. The original 1e-6 limits remain fixed. Raw results are
byte-identical between the two interfaces. No failure is counted as a pass.

The general official MCP regression passed. The 42 normal queries passed.
SDK version is 2.3.0. Protocol version is 2025-11-25. Baseline metadata remains
structurally valid. Strict acceptance still fails. There are 9,003 pending
source entries and 31 pending features.

## Native checks

The copied native binary passed an unseen scene with repository reads denied.
A denial control proved that the process could not read `Cargo.toml`. The scene
uses a local Y mirror, a reflected nonuniform object scale, two affine UV
layers, a plane clamp, a distinct coincident vertex and a hidden vertex. Checks
cover actual positions, UV values, receipts, shared ownership, stale requests,
failed batches, undo, replay and fresh reload. No measured outputs enter the
product operation.

The actual Apple M1 Max Metal renderer passed a mirrored grid deformation with
saved UV correction. Fifteen vertices and 14,302 pixels changed. Untouched
corners stayed fixed. The image after fresh reload is byte-identical. The image
was inspected. This proves rendered geometry and persistence in that scene.
It does not prove complete texture or UV preview feature support.

The first GPU driver used an old expected starting X coordinate. It failed.
Its driver, stderr and partial scene remain in `uv-mirror-gpu-attempt-1`.
The corrected driver includes its authored starting X of 0.5. The product
binary did not change. The failed attempt is not acceptance evidence.

## Evidence and remaining work

`docs/evidence/mesh-transform-core/uv-mirror-implementation-manifest.json` binds
the binary, input hashes and raw artifacts. Its checker verifies all captures,
the complete comparison, native probes, source pins and unchanged contracts.
The checker also verifies that all eleven milestones remain open without dates.
The final evidence commit is checked against the Git index and stored blobs.

The required transform gate still fails. Fixed performance tests, the complete
legacy regressions on the final candidate, three-platform CI, dependency
integration and independent acceptance remain unrun. Other corner attribute
types and multiresolution data still need support. The earlier CI attempts were
refused before execution due to the GitHub account billing limit. A later
head-specific CI record must confirm the current execution state.

Issue #48 stays open with `agy:doing`. PR #49 stays a draft. No milestone closes.
Continue with the remaining numeric failures and retain the fixed test limits.
