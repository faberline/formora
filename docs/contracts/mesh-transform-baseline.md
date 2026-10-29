# Mesh component transform baseline

Issue #46 extends #14. Product implementation belongs to 0.2.
The input and this contract must be committed before reference capture.
No Rust transform implementation is part of this baseline issue.

## Fixed source

Use Blender 5.2.3 LTS, build `e13b728c6880`.
Core source commit: `e13b728c6880d3084d9d57c30031ed5df8b39dee`.
Official manual branch `blender-v5.2-release` resolves to
`4a3be8f9ed3b66b24913e0a0d491d3429a70ea08`.
Pin the complete relevant manual files, Git blobs, URLs and SHA-256 values.
HTML access failed; the official manual repository content API supplies the same versioned source.
Keep the existing 9,047 inventory IDs and every existing pin.

## Functional contracts

Add separate pending cases for translate, rotate, resize, transform orientation,
transform pivot, proportional falloff, connected influence and projected influence.
Each case links actual source IDs, explicit authored inputs and required result fields.
Do not accept a feature merely because one finite suite exists.

The authored fixture contains a raised connected grid, a separate face island,
a wire, a point at another depth, a hidden face, two UV layers, materials,
smooth flags, seams and vertex weights.
Record and check all initial geometry and selection against the authored JSON.
Exercise vertex, edge and face selection, active elements, all seven built-in
directions, explicit custom matrices, all five pivots, all eight axis masks,
parent frames, nonuniform/reflected scale and singular targets.
Include zero/negative scales, zero/reverse/full-turn rotations, small values,
center overrides, mirror options, precise mode and face-attribute correction.
Proportional editing covers every falloff, connected/projected combinations and radius boundaries.
Empty and hidden-only selections must have explicit source outcomes.

Keep the full operator parameter definitions, including array lengths, flag enums,
defaults and numeric limits. Record parameters not covered by this mesh-edit suite.
Snapping, topology-changing auto-merge/split, other data types, object modes,
capacity and complete numeric domains remain necessary roadmap work.
Legacy mouse/key confirmation is covered by the already approved GUI-parity exclusion.
Do not extend that exclusion to a product function.

## Fixed comparison and evidence

Run the complete fixed input in two separate reference processes.
Require different process IDs and identical fixed executable hashes.
Retain parameters, environment, complete before/after stable-ID geometry,
normals, world matrices, selection, hidden state, history, active face, groups,
UV values/order/active layer, materials, seams and smooth flags.
Compare oriented topology and logical identities exactly.
Position tolerance is 1e-6 metres per component.
Normal and UV tolerances are 1e-6 per component.
Reject non-finite values and modified pins, hashes, IDs or inputs.
Compare every deterministic result across the two processes.
Add independent analytic checks for simple identity-frame transformations.
Add negative tests that actually corrupt results and require rejection.

The fixed source seeds RANDOM falloff from whole clock seconds in
`transform_generics.cc`; it does not expose that seed as an operator input.
Do not claim two independent random results must be identical.
For RANDOM, verify stable topology/attributes/selection, finite normals and
the requested transform path with an influence in [0,1].
Retain both complete outputs and label this as a stochastic support check.
It is not RNG sequence, distribution, full numeric or product acceptance.
Do not reinterpret stochastic checks as deterministic position agreement.

Reference capture must be atomic and refuse existing output directories.
It must refuse changed inputs or adapter files while running.
Failed, skipped, missing and unrun checks cannot pass.
The catalog entries remain pending and `complete_products` remains empty.
The strict baseline must continue to report incomplete work.

## Fixed later product gates

CLI and MCP must use one Rust core and expose real result identities.
Save/reload and undo must preserve geometry and shared references.
Invalid parameters, stale revisions, singular targets, failed batches and failed
saves must roll back without issuing success receipts.
Existing numerical, MCP, native preview, isolation and performance checks remain.

Apple M1 Max / macOS / release: transform a 100×100 quad grid with each of the
three basic operations three times. Core <=250 ms; operation/save/reload <=2000 ms.
Use row-major integer XY vertices from (0,0,0) to (100,100,0), all vertices selected,
GLOBAL orientation, MEDIAN_POINT pivot, an identity object frame, no proportional
influence, no snapping and no UV correction. Translate by (0.375,-0.625,0.25),
rotate by 0.61 radians about the source's unconstrained Z axis, and resize by
(1.25,0.65,1.1). Keep the complete 10,201/20,200/10,000 topology and stable IDs.
Core timing includes the validated atomic editor operation and actual result receipt.
Prepare input before timing. Pipeline timing includes the operation, saving and a
fresh complete reload equality check. Retain monotonic raw timestamps.
Metal must show a real modification and byte-identical fresh reload output.
Required three-platform CI, dependency integration and integrated independent
acceptance remain necessary. All milestones stay open until their complete gates pass.
