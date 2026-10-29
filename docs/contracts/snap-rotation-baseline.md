# Direct-snap rotation representations: source baseline

Freeze this contract and authored inputs before native capture and before
product implementation. This extends the same unlimited 0.0–1.0 goal.
It depends on the direct-snap baseline and PR #59. It does not close them.

Use the unchanged Blender 5.2.3 executable, build e13b728c6880, source commit
e13b728c6880d3084d9d57c30031ed5df8b39dee. Reuse the pinned direct operators,
protected object setters, Euler/quaternion/axis-angle conversion and matrix
source. Record all exact reused source paths, blobs and SHA-256 values.

## Authored scope

Create exactly 2,496 cases without reading reference results:

- 1,024 selected-to-cursor cases: all eight object rotation modes crossed
  with all eight cursor modes, four parent/frame profiles and all four
  offset/rotation flag combinations.
- 1,024 selected-to-cursor lock cases: eight object modes, all sixteen
  independent X/Y/Z/W channel lock masks, two parent profiles and all four
  flag combinations. Record the four-dimensional rotation-lock UI flag too.
  The flag is true in this group and false in the main group. Do not assume
  a UI restriction changes the actual direct operator's channel setter.
- 320 boundary cases: eight object modes, five authored rotation profiles,
  two parent profiles and all four flag combinations. Cover zero rotation,
  half-turn, near-half-turn, multiple turns and nonunit axis input. Include
  both signs of unit quaternions without folding the stored sign.
- 96 cursor-only controls: eight cursor modes, four cursor operators
  (grid, selected, active, world origin) and three parent profiles.
- 32 mesh-edit controls: eight cursor modes and four flag combinations.
  Edit mode must keep the cursor and object rotation representation. Its
  local/world geometry still follows the actual source operation.

The eight modes are XYZ, XZY, YXZ, YZX, ZXY, ZYX, QUATERNION and AXIS_ANGLE.
The four frames are unparented, rotated parent, reflected parent and a
nonuniformly scaled parent. Use metre coordinates and the prior authored
small mesh with its real UVs, groups, selection, material and smooth/seam
attributes. Include real shared mesh users and an unselected child. Keep
the source data identity and selection state explicit. Delta transforms
are authored identity for this bounded slice. Nonidentity delta transforms,
singular parents, other data modes and full parameter domains remain required.

Every rotation mode must carry its actual stored channels. Keep active and
inactive Euler, quaternion and axis-angle channels in the raw capture.
Quaternion raw channel order is source W/X/Y/Z; any later product X/Y/Z/W
mapping must be explicit. Partly locked quaternion or axis-angle channels
can produce a nonunit stored representation. Capture it without silently
normalizing or replacing it. Also capture the actual evaluated matrices.

## Native capture and fixed validation

Run the complete suite in two independent native viewport processes with
different process IDs and the same fixed executable SHA-256. No background
substitute is permitted. Reject an existing output. Keep staging persistent
on failure. Exact raw JSON may use lossless gzip; verify both raw and stored
hashes. Every manifest must bind all scripts, authored inputs, source pins,
operator RNA, command line, platform, binary, mode and actual terminal exit.

Set all active and inactive authored rotation channels explicitly. Bind the
complete initial state to those authored inputs, including all locks, modes,
local/basis/world/parent-inverse matrices, cursor, mesh data/sharing, attributes
and selection. Independently calculate initial physical rotations and world
vertices from authored inputs. No measured result may prepare an input.

Compare both captures for every case. Discrete values and identities stay
exact. Raw input channel assignment must match source f32 conversion exactly.
Continuous output values use maximum absolute error 1e-6 per component for
metre positions, normals, UVs, channels and matrices. Reject all nonfinite
values. Compare raw channels as stored, not just equivalent physical poses.
Keep cancellations and errors separate from numeric passes. A setup failure,
missing field, missing case or failed process is a failed complete capture.

Add negative controls for a wrong rotation mode, quaternion order/sign,
unwanted normalization, lock flag, matrix, cursor, vertex, UV, sharing,
operator parameter, script/input hash and process identity. Each control
must fail. Include analytic identity/zero/world-origin controls and unchanged
rotation controls when use_rotation is false or the source ignores it.
Do not loosen limits or drop a required case after seeing a result.

## Later Rust product gates

Write a separate implementation contract after the native baseline passes.
It must use one Rust operation core for CLI and official MCP, actual stored
representations and locks, typed real receipts, shared geometry, fresh reload,
undo/replay, atomic failures and preservation of unrelated authored values.
Run all 2,496 cases through both interfaces, plus all prior required suites.
Retain actual Rust 1.85, repository-read-denied, native Metal, recipe, Euler,
RNG and fixed 90+30+9 release performance checks. Freeze any added workload
and its limits before implementation. Required three-platform CI, integrated
dependency acceptance and independent Codex acceptance remain gates.

This baseline is not a complete rotation or snapping feature. Keep catalog
review pending, complete_products empty, and all milestones open. The approved
all-three-axis mesh-transform rejection applies only to its exact documented
source-defect boundary. It does not authorize rejecting these object/cursor
rotation modes or changing their comparison rules.
