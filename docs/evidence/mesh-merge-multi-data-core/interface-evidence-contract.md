# Full multi-data interface evidence

Issue #79 keeps its frozen product contract and all original gates.
This document fixes the raw runtime checker before the full interface run.
It does not change the product, source inputs, comparison limits or scope.

Run all 13,440 cases once through actual CLI and once through official MCP.
Preserve every initial input, operation request, actual response, raw query,
saved scene, fresh-process query, PID and actual terminal result. Bind raw
responses to the values used by each checker. Expected native results are
opened only after real product execution. No native output enters setup.

The initial scene comes only from `multi_mesh_merge_product_inputs.scene`.
The merge request comes only from that module's independently authored request.
The initial scene is loaded by the actual product. Every mesh has a physical
asset/normal query. Every object has a world query and the explicit #80 state
query. The separate fresh process must return the complete saved final scene.
Read-only queries must not change the file. Rejected operations must preserve
the exact file bytes, in-memory scene, revision and every queried field.

Use the source gate's exact case list, source binaries, original source inputs,
independent PIDs, terminal receipts and raw hashes. Validate each source run
before comparing that case. Keep 4,352 enum rejections per interface separate
from the 9,088 finished operations. Skipped providers are not numeric matches.

Bind topology with a bijection constrained by actual positions, weights, native
integer provenance, adjacency, oriented faces and loops. A repeated integer
value alone cannot establish identity. Compare all named integer layers, UV
loops, weights including explicit zero, groups, material slots, smoothing,
seams, selection, typed history, normals and world vertices. Preserve all
attribute names and values. Integer and other discrete types stay exact.
Continuous limits remain 1e-6. Alias meshes must come from the same saved asset.

The old independently checked physical matcher uses the name `capture` for
provenance. The new checker may provide a read-only derived view of the real
`formora_v_id`, `formora_e_id` and `formora_f_id` layers under that name. It must
retain the original raw query and compare every original layer separately.
This view never enters product setup or product operations.

An absent stored editing field means no persistent edit state, as defined by
the core schema. An absent identity delta or default material index follows
the core's existing explicit serialization rules. Preserve these encodings
in raw data. Never infer scale locks from omission: require the explicit actual
`object_state.lock_scale` getter for every object, including default state.

Bind active-first provider order and shared data to actual saved context. Check
aggregate and detailed counts, status, skipped/processed outcomes, created,
removed, changed and lineage against real before/after assets. Unprocessed
data and unrelated context remain byte-equivalent in the canonical scene.

Source UI region size, camera navigation, autokey and source-only global
operator settings are captured and validated source context. They are not
new product outputs. The fixed tests have no animation, constraints, modifiers
or implicit global mesh mirror operation. These domains remain required in
the full milestones. This merge slice must not claim their implementation.

Before accepting the evidence, reject missing queries, corrupted geometry,
UV, integer layers, weights, frames, scale-lock values, source identities,
case coverage, provider order, duplicate data processing, forged receipt
counts, raw-response substitution and missing/failed terminal results.
Also prove that constructed input/request bytes never read source answers.
Keep all diagnostics and failed attempts. No skipped or unrun gate passes.
