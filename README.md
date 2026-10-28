# formora
A Rust-based 3D creation suite combining modeling, animation, real-time rendering, and game development.

External agents operate Formora through MCP and a CLI. Humans review and play the results.

The [GitHub milestones](https://github.com/faberline/formora/milestones) define the roadmap.
The current work is the [source-backed acceptance baseline](docs/baseline.md).
No product milestone has passed acceptance yet.

The [scene core](docs/scene.md) and [agent interfaces](docs/agent-interface.md) provide
agent authoring and a room-and-door example. The optional [native preview](docs/preview.md)
shows the scene, plays door interactions, and saves review notes.
[Shared mesh assets](docs/mesh-assets.md) support agent edits, saved instances, and preview picking.
[Source polygon topology](docs/polygon-assets.md) preserves faces and edges while Rust tessellates preview surfaces.

```sh
cargo test --locked
cargo run --locked -- baseline check --root . --strict
```

The strict check fails until the baseline is complete. Contract checks do not prove product parity.
