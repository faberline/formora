# Direct snapping with nonidentity delta transforms: source baseline

Freeze this contract, authored inputs and capture programs before native
capture and before Rust product changes. Continue the unlimited 0.0–1.0 goal.
Depend on draft PR #63 at 7779cf8fac799dc9aa1e94ed064df80799039b01.
This bounded source baseline does not accept a complete feature or milestone.

Use Blender 5.2.3, build e13b728c6880, source commit
e13b728c6880d3084d9d57c30031ed5df8b39dee and executable SHA-256
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619.
Reuse the exact pinned direct operators, protected setters, object matrix
composition, RNA definitions and rotation/matrix arithmetic. Record reused
source paths, Git blobs and hashes. Do not modify earlier captures or limits.

## Authored cases

Create exactly 1,792 cases without reading measured results:

- 512 selected-to-cursor cases: eight object modes, four delta profiles,
  four parent frames and four offset/rotation flag combinations.
- 1,024 protected setter cases: eight modes, all sixteen X/Y/Z/W lock masks,
  two parent frames and all four flag combinations. Use combined deltas.
  Set location X/Y/Z locks to the corresponding rotation mask bits too.
- 96 cursor controls: eight cursor modes, four cursor operators and three
  parent frames. Use combined target deltas.
- 32 mesh-edit controls: eight cursor modes and four flag combinations,
  with combined deltas and the rotated parent frame.
- 128 origin/child controls: eight object modes, all four origins-only /
  skip-children combinations and all four offset/rotation combinations.
  Use combined deltas and the nonuniformly scaled parent frame.

The eight modes, four nonsingular frames, mesh topology and real UV, group,
material, seam, smooth, selection, sharing and child data come from the fixed
rotation input generator. Each case sets every normal and delta channel.
The four delta profiles isolate translation, rotation, reflected scale and
their combination. Euler and quaternion delta values include inactive data.
The quaternion rotation profile is deliberately nonunit and negative-signed.
Preserve its stored values; physical evaluation normalizes a copy.
Parent and child have explicit distinct nonzero delta translations and identity
delta rotations/scales. Shared selected objects get the same delta profile.

The fixed source RNA disables delta axis-angle exposure with `#if 0`.
Record that absence from actual RNA. Do not invent an exposed property or
write native memory. AXIS_ANGLE object cases keep actual default internal
delta axis/angle while setting and preserving exposed inactive delta Euler
and quaternion fields. Other internal/native-data domains remain required
work; this slice does not exclude them from the full goal.

## Capture and checks

Use two separate native viewport processes with different process IDs and
the same fixed executable. No background replacement is permitted. Refuse
existing output or staging folders. Preserve staging on failure. Store exact
JSON with optional lossless gzip and bind raw and stored hashes.
Bind scripts, authored inputs, source manifests/files, baseline lock, RNA,
platform, command, process identity and actual terminal exit to each capture.

Bind all initial normal/delta channels and lock flags to authored f32 values.
Independently compose initial basis/world frames and world vertices from
authored inputs. Follow source order: delta rotation times normal rotation,
componentwise normal times delta scale, and normal plus delta location.
Do not use a captured matrix, resulting channel or geometry as an input.
Check stored before/after channel-to-matrix and matrix-to-world consistency.
Respect actual parent inverses when origins-only or skip-children changes them.

Compare every field in both captures. Discrete values remain exact.
Positions in metres, normals, UVs, channels and matrices use maximum absolute
error 1e-6 per component. Reject nonfinite values. Keep cancellation and error
outcomes separate. Missing fields/cases, setup failure or nonzero terminal
exit fail the complete capture. Do not remove a case after seeing results.

Every delta channel must remain unchanged by these direct operators. Check
unaffected normal channels, protected channels, cursor behavior, real shared
data and geometric attributes. Origin compensation may change local vertices
and parent inverses but must preserve the actual source world result.
Add negative controls for reversed delta multiplication, missing translation,
wrong scale/sign/normalization, altered inactive data or locks, stale frames,
false sharing, geometry/UV changes, source input/hash changes, same process,
missing case and source error. Include analytic identity and quarter turns.

## Later Rust gates

Write a separate before-code product contract after this complete baseline
passes. Both CLI and official MCP must run every case through the shared
operation core. Require actual saved channels, physical preview/query frames,
typed receipts, sharing, fresh reload, undo/replay, atomic errors and recipe
behavior. Retain all previous required suites and freeze new performance
workloads/limits before implementation. Three-platform CI, dependency
integration and independent Codex acceptance remain gates. Failed, skipped
or unrun required checks cannot pass. Preserve the exact approved undefined
mesh-axis rejection policy without applying it to valid object delta modes.

Keep catalog review pending, complete_products empty and all milestones open.
Singular transforms, broader parameter ranges, other data modes, continuous
snapping and capacity remain in the unchanged full product goal.
