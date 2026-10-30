# Zero-scale world results and unavailable local queries

Issue #73. Source draft PR #69 remains unintegrated. All eleven milestones
remain open. No independent product acceptance is claimed.

The user approved an explicit unavailable local matrix query while retaining
valid world data and successful operations. The separate fourteen undefined
mesh rotation input rejections keep their existing policy.

The contract is docs/contracts/snap-singular-core.md. Commits 82dfef10,
5484d433 and 747a3bbb fixed the behavior tests, source inputs, full grid
source checks, performance forms, three samples per form and 250/2000 ms
limits before Rust implementation commit 10834244.

The pinned Eigen wrapper checks a separately evaluated determinant before
its packet inverse. In a dense degenerate frame the check can be nonzero
while the inverse denominator is zero. The old Rust wrapper used only the
second determinant and returned a zero matrix. The new wrapper preserves
both stages. The derived getter reports matrix_local: null and the typed
matrix_local_error: cannot_invert when evaluation is unavailable. Valid
matrices retain their old array shape and omit the error field. Physical
world lookup errors still fail. No scene data or operation is changed by
the getter.

Evidence under docs/evidence/snap-singular-core retains the exact upstream
Eigen headers, verified dependency archive identity, raw queried world
matrices and an independent f32 determinant diagnostic. In the diagnostic
all eight before/after entity world matrices match the source f32 bits.

Native grid process 55260 completed all twenty forms and exited zero. The
source checker passed all twenty. The parent-zero cursor rotation forms
each have an unavailable after-state child local query. Other source local
queries remain numeric. Source process 34827 and its authored lock mismatch
remain in diagnostics. The first small-fixture checker did not apply to
this grid's empty UV/material domains; its failures remain. The dedicated
grid checker verifies the actual empty domains without inserting layers or
relaxing the original small-fixture validators.

Before code, 229 Python tests passed. The five Rust behavior tests had
three passes and two failures. After code, all five passed. All 276 Rust
tests passed, with zero ignored tests. The first Clippy run found a test
initialization style issue. The same values now use a struct initializer;
no assertion changed. Clippy then passed with warnings denied. Both builds
and format checking passed. Full tracker acceptance remains unrun.

The 32-request CLI/MCP pilot passed, including all twelve unavailable source
cases. It is a focused pilot, not the complete 3,528-request gate. An unseen
analytic triangle passed seventeen real native calls with repository reads
denied, including an actual denial control, physical queries, unavailable
local queries, rollback, undo, replay and a fresh process reload.

The first performance process exited 101 before any sample because the
driver omitted required grid spacing. Its original source, logs and report
remain. The driver now maps the same frozen native forms to the existing
typed API, including cursor_to_center. Samples, inputs, clocks, validation
and limits are unchanged. The corrected performance run and source
comparison are recorded below. This execution correction occurred after product
code and is recorded explicitly; the original before-code seal is unchanged.

The current completed checks and remaining gates are recorded below. The
catalog reviews stay pending and complete_products stays empty.

## Full-corpus failure and exact-zero compensation repair

The first complete CLI corpus at implementation 10834244 executed all 1,764
cases: 1,708 passed and 56 failed. The source legitimately writes an exact
4x4 zero child parent inverse during singular skip-children compensation.
The affine-only persistent state validator incorrectly rejected that result.
Every source scalar and physical coordinate is finite. The zero bottom row
is source data and must not be replaced by an invented affine row.

The interrupted evidence retains all 1,764 CLI records plus 512 MCP records.
It also retains 2,045 older delta regression records. Both processes were
stopped deliberately before repairing the confirmed bug; their actual tool
exits are 143. Neither interrupted complete gate passed.

Commit f86c73c7 fixed the exact-zero contract and four additional tests before
the validator repair. Before repair, one test passed and three failed.
Implementation aa2afb53 accepts exact all-zero matrices in addition to the
unchanged finite affine domain. It still rejects other projective matrices,
near-zero non-affine matrices, nonfinite values and f32 range overflow.
All nine query/compensation tests passed. Then all 280 Rust tests passed,
with no ignored tests. Clippy, formatting and both builds passed on actual
Rust 1.85, with unchanged verification inputs.

At the earlier implementation, all sixty timed trial-02 physical outputs
passed source comparison. Timing still failed: parent-zero cursor-origin
sample three took 287.408084 ms against 250 ms. The complete lossless archive
retains 187 files, 576,983,950 raw bytes. The separate physical comparison
report still has passed:false and required_new_performance_gate_passed:false.
An initial canonical-input comparison failed on selected-set ordering and
omitted default-false flags. Those failures remain. The checker now compares
the same authored values using the documented canonical serializer spelling;
it does not change any input, output, numeric value or timing limit.

The repaired aa2afb53 implementation completed a new full sixty-sample
trial-03 with exit zero. All time limits passed: maximum core 173.4855 ms,
maximum operation/save/reload 501.955209 ms. These are a different corrected
implementation, not selected samples from the failed trial. Its source
comparison and the 177 retained timing/source samples subsequently passed.
The retained native drivers, workloads, forms, clocks, counts and limits
remain byte-for-byte unchanged. Their new controllers only bind this
implementation and fresh output/executable paths.

## Repaired implementation: completed local checks

At implementation aa2afb53, the complete 3,528-request zero-scale corpus
passed through the real CLI and official MCP SDK. The raw-response audit
reconstructed every saved scene, physical snapshot and receipt. It checked
both native source processes. There were 24,448 numeric local queries and
24 explicit unavailable queries, twelve per interface. The unavailable
queries are not numeric matches. See zero-api-full-02 and
complete-api-audit-01.json under the evidence directory.

All 237 timing samples and their complete physical source comparisons
passed. This consists of sixty new samples and 177 retained samples across
six source comparisons. See performance/all-source-comparison-01/report.json.
The first failed timing remains failed, and all original samples remain
available. Exact raw-byte archives retain both hashes and reversible
compression. A separate 187-file restore checked every raw hash and queried
the restored singular child with the actual CLI.

The repaired binary also passed 229 Python tests, seven retained native
source-read-denied suites, actual failed-save rollback, primitive recipe
regeneration, original input rejections, source Euler checks, RNG one-shot
cases and five native Metal suites including the new singular triangle.
The new Metal proof changed 83,706 pixels. Each saved/reloaded render pair
was byte-identical. These are local checks, not independent acceptance.

The complete retained 14,326-request CLI/MCP gate is still running. The
delta suite completed all 3,584 requests. Raw rotation and later suites
remain pending until their real terminal results and complete raw audit
are available. No partial count accepts the full retained gate.

CI at published head dd762766 ended in failure before any job step ran.
GitHub reports the account payment/spending restriction. The push run is
41003600761 and the PR run is 41003666282. No rerun, billing change, runner
change, PR diff review or merge was performed. Three-platform CI, stack
integration and independent Codex acceptance remain unpassed. All eleven
milestones remain open.
