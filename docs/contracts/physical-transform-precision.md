# Shared physical transform precision

This extends issue #48 before implementation. Keep all fixed source cases,
expected results, 1e-6 limits, capacity limits and acceptance gates.

Native scenes also retain their existing high-precision transform behavior.
Add `Transform.precision` with `f64` (default) and `f32`. Omit the default from
saved JSON so legacy representation stays unchanged. This is actual authored
scene state. Preserve it through edit, undo, animation and save/reload. Every
consumer must respect it. The source adapter explicitly authors `f32` for its
Blender object profiles and parents. This choice derives from source storage,
never from a measured result or a failing case. Keep all existing high-precision
preview and picking tests with their original limits.

The pinned object code constructs float32 rotation, scale and translation
matrices. Euler matrices use double trigonometry of stored float32 angles and
float32 matrix entries. Quaternion matrices normalize the stored quaternion in
float32, then use the pinned double-intermediate matrix conversion. Axis-angle
uses the pinned normalized-axis float32 Rodrigues matrix. Preserve the chosen
stored rotation representation and full authored values. Reject nonfinite or
unrepresentable calculations before any edit is published.

Compose physical local and parent frames through one shared native matrix
builder. In `f32` mode use the frozen source's float32 scale and four-term
balanced parent matrix product. Cast a higher-precision parent's actual matrix
at this child's explicit precision boundary. In default `f64` mode retain the
existing double-quaternion, scale and parent-product path. Retain reflected and
zero scales. Verify the single-precision path against the
actual reference binary and the primary object, SIMD and matrix sources.
All six measured Euler parent frames match the balanced path exactly. Do not
replace this with a double-precision product merely because it is more precise.

Mesh creation, transforms, geometric orientation, preview, rendering and picking
must consume that same physical matrix. Keep the shared quaternion conversion
for authored orientation and door rotation validation. Door animation still
replaces its actual stored representation. This supersedes the earlier gimbal
contract's direct double-quaternion-to-world construction rule. It does not
introduce a second authored rotation state or change saved JSON fields.

Add a read-only entity query: `scene inspect --entity ID --world`, and MCP
`scene_inspect` with `entity` and `world: true`. Return the actual row-major
`world_matrix`. For a mesh entity also return its typed vertex-ID map as
`world_vertices`. Resolve shared asset positions or actual built-in box
vertices from that entity. No input matrix, measured result or reference file
may be accepted by this query. Other entity types return their matrix only.
Reject `world` without an entity, or with an asset-only or other incompatible
query option. Querying must not change memory, disk, revision or undo.

In `f32` mode world vertex observations follow the pinned Python vector query path: float32
matrix entries and vertex coordinates, float32 products, double accumulation,
then one final float32 result. This differs from the core's internal float32
vector operations. Default `f64` queries retain double matrix/point arithmetic.
Keep those internal operations unchanged unless separately
verified. The source adapter must observe the actual native query. It may not
rebuild a world frame with a different quaternion or arithmetic path.

The source's local transform centre uses `calculateCenterLocal` and the actual
container `invert_m4_m4_fallback` result. The production function first tries
`EIG_invert_m4_m4`, with a zero determinant threshold. Reuse the already verified
Rust port of its pinned Eigen block inverse, including the ARM reciprocal and
two refinements. Only a rejected inverse uses the partial Gauss path. In
explicit `f32` mode use that complete path for nonsingular and singular frames. Preserve
the existing native `f64` nonsingular inverse-times-offset rule. The earlier
safe-inverse contract's default native behaviour remains unchanged. Do not
replace the operation's linear inverse with this distinct pivot matrix.

Independent tests must cover all rotation representations and Euler orders,
nonuniform reflected parent chains, balanced cancellation, point accumulation,
zero scales, shared instances, saved reload, query purity, overflow and failed
batches/saves. Preserve the complete older creation and preview gates. Run the
remaining source diagnostics, then the unchanged full comparison. Report all
new regressions and failures. A focused improvement cannot accept this issue.
