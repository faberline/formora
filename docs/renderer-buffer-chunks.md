# Render complete large vertex streams

A GPU buffer is one block of device memory. Each device has a byte limit for that block. Formora splits large preview vertex streams into smaller blocks. A split always falls between complete triangles.

Full `draw`, `capture`, prepared snapshots and layers use all blocks in source order. A layer's global vertex ranges map to the correct local range in each block. Mesh IDs, annotations, positions, normals, colors and material values keep their existing rules. No model, source corner or instance is removed. No shader or project format changes.

For the reported device limit of 268,435,456 bytes, a 470,336,976-byte stream splits into two buffers:

| Buffer | Corners | Bytes |
| --- | ---: | ---: |
| First | 5,592,405 | 268,435,440 |
| Second | 4,206,282 | 201,901,536 |
| Total | 9,798,687 | 470,336,976 |

The default limit comes from the actual requested device limits. It does not request a larger device limit or an optional GPU feature. Counts and chunk boundaries use checked arithmetic. Invalid non-triangle streams and counts outside the supported range return `SceneError`. Empty streams use no vertex buffer and render a clear frame.

## Debug smaller allocations

`PreparedScene::vertex_buffer_count()` returns the number of GPU vertex buffers. `Renderer::vertex_buffer_chunk_limit()` returns the current byte limit for each new vertex upload.

`Renderer::set_vertex_buffer_chunk_limit(Some(bytes))` sets a smaller allocation limit. It must fit at least one full triangle and stay within the device limit. Invalid values return an error and preserve the previous setting. `None` restores the device limit.

This option changes allocation size only. It keeps every corner and the same draw order. It is useful for testing buffer boundaries with a small scene. Very small limits create many GPU buffers. Use the default for normal work.

A changed limit forces a new upload layout, including when `prepare_from` reuses unchanged CPU vertices. Existing snapshots keep their buffers and remain valid. Resetting the policy does not mutate older snapshots.

## Verify the repair

Pure-memory tests check the reported large size without allocating that source stream. They also check rounding, empty data, malformed input, maximum-count arithmetic and ranges that cross buffers.

The separate external consumer forces one triangle per actual GPU buffer. It compares the output with the normal single-buffer reference. It checks all corners, buffer counts, global layer order, annotations, old and future snapshots, resize, errors, empty output and policy reset. Those GPU checks run in CI or in independently authorized consumers.

The actual retained Vortex input still needs its own full capture, source hash, buffer count and process exit evidence on the fixed commit. Small correctness cases do not establish full-scene performance, the 56-model final gate or FF's original workload and timing budgets.
