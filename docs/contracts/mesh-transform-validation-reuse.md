# Reuse validated topology during mesh transforms

This extends issue #48 before implementation. Keep every source input, expected
result, 1e-6 comparison limit and fixed performance limit. All existing source,
regression, native, failure, integration and independent gates still apply.

The current 100-by-100 release grid fails all nine core samples at
269.346166–278.49525 ms. The core limit is 250 ms. A separate diagnostic measures
asset validation at about 47–49 ms and automatic normals at about 75–78 ms.
These component measurements locate work. They are not acceptance timings.

Full asset validation already builds topology to check editing and seam IDs.
Allow an internal caller to obtain that same owned topology after every asset
and selection-attribute check succeeds. Reuse it in transform setup and normal
calculation. Do not build a second equivalent graph or silently skip a check.
Public asset validation retains its original behavior for assets that need no
graph. The new internal path requests a graph when necessary.

Keep validation of IDs, geometry, border edges, UV layers and layout, normal
payloads, material slots, recipes, diagnostics, vertex groups and weights,
smooth-triangle IDs, seams, selected and hidden components, selection history
and active face. Keep budget checks, finite arithmetic checks, final asset
validation, validation after each batch command, and persist-on-success saves.
Keep the current arithmetic order and normal algorithm. Do not change error
or receipt semantics. Do not introduce a persistent topology cache that could
outlive a geometry or selection change.

Tests must fault invalid metadata through both transformed geometry and normal
queries. Failed transforms must leave the supplied scene unchanged. Compare
the complete 2,406 raw results against the previous candidate. Require unchanged
result bytes and preserve its fourteen known source failures. Rerun every
required legacy regression and native check for the final candidate.

Use the same release grid, identity frame, global direction, median pivot,
operation values, selected 10,201 vertices, complete 20,200 edges and 10,000
faces. Measure all three operations three times. Core must remain <=250 ms.
Operation/save/fresh-reload must remain <=2000 ms. Retain every raw sample and
all identities, input/output hashes and complete reload equality checks.
Independently compare this large grid with the fixed source at the unchanged
1e-6 limit. A timing pass alone cannot accept the feature, issue or milestone.
