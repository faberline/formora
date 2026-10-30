# Persistent vertex merge implementation

Issue 72 remains agy:doing. All eleven milestones stay open.

The typed merge_mesh command reads the saved asset, owner frame, cursor,
selection and history. CLI and MCP share this scene command. The candidate
asset is validated before publication. Session save and editor batch failure
retain the existing atomic boundary. Merge receipts are omitted when empty.

The kernel changes real persistent topology. It includes selected vertex
clusters, selected-edge shell traversal, f32 means, integer and group
interpolation, zero-weight handling, face splits before welding, edge/face
deduplication, oriented UV loops, history and active-face remapping. Shared
users keep one real asset. It does not read source files at runtime.

Frozen nine merge tests and five integer interpolation tests remain unchanged.
Actual Rust 1.85 passed 61 focused tests with zero ignored, including existing
mesh, polygon, creation and agent tests. Library Clippy passed with warnings
denied. Preserve the first compiler and Clippy failures, and the omitted
sparse-fixture test failure. Fixture inclusion changed no fixture bytes.

The nine-case native-protocol diagnostic passed against both original native
captures. A full 1,024-case diagnostic is running. This diagnostic does not
count as the real CLI/MCP gate. It matches physical coordinates, attributes
and actual topology through a bijection. Repeated integer values never
identify components alone. Oriented face loops and their UV/normal corners
are aligned only by cyclic rotation. Source numeric limits remain 1e-6.
The first diagnostic candidate probe propagated a nonmatch ValueError; its
nine failures remain. Catching that error changes candidate selection only.

Still required: all 2,048 real CLI/MCP requests and raw binding audit,
corruption controls, full retained suites, source-read denial, real failed
saves, unseen analytic inputs, Metal proof, thirty new and 177 retained
performance samples with source comparisons, three-platform CI, stack
integration and independent Codex acceptance. Complete numeric domains,
multiple independent edit assets and all other product functions remain in
the original goal. No feature or milestone acceptance is claimed.

## Additional persistence and receipt failures

The first implementation passed all 1,024 native-protocol source cases.
That result did not cover all authored acceptance requirements. Three
additional frozen controls then failed: explicit endpoint f64 persistence,
an existing edge whose geometry moved, and successful edge-mode collapse
with no selected edges. Preserve all three actual failures. The test seal
is 46e8856c and the contract seal is 1d7c83ad, both before repair.

The repair preserves explicit endpoint coordinates without conversion.
Center/cursor/collapse retain source f32 arithmetic. Receipts compare real
stored values, moved geometry and actual selected/hidden flags. Successful
edge-only collapse clears selected flags even with an empty edge buffer.
All 64 focused Rust tests passed with zero ignored. Library Clippy, build
and formatting passed. Source and full interface gates must run again at
this repaired implementation. Prior source success does not pass it.

## Repaired implementation e45e0a81

The complete 1,024-case native-protocol diagnostic passed again, with real
exit zero, against both original native captures. The actual CLI and
official MCP pilot passed all 26 requests. The second pilot also binds
every actual request and raw response to its saved state and receipt.
Nine physical-data controls and eleven API-evidence controls rejected
corruptions. Receipt controls also forge the matching raw result, so the
receipt checker must reject the false claim independently of transport.

Actual Rust 1.85 passed all 288 all-feature/all-target tests, with zero
ignored tests. All-feature/all-target Clippy passed with warnings denied.
The release build and frozen thirty-sample driver compilation passed.
The complete 2,048-request interface gate and actual timing gates remain
unrun at this preparation seal. Independent acceptance remains unrun.
