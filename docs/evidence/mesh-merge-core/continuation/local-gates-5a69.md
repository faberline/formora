# Regeneration repair checks at 5a69c885

This records local work for issues #72 and #76 and draft PR #75.
It does not accept an issue or milestone.

## Change and frozen failure

Regeneration used to remove the editing record while an edit object still
used the shared asset. The real CLI server rejected regeneration at call 27.
Six native Rust controls then had one pass and five failures.
Commit `4601fae03221009e7b3d76e3e7395354c7959311` freezes those tests,
the contract, raw calls and actual failures before the repair.

Commit `5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d` repairs that state.
It keeps each active asset's selection modes and preview setting.
It clears old component selections, hidden flags, history and active face.
It keeps entities, shared asset identity, object context and creation frame.
Object-mode regeneration keeps its exact existing result.

## Completed checks on the repaired build

- Actual Rust 1.85 passed all 303 tests with all features and targets.
  Zero tests were ignored.
  The frozen six tests passed, including all 60 generator/mode/preview combinations.
- All 215 Python tests passed.
  All-feature/all-target Clippy passed with warnings denied.
  Formatting, default debug/release builds and the preview build passed.
- Twenty actual recipe workflows passed: ten through the native CLI server
  and ten through the official MCP SDK.
  They include 60 successful merge requests with no-ops and replay,
  120 rejected apply requests, real undo, regeneration undo/replay and fresh reload.
- The separate one-shot CLI/official MCP corpus passed all 2,048 requests.
  The complete raw audit also passed all 2,048 records against both fixed captures.
  Eleven full-report/authorship controls, eleven API controls and nine physical
  controls rejected false evidence.
  The setup-leak control inserts a measured product-result mesh and forges matching
  raw arguments. The canonical authored-input guard rejects it.
  Forged records are never sent to the product.
- All 207 fixed timing samples passed on the repaired release library.
  All 30 new saved outputs passed physical source comparison.
  The 30 new samples reached 165.107084 ms core against 250 ms,
  and 188.131583 ms operation/save/reload against 2,000 ms.
  All 177 retained physical source comparisons also passed.
  All 207 timing and physical source checks passed on this build.
- Nine native unseen tests passed with source and prior-answer reads denied.
  Nineteen native calls passed actual failed-save rollback and fresh reload.
  Four additional native controls proved denial of current and prior answer files.
  The six frozen regeneration tests also passed with that native denial policy.
  This includes all 60 generator/mode/preview combinations.
- Seven retained source-denied suites, five retained local lifecycle suites,
  48 fresh CLI RNG cases and six exact Euler-order checks passed.
- All five native Metal proofs passed on the repaired preview executable.
  The merge proof changed 16,155 pixels.
  Saved and freshly reloaded images match exactly.
  All three merge PNGs also match the prior implementation byte for byte.
- The first 3,584 retained interface requests and their separate raw audit passed.
  The rest of the 14,326 requests and asset checks are still running.

## Exact artifacts

`regenerate-build-bindings-01.json` records the build digests.
The default executable SHA-256 is
`0e882777416ca728e55ca7212259d1b65a1bc6703706ded440bd822b7e70d2aa`.
The release library SHA-256 is
`a06c8aa897ce51992ca08779627eb4041ef0db51d4ccca9dab08ce3fdbc1a0f6`.
The preview executable SHA-256 is
`0f1923e013d95d8b19a4c16bb5e05b949aa5c8f359dd93d869707b0146c1411d`.

The four `regenerate-completed-*` manifests bind archived files to their
original bytes and SHA-256. Large JSON files use lossless gzip.
Original files and the older failed and successful trials remain intact.
Evidence at implementation 224a4360 is historical evidence for that build.
It does not pass gates on this repaired build.

## Still required

Finish the complete retained interface/asset run.
Audit and archive all required raw records.
Three-platform CI, dependency integration and independent Codex acceptance
remain unpassed. At published evidence head 509b71d9, six CI jobs stopped
before their first step due to the GitHub account payment or spending-limit
restriction. Raw jobs and annotations are in `ci-repaired-head-509b-01/`.
Later-head CI is not accepted.

Keep #72 and #76 open with `agy:doing`.
All eleven milestones stay open. `complete_products` stays empty.
The full source catalog and full parameter/data/capacity domains remain work
in the original 0.0–1.0 goal.
