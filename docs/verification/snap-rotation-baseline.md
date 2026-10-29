# Direct-snap rotation baseline: local source evidence

Issue #60 extends milestone 0.0. Contract bb3bdb3d was committed before
capture. Commit de019498 froze 2,496 authored inputs and source adapters.
The parent is draft PR #59, head 9572c28100d2a0fed31ed620fed7a9b061e26ef6.
No Rust product code changed in this baseline slice.

## Native results

Two independent native Blender 5.2.3 viewport processes completed all 2,496
cases each. Process IDs are 45292 and 47244. Both actual terminal exits are
zero. Both use executable SHA-256
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
Build e13b728c6880 and full source commit
e13b728c6880d3084d9d57c30031ed5df8b39dee remain fixed.

The final comparison passed every case against both raw captures. It binds
initial state to authored inputs and independently evaluates rotation and
world matrices. It checks raw active/inactive rotation channels, all locks,
parent frames, mesh sharing, geometry, attributes, normals and actual operator
parameters. Both processes returned FINISHED for every case. No failed or
cancelled result was counted as a numeric pass.

The 4,992 exact JSON artifacts are stored losslessly as gzip. Their manifests
bind both compressed and raw hashes. Native terminal receipts bind each
manifest and the exact historical lock bytes. The controller archived that
lock only after checking it matched the source process's recorded input hash.
Verification permits later appended pins while checking every historical pin
and unchanged baseline criteria. Repository paths can move to another
checkout without changing any captured byte or its identity.

New pinned primary source files cover cursor RNA, cursor physical rotation
and persistent scene data. All 7,177 prior pins are unchanged. Four new pins
bring the lock to 7,181 entries. Reused manifests retain exact object setters,
direct operators and Euler/quaternion/axis-angle arithmetic.

## Local gates

- Full final source reproduction: 2,496 cases passed, terminal exit 0.
- All Python tests: 140 passed, terminal exit 0.
- Final focused controls: 22 passed after the final provenance checks.
  Controls reject bad modes, raw quaternion order/sign/normalization, locks,
  matrices, cursor, geometry, UVs, sharing, nonfinite values, request changes,
  source errors, process reuse and changed script provenance. Zero rotation
  and a quarter turn also have analytic checks.
- The workflow now requires full raw rotation-source verification on all
  three platforms. These CI checks have not run successfully.
- Baseline metadata is structurally valid, with no reported problems.
  Strict readiness exits 2. All 38 features and 8,994 sources remain pending.
  Both products remain incomplete and complete_products is empty.

Partially locked quaternion channels can be nonunit in the actual source.
They remain raw stored channels. Evaluation normalizes a physical copy.
Replacing the stored channels with a normalized quaternion fails validation.
The approved all-axis mesh-transform source-defect rejection is unchanged.
It does not apply to these object/cursor cases.

## Preserved failures

The first diagnostic native launch exited 1 before creating capture staging.
The adapter expected a files key in manifests that use source_files. Its
driver and stdout/stderr remain under diagnostics/pilot-01. An unsupported
--noaudio argument was also reported. The fresh command omits that argument.
The corrected manifest adapter validates both exact schemas. A new native
12-case pilot passed. Its complete focused output is retained under
diagnostics/pilot-02 and is not accepted as a complete baseline.

The first Python control run exited 1 before executing tests. A class field
named run shadowed the unittest runner method. Renaming that field to case
fixed the harness. Its original error output remains retained. All 20
controls then passed. Two further provenance controls bring the final total
to 22. Earlier complete comparison reports also remain retained; only
reproduction-final.json binds the final comparator bytes and terminal checks.

## Remaining gates

Three-platform CI, dependency integration and independent Codex acceptance
remain required. PR #59's six jobs failed before starting because GitHub
reported failed account payments or a spending-limit restriction. No merge
or PR diff review was performed through that failed gate.

This is source evidence. The additional rotation modes are not yet a Rust
implementation. All 2,496 cases still need both real product interfaces under
a separate before-code contract. Retain all previous required performance,
native, recipe, source and transaction gates. Other data modes, continuous
snapping, delta transforms, singular-parent cases, full parameter domains and
capacity remain work under the original unlimited goal. No complete catalog
feature, issue or milestone is accepted. All eleven milestones remain open.
