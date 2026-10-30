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
comparison are pending. This execution correction occurred after product
code and is recorded explicitly; the original before-code seal is unchanged.

Still required: all 3,528 requests, retained 14,326 requests, sixty new and
177 retained performance samples and source comparisons, retained asset,
RNG, recipe and failed-save checks, native Metal proof, three-platform CI,
dependency integration and independent Codex acceptance. The catalog
reviews stay pending and complete_products stays empty.
