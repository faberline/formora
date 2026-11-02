use super::buffers::{Draw, VertexBuffers};
use super::math::{self, Vertex};
use crate::scene::{Result, Scene, SceneError};
use crate::scene_store::SceneStore;
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::Instant;
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

enum SceneInput<'a> {
    Live(&'a Scene),
    Store(&'a SceneStore),
}

#[derive(Clone, Default)]
struct Prepared {
    geometry: math::GeometryCache,
    vertex: Option<Arc<VertexBuffers>>,
}

/// Immutable GPU snapshot, tied to the Renderer that prepared it.
/// Prepare again after geometry, material, annotation or lighting changes.
pub struct PreparedScene {
    owner: Arc<()>,
    vertex: Arc<VertexBuffers>,
    count: u32,
    lights: wgpu::Buffer,
    light_count: u32,
    camera: math::Camera,
    cache: Arc<Prepared>,
    ranges: math::DrawRanges,
    world: BTreeMap<String, glam::DMat4>,
}

impl PreparedScene {
    /// The camera at prepare time and at that renderer size.
    pub fn camera(&self) -> &math::Camera {
        &self.camera
    }
    /// The exact validated prepare-time world transform. It does not read live data.
    pub fn world_transform(&self, id: &str) -> Option<glam::DMat4> {
        self.world.get(id).copied()
    }

    /// Number of immutable GPU vertex buffers. All corners are retained across them.
    pub fn vertex_buffer_count(&self) -> usize {
        self.vertex.buffer_count()
    }

    pub fn vertex_count(&self) -> u32 {
        self.count
    }
}

/// Immutable shared lighting, tied to the renderer that prepared it.
pub struct PreparedLighting {
    owner: Arc<()>,
    lights: wgpu::Buffer,
    count: u32,
}

/// A submitted present request is not proof of physical display.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DrawOutcome {
    Submitted,
    Skipped,
}

/// Raw GPU render-pass ticks and their conversion. Excludes CPU preparation and readback.
#[derive(Clone, Copy, Debug)]
pub struct GpuPassTiming {
    pub start_tick: u64,
    pub end_tick: u64,
    pub timestamp_period_ns: f32,
    pub render_ms: f64,
    /// Blocking map/poll/readback wall time. Include this in complete frame accounting.
    pub cpu_readback_seconds: f64,
}

/// Skipped surface frames never contain a GPU timing sample.
#[derive(Clone, Copy, Debug)]
pub struct ProfiledFrame {
    pub outcome: DrawOutcome,
    pub gpu: Option<GpuPassTiming>,
}

struct PassQuery {
    set: wgpu::QuerySet,
    resolve: wgpu::Buffer,
    readback: wgpu::Buffer,
}

/// Basic GPU preview owned by an external host or the standalone tool.
///
/// The host owns the window, event loop and scene. No [`crate::session::Session`]
/// or scene revision change is required. Enable the `preview` feature.
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
    prepared: Mutex<Prepared>,
    owner: Arc<()>,
    profiled: bool,
    vertex_buffer_chunk_limit: u64,
    pub width: u32,
    pub height: u32,
    pub adapter: String,
}

fn error(e: impl std::fmt::Display) -> SceneError {
    SceneError(e.to_string())
}

impl Renderer {
    /// Creates a window surface, or an offscreen renderer when `window` is `None`.
    /// Dimensions are physical pixels and must be nonzero. GPU setup can fail.
    pub async fn new(window: Option<Arc<Window>>, width: u32, height: u32) -> Result<Self> {
        Self::create(window, width, height, false).await
    }

    /// Opt-in blocking GPU pass profiling. Fails if timestamp queries are unsupported.
    /// Normal `new` does not request this optional device feature.
    pub async fn new_profiled(
        window: Option<Arc<Window>>,
        width: u32,
        height: u32,
    ) -> Result<Self> {
        Self::create(window, width, height, true).await
    }

    async fn create(
        window: Option<Arc<Window>>,
        width: u32,
        height: u32,
        profiled: bool,
    ) -> Result<Self> {
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
        let features = if profiled {
            wgpu::Features::TIMESTAMP_QUERY
        } else {
            wgpu::Features::empty()
        };
        if !adapter.features().contains(features) {
            return Err(error("adapter does not support GPU timestamp queries"));
        }
        let (device, queue) = adapter
            .request_device(&wgpu::DeviceDescriptor {
                label: Some("Formora preview"),
                required_features: features,
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
        let vertex_buffer_chunk_limit = device.limits().max_buffer_size;
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
            prepared: Mutex::default(),
            owner: Arc::new(()),
            profiled,
            vertex_buffer_chunk_limit,
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

    /// Reconfigures the surface and depth buffer. A zero dimension is ignored.
    /// Call this with the window's physical size after a resize event.
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

    /// Fully validates current data and prepares an immutable snapshot, irrespective of revision.
    /// Record this cost separately and include it in a frame that needs to update geometry.
    pub fn prepare(&self, scene: &Scene) -> Result<PreparedScene> {
        let mut prepared = self
            .prepared
            .lock()
            .map_err(|_| error("renderer preparation cache is poisoned"))?;
        self.prepare_cached(SceneInput::Live(scene), &mut prepared)
    }

    /// Branches the previous snapshot's CPU cache. Other preparations cannot evict it.
    /// Fully validates current Scene values. The base and all older branches stay immutable.
    pub fn prepare_from(&self, previous: &PreparedScene, scene: &Scene) -> Result<PreparedScene> {
        if !Arc::ptr_eq(&self.owner, &previous.owner) {
            return Err(error("prepared scene belongs to another renderer"));
        }
        let mut prepared = previous.cache.as_ref().clone();
        self.prepare_cached(SceneInput::Live(scene), &mut prepared)
    }

    /// Prepare a validated core-owned scene. Raw Scene APIs remain value-checked.
    pub fn prepare_store(&self, store: &SceneStore) -> Result<PreparedScene> {
        let mut prepared = self
            .prepared
            .lock()
            .map_err(|_| error("preview cache lock poisoned"))?;
        self.prepare_cached(SceneInput::Store(store), &mut prepared)
    }

    /// Branch from an immutable snapshot using core-owned input stamps.
    pub fn prepare_store_from(
        &self,
        previous: &PreparedScene,
        store: &SceneStore,
    ) -> Result<PreparedScene> {
        if !Arc::ptr_eq(&self.owner, &previous.owner) {
            return Err(error("prepared scene belongs to another renderer"));
        }
        let mut prepared = previous.cache.as_ref().clone();
        self.prepare_cached(SceneInput::Store(store), &mut prepared)
    }

    fn prepare_cached(
        &self,
        input: SceneInput<'_>,
        prepared: &mut Prepared,
    ) -> Result<PreparedScene> {
        let (scene, (world, vertices)) = match input {
            SceneInput::Live(scene) => (scene, prepared.geometry.prepare(scene)?),
            SceneInput::Store(store) => (store.scene(), prepared.geometry.prepare_store(store)?),
        };
        let camera = math::camera_with_world(scene, self.width, self.height, &world)?;
        let lighting = self.lighting(math::lights_with_world(scene, &world))?;
        let ranges = prepared.geometry.draw_ranges()?;
        Self::validate_camera(&camera)?;
        let count = u32::try_from(vertices.len()).map_err(error)?;
        if !prepared
            .vertex
            .as_ref()
            .is_some_and(|old| old.matches(&vertices, self.vertex_buffer_chunk_limit))
        {
            prepared.vertex = Some(Arc::new(VertexBuffers::new(
                &self.device,
                Arc::clone(&vertices),
                self.vertex_buffer_chunk_limit,
            )?));
        }
        let vertex = Arc::clone(prepared.vertex.as_ref().expect("prepared vertex buffers"));
        Ok(PreparedScene {
            owner: Arc::clone(&self.owner),
            vertex,
            count,
            lights: lighting.lights,
            light_count: lighting.count,
            camera,
            cache: Arc::new(prepared.clone()),
            ranges,
            world,
        })
    }

    /// Validates only lights and their ancestors. Does not validate live mesh data.
    pub fn prepare_lighting(&self, scene: &Scene) -> Result<PreparedLighting> {
        self.lighting(math::lights_view(scene)?)
    }

    fn lighting(&self, source: Vec<math::WorldLight>) -> Result<PreparedLighting> {
        let mut lights = Vec::with_capacity(source.len().max(1));
        for light in source {
            let p = light.position.as_vec3();
            let color = [
                light.color[0] as f32,
                light.color[1] as f32,
                light.color[2] as f32,
                (light.intensity / 100.0) as f32,
            ];
            if !p.is_finite() || !color.iter().all(|n| n.is_finite()) {
                return Err(error("light exceeds preview range"));
            }
            lights.push(Light {
                position: [p.x, p.y, p.z, 1.0],
                color,
            });
        }
        let count = u32::try_from(lights.len()).map_err(error)?;
        if lights.is_empty() {
            lights.push(Light::zeroed());
        }
        let lights = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("Scene lights"),
                contents: bytemuck::cast_slice(&lights),
                usage: wgpu::BufferUsages::STORAGE,
            });
        Ok(PreparedLighting {
            owner: Arc::clone(&self.owner),
            lights,
            count,
        })
    }

    /// Current byte limit for each new vertex upload chunk.
    pub fn vertex_buffer_chunk_limit(&self) -> u64 {
        self.vertex_buffer_chunk_limit
    }

    /// Optional allocation-only debug policy. None restores the actual device limit.
    /// Existing immutable snapshots remain valid. New uploads use complete triangles.
    pub fn set_vertex_buffer_chunk_limit(&mut self, bytes: Option<u64>) -> Result<()> {
        let limit = bytes.unwrap_or(self.device.limits().max_buffer_size);
        if limit > self.device.limits().max_buffer_size {
            return Err(error("vertex buffer chunk limit exceeds device maximum"));
        }
        super::buffers::triangle_ranges(0, limit)?;
        self.vertex_buffer_chunk_limit = limit;
        Ok(())
    }

    fn validate_camera(camera: &math::Camera) -> Result<()> {
        if !camera.position.is_finite()
            || !camera.position.as_vec3().is_finite()
            || !camera.view_projection.is_finite()
            || !camera.view_projection.as_mat4().is_finite()
        {
            return Err(error("camera exceeds preview range"));
        }
        Ok(())
    }

    fn validate_snapshot(&self, snapshot: &PreparedScene, camera: &math::Camera) -> Result<()> {
        if !Arc::ptr_eq(&self.owner, &snapshot.owner) {
            return Err(error("prepared scene belongs to another renderer"));
        }
        Self::validate_camera(camera)
    }

    fn encode(&self, scene: &Scene, view: &wgpu::TextureView) -> Result<wgpu::CommandEncoder> {
        let snapshot = self.prepare(scene)?;
        self.encode_prepared(&snapshot, snapshot.camera(), view)
    }

    fn encode_prepared(
        &self,
        snapshot: &PreparedScene,
        camera: &math::Camera,
        view: &wgpu::TextureView,
    ) -> Result<wgpu::CommandEncoder> {
        self.validate_snapshot(snapshot, camera)?;
        self.encode_draws(
            &snapshot.vertex.draws(0..snapshot.count)?,
            camera,
            &snapshot.lights,
            snapshot.light_count,
            view,
            None,
        )
    }

    fn encode_draws(
        &self,
        draws: &[Draw<'_>],
        camera: &math::Camera,
        lights: &wgpu::Buffer,
        light_count: u32,
        view: &wgpu::TextureView,
        query: Option<&PassQuery>,
    ) -> Result<wgpu::CommandEncoder> {
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
                    resource: lights.as_entire_binding(),
                },
            ],
        });
        let eye = camera.position.as_vec3();
        let uniform = Uniform {
            view_projection: camera.view_projection.as_mat4().to_cols_array_2d(),
            eye: [eye.x, eye.y, eye.z, 1.0],
            light_meta: [light_count, 0, 0, 0],
        };
        self.queue
            .write_buffer(&self.uniform, 0, bytemuck::bytes_of(&uniform));
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
                timestamp_writes: query.map(|q| wgpu::RenderPassTimestampWrites {
                    query_set: &q.set,
                    beginning_of_pass_write_index: Some(0),
                    end_of_pass_write_index: Some(1),
                }),
                occlusion_query_set: None,
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            for draw in draws {
                pass.set_vertex_buffer(0, draw.vertex.slice(..));
                pass.draw(draw.range.clone(), 0..1);
            }
        }
        if let Some(q) = query {
            encoder.resolve_query_set(&q.set, 0..2, &q.resolve, 0);
            encoder.copy_buffer_to_buffer(&q.resolve, 0, &q.readback, 0, 16);
        }
        Ok(encoder)
    }

    /// Renders the supplied scene to the window. Fails without a window surface.
    /// A recoverable surface error can skip a frame while returning `Ok(())`.
    pub fn draw(&mut self, scene: &Scene) -> Result<()> {
        self.present(|view| self.encode(scene, view)).map(|_| ())
    }

    /// Draws immutable prepared data with a current camera. Does not read a live Scene.
    pub fn draw_prepared(&mut self, snapshot: &PreparedScene, camera: &math::Camera) -> Result<()> {
        self.validate_snapshot(snapshot, camera)?;
        self.present(|view| self.encode_prepared(snapshot, camera, view))
            .map(|_| ())
    }

    fn layer_draws<'a>(
        &self,
        layers: &[&'a PreparedScene],
        camera: &math::Camera,
        lighting: &PreparedLighting,
    ) -> Result<Vec<Draw<'a>>> {
        Self::validate_camera(camera)?;
        if !Arc::ptr_eq(&self.owner, &lighting.owner) {
            return Err(error("prepared lighting belongs to another renderer"));
        }
        for layer in layers {
            self.validate_snapshot(layer, camera)?;
        }
        let ranges: Vec<_> = layers.iter().map(|l| &l.ranges).collect();
        let mut draws = Vec::new();
        for (index, range) in math::ordered_ranges(&ranges)? {
            layers[index].vertex.append_draws(range, &mut draws)?;
        }
        Ok(draws)
    }

    /// Draws all mesh IDs in global source order, then annotations in layer order.
    /// No live geometry is read. Reprepare every layer affected by source changes.
    pub fn draw_layers(
        &mut self,
        layers: &[&PreparedScene],
        camera: &math::Camera,
        lighting: &PreparedLighting,
    ) -> Result<DrawOutcome> {
        let draws = self.layer_draws(layers, camera, lighting)?;
        self.present(|view| {
            self.encode_draws(&draws, camera, &lighting.lights, lighting.count, view, None)
        })
    }

    /// Captures the same ordered layers with current shared lights. Replaces output on success.
    pub fn capture_layers(
        &self,
        layers: &[&PreparedScene],
        camera: &math::Camera,
        lighting: &PreparedLighting,
        path: &Path,
    ) -> Result<()> {
        let draws = self.layer_draws(layers, camera, lighting)?;
        self.capture_frame(path, |view| {
            self.encode_draws(&draws, camera, &lighting.lights, lighting.count, view, None)
        })
    }

    fn pass_query(&self) -> Result<PassQuery> {
        if !self.profiled {
            return Err(error("use Renderer::new_profiled for GPU pass timing"));
        }
        Ok(PassQuery {
            set: self.device.create_query_set(&wgpu::QuerySetDescriptor {
                label: Some("Preview GPU pass time"),
                ty: wgpu::QueryType::Timestamp,
                count: 2,
            }),
            resolve: self.device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("Preview timestamp resolve"),
                size: 16,
                usage: wgpu::BufferUsages::QUERY_RESOLVE | wgpu::BufferUsages::COPY_SRC,
                mapped_at_creation: false,
            }),
            readback: self.device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("Preview timestamp readback"),
                size: 16,
                usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
                mapped_at_creation: false,
            }),
        })
    }

    fn read_timing(&self, query: PassQuery) -> Result<GpuPassTiming> {
        let start = Instant::now();
        let (send, receive) = std::sync::mpsc::sync_channel(1);
        query
            .readback
            .slice(..)
            .map_async(wgpu::MapMode::Read, move |result| {
                let _ = send.send(result);
            });
        self.device.poll(wgpu::PollType::Wait).map_err(error)?;
        receive.recv().map_err(error)?.map_err(error)?;
        let data = query.readback.slice(..).get_mapped_range();
        let begin = u64::from_ne_bytes(data[..8].try_into().map_err(error)?);
        let end = u64::from_ne_bytes(data[8..16].try_into().map_err(error)?);
        drop(data);
        query.readback.unmap();
        let period = self.queue.get_timestamp_period();
        let render_ms = timing_ms(begin, end, period)?;
        Ok(GpuPassTiming {
            start_tick: begin,
            end_tick: end,
            timestamp_period_ns: period,
            render_ms,
            cpu_readback_seconds: start.elapsed().as_secs_f64(),
        })
    }

    /// Blocking diagnostic surface draw. Count its CPU/readback overhead in the full frame.
    pub fn draw_layers_profiled(
        &mut self,
        layers: &[&PreparedScene],
        camera: &math::Camera,
        lighting: &PreparedLighting,
    ) -> Result<ProfiledFrame> {
        let draws = self.layer_draws(layers, camera, lighting)?;
        let query = self.pass_query()?;
        let outcome = self.present(|view| {
            self.encode_draws(
                &draws,
                camera,
                &lighting.lights,
                lighting.count,
                view,
                Some(&query),
            )
        })?;
        let gpu = if outcome == DrawOutcome::Submitted {
            Some(self.read_timing(query)?)
        } else {
            None
        };
        Ok(ProfiledFrame { outcome, gpu })
    }

    /// Blocking offscreen diagnostic of the same pass. Does not present or write files.
    /// Its GPU time alone cannot establish full-pipeline performance or FPS.
    pub fn profile_layers(
        &self,
        layers: &[&PreparedScene],
        camera: &math::Camera,
        lighting: &PreparedLighting,
    ) -> Result<GpuPassTiming> {
        let draws = self.layer_draws(layers, camera, lighting)?;
        let query = self.pass_query()?;
        let texture = self.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Preview profiled offscreen"),
            size: wgpu::Extent3d {
                width: self.width,
                height: self.height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: self.format,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });
        let view = texture.create_view(&Default::default());
        let encoder = self.encode_draws(
            &draws,
            camera,
            &lighting.lights,
            lighting.count,
            &view,
            Some(&query),
        )?;
        self.queue.submit([encoder.finish()]);
        self.read_timing(query)
    }

    fn present(
        &self,
        encode: impl FnOnce(&wgpu::TextureView) -> Result<wgpu::CommandEncoder>,
    ) -> Result<DrawOutcome> {
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
                return Ok(DrawOutcome::Skipped);
            }
            Err(wgpu::SurfaceError::Timeout | wgpu::SurfaceError::Other) => {
                return Ok(DrawOutcome::Skipped);
            }
            Err(e) => return Err(error(e)),
        };
        let view = frame.texture.create_view(&Default::default());
        self.queue.submit([encode(&view)?.finish()]);
        frame.present();
        Ok(DrawOutcome::Submitted)
    }

    /// Renders a separate offscreen frame and writes PNG, replacing an existing file.
    /// This blocks for GPU readback. It is not a desktop screenshot or atomic save.
    pub fn capture(&self, scene: &Scene, path: &Path) -> Result<()> {
        self.capture_frame(path, |view| self.encode(scene, view))
    }

    /// Captures a new offscreen frame from the snapshot. Replaces existing output.
    pub fn capture_prepared(
        &self,
        snapshot: &PreparedScene,
        camera: &math::Camera,
        path: &Path,
    ) -> Result<()> {
        self.validate_snapshot(snapshot, camera)?;
        self.capture_frame(path, |view| self.encode_prepared(snapshot, camera, view))
    }

    fn capture_frame(
        &self,
        path: &Path,
        encode: impl FnOnce(&wgpu::TextureView) -> Result<wgpu::CommandEncoder>,
    ) -> Result<()> {
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
        let mut encoder = encode(&view)?;
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

fn timing_ms(begin: u64, end: u64, period: f32) -> Result<f64> {
    if end <= begin || !period.is_finite() || period <= 0.0 {
        return Err(error("invalid GPU pass timestamp sample"));
    }
    let milliseconds = (end - begin) as f64 * f64::from(period) / 1_000_000.0;
    if !milliseconds.is_finite() || milliseconds <= 0.0 {
        return Err(error("invalid GPU pass timestamp duration"));
    }
    Ok(milliseconds)
}

#[cfg(test)]
mod tests {
    #[test]
    fn timestamp_conversion_requires_real_positive_sample() {
        assert_eq!(super::timing_ms(100, 250, 2.0).unwrap(), 0.0003);
        for (a, b, p) in [
            (0, 0, 1.),
            (4, 3, 1.),
            (0, 1, 0.),
            (0, 1, -1.),
            (0, 1, f32::NAN),
            (0, 1, f32::INFINITY),
        ] {
            assert!(super::timing_ms(a, b, p).is_err());
        }
    }
}
