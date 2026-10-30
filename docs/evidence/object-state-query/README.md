# Object scale-lock state query — local evidence

Refs #80 and #79. All issues and milestones remain open. This is one property
query slice. It does not accept the complete modeling milestone or 1.0.

The frozen contract is `docs/contracts/object-state-query.md`. The implementation
commit is `0a5a3bed31b974fc5cee98155c3dc7113bf12a87`. It adds persistent
per-object `lock_scale` flags and one shared CLI/MCP metadata query. It keeps
default stored output unchanged when all new flags are false. The query reports
actual flags explicitly and does not invert matrices. It preserves the approved
singular-frame query policy; the separate singular-frame PR still needs integration.

## Source gate before implementation

- Fixed Blender 5.2.3, build `e13b728c6880`, binary SHA-256
  `de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619`.
- The independent author fixes 160 cases: eight boolean triples, five objects,
  two modes and two nonsingular frames. Objects include a parent, two independent
  edit meshes, a linked user and an outside mesh.
- Two real viewport processes, PID 63072 and 64988, each completed all 160 cases
  and exited 0. Each case includes before/after values, a saved real native file,
  and actual values after reopening that file. All raw records and lossless native
  files remain in `native-02/` and `native-03/` with parent terminal receipts.
- `source-comparison-01.json` passes exact booleans and identities and the frozen
  1e-6 matrix limit. Native file bytes and input hashes are bound to the receipts.
- Ten record corruption controls and seven header/terminal corruption controls
  pass. Forged operations are never executed. The original artifacts are unchanged.
- The first native capture failed after one saved/reopened case because Blender's
  old UI context expired. `native-01.staging/` and `native-01-process/` retain the
  failure. A persistent timer yields to Blender's event loop before the next case.
  No test input, source result or threshold changed.

## Frozen product controls

`before-code-seal-01.json` fixes the eight tests before product edits. The actual
old library passed the legacy format test and failed the seven new-feature tests.
`before-code-01/` preserves the output and exit 101. The frozen test SHA-256 is
`2a368ca82b87e9168a8db9675e383e12dc4625e78ad6bf78ca0df3d18989a205`.
The #79 frozen test SHA-256 remains
`4f1d536765e7f92109694d130a4ac9adcd3598993d427c60e8b873ce3b48a91f`.

All eight new tests now pass. They check explicit defaults, every flag combination,
per-object state, shared-mesh independence, saving, fresh load, undo, replay,
stale revisions, late batch failures, actual failed saving, invalid vectors,
unknown state owners, exclusive query options and metadata under a zero-scale parent.

The initial full Rust build exposed two old explicit `InspectRequest` literals.
They now include `object_state: false`; their old assertions are unchanged.
`compile-diagnostic-01/` keeps the actual compiler failure.

## Actual interfaces and independent recheck

- `runtime-01/` stores all 320 real cases: 160 CLI and 160 official MCP SDK cases.
  Setup uses independently authored input only. Expected native results are opened
  after real product execution. The MCP protocol is 2025-11-25.
- Each record preserves actual requests, raw responses, full scenes, every object's
  metadata and world queries, saved state and a separate fresh CLI load. MCP child
  PIDs, binary hashes and actual zero terminal exits have separate parent receipts.
- `runtime-verification-01.json` rechecks all 320 raw records against both source
  runs. It binds 10,880 actual calls to the stored query results. Eight forged
  product-record controls all fail as required. Original records remain unchanged.
- The first recheck compared Python tuples with their JSON arrays directly and
  stopped before checking product records. `verifier-diagnostic-01.json` retains
  this failure. Exact comparison now uses the same JSON representation.
- `isolation-02/` passes 24 unseen object/flag cases while macOS denies the product
  access to both repositories and the existing raw runtime answers. Three actual
  cat controls fail with access denied. Tests include a singular parent, linked
  users, invalid vectors, late invalid state, undo, replay and a fresh process load.
  `isolation-diagnostic-01/` retains the first driver's wrong optional-field access.
  The valid default format omits an absent context; the corrected driver still
  checks explicit default getter results. Product code is unchanged.

## Build and unchanged capacity limits

`build-02/` binds Rust 1.85 builds to source commit and executable hashes.
All 319 Rust tests pass with zero ignored tests. All 215 Python tests pass.
Clippy with all features/targets and `-D warnings` passes. Formatting passes.

`capacity-01/` preserves all thirty original capacity samples after this change.
The driver SHA-256 is unchanged:
`1e0c935ae4366c7275b04480ba38a66951089954837e96ffd5b4cbd572e34799`.
Both meshes still contain 10,201 vertices, 20,200 edges and 10,000 quads.
Ten forms each have three samples. All required validation stays inside the clocks.
All thirty samples pass: maximum core 406.040125 ms against 500 ms, and maximum
operation/save/fresh-load 766.680167 ms against 4,000 ms. Actual process PID 81702
exited 0. No input or limit changed. Prior #79 failed timings remain intact.

Archives use lossless copies with per-file raw and stored hashes. Originals remain
outside this checkout. Prior product binaries were copied and hashed before rebuild.

## Still required

The full #79 13,440-case CLI/MCP matrix must query actual scale-lock state before
claiming complete native object-state parity. All retained 16,374 interface records,
1,687 assets, 207 timing/source samples, native/GPU/recipe/save gates must be rerun
for the effective new product. Three-platform CI, dependency integration and
independent Codex acceptance remain required. Previous CI could not start due to
the account payment/spending restriction. No failed or unrun gate is a pass.
Issues #79/#80 remain `agy:doing`. All eleven milestones remain open.
