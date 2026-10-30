# Persistent object state query

Issue #80. Keep the full 0.0–1.0 goal and all #79 gates.

Before product changes, freeze 160 independent inputs: all eight scale-lock
boolean triples, five objects, two modes and two nonsingular frames.
The scene has two independent meshes, a linked user, an outside mesh and a
parent. Use fixed Blender 5.2.3 with the admitted e13b728c6880 build and binary.
Run all cases in two fresh real viewport processes. Bind initial and assigned
values to authored inputs. Save a real native file, reopen it and query again.
Keep raw values, sharing, geometry counts, matrices, actual PIDs and exits.
Boolean values and identities must be exact. Matrices use the fixed 1e-6
absolute limit. Property changes cannot alter geometry or object frames.
Capture source mode transitions separately; native UI mode restoration is
not inferred from the stored property. No source or product acceptance is
claimed from case counts alone. Add missing-case, value, sharing, matrix,
source-identity and missing/failed-terminal corruption controls.

Persist `lock_scale: [bool; 3]` in each object's state. The default is false
on each axis. Omit that new field from stored state when all axes are false.
Linked mesh users keep separate object states.

Add an explicit `object_state` inspection option. It requires one entity
and excludes mesh, world, normals, topology and tessellation query options.
Return revision, entity ID, entity and `object_state`, including an explicit
three-axis `lock_scale` value even for default state or absent context.
Do not compute or invert local/world matrices for this metadata query.
This preserves valid state queries under singular frames and keeps the
separately approved local cannot_invert/world-preservation policy intact.
The CLI spelling is `scene inspect --entity ID --object-state`.
The MCP spelling is `scene_inspect` with entity and object_state=true.
Default query formats stay unchanged. Use one core for both interfaces.

Before product changes, freeze direct behavior controls for explicit defaults,
all eight triples, per-object independence, persistence, fresh load, undo and
replay, invalid state/batch/save rollback, invalid query combinations and
singular frames. Record the actual old implementation failures.

Run every source case through real CLI and official MCP with full raw requests,
results, saved state and independent fresh load. Query values must come from
actual saved object state. Reject missing fields and fabricated values.
Keep existing 311 Rust tests, Python checks, #79's thirty capacity samples,
all retained 16,374 interface records, 1,687 assets and 207 timing/source gates.
No failed, skipped or unrun required gate passes. Keep all original thresholds.
CI, integration and independent Codex acceptance remain required.
Scale operations, all object constraints and complete milestones remain
required later work. This metadata query does not implement those domains.
