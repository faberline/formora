# Scene snapping: local evidence, pending integration

Issue #58 belongs to milestone 0.2. Its contract was committed before code
at d4a3242. Additional exact Blender object-data/iteration source bytes were
committed at a32b87c. The parent is PR #57, head 0f9ce070c7f7116a10fbd93e8c6536abd4414e74.

Implementation commits are a7513ea86ef3dc60b9031b091ac2bf88fe21afe4 and
dcb484218708959ac28b4a1ac79d5ef8b4156a02.

No complete snapping feature, issue, integration or milestone is accepted.
All eleven milestones remain open. Required CI and independent integrated
acceptance remain unrun. The previous PR's GitHub jobs failed before starting
because GitHub reported the account payment/spending-limit restriction.

## Current implementation

The common Rust command core has persistent object selection, edit-mode
owners, authored order, channel locks, parent-inverse matrices and origin/
child settings. `snap_scene` provides seven actions and real receipts.
Queries, preview and scene authoring use the same physical world matrices.
Linked edit data has one actual edit owner. Other users see its live geometry.
Cursor rotation currently requires authored Euler channels in object mode.
Unsupported rotation representations reject atomically.

Object origins transform actual shared mesh data. Child compensation changes
the stored parent inverse. Parent conversion follows the pinned dependency
graph evaluation points. Budget and transaction errors keep the prior state.
Normals always use current positions. Geometry-only code can reuse validated
incidence. The command still performs mandatory full scene validation before
publishing any receipt, revision, undo entry or saved file.

## Final local checks

- Rust 1.85 all-feature tests: 250 passed at dcb4842.
  Twelve new scene tests include current-position normals,
  parent evaluation, selected descendants, aggregate budgets and failed save.
- Python tests: 118 passed after the temporary-case-directory change.
- All 5,750 CLI and official MCP requests passed on the final binary.
  The new 1,100 requests contain 1,094 numeric source comparisons,
  four explicit cancellations and two atomic rejections. The retained
  2,244 single-mesh requests contain 2,072 numeric comparisons,
  136 cancellations and 36 atomic rejections. The 2,406 transform requests
  retain 2,344 deterministic cases, 48 stochastic checks and 14 explicitly
  approved source-defect rejections. Rejection is not a numeric match.
- The evidence checker rechecked every raw request against authored setup
  and BOTH unchanged native source captures. It verified raw artifact hashes,
  matrices, actual receipts, geometry, attributes and normals.
- Retained generation, scale, selection, creation, payload and normal suites:
  1,591 checks passed. All 96 RNG checks, 48 fresh-process RNG checks and the
  official MCP smoke passed. All six Euler-order native frame checks matched.
- Native read-denied proof: 25 calls passed on the final binary. Four retained
  primitive, selection, creation and RNG isolation proofs also passed.
  Each actual repository-read denial was checked. Fresh reloads passed.
- Both new scene-snap and retained mesh-snap recipe proofs passed. Real edits
  mark recipes. Cursor-only and failed batches preserve them. Undo, replay,
  regeneration and fresh-process reload passed.
- Three native Metal proofs passed. The new shared scene changed 25 vertices
  and 6,860 pixels. Its child world frame stayed fixed through actual stored
  parent-inverse changes. Retained RNG and mirror scenes changed 12,532 and
  14,302 pixels. Each saved reload produced byte-identical PNG output.
- Native source performance capture: all 30 class/form cases completed in
  process 64573, terminal exit 0. Exact JSON bytes are retained losslessly in
  `performance/source-gzip/`. All 90 saved product samples passed fresh source
  comparisons for geometry, attributes, normals and object frames.
- Actual Rust 1.85 Clippy, format, debug build and release library build passed.
  Baseline metadata is structurally valid. Strict readiness returns exit 2:
  8,994 sources and all 38 features remain pending. No complete product is
  recorded. These checks do not accept the catalog.

All final product checks use binary SHA-256
`896fdd2583d684a1170e95fd4475351f7da254a9044d0174a5fb67eed840d1d5`.
`check-evidence.stdout` records the completed evidence audit, terminal exit 0.

## Preserved failures and interruptions

The first eleven-case pilot had one mode mismatch. The authored setup was
corrected to admit only the active-first unique edit owner, as the source does.
The next 550 CLI cases had 548 comparisons pass and two fail. Cases snap_1521
and snap_1533 exposed stale versus refreshed parent-evaluation timing. A source-
based evaluation snapshot fixed that behavior. Both complete diagnostic runs
remain in `diagnostics/` and are not accepted full gates.

Three subsequent real-interface runs ended with exit 1 during host storage
failure. Their completed raw JSON files have no reported comparison failure:
709 scene snap files (550 CLI and 159 MCP), 916 single-mesh snap files, and
1,717 legacy transform files (1,203 CLI and 514 MCP). None has a complete gate
report. Their interruption manifests and stderr remain under `diagnostics/`.
Lossless directory renames retained the original bytes without duplication.

The first large-grid native capture failed with OS error 28 after 26 forms.
Its temporary-directory exception cleanup removed the incomplete raw stage.
Only its driver/stdout/stderr survive. It is wholly unaccepted. The corrected
driver retains interrupted staging and writes exact JSON bytes through gzip.
The fresh 30-form source capture above completed successfully.

Three shell writes were rejected by the cap guard. One proposed removing
fresh raw duplicates after archiving. Two later writes contained syntax the
guard could not inspect. None executed. Non-destructive file patches added
new drivers. Every raw saved sample remains, including the archived copies.
No previously rejected external-cache cleanup was attempted.

Performance class C selected-grid has three pre-final samples within 500 ms.
The initial A selected-grid samples exceeded 250 ms. Reusing validated incidence
reduced two repeat samples below 250 ms, but another took 396.533292 ms. The
repeat therefore failed. Every sample and failed report is retained. Current-
position normal reuse and removal of duplicate private-candidate validation
was measured again at a7513ea. All 90 samples completed; 89 met limits.
Class C selected-cursor-true-true sample 2 took 506.860917 ms against 500 ms.
The whole timing gate failed. Every raw scene also has a verified byte-exact
copy in final-samples-scenes-07.zip (1,118,268,759 original bytes; 47,224,339
archive bytes). All raw copies remain. A further private multi-edit topology
reuse fix at dcb4842 retains mandatory final scene validation. Its new normal-
overflow rollback test passes. A further complete 90-sample trial at dcb4842
used one process per group and outputs inside the watched checkout. It had
18 timing failures. All 90 source comparisons passed, but its diagnostic
report correctly retains a failed whole gate. Host load was high when checked
afterward. The cause of timing variation is undetermined.

## Final fixed performance gates

A fresh full trial restored the original single-native-process method and
wrote outputs outside the watched checkout, on the same filesystem. Product
code, input bytes, timing intervals, hardware, sample counts and limits stayed
fixed. It ran every required sample. It did not discard warmups or select
successful samples. No other process, priority or host setting was changed.
`performance/one-process-10/` retains all raw samples, receipts, native output,
host observations and the controller report. All 90 samples passed:

| Class | Core range (ms) | Operation/save/reload range (ms) | Core/pipeline limits (ms) |
|---|---:|---:|---:|
| A | 100.576542–133.118167 | 238.408583–302.832708 | 250 / 2,000 |
| B | 100.189166–134.189041 | 238.720250–350.993875 | 250 / 2,000 |
| C | 202.414541–305.951625 | 472.907584–672.159958 | 500 / 4,000 |

`performance/source-comparison-10.json` records all 90 fresh saved-scene and
CLI frame/normal source comparisons, terminal exit 0. It uses the original
1e-6 limits. The 18-failure diagnostic trial remains wholly unaccepted.

All 30 retained snap performance samples passed, with maximum core time
215.644792 ms. All nine retained transform performance samples passed, with
maximum core time 228.841417 ms. Every one of these 39 saved samples passed
fresh source comparison. Transform position and normal maximum errors are
zero. Both retained drivers use the final release library and original
250/2,000 ms limits. All 129 final release samples passed.

## Remaining required gates

Optional gzip changes only artifact storage. It preserves exact
JSON bytes, rejects non-finite output and refuses existing artifact paths.
Temporary per-case scenes are reclaimed only after all actual calls and fresh
reload checks finish; their before/after data remain in the retained artifact.

Run required three-platform CI, integrate the dependency chain and obtain
independent Codex acceptance. The local evidence checker is not independent
product acceptance. The issue remains open with agy:doing until these gates pass.
Failed, skipped or unrun checks cannot pass. Keep catalog review pending and
complete_products empty. The original unlimited goal covers every milestone.
