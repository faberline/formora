# Mesh selection baseline contract

This contract extends issue #14. It does not implement or accept product selection.
Reference: Blender 5.2.3 LTS, build `e13b728c6880`, manual family 5.2.
The product implementation belongs to milestone 0.2.

## Fixed scope and inputs

Read and retain the complete `selecting/all_by_trait.html` and
`selecting/introduction.html` pages from the frozen manual family.
Register six trait functions and four selection-mode functions.
The introduction page itself remains pending because its other tools are not covered here.

Use one explicit mesh with a quad grid, a closed tetrahedron, an isolated vertex,
a wire edge, two face regions connected only at a vertex, a three-face shared edge,
an inconsistently wound two-face edge, an isolated pentagon and a hidden component.
Give each vertex, edge and face a logical ID before any selection operation.
Use custom integer attributes to retain those IDs through the reference mesh.

Fix these 530 runs before capturing results:

| Function | Matrix | Runs |
| --- | --- | ---: |
| Ordinary mode conversion | Three initial and three target modes | 9 |
| Combined modes | Seven nonempty masks, three target modes, three actions, extend enabled | 63 |
| Expand conversion | V→E, V→F, E→F with expand enabled | 3 |
| Contract conversion | F→V, F→E, E→V with expand enabled | 3 |
| Non-manifold selection | All 32 classification masks, V/E modes, extend on/off | 128 |
| Loose geometry | V/E/F modes, extend on/off | 6 |
| Interior faces | V/E/F modes, empty and nonempty initial selection | 6 |
| Faces by sides | V/E/F, four comparisons, counts 3/4/5/INT_MAX, extend on/off | 96 |
| Poles by count | V/E/F, four comparisons, counts 0/3/4/INT_MAX, exclude-nonmanifold and extend on/off | 192 |
| Ungrouped vertices | V/E/F, extend on/off, absent/empty/positive/zero-weight groups | 24 |

INT_MAX is 2,147,483,647. V/E/F mean vertex, edge and face selection.
Preserve operator parameters from the actual reference build.
Explicitly declare expected reference errors before treating them as negative cases.
Any other capture error fails the batch. Never skip a run or publish a partial batch.

The initial reference probes declare 20 negative ungrouped-selection cases:
all 16 edge/face-mode cases reject the mode; four vertex-mode cases with absent
or empty groups reject the missing weights. Positive and zero-weight membership
are valid in vertex mode. Record the exact reference reason and unchanged state.

## Fixed result and comparison rules

Record before/after topology, positions, logical IDs, selected IDs, hidden IDs,
selection-mode mask, ordered selection history, active face and group weights.
The reference operation status and declared negative result are part of the result.
Exact sets and order must match where applicable. Do not compare counts alone.
Selection must not modify topology, positions, hidden state or group weights.
No position tolerance is needed for an operation that must not move geometry.

Run the same suite in two fresh reference processes. Compare every recorded run.
The comparer must reject changed component identity, geometry, selection, hidden state,
mode, active face, history and group membership/weights. It must reject omitted runs.
Pin inputs, tools, official page bytes, actual executable and both manifests by SHA-256.
Keep reference reproduction separate from Formora acceptance.

## Future product requirements, fixed before implementation

CLI and MCP must query and change selection through one Rust core.
Operate on stable mesh/component IDs. A legacy editor mode is not required.
Expose the equivalent domain mask and active/history state through the agent API.
Store selection state, reject invalid requests atomically, preserve unrelated attributes,
support undo, and retain the result after save/reload. Verify CLI/MCP equivalence.
The preview must show the selected components and respect hidden geometry.

For the initial capacity sample, use a 100×100 quad grid on Apple M1 Max/macOS/release.
Measure three runs for each selection function and mode conversion. Core selection
must take at most 100 ms per run. Select/save/reload must take at most 2,000 ms per run.
These limits are fixed before product selection is implemented. They must not be increased
to obtain a pass. Larger-capacity and full numeric-domain evidence remain required
before full function acceptance.

Full multi-object behavior, screen-space pick/box/circle/lasso and other selection
functions retain their original scope. This finite suite does not cover them.
New catalog contracts stay `pending`. Full inventory completion stays false.
All required three-platform CI, integration and independent content review remain open.
