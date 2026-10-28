# Triangle asset verification

Scope: [issue #30](https://github.com/faberline/formora/issues/30).
The [fixed contract](../contracts/mesh-assets.md) was committed in `f5aca91` before feature code.
No milestone has passed full acceptance.

## Local checks

On macOS 26.5.2 arm64, Apple M1 Max, Rust 1.96.1:

- `cargo fmt --check`: passed.
- `cargo clippy --locked --all-features --all-targets -- -D warnings`: passed.
- `cargo test --locked --all-features`: 71 tests passed. This count includes a Unix-only lock regression.
- `python3 -m unittest discover -s tools/tests -q`: 32 tests passed.
- `tools/mcp_smoke.py` with official MCP Python SDK 2.3.0: passed. Tool schema validation, mesh creation, vertex edits, query, referenced deletion rejection, undo and process reload ran through the real stdio server.
- The baseline strict check exits 2. There are 9,047 sources and 13 pending feature contracts. There are 9,036 pending sources. Product acceptance is `unrun`. This expected incomplete result is not a passed product gate.

The asset tests use the pinned Blender 5.2.3 plane and cube triangle payloads.
Storage preserves their coordinates, corner UVs and normals. Preview coordinates under rotation,
translation and nonuniform scale stay within the existing 1e-6 metre bound.
These tests do not generate these primitives in Formora.

## Fixed performance sample

Run `cargo run --locked --release --example mesh_asset_bench`.
The program uses 10,201 vertices and 20,000 triangles. It runs three times and fails above the fixed limits.
The [measured report](../evidence/mesh-assets/performance.json) records the code hashes and all times.

| Run | Validation | Create, edit, save and reload |
| --- | ---: | ---: |
| 1 | 8.40 ms | 186.86 ms |
| 2 | 9.57 ms | 173.61 ms |
| 3 | 9.74 ms | 176.04 ms |
| Fixed maximum per run | 250 ms | 2,000 ms |

All three runs passed. The reported total includes creating the empty scene, two saved command batches,
and a new scene load. The loaded scene and all unchanged triangle attributes are checked.
This one sample is not a general modeling performance result.

## Native GPU evidence

`tools/mesh_asset_evidence.py` launches the built CLI for every operation and render.
The [manifest](../evidence/mesh-assets/manifest.json) records the exact binary, source and capture input hashes.
The adapter was Apple M1 Max, Metal. The saved [scene](../evidence/mesh-assets/scene.json) uses one asset in two entities.

- The [initial image](../evidence/mesh-assets/before.png) shows two flat panels with separate triangle materials.
- Editing vertex `b` through the CLI changes both instances in the [edited image](../evidence/mesh-assets/after-edit.png).
- A new process loads the saved scene. Its [reopened image](../evidence/mesh-assets/reopened.png) is byte-identical to the edited image.
- The edited image differs from the initial image. The saved asset query confirms the new vertex value.
- Codex inspected the image. The two panels are visible in front of the room wall.

The first capture put the panels behind the outside wall. Its before/after comparison failed.
It is not accepted evidence. The capture scene was corrected to place both panels in front of the wall.
The final capture was rerun after the wire JSON fix below.

## Regression found during review

Wire adapters first parsed JSON into a generic value. That parser discarded duplicate object keys.
The typed mesh deserializer therefore could not reject duplicate vertex IDs in stream requests.
A real-process test failed before the fix: the native reply reported success for a repeated vertex ID.

The wire parser now checks every object before building a generic value. Both native JSONL and MCP
reject the ambiguous request before mutation. The same regression passes after the fix and checks the saved bytes.
The CLI direct request and saved scene loaders also reject duplicate component IDs.

## Remaining acceptance

Three-platform CI must pass for the exact submitted candidate before integration.
After integration, verify that its tree matches the tested candidate before closing issue #30.
The issue remains open with `agy:done` until that review is complete.

Native window input was not rerun for this candidate. Windows and Linux GPU execution remain unrun.
This scope stores triangle buffers. Polygon boundaries, loose edges, primitive generation, UV editing,
texture rendering, generated smooth normals, sculpting and complete modeling acceptance remain pending.
All milestones stay open until their own conditions and predecessor conditions pass.
