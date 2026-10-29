# Reject the source's undefined all-axis rotation

On 2026-10-29 the human chose an explicit rejection for this source defect.
This replaces the native API's previous three-axis rotation extension.
It does not change any defined source transformation or numeric limit.

## Exact boundary

Reject a `transform_mesh` request when `change.kind` is `rotate` and every
`constraint_axis` flag is true. Reject every angle, orientation, pivot and
selection state at that boundary. Do not infer a zero axis or silently change
the request to an unconstrained rotation. All-false rotation remains valid.
One-axis and two-axis rotations remain valid. Translation and resize keep
their existing three-axis behavior.

The error must be exactly:

`mesh transform rotation cannot constrain all three axes: undefined Blender 5.2.3 source behavior`

Return no success receipt. Preserve scene data, revision, disk bytes and undo
history. A rejected command inside a batch rolls back the whole batch.
CLI, the native session and official MCP use this same operation core.
Describe the semantic restriction in the machine-readable agent schema.

## Evidence for the boundary

Use the fixed Blender 5.2.3 source commit
`e13b728c6880d3084d9d57c30031ed5df8b39dee` and executable hash
`de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619`.
The pinned `constraints_rotation_impl` handles masks with one or two axes.
It makes no assignment for three axes. `transform_mode_rotation_axis_get`
calls that callback without first assigning the output. `applyRotation`
declares its axis without initialization. Retain the complete source files.

Compile the unchanged callback body with minimal dependency declarations.
Initialize a sentinel axis before calling it for all eight masks. Verify that
the three-axis case preserves the sentinel, while the six defined constraint
cases copy the correct source basis axis. Keep raw compiler commands and
outputs. This probe avoids executing an uninitialized C++ read.
Retain disassembly from the fixed native executable's caller and callbacks.
Bind every artifact to its source and executable hash.

## Fixed verification

Keep all 1,203 source inputs and both complete reference processes unchanged.
Run all 2,406 original requests through CLI and official MCP. Do not remove
the seven affected source cases. Their fourteen product checks must require
the exact rejection and unchanged complete scene, geometry, attributes,
normals, world queries and disk bytes. Label them as human-approved rejection
checks. Do not count them as numerical matches to the observed source output.

The other 2,392 raw results must remain byte-identical to the previous RNG
candidate. This includes 2,344 defined deterministic comparisons and 48
stochastic support checks. Preserve the fixed 1e-6 position, normal and UV
limits and the original RANDOM support rules. Keep all previous failure
evidence. The defect does not authorize classifying any other error as a pass.

Add negative tests for a wrong error, a success receipt, a changed scene,
an altered request mask and accidental application of the policy to defined
rotation, translation or resize. Cover direct Rust execution, a failed batch,
an existing undo entry, saved files, the CLI and official MCP.

Retain actual Rust 1.85 tests, Python tests, formatting, Clippy, all old
generation/selection/creation/payload/normal/MCP regressions, new seeded RNG
checks, six source world queries, repository-denied execution and both native
Metal checks. Keep the unchanged nine-sample release grid benchmark and its
250 ms core / 2,000 ms pipeline limits. Failed or unrun checks cannot pass.

Required three-platform CI, dependency integration and independent acceptance
remain required. All eleven milestones retain their full scope. This policy
does not accept a feature, issue or milestone by itself.
