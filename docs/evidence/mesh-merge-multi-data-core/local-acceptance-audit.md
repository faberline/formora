# Local evidence audit for issues #79 and #80

This is a controller evidence audit. It is not independent Codex acceptance
or a PR diff review. The complete milestone scope stays unchanged.
The audit concerns the bounded contracts for context-wide mesh merge and
the actual per-object scale-lock query. It accepts no modeling milestone.

The effective product source is
`0a5a3bed31b974fc5cee98155c3dc7113bf12a87`.
No `src`, `tests`, `Cargo.toml` or `Cargo.lock` file changed after that product
build. Eleven evidence tools were later added. Their actual interface runs,
raw audits, denial tests and corruption controls provide their separate
validation. No existing tool was changed after that build.
All 216 registered full-run inputs still match the frozen hashes.

## Issue #79

| Required evidence | Observed result | Evidence |
| --- | --- | --- |
| Source baseline before Rust | Both 13,440-case native runs pass. Capacity source processes 86168 and 7564 each complete all 30 cases. All four admission report hashes still match the original source worktree. The full runtime/raw audit also revalidates the functional source gate. | [Implementation admission](implementation-admission-01.json), [fixed capacity source report](https://github.com/faberline/formora/blob/279061fbfff074c6aa03f04a961761dc88a5e4d9/docs/evidence/mesh-merge-multi-data-baseline/capacity-source-comparison-01.json), [full raw gate](completed-full-runtime-03.md) |
| Frozen behavior before product edits | Eight controls compile against the old library. One legacy control passes; seven new-feature controls fail with exit 101. Original failures stay intact. | [Before-code result](before-code-behavior-02/report.json) |
| Direct behavior after edits | All eight controls pass in the Rust suite. The source-read-denied proof also runs those eight and nine retained controls, with actual zero child exits. | [Denied execution](completed-functional-01.md) |
| Both real interfaces and actual state queries | All 13,440 cases run through each of CLI and official MCP. Actual scale-lock replies are included. | [Full raw gate](completed-full-runtime-03.md) |
| Raw transport, saved state, exact attributes and receipts | All 26,880 records and 860,160 calls are rechecked. Thirty forged-record controls fail as required. Rejections remain separate from numeric matches. | [Full raw gate](completed-full-runtime-03.md) |
| No source answers in authored setup | All 13,440 constructors run with file access denied and zero reads. Forged source-answer fields are rejected. | [Full raw gate](completed-full-runtime-03.md) |
| Two class-A grids and all 30 fixed capacity samples | All samples pass at unchanged 500/4,000 ms limits. Maximum core is 406.040125 ms; maximum operation/save/fresh-load is 766.680167 ms. Validation stays in the clocks. | [Effective-build capacity evidence](../object-state-query/README.md) |
| Preserve 16,374 interface records and 1,687 assets | All complete. Raw audits preserve cancellations, atomic rejections and the 14 approved undefined-rotation rejections separately. | [Retained functional gate](completed-functional-02.md) |
| Preserve all 207 timings and physical source comparisons | All complete, with unchanged workloads, limits and source tolerances. The failed host-probe attempt is preserved. | [Complete timing/source gate](completed-timing-source-04.md) |
| Source-denied unseen behavior and failed saving | The 17 frozen denied controls and 27 new native calls pass. Real failed saving leaves both assets, revision and undo history unchanged. Undo, replay and fresh load pass. | [Native evidence](completed-functional-01.md) |
| Primitive recipes and native Metal output | Retained and new recipes each pass 20 cases and 120 failure controls. New recipe raw calls and terminals are audited. New two-data Metal and all five retained Metal suites pass; actual images were inspected. | [New proofs](completed-functional-01.md), [retained proofs](completed-functional-02.md) |
| Existing native lifecycle and isolation | Twelve small suites, 19 failed-save checks, 48 RNG checks and six exact Euler checks pass with actual zero exits. | [Retained native gates](completed-functional-02.md) |

## Issue #80

| Required evidence | Observed result | Evidence |
| --- | --- | --- |
| Fixed actual state source before implementation | Two native viewport processes each complete 160 cases with native save/reopen. Exact booleans, identities and 1e-6 matrices pass. Seventeen source corruption controls pass. | [Source comparison](../object-state-query/source-comparison-01.json), [source evidence](../object-state-query/README.md) |
| API and failure controls before product edits | Eight frozen controls give one legacy pass and seven failures on the old library. All eight later pass. The frozen test hash stays unchanged. | [Original failed controls](../object-state-query/before-code-01/test.stdout), [before-code seal](../object-state-query/before-code-seal-01.json) |
| Actual defaults, all boolean triples and per-object persistence | CLI 160 and official MCP 160 cases pass, including distinct state on shared-mesh users. Their 10,880 raw calls and fresh loads are checked. Eight forged records are rejected. | [Raw verification](../object-state-query/runtime-verification-01.json) |
| Save, undo, replay, invalid batches and singular-parent metadata | Frozen behavior controls and 24 unseen source-denied cases pass. The query does not invert a matrix or invent a context. | [Effective implementation evidence](../object-state-query/README.md) |
| Full #79 real getter coverage | The complete 26,880-record gate checks actual `object_state` replies before and after operations. | [Full raw gate](completed-full-runtime-03.md) |
| Retained functional, native and performance gates | The same effective executable passes the full retained set and all 207 timing/source samples. | [Retained gate](completed-functional-02.md), [timing/source gate](completed-timing-source-04.md) |

## Shared checks and remaining gates

The effective-build archive records Rust 1.85 builds for the default binary,
preview binary and release library. Its test log contains 319 passing Rust
tests with zero failed or ignored tests. Python records 215 passing tests.
The stored format, Clippy, Rust and Python terminal codes are all 0.
The default, preview and library hashes match the binaries used by the later
native, interface and performance proofs. The relevant raw build records are
in `../object-state-query/build-02/`.

These local results do not satisfy the remaining gates:

- Required platform CI has not passed. The latest published-head workflows
  were queued at the last readback. A queued or missing result is not a pass.
- Dependency integration is unrun. Source PR #78 and other required stacked
  changes remain unaccepted. The general zero-scale query repair in PR #74
  is a separate unintegrated change. Its approved policy remains unchanged.
- Independent Codex acceptance is unrun. This controller audit cannot replace it.

No local test failure is converted to a pass. The original failed timings,
compile attempts, source captures and helper diagnostics remain available.
The fourteen undefined three-axis rotation inputs remain explicit rejections.
Full parameter, data, capacity and singular-frame domains remain in the original
milestones. The current bounded evidence cannot accept those broader domains.
Issues #79 and #80 stay open with `agy:doing`. All 11 milestones stay open.
