# Distance merge capacity inputs

Issue #82. Freeze this workload and its harness before Rust distance work.
Source observations do not establish Rust product timing or acceptance.

Each class-A mesh has 10,201 vertices, 20,200 edges and 10,000 quads. Two
independent grids have different authored heights. They carry two UV layers,
material slots, smooth/seam/sharp flags, three named integer layers per domain,
group names, explicit zero weights and native creation order. A linked user
and outside unedited data remain present in each scene.

The registry has 64 forms and three required samples per form: 192 samples.
Forms cover all eight boolean option combinations, one/two edited class-A
data, all/alternating vertex selection and automatic/custom constant normals.
The threshold is 0.1875. Frames use the frozen noncommuting scene hierarchy.
Selection history uses the authored forward native order.

The grids come only from literal formulas. The compressed asset pack records
both stored and raw SHA-256 digests. The offline checker regenerates all assets
and forms with file access denied. No measured result enters an input.

Run the complete frozen registry in fresh native viewport processes and retain
source results before opening the Rust distance issue. Every sample and form
is required. Keep failures, individual timings and complete raw state/native
save/reopen evidence. Do not discard slow samples or replace them with a mean.

The core clock includes initial validation, the operation, a complete output
snapshot and validation. The pipeline clock also includes native save, an
independent native file reopen, fresh state queries and complete validation.
Evidence compression and report writing are outside the product clock; none
of the state checks are removed from it.

Product limits remain 250 ms core and 2,000 ms operation/save/fresh-read per data.
Two edited data retain 500/4,000 ms limits. Full validation stays inside these
clocks. Hardware remains Apple M1 Max. All three samples per form must meet
the product limits during later Rust acceptance.

Report native source time as native time. Preserve each comparison against
the frozen product budgets, including overruns. A native source observation
is not a Rust timing pass. Product performance remains unrun until the actual
Rust core and pipeline execute the same inputs with full validation.

Commit the harness, individual/pair comparison and all inputs before creating
the immutable capacity seal. It records the functional source dependency,
actual hardware and unchanged product limits. Verify it before each native
process and retain all input digests unchanged through that process.

Small, explicitly selected diagnostic subsets may check setup before the full
runs. Their manifests must say diagnostic. They cannot pass the complete
192-sample gate. A failed diagnostic retains its initial checkpoint and error.
The two complete captures require distinct real PIDs, actual successful parent
waits, every sample, full source state checks and equal semantic output.
Individual native timings may differ and remain recorded separately.

Native capacity results and Rust product timing remain unrun until those
programs actually execute. Source #82 and all milestones remain open.
