# Update from a previous snapshot

`Renderer::prepare_from(previous, scene)` makes a new immutable snapshot. It starts with the previous snapshot's CPU preparation cache. Other layer or reference preparations cannot evict that cache.

```rust,ignore
let next_fixed = renderer.prepare_from(&previous_fixed, &current_fixed_scene)?;
let next_dynamic = renderer.prepare_from(&previous_dynamic, &current_dynamic_scene)?;
```

Keep each layer's previous `PreparedScene` or `Arc<PreparedScene>`. Use its own previous snapshot when updating that layer. Keep current lighting and camera separate, as described in [geometry layers](renderer-layers.md).

The new method fully validates the actual current `Scene`. It keeps the existing exact-value asset and vertex cache rules. It does not trust revision, allocation identity, a caller's dirty flag or a previous validation claim. Changed, invalid, recipe, weight and unused asset inputs retain their existing validation behavior. A foreign renderer snapshot is rejected.

Each snapshot keeps private immutable CPU cache data. Cache branches share immutable asset and vertex payloads through `Arc`, a Rust handle for shared ownership. They copy their mutable indexes. An unchanged branch can reuse its GPU vertex buffer. Changed geometry gets a new buffer. Current camera and lighting are prepared from current input. An invalid branch cannot change its base snapshot. Two future branches can share one older base safely. Resizing uses the renderer's current dimensions.

`Renderer::prepare` keeps its existing shared-cache behavior. `draw` and `capture` keep full live-scene validation. The new method is optional. No scene format, shader or dependency change is required.

This cache uses memory to retain the CPU inputs, resolved assets and vertices needed by older snapshots. Release snapshots when they are no longer needed. Cloning indexes and validating current data still take time. Include that cost, changed geometry preparation and uploads in the actual frame. This method does not certify the whole host pipeline or remove its partition and projection costs.

The CPU benchmark runs only in CI. It uses the existing public 256-instance, 189-face fixture. After three warmups, it records eight pairs in alternating order. It compares clone-plus-update from the old valid static cache against preparing that same updated static scene after another scene evicts the shared cache. Every result must match direct vertex bits. The branch median must be at most 25% of the evicted-cache median. Raw clone, eviction, preparation and cold costs are retained. Both older benchmark thresholds remain unchanged.

The [external GPU consumer](../tools/renderer-consumer/src/main.rs) checks branch pixels, current lights, changed static and dynamic layers, two futures, retained older frames, invalid inputs, foreign renderer rejection and resize. Tests run in CI or in independently authorized consumers. Small regressions do not pass the original FF workload and performance gates or the final common-pin Vortex gate.
