# Rust material renderer

This slice supports the Rust CLI modeling path.
Swift remains the app interface and model import entry.
This library does not change an app or a saved model.

## Checked data

Use `material_project::load` to read a project with its expected raw SHA-256.
Use `material_project::validate_bytes` when the caller already has the bytes in memory.
Both paths use the same native scene and image checks.
See [the material project contract](material-project.md) for paths and file limits.

`RenderScene::from_project(&project)` borrows that checked project.
It derives triangles from all native faces with the pinned bb025 tessellator.
It rejects tessellation diagnostics.
It keeps each source face, corner index, vertex ID, and authored UV value.
Shared vertices can have different UV values at different face corners.
The derived vertex buffer uses `f32` values. The editable source retains its original values.
The native world transform is applied once. `Frame::model_to_world` adds a caller instance transform.

Entity material overrides take priority over mesh material slots.
A native material without an image uses identity white and its native base color.
Missing bound images are errors. They do not use a fallback image.
Used materials must have alpha 1 in this profile.

## Caller ownership

Enable the `render` feature for `formora::material_renderer`.
The default build has no GPU or window dependency.
The module re-exports its exact `wgpu` version.

The caller creates and owns the adapter, device, queue, target textures, encoder,
render pass, viewport, submission, and readback.
`Renderer::new(&device, format)` creates the pipeline on that device.
It accepts `Rgba8UnormSrgb` and `Bgra8UnormSrgb` color targets.
Use a `Depth32Float` depth attachment with one sample.
The pipeline uses depth writes and `Less`. It has no culling or blending.

`renderer.upload(&device, &queue, &scene)` uploads checked in-memory resources.
It returns a `GpuScene` with its own frame buffer.
Use `gpu_scene.set_frame(&queue, &frame)` before submission.
Use `renderer.draw(&gpu_scene, &mut pass)` inside the caller's render pass.
Use the same renderer, device, and queue for that scene.
The caller must supply a queue from that device and a compatible pass.
wgpu reports other device or attachment errors through the caller's error handling.

Create a separate `GpuScene` for each instance that needs a different frame.
The queue writes are visible at submission time.
Do not update one frame buffer between encoded draws and expect separate values.
Matrices are column-major, as in WGSL.
The shader supports the caller's perspective matrix.
The CPU pixel reference supports only affine, orthographic frames and interior pixels.

## Color and the fixed test

The shader uses per-corner UV values and flips V once at image sampling.
Images use `Rgba8UnormSrgb`, one mip, nearest sampling, and clamp-to-edge.
The native base color is a linear factor.
The shader multiplies it by the decoded image color.
The sRGB target encodes the result.
This is an opaque, unlit profile. It does not add lighting, PBR, or tone mapping.

The [frozen protocol](../protocols/material-render-v1.json) fixes the camera,
128 by 128 target, four interior pixels, source hashes, and channel tolerance.
Each GPU channel must differ from both the CPU reference and its golden value by at most 1.
The gray cases also test the color transfer and linear material factor.
Do not move the probes or reduce the limits after a failure.

`RenderIdentity` records raw project, scene, and encoded image hashes.
Its `render_revision` hashes the included validator and renderer source inputs.
This revision is not a Git commit or a reproducible binary attestation.
Record the source commit, archive hash, compiler, and binary hash with external results.

## External headless consumer

`consumers/material-headless` is a separate Rust package.
Its default mode uses no GPU. This also checks the public API from outside the crate.
Build it without running it:

```sh
cargo build --locked --manifest-path consumers/material-headless/Cargo.toml
cargo build --locked --manifest-path consumers/material-headless/Cargo.toml --features gpu
```

An operator can run a CPU check with an absolute project path and its exact raw hash:

```sh
cargo run --locked --manifest-path consumers/material-headless/Cargo.toml -- --project /absolute/project.json --expected-project-sha256 HASH --case panel
```

GPU execution is explicit. The optional mode requires an actual Metal GPU.
It does not request a fallback adapter or open a window.
After the operator admits that run, use a new output file:

```sh
cargo run --locked --manifest-path consumers/material-headless/Cargo.toml --features gpu -- --project /absolute/project.json --expected-project-sha256 HASH --case panel --gpu --output /absolute/new-panel.rgba
```

The consumer waits for readback and emits one JSON result.
The raw file contains 128 by 128 RGBA8 pixels with a top-left origin and 512-byte rows.
Its exit code is 1 if a required pixel or wgpu validation check fails.
The other cases are `gray128`, `gray128-half`, and `red-half`.
Use separate copied projects with the protocol's exact image and material change.
Keep original inputs unchanged.
The diagnostic consumer accepts the original panel geometry only.
It compares the four allowed material factors as exact `f64` numbers.
JSON `1` and `1.0` have the same value. Nearby values do not pass through rounding.
All other source fields must still match the original panel.
The public library also accepts other valid native material projects.

CI compiles both external modes and runs CPU geometry and shader validation tests.
CI does not create a GPU device or run this consumer.
Compile success is not GPU, app, model-set, or performance acceptance.
