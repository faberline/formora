# formora
A Rust-based 3D creation suite combining modeling, animation, real-time rendering, and game development.

External agents operate Formora through MCP and a CLI. Humans review and play the results.

The [GitHub milestones](https://github.com/faberline/formora/milestones) define the roadmap.
The current work is the [source-backed acceptance baseline](docs/baseline.md).
No product milestone has passed acceptance yet.

```sh
cargo test --locked
cargo run --locked -- baseline check --root . --strict
```

The strict check fails until the baseline is complete. Contract checks do not prove product parity.
