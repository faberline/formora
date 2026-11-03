# Reuse geometry across frames

Enable the `preview` feature. The host owns each scene and decides which geometry must change. Use complete scene validation when preparing each layer. Keep `draw(&full_scene)` as the reference for image and behavior checks.

`PreparedScene` stores immutable GPU geometry. It also stores the world transforms from that exact validated input. `world_transform(id)` returns a copy of that prepare-time transform, or `None`. It does not read or validate current host data. Use a current snapshot for picking. A stale snapshot is not evidence of a current pose.

## Draw static and dynamic layers

```rust,no_run
use formora::geometry::camera_view;
use formora::preview::{DrawOutcome, Renderer};
use formora::scene::{Result, Scene};

fn frame(
    renderer: &mut Renderer,
    static_scene: &Scene,
    dynamic_scene: &Scene,
    current_scene: &Scene,
) -> Result<()> {
    // Keep this static snapshot across frames in the host.
    // Reprepare it in the frame where its actual inputs change.
    let fixed = renderer.prepare(static_scene)?;
    let moving = renderer.prepare(dynamic_scene)?;
    let lights = renderer.prepare_lighting(current_scene)?;
    let camera = camera_view(current_scene, renderer.width, renderer.height)?;
    let outcome = renderer.draw_layers(&[&fixed, &moving], &camera, &lights)?;
    match outcome {
        DrawOutcome::Submitted => { /* submitted; a present was requested */ }
        DrawOutcome::Skipped => { /* record a skipped frame, not a rendered sample */ }
    }
    Ok(())
}
```

Each layer is an ordinary `Scene`. Include every transform ancestor that its meshes need. Keep only required mesh assets and their material dependencies in a dynamic layer. Unused assets still receive full validation. Building a full-scene clone every frame can retain the original cost. Mesh entity IDs must be unique across layers. Ancestor, camera, asset and material IDs may occur in more than one layer. Each layer keeps its own validated asset and material values. The host must keep those values consistent with its full-scene reference.

Meshes render in global entity ID order. The input layer order does not change this order. This preserves alpha and equal-depth behavior from a single scene. Annotations render after all meshes, in input layer order. Concatenate the full reference's annotations in that same order. Adjacent ranges in one buffer share a draw call.

`capture_layers(&[&fixed, &moving], &camera, &lights, path)` uses the same order and writes a new offscreen PNG. Foreign renderer data, duplicate mesh IDs and invalid cameras fail before output replacement or submission. A snapshot remains tied to its original renderer.

`prepare_lighting` validates the current light entities and their transform ancestors. It includes stored native transform channels and `parent_inverse`. It keeps lights in global entity ID order. It ignores unrelated mesh data. This is an explicit partial view, like `camera_view`. It does not certify the whole live scene. The resulting `PreparedLighting` is immutable and belongs to one renderer. Supply the current lighting to every layer. A layer's old prepared lighting is ignored by the layer methods.

Stored light intensity uses the [preview light scale](preview.md#燈光強度). The renderer divides it by `100.0` before distance attenuation. These values are not physical light units. Reprepare lighting after a light changes. Keep the original light inputs and failed images when making a separate diagnostic scene.

Geometry, topology, material, annotation and ancestor changes require preparation of every affected layer. Camera-facing vertex and edge edit markers also require preparation when their camera changes. Keep static changes, validation, CPU preparation and GPU upload costs in the frame where they occur. Revision is never a validity key. Source changes that cross layers require updates to all affected layers.

## Measure a GPU pass

Create a renderer with `Renderer::new_profiled(window, width, height)`. This requests `TIMESTAMP_QUERY`. It fails if the adapter cannot support that feature. `Renderer::new` keeps its original feature requirements.

`draw_layers_profiled` submits the same ordered render pass to the window. It returns `ProfiledFrame`. A submitted frame contains `Some(GpuPassTiming)`. A skipped frame contains `None`. Submission and a present request do not prove that the display showed the frame.

`profile_layers` measures the same pass on an offscreen target. It does not present or write a file. Neither method is a full-pipeline benchmark.

Each timing sample includes:

- `start_tick` and `end_tick`: raw GPU render-pass timestamps.
- `timestamp_period_ns`: nanoseconds per tick from the queue.
- `render_ms`: `(end_tick - start_tick) * timestamp_period_ns / 1_000_000`.
- `cpu_readback_seconds`: blocking map, poll and readback wall time.

Equal or reversed ticks and invalid periods return errors. Missing or failed samples cannot pass a budget. No CPU clock value substitutes for GPU time. See the [wgpu 26 queue documentation](https://docs.rs/wgpu/26.0.1/wgpu/struct.Queue.html#method.get_timestamp_period) for the tick conversion.

Profiling blocks for readback. Record the caller's full frame wall time too. Include CPU simulation, scene projection, validation, preparation, uploads, submission, readback and presentation work in the full-pipeline accounting. GPU pass timestamps exclude CPU work, pre-pass transfer work and display latency. Offscreen time does not establish window FPS. Record skipped frames and failed samples separately.

The original consumer gates stay unchanged. FF Modern requires 1,000 villagers, 200 active raiders, 234 PBR assets and four heatmaps. Its GPU rendering budget is 6.50 ms. Its complete pipeline budget is 13.45 ms, with actual 60 FPS and the required behavior checks. A smaller scene or a faster median alone cannot pass those gates. Vortex's frozen 56-model corner, image and GPU checks also remain required.

## Evidence

The separate [consumer crate](../tools/renderer-consumer/src/main.rs) checks layer pixels against full-scene pixels. It includes interleaved mesh IDs, overlapping alpha surfaces, annotations, current lights, same-revision updates, retained snapshots, world transforms, resize and invalid-input file preservation. It reads actual GPU pass timestamps in CI. These small regressions do not establish either product's full acceptance.
