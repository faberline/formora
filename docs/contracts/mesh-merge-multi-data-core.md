# Context-wide edit mesh merge: before-code contract

Issue #79. Source dependency: #77 and draft PR #78.
Keep the complete 0.0–1.0 goal and the existing single-entity merge contract.
Complete both 13,440-case source captures and both thirty-sample class-A
source captures before product implementation. Keep actual failures.

Add a new `merge_edit_meshes` command with a `merge` object containing
`method`, `uvs` and `max_components`. Methods and defaults use the existing
typed merge fields. No entity override is accepted on this command.
Read the active entity, authored order and edit owners from object context.
Keep `merge_mesh` behavior unchanged for callers that name one entity.

Use active first, then `Context::ordered`. Process each edit mesh data once.
Do not promote a linked non-edit user to an edit owner. Preserve all sharing.
Evaluate CURSOR in each actual provider's world frame.
CENTER, CURSOR and COLLAPSE process every eligible selected edit data set.
FIRST and LAST check the active selection mask and typed history endpoint.
An unavailable active choice is an atomic error containing `unavailable`.
Never use another mesh's history to admit the command.
After a successful FIRST or LAST merge, do not process later data.

Add `edit_merges` to edit results. Each aggregate receipt has
`command_index`, `active_entity`, `method`, `uvs`, `status`, `provider_order`,
aggregate `before`/`after` counts and `providers` in actual provider order.
Each provider has `entity`, `mesh_asset`, `shared_instances`, `outcome`
and `merge`. `merge` is the existing detailed receipt for an operation that
ran, or null when not processed. Provider outcomes are `merged`, `unchanged`,
`skipped_empty_selection`, `not_processed_after_success`, and
`skipped_history_endpoint`. Rejected commands publish no partial receipt.
An all-empty CENTER/CURSOR/COLLAPSE is FINISHED, with explicit empty skips.
Do not count rejections or skipped data as numeric matches.

Apply the component budget to the sum of unique edit data before mutation.
Never charge a shared instance twice or charge the outside non-edit data.
Keep finite-value validation, complete topology and attribute validation,
atomic batches, version checks, failed-save protection, undo and replay.
The known late command must be reached before its error can prove rollback.

Before implementation, freeze the eight authored-literal controls in
`tests/mesh_merge_multi_data.rs`. Keep their actual before-code result.
Retain every assertion. Setup contains no captured source answers.
The legacy control must still pass. New behavior must fail before code.
The first harness compile failed because the internal `EditResult` is not
serializable. Preserve that failure. Read receipts through the existing
public agent dispatch and its saved session result instead. Keep all eight
behavior assertions and re-seal this harness correction before execution.

Run all 13,440 source cases through actual CLI and official MCP, with full
requests, results, physical queries, saved assets and independent fresh load.
Keep 1e-6 absolute continuous limits and exact discrete comparisons.
Add raw-evidence corruption and source-answer leakage rejection controls.
Retain source-denied unseen operations, native saves, recipes and Metal.

Both attributed class-A grids retain 10,201 vertices, 20,200 edges and
10,000 quads each. Five methods times two UV settings, three samples each.
Each core sample must be at most 500 ms. Each full operation/save/fresh-load
sample must be at most 4,000 ms. Keep original validation in those clocks.
The frozen `capacity-driver.rs` validates full input before each operation
and full results inside each clock. Compare actual aggregate core receipts
with saved-session receipts. The old core has no `edit_merges` field yet;
record its compile failure as an admission boundary, never a timing pass.
Keep all preceding workloads and limits, including the 207 retained samples.
Keep all 16,374 retained interface records and 1,687 asset checks.

Required Rust/Python checks, all native evidence, platform CI, dependency
integration and independent Codex acceptance remain required.
No failed, skipped or unrun required test passes.
Full parameter/data/capacity and singular-frame domains remain follow-up
work in the original milestones. Keep approved zero-scale query handling
and the fourteen explicit undefined-source rotation input rejections.
All milestones stay open until their full acceptance is complete.
