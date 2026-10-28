# Polygon asset verification

Scope: [issue #32](https://github.com/faberline/formora/issues/32).
The [fixed contract](../contracts/polygon-assets.md) was committed as `dfd8f9d` before feature code.
This does not complete a product milestone. The full source baseline and predecessor gates remain open.

## Local checks

On macOS 26.5.2 arm64, Apple M1 Max, Rust 1.96.1:

- Rust format and Clippy with all features and targets passed.
- `cargo test --locked --all-features`: 79 tests passed. The count includes one Unix-only lock test.
- Python comparison and collection tests: 32 passed.
- Official MCP SDK 2.3.0: input schemas, polygon creation, tessellation query, vertex edit, undo and process reload passed.
- The strict full baseline check exits 2. It reports 9,047 sources, 9,036 pending sources and 13 pending features. `product_acceptance` remains `unrun`.

The polygon tests check concave surfaces on four plane orientations, at three scales, in both winding orders.
They check signed area, triangle interiors, source winding, sampled coverage without overlaps or holes,
collinear and coincident corners, collapsed faces and self-intersection errors.
Preview tests verify arm/base hits and a miss through the notch. A separate test checks distinct source corner normals
against each derived render vertex. Multi-layer order, active layer, loose edges and nonmanifold sharing survive query and undo.

Real-process CLI and MCP tests return the same tessellation. A crossing projection produces an error without a partial result.
The failed query leaves undo usable. Restoring the prior asset and querying a collapsed asset returns an explicit diagnostic.

## Source payload preservation

`tools/polygon_reference_smoke.py` passes all 57 fixed Blender 5.2.3 payloads through actual CLI processes.
Each case creates an asset, saves it, reloads it, queries it and runs Rust tessellation.
The [results](../evidence/polygon-assets/payloads/report.json) pin each reference and candidate by SHA-256.
The existing semantic comparer verifies exact oriented topology and the existing 1e-6 position, normal and UV limits.
UV order, source face and corner normals, smooth flags, edges, transforms and local/world bounds are included.
The derived triangle count also matches each regular reference payload.

This adapter reads existing reference geometry as input. It does not call a Formora primitive generator.
Primitive creation, context behavior and the 13 baseline feature contracts remain unaccepted.
The new CI step runs these payload checks on all three desktop platforms.

## Fixed performance samples

Run release examples `polygon_asset_bench` and `mesh_asset_bench`.
The [polygon report](../evidence/polygon-assets/performance.json) records all runs and source hashes.
The [old triangle sample report](../evidence/polygon-assets/triangle-regression-performance.json) confirms the original limits still hold.

| Polygon sample run | Validation | Tessellation | Create, edit, save and reload |
| --- | ---: | ---: | ---: |
| 1 | 23.07 ms | 27.79 ms | 212.09 ms |
| 2 | 18.42 ms | 23.70 ms | 196.07 ms |
| 3 | 18.42 ms | 24.46 ms | 194.85 ms |
| Fixed per-run maximum | 250 ms | 500 ms | 2,000 ms |

The polygon sample contains 10,201 vertices, 20,200 edges and 10,000 quads.
It derives 20,000 triangles without diagnostics. The old 20,000-triangle sample also passes all three runs.
These are finite CPU samples on one host. They do not prove large-world or viewport performance.

## Native Metal evidence

The [capture manifest](../evidence/polygon-assets/manifest.json) records source files, shader, capture inputs,
exact binary hash, every process result and pixel assertions. The MCP and source-payload reports use the same binary hash.

The top-down camera observes a U-shaped polygon. The [initial image](../evidence/polygon-assets/before.png)
has a rectangular notch. Pixel probes confirm the notch is background while both arms and the base are filled.
Changing one original vertex gives the [edited shape](../evidence/polygon-assets/after-edit.png).
A point that was filled becomes background. A new process loads the saved scene and produces a byte-identical
[reopened image](../evidence/polygon-assets/reopened.png). Codex also inspected the rendered shape.

A crossing version fails to render. No new output file appears. A pre-existing PNG keeps its exact bytes.
The crossing scene also remains unchanged. Failed process output is recorded in the manifest.

The first evidence script read failure text from stderr. The CLI returns JSON errors on stdout.
That script assertion failed. It was corrected and rerun in a new directory. The stored capture is the corrected run.

## Remaining integration and product gates

The issue stays open until the exact candidate passes three-platform CI and independent integration review.
After merge, compare the integrated tree with the tested candidate before closing this bounded issue.

Native window input for this candidate and Windows/Linux GPU execution remain unrun.
Loose-edge drawing and picking, primitive generation, polygon editing tools, UV editing, textures,
automatic smooth normals, sculpting and complete modeling parity remain pending.
All milestones require their full functional evidence and predecessor acceptance before closing.
