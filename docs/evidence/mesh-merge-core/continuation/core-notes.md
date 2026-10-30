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
