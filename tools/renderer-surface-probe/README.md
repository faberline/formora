# Same-scene surface/offscreen GPU probe

This is a separate diagnostic consumer.
The engine stays at `d25a2a7ed7c16fa8d61f70e9c2f65926e962303d`.
The build checks all 99 original SDK files against their saved hashes.
It does not change the renderer, shader, timer or FF limits.

Build with Rust 1.85 or newer:

```sh
cargo build --locked --release --manifest-path tools/renderer-surface-probe/Cargo.toml
```

Run on an authorized GPU test host:

```sh
tools/renderer-surface-probe/target/release/formora-renderer-surface-probe SCENE.json NEW_OUTPUT_DIRECTORY 2200 1480 --active false --dynamic-prefix ff_hud,ff_villager_,ff_site_edge_
```

The output directory must not exist.
Keep the original scene and prior failures.
The probe reads the scene once and checks its file hash at the end.
It never writes the source.
Do not upload private scenes to GitHub or CI.

Without `--dynamic-prefix`, it uses one complete snapshot.
With this option, it uses two snapshots.
It keeps all IDs, transforms, parents, assets and materials.
It makes the other part's mesh entities Empty.
It keeps annotations in the fixed part only.
Split mode rejects editor contexts instead of dropping validation.
The complete and split snapshots must have the same total corner count.
Their offscreen PNGs must have identical RGBA bytes.

Each pair uses the same Renderer, snapshots, camera, lights and physical size.
It calls `draw_layers_profiled` and `profile_layers` in alternating order.
There are 5 warmup pairs and 8 measured pairs.
All warmups and slow samples remain in the report.
It records raw ticks, period, GPU time, query readback and whole-call wall time.
Readback overlaps GPU work and is already inside call wall time.
Do not add those values or subtract an unmeasured wait.

Actual focus, visibility, observed occlusion and refresh are recorded when available.
Unknown values stay null.
`--active true` requests activation as a separate recorded condition.
Do not use it to replace an earlier inactive run.
A changed physical size, skipped draw, early close or bad timestamp fails the diagnostic.

Both timing paths use the pinned Renderer's same target format.
Its API does not expose the exact format name.
The probe does not read actual surface pixels.
The PNG comparison is a separate offscreen complete/split check.
It does not prove physical presentation or FPS.

`completed_diagnostic_not_budget_acceptance` means the diagnostic finished.
It does not mean the original FF 6.50 ms GPU gate passed.
The report counts samples above that unchanged reference limit.
It does not replace the original workload, 1.10 ms input/pick, 3.80 ms ECS,
13.45 ms pipeline, 1,000 villagers plus 200 raiders, 234 PBR assets or four heatmaps.

Coordinate other test processes before measuring.
Record known background work without claiming full system isolation.
Keep the probe commit, engine commit, binary and input hashes, argv and actual wait/exit.
Root-agent local checks are compile/static and pure-memory tests only.
CI or an independently authorized consumer executes GPU work.
