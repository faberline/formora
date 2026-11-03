//! Executed only by an independently authorized operator with --gpu.
use formora::{
    material_project::render_data::{Frame, ReferencePixel, RenderScene},
    material_renderer::{Renderer, wgpu},
};
use serde_json::{Value, json};
use std::{io::Write, path::Path};

pub async fn capture(
    scene: &RenderScene<'_>,
    frame: &Frame,
    output: &Path,
    cpu: &[ReferencePixel],
    goldens: &[[u8; 4]],
) -> Result<Value, Box<dyn std::error::Error>> {
    // The external caller owns every device/target/pass. The library creates none of these.
    let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
        backends: wgpu::Backends::METAL,
        ..Default::default()
    });
    let adapter = instance
        .request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            force_fallback_adapter: false,
            compatible_surface: None,
        })
        .await?;
    let info = adapter.get_info();
    if info.backend != wgpu::Backend::Metal || info.device_type == wgpu::DeviceType::Cpu {
        return Err("protocol requires an actual Metal GPU, no fallback".into());
    }
    let (device, queue) = adapter
        .request_device(&wgpu::DeviceDescriptor {
            label: Some("External Formora material consumer"),
            required_features: wgpu::Features::empty(),
            required_limits: wgpu::Limits::default(),
            memory_hints: wgpu::MemoryHints::MemoryUsage,
            trace: wgpu::Trace::Off,
        })
        .await?;
    device.push_error_scope(wgpu::ErrorFilter::Validation);
    let renderer = Renderer::new(&device, wgpu::TextureFormat::Rgba8UnormSrgb)?;
    let mut model = renderer.upload(&device, &queue, scene)?;
    model.set_frame(&queue, frame)?;
    let size = wgpu::Extent3d {
        width: 128,
        height: 128,
        depth_or_array_layers: 1,
    };
    let color = device.create_texture(&wgpu::TextureDescriptor {
        label: Some("External caller color"),
        size,
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: wgpu::TextureFormat::Rgba8UnormSrgb,
        usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
        view_formats: &[],
    });
    let depth = device.create_texture(&wgpu::TextureDescriptor {
        label: Some("External caller depth"),
        size,
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: wgpu::TextureFormat::Depth32Float,
        usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
        view_formats: &[],
    });
    let view = color.create_view(&Default::default());
    let depth_view = depth.create_view(&Default::default());
    let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
        label: Some("External caller encoder"),
    });
    {
        let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("External caller pass"),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: &view,
                depth_slice: None,
                resolve_target: None,
                ops: wgpu::Operations {
                    load: wgpu::LoadOp::Clear(wgpu::Color {
                        r: 0.0,
                        g: 0.0,
                        b: 0.0,
                        a: 1.0,
                    }),
                    store: wgpu::StoreOp::Store,
                },
            })],
            depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                view: &depth_view,
                depth_ops: Some(wgpu::Operations {
                    load: wgpu::LoadOp::Clear(1.0),
                    store: wgpu::StoreOp::Store,
                }),
                stencil_ops: None,
            }),
            occlusion_query_set: None,
            timestamp_writes: None,
        });
        renderer.draw(&model, &mut pass)?;
    }
    let buffer = device.create_buffer(&wgpu::BufferDescriptor {
        label: Some("External caller readback"),
        size: 128 * 128 * 4,
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    encoder.copy_texture_to_buffer(
        color.as_image_copy(),
        wgpu::TexelCopyBufferInfo {
            buffer: &buffer,
            layout: wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(512),
                rows_per_image: Some(128),
            },
        },
        size,
    );
    queue.submit([encoder.finish()]);
    let (send, recv) = std::sync::mpsc::sync_channel(1);
    buffer.slice(..).map_async(wgpu::MapMode::Read, move |r| {
        let _ = send.send(r);
    });
    device.poll(wgpu::PollType::Wait)?;
    recv.recv()??;
    let rgba = buffer.slice(..).get_mapped_range().to_vec();
    buffer.unmap();
    let validation = device.pop_error_scope().await;
    let mut file = std::fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(output)?;
    file.write_all(&rgba)?;
    file.sync_all()?;
    let mut probes = Vec::new();
    let mut ok = validation.is_none();
    for (i, p) in cpu.iter().enumerate() {
        let offset = ((p.xy[1] * 128 + p.xy[0]) * 4) as usize;
        let actual: &[u8] = &rgba[offset..offset + 4];
        let cpu_diff: Vec<_> = actual
            .iter()
            .zip(p.rgba8)
            .map(|(a, b)| a.abs_diff(b))
            .collect();
        let golden_diff: Vec<_> = actual
            .iter()
            .zip(goldens[i])
            .map(|(a, b)| a.abs_diff(b))
            .collect();
        let pass = cpu_diff.iter().chain(&golden_diff).all(|d| *d <= 1);
        ok &= pass;
        probes.push(json!({"xy":p.xy,"RGBA8":actual,"CPU_RGBA8":p.rgba8,"golden_RGBA8":goldens[i],"CPU_channel_difference":cpu_diff,"golden_channel_difference":golden_diff,"ok":pass}));
    }
    Ok(
        json!({"ok":ok,"backend":format!("{:?}",info.backend),"adapter":info.name,"device_type":format!("{:?}",info.device_type),"format":"Rgba8UnormSrgb","shader_sha256":formora::model_package::sha256(formora::material_renderer::SHADER.as_bytes()),"protocol_sha256":formora::model_package::sha256(formora::material_project::render_data::PROTOCOL.as_bytes()),"raw_RGBA_file":output,"raw_RGBA_sha256":formora::model_package::sha256(&rgba),"gpu_wait_completed":true,"wgpu_validation_error":validation.map(|e|e.to_string()),"probes":probes,"PBR_or_App_acceptance":false}),
    )
}
