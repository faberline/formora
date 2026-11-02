//! Independent public-API consumer. Execute GPU/file checks in CI, not unit tests.
use formora::mesh::{MeshAsset, Triangle};
use formora::preview::{DrawOutcome, PreparedScene, Renderer};
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

fn rgba(path: &Path, size: PhysicalSize<u32>) -> Result<Vec<u8>> {
    let mut reader = png::Decoder::new(BufReader::new(fs::File::open(path)?)).read_info()?;
    let mut data = vec![0; reader.output_buffer_size().ok_or("PNG too large")?];
    let info = reader.next_frame(&mut data)?;
    assert_eq!((info.width, info.height), (size.width, size.height));
    assert_eq!(info.color_type, png::ColorType::Rgba);
    data.truncate(info.buffer_size());
    Ok(data)
}

fn pixels(path: &Path, size: PhysicalSize<u32>) -> Result<Vec<u8>> {
    let data = rgba(path, size)?;
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
    fn authored_cancellation(
        &self,
        renderer: &mut Renderer,
        size: PhysicalSize<u32>,
    ) -> Result<()> {
        let mut scene = scene();
        let small = 1. / (1_u64 << 60) as f64;
        scene.mesh_assets.insert(
            "needle".into(),
            MeshAsset {
                vertices: BTreeMap::from([
                    ("a".into(), [1., 1., 0.]),
                    ("b".into(), [0., 0., 0.]),
                    ("c".into(), [small, 0., 0.]),
                ]),
                triangles: BTreeMap::from([(
                    "face".into(),
                    Triangle {
                        vertices: ["a", "b", "c"].map(str::to_owned),
                        uv_layers: BTreeMap::new(),
                        corner_normals: Some([[0., 0., 1.]; 3]),
                        corner_colors: None,
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
            id: "needle".into(),
        };
        scene.entities.insert(
            "camera_parent".into(),
            Entity {
                name: "Camera parent".into(),
                parent: None,
                transform: Transform::default(),
                content: EntityKind::Empty,
            },
        );
        scene.entities.get_mut("camera").unwrap().parent = Some("camera_parent".into());
        scene.object_context = Some(formora::objects::Context {
            states: BTreeMap::from([(
                "camera".into(),
                formora::objects::State {
                    parent_inverse: Some([
                        [small, 2., 0., 0.],
                        [0., 2., 0., 0.],
                        [0., 0., 1., 0.],
                        [0., 0., 0., 1.],
                    ]),
                    ..Default::default()
                },
            )]),
            ..Default::default()
        });
        let before = scene.clone();
        let path = self.output.join("cancellation-live.png");
        renderer.capture(&scene, &path)?;
        let image = pixels(&path, size)?;
        let snapshot = renderer.prepare(&scene)?;
        assert_eq!(snapshot.vertex_count(), 3);
        let camera = formora::geometry::camera_view(&scene, size.width, size.height)?;
        renderer.capture_prepared(
            &snapshot,
            &camera,
            &self.output.join("cancellation-prepared.png"),
        )?;
        assert_eq!(
            pixels(&self.output.join("cancellation-prepared.png"), size)?,
            image
        );
        assert_eq!(scene, before);
        scene
            .mesh_assets
            .get_mut("needle")
            .unwrap()
            .vertices
            .get_mut("c")
            .unwrap()[0] = small * 0.5;
        renderer.capture(&scene, &self.output.join("cancellation-changed.png"))?;
        assert_ne!(
            pixels(&self.output.join("cancellation-changed.png"), size)?,
            image
        );
        renderer.capture_prepared(
            &snapshot,
            &camera,
            &self.output.join("cancellation-retained.png"),
        )?;
        assert_eq!(
            pixels(&self.output.join("cancellation-retained.png"), size)?,
            image
        );
        assert_eq!(scene.revision, 0);
        println!(
            "PASS authored cancellation face is visible, three corners retained, live/prepared equal and old snapshot immutable"
        );
        Ok(())
    }

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

    fn layers(
        &self,
        renderer: &mut Renderer,
        size: PhysicalSize<u32>,
        windowed: bool,
    ) -> Result<()> {
        let mut full = scene();
        full.entities.remove("box");
        for (index, id) in ["a", "b", "c", "d"].iter().enumerate() {
            let color = [
                [1., 0.1, 0.1, 0.45],
                [0.1, 1., 0.1, 0.7],
                [0.1, 0.1, 1., 0.6],
                [1., 1., 0.1, 0.8],
            ][index];
            full.materials.insert(
                id.to_string(),
                Material {
                    base_color: color,
                    roughness: 0.6,
                    metallic: 0.,
                },
            );
            full.entities.insert(
                id.to_string(),
                Entity {
                    name: id.to_string(),
                    parent: None,
                    transform: Transform {
                        translation: [(index as f64 - 1.5) * 0.3, 0., 0.],
                        ..Default::default()
                    },
                    content: EntityKind::Mesh {
                        geometry: Geometry::Plane { size: [2.8, 2.] },
                        material: Some(id.to_string()),
                    },
                },
            );
        }
        for (id, x, color) in [
            ("a_light", -2., [0.2, 1., 0.4]),
            ("z_light", 3., [1., 0.3, 0.2]),
        ] {
            full.entities.insert(
                id.into(),
                Entity {
                    name: id.into(),
                    parent: None,
                    transform: Transform {
                        translation: [x, 0., 4.],
                        ..Default::default()
                    },
                    content: EntityKind::Light {
                        color,
                        intensity: 80.,
                    },
                },
            );
        }
        // Caller order is [dynamic, static]. All annotations follow all mesh IDs.
        full.annotations = vec![
            formora::scene::Annotation {
                entity: None,
                position: [-0.5, 0.6, 0.5],
                text: "dynamic".into(),
            },
            formora::scene::Annotation {
                entity: None,
                position: [0.5, 0.6, 0.5],
                text: "static".into(),
            },
        ];
        let layer = |source: &Scene, ids: &[&str], note: usize| {
            let mut part = source.clone();
            part.entities.retain(|id, e| {
                !matches!(e.content, EntityKind::Mesh { .. }) || ids.contains(&id.as_str())
            });
            part.annotations = vec![source.annotations[note].clone()];
            part
        };
        let before = full.clone();
        let mut static_snapshot = renderer.prepare(&layer(&full, &["a", "c"], 1))?;
        let original_static = renderer.prepare(&layer(&full, &["a", "c"], 1))?;
        let original_dynamic = renderer.prepare(&layer(&full, &["b", "d"], 0))?;
        let original_lights = renderer.prepare_lighting(&full)?;
        let original_camera = formora::geometry::camera_view(&full, size.width, size.height)?;
        let mut first = None;
        let mut retained_future = None;
        for step in 0..4 {
            match step {
                1 => {
                    full.entities.get_mut("b").unwrap().transform.translation[1] += 0.5;
                    full.materials.get_mut("d").unwrap().base_color = [0.8, 0.2, 0.7, 0.8];
                }
                2 => {
                    full.entities.get_mut("a_light").unwrap().content = EntityKind::Light {
                        color: [0.1, 0.3, 1.],
                        intensity: 250.,
                    };
                    full.entities
                        .get_mut("camera")
                        .unwrap()
                        .transform
                        .translation[0] += 0.3;
                }
                3 => {
                    full.entities.get_mut("a").unwrap().transform.translation[1] -= 0.5;
                    static_snapshot =
                        renderer.prepare_from(&static_snapshot, &layer(&full, &["a", "c"], 1))?;
                }
                _ => {}
            }
            let dynamic =
                renderer.prepare_from(&original_dynamic, &layer(&full, &["b", "d"], 0))?;
            let camera = formora::geometry::camera_view(&full, size.width, size.height)?;
            let lights = renderer.prepare_lighting(&full)?;
            let current = full.clone();
            let reference = self.output.join(format!("layers-reference-{step}.png"));
            let output = self.output.join(format!("layers-ordered-{step}.png"));
            let chunk_limit = renderer.vertex_buffer_chunk_limit();
            renderer.set_vertex_buffer_chunk_limit(None)?;
            renderer.capture(&full, &reference)?;
            renderer.set_vertex_buffer_chunk_limit(Some(chunk_limit))?;
            renderer.capture_layers(&[&dynamic, &static_snapshot], &camera, &lights, &output)?;
            let image = pixels(&reference, size)?;
            assert_eq!(
                pixels(&output, size)?,
                image,
                "layers must match full-scene order and current lights"
            );
            if let Some(previous) = &first {
                assert_ne!(
                    &image, previous,
                    "actual dynamic updates must change reference"
                );
            } else {
                first = Some(image.clone());
            }
            let world = formora::geometry::world_transforms(&full)?;
            for id in ["b", "d", "camera"] {
                assert_eq!(
                    dynamic
                        .world_transform(id)
                        .unwrap()
                        .to_cols_array()
                        .map(f64::to_bits),
                    world[id].to_cols_array().map(f64::to_bits)
                );
            }
            assert!(dynamic.world_transform("missing").is_none());
            assert!(dynamic.world_transform("a").is_none());
            if windowed {
                let mut submitted = false;
                for _ in 0..10 {
                    let result = renderer.draw_layers_profiled(
                        &[&dynamic, &static_snapshot],
                        &camera,
                        &lights,
                    )?;
                    match result.outcome {
                        DrawOutcome::Submitted => {
                            let sample = result.gpu.ok_or("submitted frame lacks timestamp")?;
                            println!(
                                "GPU layers surface step={step} start={} end={} period_ns={} render_ms={} cpu_readback_seconds={}",
                                sample.start_tick,
                                sample.end_tick,
                                sample.timestamp_period_ns,
                                sample.render_ms,
                                sample.cpu_readback_seconds
                            );
                            submitted = true;
                            break;
                        }
                        DrawOutcome::Skipped => assert!(result.gpu.is_none()),
                    }
                }
                assert!(submitted, "no surface frame submitted");
                assert!(matches!(
                    renderer.draw_layers(&[&dynamic, &static_snapshot], &camera, &lights)?,
                    DrawOutcome::Submitted | DrawOutcome::Skipped
                ));
            } else {
                assert!(
                    renderer
                        .draw_layers(&[&dynamic, &static_snapshot], &camera, &lights)
                        .is_err()
                );
            }
            let sample =
                renderer.profile_layers(&[&dynamic, &static_snapshot], &camera, &lights)?;
            assert!(sample.end_tick > sample.start_tick && sample.render_ms > 0.);
            println!(
                "GPU layers offscreen step={step} start={} end={} period_ns={} render_ms={} cpu_readback_seconds={}",
                sample.start_tick,
                sample.end_tick,
                sample.timestamp_period_ns,
                sample.render_ms,
                sample.cpu_readback_seconds
            );
            assert_eq!(full, current);
            assert_eq!(full.revision, before.revision);
            let good = fs::read(&output)?;
            assert!(
                renderer
                    .capture_layers(&[&dynamic, &dynamic], &camera, &lights, &output)
                    .is_err()
            );
            assert_eq!(fs::read(&output)?, good);
            let mut invalid = camera.clone();
            invalid.view_projection.x_axis.x = f64::NAN;
            assert!(
                renderer
                    .capture_layers(&[&dynamic], &invalid, &lights, &output)
                    .is_err()
            );
            assert_eq!(fs::read(&output)?, good);
            if step == 0 {
                let foreign = pollster::block_on(Renderer::new(None, size.width, size.height))?;
                let foreign_scene = foreign.prepare(&full)?;
                let foreign_lights = foreign.prepare_lighting(&full)?;
                assert!(renderer.prepare_from(&foreign_scene, &full).is_err());
                let mut invalid = full.clone();
                invalid.mesh_assets.insert(
                    "unused-invalid".into(),
                    MeshAsset {
                        vertices: BTreeMap::from([("bad".into(), [f64::NAN, 0., 0.])]),
                        ..Default::default()
                    },
                );
                assert!(renderer.prepare_from(&original_static, &invalid).is_err());
                assert!(
                    renderer
                        .capture_layers(&[&foreign_scene], &camera, &lights, &output)
                        .is_err()
                );
                assert!(
                    renderer
                        .capture_layers(&[&dynamic], &camera, &foreign_lights, &output)
                        .is_err()
                );
                assert!(
                    foreign
                        .profile_layers(&[&foreign_scene], &camera, &foreign_lights)
                        .is_err()
                );
                assert_eq!(fs::read(&output)?, good);
                let mut wrong = full.clone();
                let a = wrong.entities.remove("a").unwrap();
                let b = wrong.entities.remove("b").unwrap();
                wrong.entities.insert("a".into(), b);
                wrong.entities.insert("b".into(), a);
                let path = self.output.join("layers-order-negative.png");
                renderer.capture(&wrong, &path)?;
                assert_ne!(
                    pixels(&path, size)?,
                    image,
                    "fixture must detect ID-order mistakes"
                );
            }
            let mut bad_light = full.clone();
            bad_light.entities.get_mut("a_light").unwrap().content = EntityKind::Light {
                color: [1.; 3],
                intensity: f64::NAN,
            };
            assert!(renderer.prepare_lighting(&bad_light).is_err());
            assert_eq!(fs::read(&output)?, good);
            if step == 1 {
                retained_future = Some((dynamic, camera, lights, image));
            }
        }
        let (future, future_camera, future_lights, future_pixels) =
            retained_future.ok_or("missing future branch")?;
        let path = self.output.join("layers-future-retained.png");
        renderer.capture_layers(
            &[&future, &original_static],
            &future_camera,
            &future_lights,
            &path,
        )?;
        assert_eq!(
            pixels(&path, size)?,
            future_pixels,
            "a later branch must not mutate an earlier future"
        );
        let unchanged = renderer.prepare_from(&original_static, &layer(&before, &["a", "c"], 1))?;
        let path = self.output.join("layers-unchanged-branch.png");
        renderer.capture_layers(
            &[&original_dynamic, &unchanged],
            &original_camera,
            &original_lights,
            &path,
        )?;
        assert_eq!(pixels(&path, size)?, first.as_ref().unwrap().as_slice());
        let path = self.output.join("layers-original-retained.png");
        renderer.capture_layers(
            &[&original_dynamic, &original_static],
            &original_camera,
            &original_lights,
            &path,
        )?;
        assert_eq!(pixels(&path, size)?, first.unwrap());
        // The same immutable geometry also survives a real target resize.
        let original_size = (renderer.width, renderer.height);
        renderer.resize(size.width + 8, size.height + 6);
        let resized = PhysicalSize::new(renderer.width, renderer.height);
        let camera = formora::geometry::camera_view(&before, resized.width, resized.height)?;
        let path = self.output.join("layers-retained-resized.png");
        renderer.capture_layers(
            &[&original_dynamic, &original_static],
            &camera,
            &original_lights,
            &path,
        )?;
        let reference = self.output.join("layers-reference-resized.png");
        renderer.capture(&before, &reference)?;
        assert_eq!(pixels(&path, resized)?, pixels(&reference, resized)?);
        renderer.resize(original_size.0, original_size.1);
        println!(
            "PASS snapshot CPU branches, retained future and full validation; layers: global ID order, shared current lighting, same-revision updates, immutable world poses, old snapshots, annotations, resize, foreign/duplicate rejection and real GPU ticks"
        );
        Ok(())
    }

    fn chunked_buffers(
        &self,
        renderer: &mut Renderer,
        size: PhysicalSize<u32>,
        windowed: bool,
    ) -> Result<()> {
        let scene = scene();
        let original_limit = renderer.vertex_buffer_chunk_limit();
        let reference = self.output.join("chunk-single-reference.png");
        renderer.capture(&scene, &reference)?;
        let expected = pixels(&reference, size)?;
        let old = renderer.prepare(&scene)?;
        assert_eq!(old.vertex_buffer_count(), 1);
        let triangle_bytes = 3 * std::mem::size_of::<formora::geometry::Vertex>() as u64;
        for invalid in [0, triangle_bytes - 1, u64::MAX] {
            assert!(
                renderer
                    .set_vertex_buffer_chunk_limit(Some(invalid))
                    .is_err()
            );
            assert_eq!(renderer.vertex_buffer_chunk_limit(), original_limit);
        }
        renderer.set_vertex_buffer_chunk_limit(Some(triangle_bytes))?;
        let split = renderer.prepare_from(&old, &scene)?;
        assert_eq!(split.vertex_count(), 36);
        assert_eq!(
            split.vertex_buffer_count(),
            12,
            "one actual buffer per source triangle"
        );
        let camera = formora::geometry::camera_view(&scene, size.width, size.height)?;
        let lights = renderer.prepare_lighting(&scene)?;
        let path = self.output.join("chunk-prepared.png");
        renderer.capture_prepared(&split, &camera, &path)?;
        assert_eq!(pixels(&path, size)?, expected);
        renderer.capture(&scene, &self.output.join("chunk-live.png"))?;
        assert_eq!(pixels(&self.output.join("chunk-live.png"), size)?, expected);
        renderer.capture_layers(
            &[&split],
            &camera,
            &lights,
            &self.output.join("chunk-layer.png"),
        )?;
        assert_eq!(
            pixels(&self.output.join("chunk-layer.png"), size)?,
            expected
        );
        renderer.capture_prepared(&old, &camera, &self.output.join("chunk-old-retained.png"))?;
        assert_eq!(
            pixels(&self.output.join("chunk-old-retained.png"), size)?,
            expected
        );
        assert_eq!(old.vertex_buffer_count(), 1);
        if windowed {
            renderer.draw_prepared(&split, &camera)?;
            renderer.draw_layers(&[&split], &camera, &lights)?;
        }
        let empty = Scene::default();
        let no_vertices = renderer.prepare(&empty)?;
        assert_eq!(no_vertices.vertex_count(), 0);
        assert_eq!(no_vertices.vertex_buffer_count(), 0);
        let empty_path = self.output.join("chunk-empty.png");
        renderer.capture_prepared(&no_vertices, no_vertices.camera(), &empty_path)?;
        let clear = rgba(&empty_path, size)?;
        assert!(clear.chunks_exact(4).all(|p| p == &clear[..4]));
        // Repeat all interleaved global mesh/annotation and future-branch checks
        // with real one-triangle GPU buffers. Each reference uses the normal limit.
        self.layers(renderer, size, windowed)?;
        renderer.set_vertex_buffer_chunk_limit(None)?;
        assert_eq!(renderer.vertex_buffer_chunk_limit(), original_limit);
        let joined = renderer.prepare_from(&split, &scene)?;
        assert_eq!(joined.vertex_buffer_count(), 1);
        renderer.capture_prepared(&joined, &camera, &self.output.join("chunk-reset.png"))?;
        assert_eq!(
            pixels(&self.output.join("chunk-reset.png"), size)?,
            expected
        );
        println!(
            "PASS complete triangle GPU chunks:12buffers/36corners,single-vs-chunk pixel parity,old snapshots,policy errors,empty frame,global layered order,resize and prepare_from rechunking"
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
        self.authored_cancellation(renderer, size)?;
        self.layers(renderer, size, windowed)?;
        self.chunked_buffers(renderer, size, windowed)?;
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
            let renderer = pollster::block_on(Renderer::new_profiled(
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
        let mut renderer =
            pollster::block_on(Renderer::new_profiled(None, INITIAL.width, INITIAL.height))?;
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
