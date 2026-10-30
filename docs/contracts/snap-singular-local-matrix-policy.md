# Approved unavailable local-matrix query policy

The user approved this rule in the active goal chat:

> 局部矩陣回報「無法求逆」，保留有效的操作結果與世界座標。

The decision is also recorded in issue #68, comment 6513201148.
It amends the source failure treatment before its Rust implementation.
Continue the complete 0.0–1.0 goal. No milestone or issue closes from approval.

## Exact source evidence

Keep all 1,764 authored zero-scale cases. Native diagnostic viewport processes
26380 and 27123 both completed every case with actual exit 0. They reproduce
the same twelve invalid after-state child matrix_local queries:

- singular_snap_0581, singular_snap_0583
- singular_snap_0591, singular_snap_0593
- singular_snap_0601, singular_snap_0603
- singular_snap_1549, singular_snap_1551
- singular_snap_1553, singular_snap_1555
- singular_snap_1557, singular_snap_1559

These cases use parent normal or delta Z scale zero, YXZ/YZX/ZXY target
rotation modes, and selected-to-cursor with rotation, with both offset values.
Every invalid field is in the after-state child's 4x4 matrix_local getter.
The raw diagnostic records retain all sixteen NaN scalar paths and f32/f64
bits. Keep the original strict capture failure (process 24423, exit 1) and
all diagnostic records unchanged. Do not relabel that failed capture as a pass.

## Product behavior

Keep the successful operation and its valid world matrices, positions and
other results. A local-matrix query that cannot produce a finite source-derived
result returns an explicit unavailable/cannot-invert result. It must not
publish NaN, silently substitute a numeric matrix, or reject the whole valid
operation. The query itself must not change scene data, revision or undo.
A separate world query continues to return its actual valid result.

Use actual evaluated frames and arithmetic to decide availability. Never
branch on a fixture ID, rotation-mode list or stored source answer. Keep
finite source results, including its exact-zero inverse fallback, under the
existing numeric checks. Do not declare all zero-scale inputs unavailable.

This policy is separate from the approved fourteen undefined mesh-axis
input rejections. Those still reject their exact input atomically. Do not
replace either policy with the other or extend source acceptance to a new
unmeasured defect. Other parameter/data/capacity domains remain required.

## Amended source validation

Compare both native captures with every original case and raw field retained.
Validate tagged invalid scalars only at the approved child-local getter paths.
Require the exact captured field/path/bit structure and source input witness.
Any unapproved invalid field, case, source outcome or missing result fails.

Check the physical state independently with the local getter in a separate
query channel. Do not insert fake numeric values into that getter to make a
validator pass. Validate all authored inputs and all remaining matrices,
geometry, attributes, sharing, settings, raw channels and world results.
Validate every available local getter with the original rules and 1e-6 limit.
Compare the complete raw capture across processes, including the NaN tags.

Report available numeric local queries and twelve unavailable local queries
separately. The twelve are policy outcomes, not numeric matrix matches.
No rejected whole operation, dropped case, skipped field or reduced numeric
limit can satisfy this approval. Preserve the original strict and diagnostic
reports as historical results, with their original failed/unaccepted status.

Freeze negative controls before product code: wrong unavailable case/path,
altered NaN bits, fake zero matrix, hidden world/geometry change, missing case,
same process and failed/missing terminal receipt must fail. Later run every
case through actual CLI and official MCP, persistence, physical queries,
real receipts, fresh reload, undo/replay and atomic error gates. Keep native
preview, source-denied checks, before-code performance limits, all retained
gates, three-platform CI, integration and independent Codex acceptance.

Approval resolves the policy question. It does not itself pass the amended
source validator, implement the query, or accept a complete product function.
