//! Caller-owned wgpu rendering. No adapter, window, filesystem or event loop.
use crate::material_project::render_data::{
    Frame, RenderError, RenderIdentity, RenderScene, Vertex,
};
use std::{
    collections::BTreeMap,
    sync::atomic::{AtomicU64, Ordering},
};
pub use wgpu;
use wgpu::util::DeviceExt;

pub const SHADER: &str = include_str!("shader.wgsl");
static NEXT_RENDERER: AtomicU64 = AtomicU64::new(1);

pub struct Renderer {
    id: u64,
    device: wgpu::Device,
    pipeline: wgpu::RenderPipeline,
    frame_layout: wgpu::BindGroupLayout,
    material_layout: wgpu::BindGroupLayout,
    target_format: wgpu::TextureFormat,
}
struct GpuBatch {
    vertices: wgpu::Buffer,
    count: u32,
    material: wgpu::BindGroup,
    _factor: wgpu::Buffer,
}
pub struct GpuScene {
    renderer_id: u64,
    queue: wgpu::Queue,
    frame: wgpu::Buffer,
    frame_group: wgpu::BindGroup,
    batches: Vec<GpuBatch>,
    _images: Vec<wgpu::Texture>,
    identity: RenderIdentity,
}
impl GpuScene {
    pub fn identity(&self) -> &RenderIdentity {
        &self.identity
    }
    /// Update this instance's GPU frame only. Allocate another GpuScene for another instance.
    pub fn set_frame(&mut self, queue: &wgpu::Queue, frame: &Frame) -> Result<(), RenderError> {
        frame.validate()?;
        if queue != &self.queue {
            return Err(RenderError::new(
                "wrong_queue",
                "Use the queue supplied at upload",
            ));
        }
        queue.write_buffer(&self.frame, 0, bytemuck::bytes_of(frame));
        Ok(())
    }
}

impl Renderer {
    pub fn new(
        device: &wgpu::Device,
        target_format: wgpu::TextureFormat,
    ) -> Result<Self, RenderError> {
        if !matches!(
            target_format,
            wgpu::TextureFormat::Rgba8UnormSrgb | wgpu::TextureFormat::Bgra8UnormSrgb
        ) {
            return Err(RenderError::new(
                "unsupported_target",
                "This profile requires an RGBA8/BGRA8 sRGB target",
            ));
        }
        let frame_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("Formora material frame"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: wgpu::BufferSize::new(std::mem::size_of::<Frame>() as u64),
                },
                count: None,
            }],
        });
        let material_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("Formora image material"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 2,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: wgpu::BufferSize::new(16),
                    },
                    count: None,
                },
            ],
        });
        let layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("Formora material pipeline layout"),
            bind_group_layouts: &[&frame_layout, &material_layout],
            push_constant_ranges: &[],
        });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Formora unlit image"),
            source: wgpu::ShaderSource::Wgsl(SHADER.into()),
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("Formora unlit image"),
            layout: Some(&layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs"),
                compilation_options: Default::default(),
                buffers: &[wgpu::VertexBufferLayout {
                    array_stride: std::mem::size_of::<Vertex>() as u64,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &wgpu::vertex_attr_array![0=>Float32x3,1=>Float32x2],
                }],
            },
            primitive: wgpu::PrimitiveState {
                cull_mode: None,
                ..Default::default()
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth32Float,
                depth_write_enabled: true,
                depth_compare: wgpu::CompareFunction::Less,
                stencil: Default::default(),
                bias: Default::default(),
            }),
            multisample: Default::default(),
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format: target_format,
                    blend: None,
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            multiview: None,
            cache: None,
        });
        Ok(Self {
            id: NEXT_RENDERER.fetch_add(1, Ordering::Relaxed),
            device: device.clone(),
            pipeline,
            frame_layout,
            material_layout,
            target_format,
        })
    }
    pub fn target_format(&self) -> wgpu::TextureFormat {
        self.target_format
    }

    pub fn upload(
        &self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        scene: &RenderScene<'_>,
    ) -> Result<GpuScene, RenderError> {
        if device != &self.device {
            return Err(RenderError::new(
                "wrong_device",
                "Upload must use the renderer's caller device",
            ));
        }
        let limits = device.limits();
        // Validate all ranges before creating any image/buffer for this upload.
        for image in scene.project.decoded.values() {
            if image.width > limits.max_texture_dimension_2d
                || image.height > limits.max_texture_dimension_2d
                || image.width.checked_mul(4).is_none()
            {
                return Err(RenderError::new(
                    "gpu_limits",
                    "Image exceeds caller device limits",
                ));
            }
        }
        for batch in &scene.batches {
            let bytes = batch
                .vertices
                .len()
                .checked_mul(std::mem::size_of::<Vertex>())
                .ok_or_else(|| RenderError::new("gpu_limits", "Vertex byte count overflow"))?;
            if bytes as u64 > limits.max_buffer_size || u32::try_from(batch.vertices.len()).is_err()
            {
                return Err(RenderError::new(
                    "gpu_limits",
                    "Vertex buffer exceeds caller device limits",
                ));
            }
        }
        let mut images = Vec::new();
        let mut views = BTreeMap::new();
        for (id, image) in &scene.project.decoded {
            let rgba: Vec<u8> = image
                .pixels
                .chunks_exact(3)
                .flat_map(|c| [c[0], c[1], c[2], 255])
                .collect();
            let texture = upload_image(device, queue, image.width, image.height, &rgba);
            views.insert(Some(id.clone()), texture.create_view(&Default::default()));
            images.push(texture);
        }
        // An untextured native material uses identity white, not a missing-file fallback.
        let white = upload_image(device, queue, 1, 1, &[255; 4]);
        views.insert(None, white.create_view(&Default::default()));
        images.push(white);
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("Formora nearest clamp"),
            address_mode_u: wgpu::AddressMode::ClampToEdge,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            address_mode_w: wgpu::AddressMode::ClampToEdge,
            mag_filter: wgpu::FilterMode::Nearest,
            min_filter: wgpu::FilterMode::Nearest,
            mipmap_filter: wgpu::FilterMode::Nearest,
            ..Default::default()
        });
        let frame = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Formora instance frame"),
            contents: bytemuck::bytes_of(&Frame::default()),
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });
        let frame_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("Formora instance frame"),
            layout: &self.frame_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: frame.as_entire_binding(),
            }],
        });
        let mut batches = Vec::new();
        for batch in &scene.batches {
            let vertices = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("Formora per-corner vertices"),
                contents: bytemuck::cast_slice(&batch.vertices),
                usage: wgpu::BufferUsages::VERTEX,
            });
            let factor = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("Formora linear native material factor"),
                contents: bytemuck::cast_slice(&batch.factor),
                usage: wgpu::BufferUsages::UNIFORM,
            });
            let material = device.create_bind_group(&wgpu::BindGroupDescriptor {
                label: Some("Formora image material"),
                layout: &self.material_layout,
                entries: &[
                    wgpu::BindGroupEntry {
                        binding: 0,
                        resource: wgpu::BindingResource::TextureView(&views[&batch.image]),
                    },
                    wgpu::BindGroupEntry {
                        binding: 1,
                        resource: wgpu::BindingResource::Sampler(&sampler),
                    },
                    wgpu::BindGroupEntry {
                        binding: 2,
                        resource: factor.as_entire_binding(),
                    },
                ],
            });
            batches.push(GpuBatch {
                vertices,
                count: batch.vertices.len() as u32,
                material,
                _factor: factor,
            });
        }
        Ok(GpuScene {
            renderer_id: self.id,
            queue: queue.clone(),
            frame,
            frame_group,
            batches,
            _images: images,
            identity: scene.identity(),
        })
    }
    /// Caller configures matching color/depth attachments, viewport and submission.
    pub fn draw(
        &self,
        scene: &GpuScene,
        pass: &mut wgpu::RenderPass<'_>,
    ) -> Result<(), RenderError> {
        if scene.renderer_id != self.id {
            return Err(RenderError::new(
                "wrong_renderer",
                "Use the renderer that uploaded this scene",
            ));
        }
        pass.set_pipeline(&self.pipeline);
        pass.set_bind_group(0, &scene.frame_group, &[]);
        for batch in &scene.batches {
            pass.set_bind_group(1, &batch.material, &[]);
            pass.set_vertex_buffer(0, batch.vertices.slice(..));
            pass.draw(0..batch.count, 0..1);
        }
        Ok(())
    }
}
fn upload_image(
    device: &wgpu::Device,
    queue: &wgpu::Queue,
    width: u32,
    height: u32,
    rgba: &[u8],
) -> wgpu::Texture {
    let size = wgpu::Extent3d {
        width,
        height,
        depth_or_array_layers: 1,
    };
    let image = device.create_texture(&wgpu::TextureDescriptor {
        label: Some("Formora checked sRGB image"),
        size,
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: wgpu::TextureFormat::Rgba8UnormSrgb,
        usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
        view_formats: &[],
    });
    queue.write_texture(
        wgpu::TexelCopyTextureInfo {
            texture: &image,
            mip_level: 0,
            origin: wgpu::Origin3d::ZERO,
            aspect: wgpu::TextureAspect::All,
        },
        rgba,
        wgpu::TexelCopyBufferLayout {
            offset: 0,
            bytes_per_row: Some(width * 4),
            rows_per_image: Some(height),
        },
        size,
    );
    image
}

#[cfg(test)]
mod tests;
