//! Independent public-API consumer. Execute GPU/file checks in CI, not unit tests.
use formora::mesh::{MeshAsset, Triangle};
use formora::preview::{PreparedScene, Renderer};
use formora::scene::{Entity, EntityKind, Geometry, Material, Scene, Transform};
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fs;
use std::io::BufReader;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, Instant};
use winit::application::ApplicationHandler;
use winit::dpi::PhysicalSize;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::window::{Window, WindowId};

type Result<T> = std::result::Result<T, Box<dyn Error>>;
const INITIAL: PhysicalSize<u32> = PhysicalSize::new(257, 193);
const RESIZED: PhysicalSize<u32> = PhysicalSize::new(319, 211);

fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.materials.insert(
        "paint".into(),
        Material {
            base_color: [0.9, 0.05, 0.03, 1.0],
            roughness: 0.6,
            metallic: 0.0,
        },
    );
    scene.entities.insert(
        "box".into(),
        Entity {
            name: "External consumer box".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Cube { size: [2.0; 3] },
                material: Some("paint".into()),
            },
        },
    );
    scene.entities.insert(
        "camera".into(),
        Entity {
            name: "Host camera".into(),
            parent: None,
            transform: Transform {
                translation: [0.0, 0.0, 6.0],
                ..Transform::default()
            },
            content: EntityKind::Camera {
                vertical_fov_degrees: 50.0,
                near: 0.1,
                far: 100.0,
            },
        },
    );
    scene.active_camera = Some("camera".into());
    scene
}

fn pixels(path: &Path, size: PhysicalSize<u32>) -> Result<Vec<u8>> {
    let mut reader = png::Decoder::new(BufReader::new(fs::File::open(path)?)).read_info()?;
    let mut data = vec![0; reader.output_buffer_size().ok_or("PNG too large")?];
    let info = reader.next_frame(&mut data)?;
    assert_eq!((info.width, info.height), (size.width, size.height));
    assert_eq!(info.color_type, png::ColorType::Rgba);
    data.truncate(info.buffer_size());
    let background = &data[..4];
    assert!(data.chunks_exact(4).filter(|p| *p != background).count() > 100);
    Ok(data)
}

struct Trial {
    scene: Scene,
    original: Scene,
    output: PathBuf,
    previous: Option<Vec<u8>>,
    last_prepared: Option<PreparedScene>,
}

impl Trial {
    fn corner_colors(&self, renderer: &mut Renderer, size: PhysicalSize<u32>) -> Result<()> {
        let mut scene = scene();
        let colors = [[1., 0., 0., 1.], [0., 1., 0., 1.], [0., 0., 1., 1.]];
        scene.mesh_assets.insert(
            "gradient".into(),
            MeshAsset {
                vertices: BTreeMap::from([
                    ("a".into(), [-1., -1., 0.]),
                    ("b".into(), [1., -1., 0.]),
                    ("c".into(), [0., 1., 0.]),
                ]),
                triangles: BTreeMap::from([(
                    "face".into(),
                    Triangle {
                        vertices: ["a", "b", "c"].map(str::to_owned),
                        uv_layers: BTreeMap::new(),
                        corner_normals: Some([[0., 0., 1.]; 3]),
                        corner_colors: Some(colors),
                        material_slot: None,
                    },
                )]),
                ..Default::default()
            },
        );
        let EntityKind::Mesh { geometry, .. } = &mut scene.entities.get_mut("box").unwrap().content
        else {
            unreachable!()
        };
        *geometry = Geometry::Asset {
            id: "gradient".into(),
        };
        let path = self.output.join("corner-live.png");
        renderer.capture(&scene, &path)?;
        let image = pixels(&path, size)?;
        let background = &image[..4];
        let distinct: BTreeSet<_> = image
            .chunks_exact(4)
            .filter(|p| *p != background)
            .map(|p| [p[0], p[1], p[2]])
            .collect();
        assert!(
            distinct.len() >= 32,
            "corner interpolation must not become a single face color"
        );
        for channel in 0..3 {
            assert!(
                distinct
                    .iter()
                    .any(|p| (0..3).all(|other| other == channel || p[channel] > p[other])),
                "each of RGB must dominate somewhere on this ambient-only triangle"
            );
        }
        let snapshot = renderer.prepare(&scene)?;
        let camera = formora::geometry::camera_view(&scene, size.width, size.height)?;
        renderer.capture_prepared(&snapshot, &camera, &self.output.join("corner-prepared.png"))?;
        assert_eq!(
            pixels(&self.output.join("corner-prepared.png"), size)?,
            image
        );
        let original = scene.clone();
        scene
            .mesh_assets
            .get_mut("gradient")
            .unwrap()
            .triangles
            .get_mut("face")
            .unwrap()
            .corner_colors = Some([[1. / 3., 1. / 3., 1. / 3., 1.]; 3]);
        renderer.capture(&scene, &self.output.join("corner-average.png"))?;
        assert_ne!(
            pixels(&self.output.join("corner-average.png"), size)?,
            image
        );
        renderer.capture_prepared(&snapshot, &camera, &self.output.join("corner-retained.png"))?;
        assert_eq!(
            pixels(&self.output.join("corner-retained.png"), size)?,
            image
        );
        let changed = renderer.prepare(&scene)?;
        renderer.capture_prepared(&changed, &camera, &self.output.join("corner-updated.png"))?;
        assert_eq!(
            pixels(&self.output.join("corner-updated.png"), size)?,
            pixels(&self.output.join("corner-average.png"), size)?
        );
        scene
            .mesh_assets
            .get_mut("gradient")
            .unwrap()
            .triangles
            .get_mut("face")
            .unwrap()
            .corner_colors
            .as_mut()
            .unwrap()[0][3] = 2.;
        assert!(renderer.capture(&scene, &path).is_err());
        assert_eq!(pixels(&path, size)?, image);
        assert_eq!(scene.revision, original.revision);
        // Warm caches must not hide errors, including assets without an instance.
        for case in 0..4 {
            renderer.capture(&original, &path)?;
            let mut bad = original.clone();
            match case {
                0 => {
                    let mut unused = MeshAsset::default();
                    unused.vertices.insert("bad".into(), [f64::NAN, 0., 0.]);
                    bad.mesh_assets.insert("unused".into(), unused);
                }
                1 => {
                    bad.materials.remove("paint");
                }
                2 => {
                    bad.mesh_assets
                        .get_mut("gradient")
                        .unwrap()
                        .triangles
                        .get_mut("face")
                        .unwrap()
                        .vertices[1] = "missing".into()
                }
                3 => {
                    bad.mesh_assets
                        .get_mut("gradient")
                        .unwrap()
                        .triangles
                        .get_mut("face")
                        .unwrap()
                        .corner_normals = Some([[0., 0., 2.]; 3])
                }
                _ => unreachable!(),
            }
            assert!(bad.validate().is_err());
            assert!(renderer.prepare(&bad).is_err());
            assert!(renderer.capture(&bad, &path).is_err());
            assert_eq!(pixels(&path, size)?, image);
            renderer.capture(&original, &path)?;
            assert_eq!(pixels(&path, size)?, image);
        }
        println!(
            "PASS warm validation rejects unused asset, removed material, missing vertex and invalid normals; original capture recovers"
        );
        println!(
            "PASS RGB corner interpolation, same-revision change, prepared parity, retained snapshot and invalid-color file preservation"
        );
        Ok(())
    }

    fn frame(&mut self, renderer: &mut Renderer, step: u32, windowed: bool) -> Result<()> {
        match step {
            1 => {
                self.scene
                    .entities
                    .get_mut("box")
                    .unwrap()
                    .transform
                    .translation[0] = 0.8
            }
            2 => self.scene.materials.get_mut("paint").unwrap().base_color = [0.03, 0.1, 0.9, 1.0],
            3 => {
                self.scene
                    .entities
                    .get_mut("camera")
                    .unwrap()
                    .transform
                    .translation[2] = 8.0
            }
            _ => {}
        }
        self.scene.validate()?;
        let before = self.scene.clone();
        if windowed {
            renderer.draw(&self.scene)?;
        }
        let path = self.output.join(format!("frame-{step}.png"));
        renderer.capture(&self.scene, &path)?;
        let size = PhysicalSize::new(renderer.width, renderer.height);
        let data = pixels(&path, size)?;
        if let Some(previous) = &self.previous {
            assert_ne!(previous, &data, "a new host scene must change the image");
        }
        let repeat = self.output.join("repeat.png");
        renderer.capture(&self.scene, &repeat)?;
        assert_eq!(pixels(&repeat, size)?, data);
        let prepared = renderer.prepare(&self.scene)?;
        assert_eq!(prepared.vertex_count(), 36);
        let camera = formora::geometry::camera_view(&self.scene, size.width, size.height)?;
        let captured = self.output.join(format!("prepared-{step}.png"));
        if windowed {
            renderer.draw_prepared(&prepared, &camera)?;
        }
        renderer.capture_prepared(&prepared, &camera, &captured)?;
        assert_eq!(
            pixels(&captured, size)?,
            data,
            "prepared and live pixels must match"
        );
        self.last_prepared = Some(prepared);
        assert_eq!(self.scene, before, "rendering must not mutate host state");
        assert_eq!(self.scene.revision, self.original.revision);
        self.previous = Some(data);
        println!(
            "PASS frame={step} size={}x{} revision={}",
            size.width, size.height, self.scene.revision
        );
        Ok(())
    }

    fn finish(
        &mut self,
        renderer: &mut Renderer,
        windowed: bool,
        size: PhysicalSize<u32>,
    ) -> Result<()> {
        assert_eq!((renderer.width, renderer.height), (size.width, size.height));
        renderer.resize(0, 0);
        renderer.resize(0, 100);
        renderer.resize(100, 0);
        assert_eq!((renderer.width, renderer.height), (size.width, size.height));
        let path = self.output.join("resized.png");
        if windowed {
            renderer.draw(&self.scene)?;
        } else {
            assert!(renderer.draw(&self.scene).is_err());
        }
        renderer.capture(&self.scene, &path)?;
        pixels(&path, size)?;
        let good = fs::read(&path)?;
        let snapshot = renderer.prepare(&self.scene)?;
        let camera = formora::geometry::camera_view(&self.scene, size.width, size.height)?;
        let retained = self
            .last_prepared
            .as_ref()
            .ok_or("no pre-resize snapshot")?;
        renderer.capture_prepared(
            retained,
            &camera,
            &self.output.join("retained-after-resize.png"),
        )?;
        assert_eq!(
            pixels(&self.output.join("retained-after-resize.png"), size)?,
            pixels(&path, size)?
        );
        renderer.capture_prepared(
            &snapshot,
            &camera,
            &self.output.join("prepared-resized.png"),
        )?;
        assert_eq!(
            pixels(&self.output.join("prepared-resized.png"), size)?,
            pixels(&path, size)?
        );
        if !windowed {
            assert!(renderer.draw_prepared(&snapshot, &camera).is_err());
        }
        let mut bad_camera = camera.clone();
        bad_camera.position.x = f64::NAN;
        assert!(
            renderer
                .capture_prepared(&snapshot, &bad_camera, &path)
                .is_err()
        );
        assert_eq!(fs::read(&path)?, good);
        let foreign = pollster::block_on(Renderer::new(None, size.width, size.height))?;
        let error = foreign
            .capture_prepared(&snapshot, &camera, &path)
            .unwrap_err();
        assert!(error.to_string().contains("another renderer"));
        assert_eq!(fs::read(&path)?, good);
        let mut changed = self.scene.clone();
        changed.materials.get_mut("paint").unwrap().base_color = [0.1, 0.9, 0.05, 1.0];
        let newer = renderer.prepare(&changed)?;
        renderer.capture_prepared(&newer, &camera, &self.output.join("prepared-newer.png"))?;
        renderer.capture(&changed, &self.output.join("live-newer.png"))?;
        let newer_pixels = pixels(&self.output.join("prepared-newer.png"), size)?;
        assert_eq!(
            newer_pixels,
            pixels(&self.output.join("live-newer.png"), size)?
        );
        assert_ne!(newer_pixels, pixels(&path, size)?);
        renderer.capture_prepared(
            &snapshot,
            &camera,
            &self.output.join("prepared-original-again.png"),
        )?;
        assert_eq!(
            pixels(&self.output.join("prepared-original-again.png"), size)?,
            pixels(&path, size)?,
            "preparing changed data must not mutate the old snapshot"
        );
        changed = self.scene.clone();
        changed
            .entities
            .get_mut("camera")
            .unwrap()
            .transform
            .translation[0] += 0.4;
        let moved_camera = formora::geometry::camera_view(&changed, size.width, size.height)?;
        renderer.capture_prepared(
            &snapshot,
            &moved_camera,
            &self.output.join("prepared-camera.png"),
        )?;
        renderer.capture(&changed, &self.output.join("live-camera.png"))?;
        assert_eq!(
            pixels(&self.output.join("prepared-camera.png"), size)?,
            pixels(&self.output.join("live-camera.png"), size)?
        );
        changed = self.scene.clone();
        changed.entities.insert(
            "light".into(),
            Entity {
                name: "Light".into(),
                parent: None,
                transform: Transform {
                    translation: [0.0, 0.0, 5.0],
                    ..Transform::default()
                },
                content: EntityKind::Light {
                    color: [0.1, 1.0, 0.1],
                    intensity: 100.0,
                },
            },
        );
        let lit = renderer.prepare(&changed)?;
        renderer.capture_prepared(&lit, &camera, &self.output.join("prepared-light.png"))?;
        renderer.capture(&changed, &self.output.join("live-light.png"))?;
        assert_eq!(
            pixels(&self.output.join("prepared-light.png"), size)?,
            pixels(&self.output.join("live-light.png"), size)?
        );
        assert_ne!(
            pixels(&self.output.join("prepared-light.png"), size)?,
            pixels(&path, size)?
        );
        renderer.capture_prepared(
            &snapshot,
            &camera,
            &self.output.join("prepared-old-light.png"),
        )?;
        assert_eq!(
            pixels(&self.output.join("prepared-old-light.png"), size)?,
            pixels(&path, size)?
        );
        assert_eq!(changed.revision, self.scene.revision);
        let mut invalid = self.scene.clone();
        invalid.active_camera = Some("missing".into());
        assert!(renderer.capture(&invalid, &path).is_err());
        assert_eq!(fs::read(&path)?, good);
        assert!(
            renderer
                .capture(&self.scene, &self.output.join("missing-parent/file.png"))
                .is_err()
        );
        renderer.capture(&self.original, &self.output.join("restored.png"))?;
        assert_eq!(self.original, scene());
        self.corner_colors(renderer, size)?;
        println!("PASS resize, zero resize, invalid-scene/output rejection, host ownership");
        fs::write(
            self.output.join("passed.txt"),
            format!(
                "adapter={}\nwindowed={windowed}\nscene_samples=5\nprepared_matches_live=true\nimmutable_snapshot_checked=true\nscene_revision={}\n",
                renderer.adapter, self.scene.revision
            ),
        )?;
        Ok(())
    }
}

struct Host {
    trial: Trial,
    window: Option<Arc<Window>>,
    renderer: Option<Renderer>,
    step: u32,
    started: Instant,
    failure: Option<String>,
    completed: bool,
    size_before_resize: Option<PhysicalSize<u32>>,
}

impl Host {
    fn redraw(&mut self, event_loop: &ActiveEventLoop) -> Result<()> {
        let renderer = self.renderer.as_mut().ok_or("renderer not ready")?;
        let window = self.window.as_ref().ok_or("window not ready")?;
        if self.step < 4 {
            self.trial.frame(renderer, self.step, true)?;
            self.step += 1;
            if self.step == 4 {
                self.size_before_resize = Some(window.inner_size());
                let _ = window.request_inner_size(RESIZED);
            }
        } else if Some(window.inner_size()) != self.size_before_resize
            && window.inner_size().width > 0
            && window.inner_size().height > 0
        {
            let actual = window.inner_size();
            renderer.resize(actual.width, actual.height);
            println!(
                "resize requested={}x{} actual={}x{}",
                RESIZED.width, RESIZED.height, actual.width, actual.height
            );
            self.trial.finish(renderer, true, actual)?;
            self.completed = true;
            event_loop.exit();
        }
        window.request_redraw();
        Ok(())
    }
}

impl ApplicationHandler for Host {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.window.is_some() {
            return;
        }
        let result = (|| -> Result<()> {
            let window = Arc::new(
                event_loop.create_window(
                    Window::default_attributes()
                        .with_title("Formora external consumer")
                        .with_inner_size(INITIAL),
                )?,
            );
            let size = window.inner_size();
            let renderer = pollster::block_on(Renderer::new(
                Some(Arc::clone(&window)),
                size.width,
                size.height,
            ))?;
            println!("adapter={}", renderer.adapter);
            self.renderer = Some(renderer);
            window.request_redraw();
            self.window = Some(window);
            Ok(())
        })();
        if let Err(error) = result {
            self.failure = Some(error.to_string());
            event_loop.exit();
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, id: WindowId, event: WindowEvent) {
        if self.window.as_ref().map(|w| w.id()) != Some(id) {
            return;
        }
        let result = match event {
            WindowEvent::Resized(size) => {
                if let Some(renderer) = &mut self.renderer {
                    renderer.resize(size.width, size.height);
                }
                Ok(())
            }
            WindowEvent::RedrawRequested => self.redraw(event_loop),
            WindowEvent::CloseRequested => Err("window closed before checks completed".into()),
            _ => Ok(()),
        };
        if let Err(error) = result {
            self.failure = Some(error.to_string());
            event_loop.exit();
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        if self.started.elapsed() > Duration::from_secs(30) {
            self.failure = Some("window trial timed out".into());
            event_loop.exit();
        }
        if let Some(window) = &self.window {
            window.request_redraw();
        }
    }
}

fn main() -> Result<()> {
    let args: Vec<_> = std::env::args_os().collect();
    if args.len() != 3 || (args[1] != "--offscreen" && args[1] != "--window") {
        return Err("usage: formora-renderer-consumer --offscreen|--window NEW_OUTPUT_DIR".into());
    }
    let output = PathBuf::from(&args[2]);
    fs::create_dir(&output)?;
    assert!(pollster::block_on(Renderer::new(None, 0, 193)).is_err());
    assert!(pollster::block_on(Renderer::new(None, 257, 0)).is_err());
    let scene = scene();
    let mut trial = Trial {
        original: scene.clone(),
        scene,
        output,
        previous: None,
        last_prepared: None,
    };
    if args[1] == "--offscreen" {
        let mut renderer = pollster::block_on(Renderer::new(None, INITIAL.width, INITIAL.height))?;
        println!("adapter={}", renderer.adapter);
        for step in 0..4 {
            trial.frame(&mut renderer, step, false)?;
        }
        renderer.resize(RESIZED.width, RESIZED.height);
        trial.finish(&mut renderer, false, RESIZED)?;
    } else {
        let event_loop = EventLoop::new()?;
        event_loop.set_control_flow(ControlFlow::Poll);
        let mut host = Host {
            trial,
            window: None,
            renderer: None,
            step: 0,
            started: Instant::now(),
            failure: None,
            completed: false,
            size_before_resize: None,
        };
        event_loop.run_app(&mut host)?;
        if let Some(error) = host.failure {
            return Err(error.into());
        }
        if !host.completed {
            return Err("window trial did not complete".into());
        }
    }
    println!("PASS external Renderer consumer");
    Ok(())
}
