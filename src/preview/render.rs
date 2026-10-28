use super::math::{self, Vertex};
use crate::scene::{EntityKind, Result, Scene, SceneError};
use std::path::Path;
use std::sync::Arc;
use wgpu::util::DeviceExt;
use winit::window::Window;

#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
struct Uniform {
    view_projection: [[f32; 4]; 4],
    eye: [f32; 4],
    light_meta: [u32; 4],
}

#[repr(C)]
#[derive(Clone, Copy, bytemuck::Pod, bytemuck::Zeroable)]
struct Light {
    position: [f32; 4],
    color: [f32; 4],
}

pub struct Renderer {
    _instance: wgpu::Instance,
    surface: Option<wgpu::Surface<'static>>,
    config: Option<wgpu::SurfaceConfiguration>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::RenderPipeline,
    uniform: wgpu::Buffer,
    depth: wgpu::TextureView,
    format: wgpu::TextureFormat,
    pub width: u32,
    pub height: u32,
    pub adapter: String,
}

fn error(e: impl std::fmt::Display) -> SceneError {
    SceneError(e.to_string())
}

impl Renderer {
    pub async fn new(window: Option<Arc<Window>>, width: u32, height: u32) -> Result<Self> {
        if width == 0 || height == 0 {
            return Err(error("render size must be nonzero"));
        }
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends: wgpu::Backends::PRIMARY,
            ..Default::default()
        });
        let surface = window
            .map(|window| instance.create_surface(window))
            .transpose()
            .map_err(error)?;
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                force_fallback_adapter: false,
                compatible_surface: surface.as_ref(),
            })
            .await
            .map_err(error)?;
        let info = adapter.get_info();
        let adapter_name = format!("{} ({:?}, {:?})", info.name, info.backend, info.device_type);
        let (device, queue) = adapter
            .request_device(&wgpu::DeviceDescriptor {
                label: Some("Formora preview"),
                required_features: wgpu::Features::empty(),
                required_limits: wgpu::Limits::default(),
                memory_hints: wgpu::MemoryHints::Performance,
                trace: wgpu::Trace::Off,
            })
            .await
            .map_err(error)?;
        let config = surface.as_ref().map(|surface| {
            let capabilities = surface.get_capabilities(&adapter);
            let format = capabilities
                .formats
                .iter()
                .copied()
                .find(wgpu::TextureFormat::is_srgb)
                .unwrap_or(capabilities.formats[0]);
            wgpu::SurfaceConfiguration {
                usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
                format,
                width,
                height,
                present_mode: wgpu::PresentMode::AutoVsync,
                desired_maximum_frame_latency: 2,
                alpha_mode: capabilities.alpha_modes[0],
                view_formats: vec![],
            }
        });
        if let (Some(surface), Some(config)) = (&surface, &config) {
            surface.configure(&device, config);
        }
        let format = config
            .as_ref()
            .map_or(wgpu::TextureFormat::Rgba8UnormSrgb, |c| c.format);
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Formora basic material"),
            source: wgpu::ShaderSource::Wgsl(include_str!("shader.wgsl").into()),
        });
        let uniform = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("Preview camera"),
            size: std::mem::size_of::<Uniform>() as u64,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        let pipeline=device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label:Some("Formora scene"),layout:None,
            vertex:wgpu::VertexState {module:&shader,entry_point:Some("vs"),compilation_options:Default::default(),buffers:&[wgpu::VertexBufferLayout {array_stride:std::mem::size_of::<Vertex>() as u64,step_mode:wgpu::VertexStepMode::Vertex,attributes:&wgpu::vertex_attr_array![0=>Float32x3,1=>Float32x3,2=>Float32x4,3=>Float32x2]}]},
            primitive:wgpu::PrimitiveState {cull_mode:None,..Default::default()},
            depth_stencil:Some(wgpu::DepthStencilState {format:wgpu::TextureFormat::Depth32Float,depth_write_enabled:true,depth_compare:wgpu::CompareFunction::Less,stencil:Default::default(),bias:Default::default()}),
            multisample:Default::default(),
            fragment:Some(wgpu::FragmentState {module:&shader,entry_point:Some("fs"),compilation_options:Default::default(),targets:&[Some(wgpu::ColorTargetState {format,blend:Some(wgpu::BlendState::ALPHA_BLENDING),write_mask:wgpu::ColorWrites::ALL})]}),
            multiview:None,cache:None,
        });
        let depth = Self::depth(&device, width, height);
        Ok(Self {
            _instance: instance,
            surface,
            config,
            device,
            queue,
            pipeline,
            uniform,
            depth,
            format,
            width,
            height,
            adapter: adapter_name,
        })
    }

    fn depth(device: &wgpu::Device, width: u32, height: u32) -> wgpu::TextureView {
        device
            .create_texture(&wgpu::TextureDescriptor {
                label: Some("Preview depth"),
                size: wgpu::Extent3d {
                    width,
                    height,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::Depth32Float,
                usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
                view_formats: &[],
            })
            .create_view(&Default::default())
    }

    pub fn resize(&mut self, width: u32, height: u32) {
        if width == 0 || height == 0 {
            return;
        }
        self.width = width;
        self.height = height;
        self.depth = Self::depth(&self.device, width, height);
        if let (Some(surface), Some(config)) = (&self.surface, &mut self.config) {
            config.width = width;
            config.height = height;
            surface.configure(&self.device, config);
        }
    }

    fn encode(&self, scene: &Scene, view: &wgpu::TextureView) -> Result<wgpu::CommandEncoder> {
        let camera = math::camera(scene, self.width, self.height)?;
        let world = math::world_transforms(scene)?;
        let mut lights = Vec::new();
        for (id, entity) in &scene.entities {
            if let EntityKind::Light { color, intensity } = &entity.content {
                let p = world[id].transform_point3(glam::DVec3::ZERO).as_vec3();
                if !p.is_finite() {
                    return Err(error("light exceeds preview range"));
                }
                let light_color = [
                    color[0] as f32,
                    color[1] as f32,
                    color[2] as f32,
                    (*intensity / 100.0) as f32,
                ];
                if !light_color.iter().all(|n| n.is_finite()) {
                    return Err(error("light exceeds preview range"));
                }
                lights.push(Light {
                    position: [p.x, p.y, p.z, 1.0],
                    color: light_color,
                });
            }
        }
        let light_count = u32::try_from(lights.len()).map_err(error)?;
        if lights.is_empty() {
            lights.push(Light::zeroed());
        }
        let light_buffer = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("Scene lights"),
                contents: bytemuck::cast_slice(&lights),
                usage: wgpu::BufferUsages::STORAGE,
            });
        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("Preview bindings"),
            layout: &self.pipeline.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: self.uniform.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: light_buffer.as_entire_binding(),
                },
            ],
        });
        let eye = camera.position.as_vec3();
        if !eye.is_finite() {
            return Err(error("camera exceeds preview range"));
        }
        let uniform = Uniform {
            view_projection: camera.view_projection.as_mat4().to_cols_array_2d(),
            eye: [eye.x, eye.y, eye.z, 1.0],
            light_meta: [light_count, 0, 0, 0],
        };
        self.queue
            .write_buffer(&self.uniform, 0, bytemuck::bytes_of(&uniform));
        let vertices = math::vertices(scene)?;
        let count = u32::try_from(vertices.len()).map_err(error)?;
        let dummy = Vertex::zeroed();
        let bytes = if vertices.is_empty() {
            bytemuck::bytes_of(&dummy)
        } else {
            bytemuck::cast_slice(&vertices)
        };
        let buffer = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("Scene triangles"),
                contents: bytes,
                usage: wgpu::BufferUsages::VERTEX,
            });
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("Scene preview"),
            });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("Scene preview"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.025,
                            g: 0.035,
                            b: 0.055,
                            a: 1.0,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                    view: &self.depth,
                    depth_ops: Some(wgpu::Operations {
                        load: wgpu::LoadOp::Clear(1.0),
                        store: wgpu::StoreOp::Store,
                    }),
                    stencil_ops: None,
                }),
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            pass.set_vertex_buffer(0, buffer.slice(..));
            pass.draw(0..count, 0..1);
        }
        Ok(encoder)
    }

    pub fn draw(&mut self, scene: &Scene) -> Result<()> {
        let Some(surface) = &self.surface else {
            return Err(error("renderer has no window"));
        };
        let frame = match surface.get_current_texture() {
            Ok(frame) => frame,
            Err(wgpu::SurfaceError::Lost | wgpu::SurfaceError::Outdated) => {
                surface.configure(
                    &self.device,
                    self.config.as_ref().expect("window configuration"),
                );
                return Ok(());
            }
            Err(wgpu::SurfaceError::Timeout | wgpu::SurfaceError::Other) => return Ok(()),
            Err(e) => return Err(error(e)),
        };
        let view = frame.texture.create_view(&Default::default());
        self.queue.submit([self.encode(scene, &view)?.finish()]);
        frame.present();
        Ok(())
    }

    pub fn capture(&self, scene: &Scene, path: &Path) -> Result<()> {
        let texture = self.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Scene capture"),
            size: wgpu::Extent3d {
                width: self.width,
                height: self.height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: self.format,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
            view_formats: &[],
        });
        let view = texture.create_view(&Default::default());
        let mut encoder = self.encode(scene, &view)?;
        let row = (self.width * 4).div_ceil(256) * 256;
        let buffer = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("Capture readback"),
            size: row as u64 * self.height as u64,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        encoder.copy_texture_to_buffer(
            texture.as_image_copy(),
            wgpu::TexelCopyBufferInfo {
                buffer: &buffer,
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(row),
                    rows_per_image: Some(self.height),
                },
            },
            wgpu::Extent3d {
                width: self.width,
                height: self.height,
                depth_or_array_layers: 1,
            },
        );
        self.queue.submit([encoder.finish()]);
        let (send, receive) = std::sync::mpsc::sync_channel(1);
        buffer
            .slice(..)
            .map_async(wgpu::MapMode::Read, move |result| {
                let _ = send.send(result);
            });
        self.device.poll(wgpu::PollType::Wait).map_err(error)?;
        receive.recv().map_err(error)?.map_err(error)?;
        let data = buffer.slice(..).get_mapped_range();
        let mut rgba = Vec::with_capacity((self.width * self.height * 4) as usize);
        for line in data.chunks(row as usize) {
            rgba.extend_from_slice(&line[..self.width as usize * 4]);
        }
        if matches!(
            self.format,
            wgpu::TextureFormat::Bgra8Unorm | wgpu::TextureFormat::Bgra8UnormSrgb
        ) {
            for pixel in rgba.chunks_exact_mut(4) {
                pixel.swap(0, 2);
            }
        }
        let file = std::fs::File::create(path).map_err(error)?;
        let mut encoder = png::Encoder::new(std::io::BufWriter::new(file), self.width, self.height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().map_err(error)?;
        writer.write_image_data(&rgba).map_err(error)?;
        writer.finish().map_err(error)?;
        drop(data);
        buffer.unmap();
        Ok(())
    }
}

pub fn render_png(scene: &Scene, path: &Path, width: u32, height: u32) -> Result<String> {
    let renderer = pollster::block_on(Renderer::new(None, width, height))?;
    renderer.capture(scene, path)?;
    Ok(renderer.adapter)
}

use bytemuck::Zeroable;
