# formora
A Rust-based 3D creation suite combining modeling, animation, real-time rendering, and game development.

External agents operate Formora through MCP and a CLI. Humans review and play the results.

The current priority is Blender-style modeling through the Rust CLI.
Ashfall, Vortex, and FF Modern use Swift for their interface and model import entry.
Rust owns model data, validation, edits, and each app's core state.
The [CLI modeling and Swift import contract](docs/cli-modeling-swift-import.md)
sets the next delivery boundary. Swift host integration remains planned.

This branch adds a CPU-only static model package importer through the CLI and MCP.
It supports the first main triangle profile, not the older polygon/color profiles.
Run `formora model schema` for the manifest, request, and receipt contracts.
Import uses `formora model import --manifest PATH --expected-manifest-sha256 HASH --output NEW_DIRECTORY`.
Use the SHA-256 of the exact manifest file bytes for `HASH`.
The output must be a new model directory. The command does not change a game save.
Swift app integration and original model-set acceptance remain separate work.

The [GitHub milestones](https://github.com/faberline/formora/milestones) define the roadmap.
The current work is the [source-backed acceptance baseline](docs/baseline.md).
No product milestone has passed acceptance yet.

The [scene core](docs/scene.md) and [agent interfaces](docs/agent-interface.md) provide
agent authoring and a room-and-door example. The optional [native preview](docs/preview.md)
shows the scene, plays door interactions, and saves review notes.
[Shared triangle assets](docs/mesh-assets.md) support agent edits, saved instances, and preview picking.

```sh
cargo test --locked
cargo run --locked -- baseline check --root . --strict
```

The strict check fails until the baseline is complete. Contract checks do not prove product parity.
