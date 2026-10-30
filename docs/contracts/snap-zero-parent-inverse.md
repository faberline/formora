# Exact-zero parent inverse from the frozen source

Continue issue #73 and docs/contracts/snap-singular-core.md. Do not change
the approved twelve unavailable local-query rules, numeric tolerances,
performance workloads, sixty samples or 250/2000 ms limits.

The first complete CLI run at implementation 10834244 found fifty-six
source-parity failures. The source keeps successful operations and stores
an exact 4x4 zero parent inverse during singular skip-children compensation.
Its child world matrix is also the real 4x4 zero matrix. All physical
coordinates are finite. The current affine-only persistent state validator
rejects this valid source outcome and rolls the operation back.

Accept the exact all-zero matrix in addition to the existing finite affine
matrices. Keep every stored scalar, including the zero bottom-right value.
Do not replace it with identity, append a fabricated affine row, drop the
child, suppress the receipt or reject the source operation. Treat it as a
numeric source result, not one of the twelve unavailable local getters.

Keep existing affine constraints for every other matrix. Reject projective
matrices, near-zero matrices with any nonzero component and a non-affine
bottom row, NaN, infinity and values outside the finite f32 range. Add fixed
tests before changing product code. Require valid raw persistence, finite
world geometry, real object receipts, unchanged child transforms, undo,
replay and a fresh file reload.

Preserve every first-run failure and actual stopped process exit. Interrupted
CLI/MCP and retained runs are incomplete and cannot pass. Repeat all required
gates at the corrected head. Keep the first performance failure: one of sixty
samples was 287.408084 ms. No corrected functional result waives that limit.
