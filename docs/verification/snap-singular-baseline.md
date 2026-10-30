# Zero-scale direct snapping: failed baseline and retained diagnosis

Issue #68 continues the complete 0.0–1.0 goal. The source baseline has not
passed. No Rust product files changed. All eleven milestones stay open.

## Before-capture contract

Commit 5458897c froze the contract, 1,764 authored cases, source manifest,
strict native adapter, comparator and six analytic controls. Commit 4182f0ed
bound the native launcher and 21 pilot cases before capture. The product
base is draft PR #67 at dcc7a293145575851660ba6690e4bf36a2b42f8f.
All 23 reused source files have exact SHA-256 and Git blob checks. The new
manifest also pins the previously present Eigen inverse source bytes to
the exact upstream commit. No prior source pins, captures or limits changed.

Use Blender 5.2.3, build e13b728c6880, full source commit
e13b728c6880d3084d9d57c30031ed5df8b39dee and executable SHA-256
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
All native runs use a real viewport. None use background mode.

## Actual failure

The strict pilot completed 21 cases in process 23947, terminal exit 0.
Its complete authored-state and physical consistency checks passed.

The first strict complete capture used process 24423 and terminal exit 1.
It retained 581 complete cases in `native-01.staging`. Serializing the
next case, singular_snap_0581, failed because an actual source value was NaN.
The staging directory, stdout, stderr, command and actual terminal result
remain unchanged. The strict adapter still refuses nonfinite JSON.
No second strict complete capture or complete baseline pass is claimed.

Commit d4e88143 then fixed a separate diagnostic adapter before diagnosis.
It preserves each invalid scalar as its path, repr and actual f32/f64 bits.
It changes neither the strict adapter nor the authored cases or limits.
Its manifest explicitly says `NOT_ACCEPTANCE`.

Two independent diagnostic viewport processes, 26380 and 27123, each
completed all 1,764 original cases with terminal exit 0. Both reproduce
the same 12 invalid cases and exact tagged scalar fields. Every operator
reports FINISHED. That status alone does not mean its result is valid.

All invalid fields are in the after-state child's matrix_local getter.
The object channels, world matrices and physical world vertices remain
finite. Normal-scale cases are 0581, 0583, 0591, 0593, 0601 and 0603.
Delta-scale cases are 1549, 1551, 1553, 1555, 1557 and 1559.
They use a zero parent Z scale, YXZ/YZX/ZXY target modes and cursor snapping
with rotation. Both offset settings are covered.

The pinned matrix_local getter inverts the parent world matrix with the
4x4 Eigen function before multiplying the child world matrix. Its inverse
uses an exact zero determinant test and writes a zero matrix on detected
failure. This is distinct from the 3x3 snapping inverse, which retains its
adjugate. A floating-point explanation for the nonfinite getter is not yet
independently proved. Do not claim a cause from the observed NaN alone.

## Checked evidence

The paired diagnostic checker verifies every raw/stored gzip hash, process,
terminal receipt, source/script/input provenance and historical lock. It
compares every captured field across both processes at the unchanged 1e-6
continuous limit and exact discrete equality. All 1,752 finite cases pass
the strict per-case authored and physical checks in both processes.

The 12 nonfinite cases are retained in full. They receive no replacement
values and no projected numeric pass. The checker explicitly records
`baseline_passed: false` and `required_full_gate_passed: false`.
Its diagnostic integrity pass is not source or product acceptance.

The source validator independently checks basis/world/vertex consistency.
For singular parents with an actual exact zero matrix column, it checks
the source matrix_local zero inverse. For dense singular frames it retains
and compares the raw getter across processes, without claiming an independent
inverse oracle. Six preparation controls and twelve actual native controls
check zero masks, raw channels, deltas, the zero getter, world frames, real
geometry, sharing, child identity, errors and cancellation mutation. The
native controls also distinguish nonzero rank-two adjugate translation from
the zero adjugate for rank-one/zero frames.

The first full Python command passed 196 tests before the twelve native
controls were added. Each native control then passed. The later complete
Python command passed all 208 tests with terminal exit 0. Its log and actual
terminal result are retained. The strict readiness check still exits 2;
all 38 features remain pending and both products remain incomplete.

## Approved policy and pending product work

The user has approved an explicit unavailable/cannot-invert local-matrix
query while preserving valid operations and world results. The decision is
recorded in issue #68, comment 6513201148. The exact amended policy is frozen
in docs/contracts/snap-singular-local-matrix-policy.md. The earlier approval
to reject fourteen undefined mesh-axis inputs remains separate.

The original failed strict capture and diagnostic-only reports remain
unchanged. The amended source validator and product implementation are still
pending. No unavailable local query is a numeric matrix match. Keep all
original cases and unchanged numeric limits; do not reject the valid operation.

This draft contains no product implementation or performance acceptance.
Three-platform CI, stack integration and independent Codex acceptance remain
unrun. The previous PR #67 CI jobs did not start because GitHub reported an
account payment/spending-limit restriction. No billing or runner settings
were changed. All product domains remain in scope.

## Reproduce the retained diagnosis

Use Python 3.12 and install `tools/requirements-mcp.txt` in the chosen
Python environment. Run from the repository root. Use a new output file:

```sh
python docs/evidence/snap-singular-baseline/check-diagnostic-captures.py --output /private/tmp/formora-zero-scale-diagnostic-new.json
python -m unittest discover -s tools/tests -v
```

The checker exits zero only for diagnostic integrity. Its JSON must still
report the failed baseline and twelve invalid source getters. It refuses
an existing output file. The first checker's exact bytes are preserved in
`diagnostics/check-diagnostic-captures-first.py` alongside its original report.
Do not overwrite the source captures to repeat a check.
