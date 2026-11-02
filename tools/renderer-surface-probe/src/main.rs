//! Frozen-input GPU timing control. Local root builds it but never executes GPU work.
use formora::{
    geometry,
    preview::{DrawOutcome, Renderer},
    scene::{EntityKind, Scene},
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    error::Error,
    fs,
    io::BufReader,
    path::{Path, PathBuf},
    sync::Arc,
    time::{Instant, SystemTime, UNIX_EPOCH},
};
use winit::{
    application::ApplicationHandler,
    dpi::PhysicalSize,
    event::WindowEvent,
    event_loop::{ActiveEventLoop, ControlFlow, EventLoop},
    window::{Window, WindowId},
};
type Result<T> = std::result::Result<T, Box<dyn Error>>;
const ENGINE: &str = "d25a2a7ed7c16fa8d61f70e9c2f65926e962303d";
const WARMUPS: usize = 5;
const PAIRS: usize = 8;

struct Args {
    scene: PathBuf,
    output: PathBuf,
    width: u32,
    height: u32,
    active: bool,
    prefixes: Vec<String>,
}
impl Args {
    fn parse(values: Vec<String>) -> Result<Self> {
        if values.len() < 4 {
            return Err("usage: SCENE OUTPUT WIDTH HEIGHT [--active true|false] [--dynamic-prefix PREFIX,...]".into());
        }
        let width: u32 = values[2].parse()?;
        let height: u32 = values[3].parse()?;
        if width == 0
            || height == 0
            || width > 8192
            || height > 8192
            || u64::from(width) * u64::from(height) > 16_777_216
        {
            return Err("physical dimensions exceed diagnostic bounds".into());
        }
        let mut result = Self {
            scene: (&values[0]).into(),
            output: (&values[1]).into(),
            width,
            height,
            active: false,
            prefixes: Vec::new(),
        };
        let mut active_seen = false;
        let mut prefix_seen = false;
        for pair in values[4..].chunks(2) {
            if pair.len() != 2 {
                return Err("option requires a value".into());
            }
            match pair[0].as_str() {
                "--active" if !active_seen => {
                    result.active = pair[1].parse()?;
                    active_seen = true;
                }
                "--dynamic-prefix" if !prefix_seen => {
                    result.prefixes = pair[1].split(',').map(str::to_owned).collect();
                    if result.prefixes.iter().any(String::is_empty) {
                        return Err("empty dynamic prefix".into());
                    }
                    prefix_seen = true;
                }
                _ => return Err("unknown or repeated option".into()),
            }
        }
        Ok(result)
    }
}
fn hash(data: &[u8]) -> String {
    format!("{:x}", Sha256::digest(data))
}
fn rgba(path: &Path) -> Result<(u32, u32, Vec<u8>)> {
    let mut reader = png::Decoder::new(BufReader::new(fs::File::open(path)?)).read_info()?;
    let mut bytes = vec![0; reader.output_buffer_size().ok_or("PNG size")?];
    let info = reader.next_frame(&mut bytes)?;
    if info.color_type != png::ColorType::Rgba || info.bit_depth != png::BitDepth::Eight {
        return Err("expected RGBA8 PNG".into());
    }
    bytes.truncate(info.buffer_size());
    Ok((info.width, info.height, bytes))
}
fn partition(scene: &Scene, prefixes: &[String]) -> Result<Vec<Scene>> {
    scene.validate()?;
    if prefixes.is_empty() {
        return Ok(vec![scene.clone()]);
    }
    if scene.object_context.is_some()
        || scene.authoring_context.is_some()
        || scene.mesh_assets.values().any(|a| a.editing.is_some())
    {
        return Err("split mode does not support editor contexts; use one-layer control".into());
    }
    let mut fixed = scene.clone();
    let mut dynamic = scene.clone();
    dynamic.annotations.clear();
    for (id, entity) in &scene.entities {
        if !matches!(entity.content, EntityKind::Mesh { .. }) {
            continue;
        }
        let hidden = if prefixes.iter().any(|p| id.starts_with(p)) {
            &mut fixed
        } else {
            &mut dynamic
        };
        hidden.entities.get_mut(id).expect("retained ID").content = EntityKind::Empty;
    }
    fixed.validate()?;
    dynamic.validate()?;
    Ok(vec![fixed, dynamic])
}
fn stats(samples: &[Value], path: &str) -> Value {
    let mut values: Vec<f64> = samples
        .iter()
        .filter(|s| !s["warmup"].as_bool().unwrap())
        .filter(|s| s["path"] == path)
        .map(|s| s["gpu_ms"].as_f64().unwrap())
        .collect();
    if values.is_empty() {
        return Value::Null;
    }
    values.sort_by(f64::total_cmp);
    let n = values.len();
    json!({"count":n,"min_ms":values[0],"max_ms":values[n-1],"median_ms":(values[(n-1)/2]+values[n/2])/2.,"samples_over_original_FF_6_50_ms":values.iter().filter(|x|**x>6.5).count()})
}
struct App {
    args: Args,
    scene: Scene,
    input_hash: String,
    report: Value,
    samples: Vec<Value>,
    window: Option<Arc<Window>>,
    renderer: Option<Renderer>,
    snapshots: Vec<formora::preview::PreparedScene>,
    camera: Option<geometry::Camera>,
    lights: Option<formora::preview::PreparedLighting>,
    pair: usize,
    occluded: Option<bool>,
    started: Instant,
    error: Option<String>,
}
impl App {
    fn run_pair(&mut self, event_loop: &ActiveEventLoop) -> Result<()> {
        if self.pair >= WARMUPS + PAIRS {
            return Ok(());
        }
        let window = self.window.as_ref().ok_or("window missing")?;
        let actual = window.inner_size();
        if (actual.width, actual.height) != (self.args.width, self.args.height) {
            return Err(format!(
                "actual physical size {}x{} differs from fixed request",
                actual.width, actual.height
            )
            .into());
        }
        let renderer = self.renderer.as_mut().ok_or("renderer missing")?;
        let camera = self.camera.as_ref().ok_or("camera missing")?;
        let lights = self.lights.as_ref().ok_or("lighting missing")?;
        let layers: Vec<_> = self.snapshots.iter().collect();
        let warmup = self.pair < WARMUPS;
        let index = if warmup {
            self.pair
        } else {
            self.pair - WARMUPS
        };
        for surface in if index % 2 == 0 {
            [true, false]
        } else {
            [false, true]
        } {
            let before = Instant::now();
            let timing = if surface {
                let frame = renderer.draw_layers_profiled(&layers, camera, lights)?;
                if frame.outcome != DrawOutcome::Submitted {
                    return Err("surface skipped; not a successful sample".into());
                }
                frame.gpu.ok_or("submitted frame has no timestamp sample")?
            } else {
                renderer.profile_layers(&layers, camera, lights)?
            };
            let wall = before.elapsed().as_secs_f64() * 1000.;
            if timing.end_tick <= timing.start_tick
                || !timing.render_ms.is_finite()
                || timing.render_ms <= 0.
            {
                return Err("invalid GPU tick sample".into());
            }
            let calculated = (timing.end_tick - timing.start_tick) as f64
                * f64::from(timing.timestamp_period_ns)
                / 1e6;
            if (calculated - timing.render_ms).abs() > 1e-9 {
                return Err("timestamp conversion mismatch".into());
            }
            let row = json!({"pair":index,"warmup":warmup,"path":if surface {"surface"}else{"offscreen"},"start_tick":timing.start_tick,"end_tick":timing.end_tick,"timestamp_period_ns":timing.timestamp_period_ns,"gpu_ms":timing.render_ms,"cpu_readback_seconds":timing.cpu_readback_seconds,"whole_call_wall_ms":wall,"actual_size":[actual.width,actual.height],"scale_factor":window.scale_factor(),"focused":window.has_focus(),"visible":window.is_visible(),"occluded_observed":self.occluded,"refresh_millihertz":window.current_monitor().and_then(|m|m.refresh_rate_millihertz()),"unix_seconds":SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs_f64()});
            println!("{row}");
            self.samples.push(row);
        }
        self.pair += 1;
        if self.pair == WARMUPS + PAIRS {
            let start = Instant::now();
            let full = self.args.output.join("full-reference.png");
            let split = self.args.output.join("prepared-layers.png");
            renderer.capture(&self.scene, &full)?;
            renderer.capture_layers(&layers, camera, lights, &split)?;
            let a = rgba(&full)?;
            let b = rgba(&split)?;
            if a != b {
                return Err("full-reference/layer offscreen RGBA differs".into());
            }
            self.report["offscreen_RGBA_exact"] = json!(true);
            self.report["offscreen_RGBA_sha256"] = json!(hash(&a.2));
            self.report["evidence_capture_decode_wall_ms"] =
                json!(start.elapsed().as_secs_f64() * 1000.);
            if hash(&fs::read(&self.args.scene)?) != self.input_hash {
                return Err("input file changed during diagnostic".into());
            }
            self.report["input_unchanged"] = json!(true);
            event_loop.exit();
        }
        Ok(())
    }
    fn fail(&mut self, event_loop: &ActiveEventLoop, error: impl std::fmt::Display) {
        self.error = Some(error.to_string());
        event_loop.exit();
    }
}
impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.window.is_some() {
            return;
        }
        let result = (|| -> Result<()> {
            let start = Instant::now();
            let window = Arc::new(
                event_loop.create_window(
                    Window::default_attributes()
                        .with_title("Formora same-scene GPU diagnostic")
                        .with_inner_size(PhysicalSize::new(self.args.width, self.args.height))
                        .with_active(self.args.active),
                )?,
            );
            let actual = window.inner_size();
            if actual != PhysicalSize::new(self.args.width, self.args.height) {
                return Err("window did not honor requested physical size".into());
            }
            let renderer = pollster::block_on(Renderer::new_profiled(
                Some(window.clone()),
                actual.width,
                actual.height,
            ))?;
            self.report["window_renderer_setup_ms"] = json!(start.elapsed().as_secs_f64() * 1000.);
            self.report["adapter"] = json!(renderer.adapter);
            let start = Instant::now();
            let geometry = geometry::vertices(&self.scene)?;
            let mut digest = Sha256::new();
            digest.update(b"formora-headless-vertices-v1");
            digest.update(bytemuck::cast_slice(&geometry));
            let expected = geometry.len();
            drop(geometry);
            let parts = partition(&self.scene, &self.args.prefixes)?;
            let snapshots = parts
                .iter()
                .map(|s| renderer.prepare(s))
                .collect::<std::result::Result<Vec<_>, _>>()?;
            if snapshots
                .iter()
                .map(|s| s.vertex_count() as usize)
                .sum::<usize>()
                != expected
            {
                return Err("split changed total corner count".into());
            }
            self.report["vertices"] = json!(expected);
            self.report["vertex_sha256"] = json!(format!("{:x}", digest.finalize()));
            self.report["layer_vertices"] = json!(
                snapshots
                    .iter()
                    .map(|s| s.vertex_count())
                    .collect::<Vec<_>>()
            );
            self.report["layer_buffers"] = json!(
                snapshots
                    .iter()
                    .map(|s| s.vertex_buffer_count())
                    .collect::<Vec<_>>()
            );
            self.report["vertex_buffer_chunk_limit"] = json!(renderer.vertex_buffer_chunk_limit());
            self.report["prepare_hash_partition_ms"] = json!(start.elapsed().as_secs_f64() * 1000.);
            self.camera = Some(geometry::camera_view(
                &self.scene,
                actual.width,
                actual.height,
            )?);
            self.lights = Some(renderer.prepare_lighting(&self.scene)?);
            self.report["source_light_entities"] = json!(
                self.scene
                    .entities
                    .values()
                    .filter(|e| matches!(e.content, EntityKind::Light { .. }))
                    .count()
            );
            self.snapshots = snapshots;
            self.renderer = Some(renderer);
            self.window = Some(window);
            Ok(())
        })();
        if let Err(e) = result {
            self.fail(event_loop, e);
        }
    }
    fn window_event(&mut self, event_loop: &ActiveEventLoop, id: WindowId, event: WindowEvent) {
        if self.window.as_ref().is_none_or(|w| w.id() != id) {
            return;
        }
        match event {
            WindowEvent::CloseRequested => {
                self.fail(event_loop, "window closed before diagnostic completion")
            }
            WindowEvent::Occluded(value) => self.occluded = Some(value),
            WindowEvent::RedrawRequested => {
                if let Err(e) = self.run_pair(event_loop) {
                    self.fail(event_loop, e);
                }
            }
            _ => {}
        }
    }
    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        if self.started.elapsed().as_secs() > 120 {
            self.fail(event_loop, "diagnostic timeout");
            return;
        }
        if let Some(w) = &self.window {
            w.request_redraw();
        }
    }
}
fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1).collect())?;
    let start = Instant::now();
    let bytes = fs::read(&args.scene)?;
    let input_hash = hash(&bytes);
    let scene: Scene = serde_json::from_slice(&bytes)?;
    scene.validate()?;
    fs::create_dir(&args.output)?;
    let report = json!({"engine_commit":ENGINE,"engine_99_files_verified_at_build":true,"input_scene":args.scene,"input_sha256":input_hash,"requested_size":[args.width,args.height],"requested_active":args.active,"dynamic_prefixes":args.prefixes,"warmup_pairs":WARMUPS,"measured_pairs":PAIRS,"load_validation_ms":start.elapsed().as_secs_f64()*1000.,"surface_format":"not exposed by pinned Renderer; both profiled paths use its same format","scope":"immutable frozen-scene paired GPU diagnostic; not original FF workload, total pipeline, physical presentation or FPS acceptance; surface pixels not read back; offscreen full/layer pixels checked","background":"caller must coordinate test processes; no absolute system isolation claim"});
    let output = args.output.clone();
    let mut app = App {
        args,
        scene,
        input_hash,
        report,
        samples: Vec::new(),
        window: None,
        renderer: None,
        snapshots: Vec::new(),
        camera: None,
        lights: None,
        pair: 0,
        occluded: None,
        started: Instant::now(),
        error: None,
    };
    let events = EventLoop::new()?;
    events.set_control_flow(ControlFlow::Poll);
    if let Err(e) = events.run_app(&mut app) {
        app.error = Some(e.to_string());
    }
    app.report["samples"] = json!(app.samples);
    app.report["surface_stats"] = stats(&app.samples, "surface");
    app.report["offscreen_stats"] = stats(&app.samples, "offscreen");
    app.report["error"] = json!(app.error);
    app.report["completed_pairs"] = json!(app.pair);
    app.report["status"] = json!(if app.error.is_none() && app.pair == WARMUPS + PAIRS {
        "completed_diagnostic_not_budget_acceptance"
    } else {
        "failed_or_incomplete"
    });
    fs::write(
        output.join("report.json"),
        serde_json::to_vec_pretty(&app.report)?,
    )?;
    if let Some(e) = app.error {
        return Err(e.into());
    }
    if app.pair != WARMUPS + PAIRS {
        return Err("incomplete diagnostic".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn args(extra: &[&str]) -> Vec<String> {
        ["scene.json", "output", "257", "193"]
            .into_iter()
            .chain(extra.iter().copied())
            .map(str::to_owned)
            .collect()
    }
    #[test]
    fn argument_bounds_and_duplicate_flags_fail_closed() {
        assert!(Args::parse(args(&["--active", "false", "--dynamic-prefix", "b-"])).is_ok());
        for extra in [
            vec!["--active", "false", "--active", "true"],
            vec!["--active", "maybe"],
            vec!["--dynamic-prefix", ""],
            vec!["--unknown", "x"],
            vec!["--active"],
        ] {
            assert!(Args::parse(args(&extra)).is_err());
        }
        for value in ["0", "8193", "4294967295"] {
            let mut a = args(&[]);
            a[2] = value.into();
            assert!(Args::parse(a).is_err());
        }
    }
    #[test]
    fn projection_preserves_worlds_assets_and_single_annotation_ownership() {
        let mut scene: Scene = serde_json::from_str(include_str!("../fixture.scene.json")).unwrap();
        scene.annotations.push(formora::scene::Annotation {
            entity: None,
            position: [0., 0., -2.],
            text: "probe".into(),
        });
        let parts = partition(&scene, &["b-".into()]).unwrap();
        assert_eq!(parts.len(), 2);
        assert_eq!(parts[0].annotations.len(), 1);
        assert!(parts[1].annotations.is_empty());
        for p in &parts {
            assert_eq!(p.entities.len(), scene.entities.len());
            assert_eq!(p.mesh_assets, scene.mesh_assets);
            assert_eq!(p.materials, scene.materials);
            assert_eq!(
                geometry::world_transforms(p).unwrap(),
                geometry::world_transforms(&scene).unwrap()
            );
        }
        assert!(matches!(
            parts[0].entities["b-dynamic"].content,
            EntityKind::Empty
        ));
        assert!(matches!(
            parts[1].entities["a-static"].content,
            EntityKind::Empty
        ));
        assert_eq!(
            parts
                .iter()
                .map(|p| geometry::vertices(p).unwrap().len())
                .sum::<usize>(),
            geometry::vertices(&scene).unwrap().len()
        );
        let mut context = scene;
        context.object_context = Some(Default::default());
        assert!(partition(&context, &["b-".into()]).is_err());
        assert!(partition(&context, &[]).is_ok());
    }
    #[test]
    fn statistics_keep_slow_samples_and_exclude_only_marked_warmups() {
        let samples = vec![
            json!({"warmup":true,"path":"surface","gpu_ms":100.}),
            json!({"warmup":false,"path":"surface","gpu_ms":1.}),
            json!({"warmup":false,"path":"surface","gpu_ms":20.}),
        ];
        let s = stats(&samples, "surface");
        assert_eq!(s["max_ms"], 20.);
        assert_eq!(s["median_ms"], 10.5);
        assert_eq!(s["samples_over_original_FF_6_50_ms"], 1);
    }
}
