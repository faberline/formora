#![cfg(feature = "headless")]
use formora::geometry::{self, GeometryCache, Vertex};
use formora::mesh::selection::{Domain, Editing, FaceRef};
use formora::mesh::{MeshAsset, Polygon, Triangle};
use formora::scene::{Annotation, Entity, EntityKind, Geometry, Material, Scene, Transform};
use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

fn triangle(vertices: [&str; 3]) -> Triangle {
    Triangle {
        corner_colors: None,
        vertices: vertices.map(str::to_owned),
        uv_layers: BTreeMap::new(),
        corner_normals: None,
        material_slot: Some(0),
    }
}

fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.materials.insert(
        "paint".into(),
        Material {
            base_color: [0.7, 0.2, 0.0, 1.0],
            roughness: 0.6,
            metallic: 0.0,
        },
    );
    let asset = MeshAsset {
        edges: BTreeMap::from([
            ("e0".into(), ["a".into(), "b".into()]),
            ("e1".into(), ["b".into(), "c".into()]),
            ("e2".into(), ["c".into(), "d".into()]),
            ("e3".into(), ["d".into(), "a".into()]),
        ]),
        vertices: BTreeMap::from([
            ("a".into(), [-1.0, -1.0, 0.0]),
            ("b".into(), [1.0, -1.0, 0.0]),
            ("c".into(), [1.0, 1.0, 0.0]),
            ("d".into(), [-1.0, 1.0, 0.0]),
            ("top".into(), [0.0, 0.0, 2.0]),
        ]),
        triangles: BTreeMap::from([
            ("t0".into(), triangle(["a", "b", "top"])),
            ("t1".into(), triangle(["b", "c", "top"])),
            ("t2".into(), triangle(["c", "d", "top"])),
            ("t3".into(), triangle(["d", "a", "top"])),
        ]),
        polygons: BTreeMap::from([(
            "base".into(),
            Polygon {
                corner_colors: None,
                vertices: ["a", "d", "c", "b"].map(str::to_owned).into(),
                uv_layers: BTreeMap::new(),
                corner_normals: None,
                normal: None,
                smooth: false,
                material_slot: Some(0),
            },
        )]),
        material_slots: vec![Some("paint".into())],
        smooth_triangles: BTreeSet::from(["t0".into(), "t1".into()]),
        ..MeshAsset::default()
    };
    scene.mesh_assets.insert("shape".into(), asset);
    scene.entities.insert(
        "parent".into(),
        Entity {
            name: "Parent".into(),
            parent: None,
            transform: Transform {
                translation: [3.0, 4.0, 5.0],
                scale: [2.0, 1.0, 1.0],
                ..Transform::default()
            },
            content: EntityKind::Empty,
        },
    );
    scene.entities.insert(
        "mesh".into(),
        Entity {
            name: "Mesh".into(),
            parent: Some("parent".into()),
            transform: Transform {
                translation: [1.0, 0.0, 0.0],
                rotation: [0.0, 0.0, 0.3826834323650898, 0.9238795325112867].into(),
                ..Transform::default()
            },
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "shape".into() },
                material: None,
            },
        },
    );
    let mut other = scene.entities["mesh"].clone();
    other.parent = None;
    other.transform.translation = [-4.0, 0.0, 0.0];
    scene.entities.insert("other".into(), other);
    scene.entities.insert(
        "cube".into(),
        Entity {
            name: "Primitive".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Cube {
                    size: [1.0, 2.0, 3.0],
                },
                material: Some("paint".into()),
            },
        },
    );
    scene
}

fn reference(scene: &Scene, cache: &mut GeometryCache) -> Arc<Vec<Vertex>> {
    let before = serde_json::to_vec(scene).unwrap();
    let expected = geometry::vertices(scene).unwrap();
    let observed = cache.vertices(scene).unwrap();
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(&expected),
        bytemuck::cast_slice::<Vertex, u8>(observed.as_slice())
    );
    assert_eq!(before, serde_json::to_vec(scene).unwrap());
    observed
}

#[test]
fn cache_warm_snapshot_is_reused_and_caller_copy_cannot_change_it() {
    let scene = scene();
    let mut cache = GeometryCache::default();
    let first = reference(&scene, &mut cache);
    let warm = reference(&scene, &mut cache);
    assert!(Arc::ptr_eq(&first, &warm));
    let mut edited = Arc::clone(&first);
    Arc::make_mut(&mut edited)[0].position[0] += 100.0;
    let after = reference(&scene, &mut cache);
    assert!(Arc::ptr_eq(&first, &after));
    assert_ne!(edited[0].position, after[0].position);
}

#[test]
fn cache_same_revision_geometry_material_parent_and_transform_updates_match_legacy_bits() {
    let mut scene = scene();
    let mut cache = GeometryCache::default();
    reference(&scene, &mut cache);
    scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .vertices
        .get_mut("top")
        .unwrap()[2] = 2.5;
    reference(&scene, &mut cache);
    scene.materials.get_mut("paint").unwrap().base_color = [0.0, 0.2, 0.7, 1.0];
    reference(&scene, &mut cache);
    scene.entities.get_mut("mesh").unwrap().parent = None;
    reference(&scene, &mut cache);
    scene.entities.get_mut("mesh").unwrap().transform.scale = [-1.0, 0.0, 2.0];
    reference(&scene, &mut cache);
    scene
        .entities
        .get_mut("parent")
        .unwrap()
        .transform
        .translation = [5.0, -2.0, 4.0];
    scene.entities.get_mut("other").unwrap().parent = Some("parent".into());
    reference(&scene, &mut cache);
    scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .polygons
        .get_mut("base")
        .unwrap()
        .normal = Some([0.0, 0.0, -1.0]);
    reference(&scene, &mut cache);
    scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .triangles
        .get_mut("t0")
        .unwrap()
        .corner_normals = Some([[0.0, 0.0, 1.0]; 3]);
    reference(&scene, &mut cache);
    assert_eq!(scene.revision, 0);
}

#[test]
fn cache_signed_zero_in_positions_authored_normals_and_materials_invalidates() {
    let mut scene = scene();
    let mut cache = GeometryCache::default();
    let first = reference(&scene, &mut cache);
    let original = scene.mesh_assets["shape"].clone();
    scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .vertices
        .get_mut("a")
        .unwrap()[2] = -0.0;
    assert_eq!(original, scene.mesh_assets["shape"]);
    let changed = reference(&scene, &mut cache);
    assert!(!Arc::ptr_eq(&first, &changed));
    scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .triangles
        .get_mut("t0")
        .unwrap()
        .corner_normals = Some([[0.0, 0.0, 1.0]; 3]);
    let before = reference(&scene, &mut cache);
    scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .triangles
        .get_mut("t0")
        .unwrap()
        .corner_normals
        .as_mut()
        .unwrap()[0][0] = -0.0;
    let after = reference(&scene, &mut cache);
    assert!(!Arc::ptr_eq(&before, &after));
    let original = scene.materials["paint"].clone();
    let before = reference(&scene, &mut cache);
    scene.materials.get_mut("paint").unwrap().base_color[2] = -0.0;
    assert_eq!(original, scene.materials["paint"]);
    let after = reference(&scene, &mut cache);
    assert!(!Arc::ptr_eq(&before, &after));
}

#[test]
fn cache_camera_and_light_updates_do_not_rebuild_static_vertex_data() {
    let mut scene = scene();
    let mut cache = GeometryCache::default();
    let before = reference(&scene, &mut cache);
    scene.entities.insert(
        "camera".into(),
        Entity {
            name: "Camera".into(),
            parent: None,
            transform: Transform {
                translation: [0.0, 0.0, 15.0],
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
    scene.entities.insert(
        "light".into(),
        Entity {
            name: "Light".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Light {
                color: [1.0; 3],
                intensity: 100.0,
            },
        },
    );
    let after = reference(&scene, &mut cache);
    assert!(Arc::ptr_eq(&before, &after));
    scene
        .entities
        .get_mut("camera")
        .unwrap()
        .transform
        .translation[0] = 1.0;
    let after = reference(&scene, &mut cache);
    assert!(Arc::ptr_eq(&before, &after));
}

#[test]
fn cache_parent_inverse_and_f32_authored_transform_changes_match_legacy() {
    let mut scene = scene();
    let mut cache = GeometryCache::default();
    reference(&scene, &mut cache);
    let mut inverse = formora::objects::identity();
    inverse[0][3] = -2.0;
    scene.object_context = Some(formora::objects::Context {
        states: BTreeMap::from([(
            "mesh".into(),
            formora::objects::State {
                parent_inverse: Some(inverse),
                ..Default::default()
            },
        )]),
        ..Default::default()
    });
    reference(&scene, &mut cache);
    scene.entities.get_mut("mesh").unwrap().transform.precision =
        formora::transforms::Precision::F32;
    reference(&scene, &mut cache);
    scene
        .object_context
        .as_mut()
        .unwrap()
        .states
        .get_mut("mesh")
        .unwrap()
        .parent_inverse
        .as_mut()
        .unwrap()[1][3] = 1.25;
    reference(&scene, &mut cache);
}

#[test]
fn camera_view_matches_full_ancestry_and_does_not_claim_full_scene_validation() {
    let mut scene = scene();
    scene.entities.insert(
        "view".into(),
        Entity {
            name: "View".into(),
            parent: Some("mesh".into()),
            transform: Transform {
                translation: [0.25, 0.5, 12.0],
                ..Transform::default()
            },
            content: EntityKind::Camera {
                vertical_fov_degrees: 50.0,
                near: 0.1,
                far: 100.0,
            },
        },
    );
    scene.active_camera = Some("view".into());
    let mut inverse = formora::objects::identity();
    inverse[0][3] = 0.125;
    scene.object_context = Some(formora::objects::Context {
        states: BTreeMap::from([(
            "view".into(),
            formora::objects::State {
                parent_inverse: Some(inverse),
                ..Default::default()
            },
        )]),
        ..Default::default()
    });
    let full = geometry::camera(&scene, 319, 211).unwrap();
    let narrow = geometry::camera_view(&scene, 319, 211).unwrap();
    assert_eq!(
        full.position.to_array().map(f64::to_bits),
        narrow.position.to_array().map(f64::to_bits)
    );
    assert_eq!(
        full.view_projection.to_cols_array().map(f64::to_bits),
        narrow.view_projection.to_cols_array().map(f64::to_bits)
    );
    scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .vertices
        .remove("a");
    assert!(geometry::camera(&scene, 319, 211).is_err());
    assert!(geometry::camera_view(&scene, 319, 211).is_ok());
    assert!(geometry::camera_view(&scene, 0, 211).is_err());
    scene.entities.get_mut("view").unwrap().parent = Some("view".into());
    assert!(geometry::camera_view(&scene, 319, 211).is_err());
}

#[test]
fn cache_edit_selection_hidden_faces_camera_markers_and_annotations_match_legacy() {
    let mut scene = scene();
    let mut cache = GeometryCache::default();
    reference(&scene, &mut cache);
    let mut editing = Editing::default();
    editing.selected.vertices.insert("a".into());
    scene.mesh_assets.get_mut("shape").unwrap().editing = Some(editing);
    reference(&scene, &mut cache);
    scene.entities.insert(
        "camera".into(),
        Entity {
            name: "Camera".into(),
            parent: None,
            transform: Transform {
                translation: [0.0, 0.0, 15.0],
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
    reference(&scene, &mut cache);
    let editing = scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .editing
        .as_mut()
        .unwrap();
    editing.mode = BTreeSet::from([Domain::Face]);
    editing.selected.vertices.clear();
    editing
        .selected
        .faces
        .insert(FaceRef::Triangle("t0".into()));
    editing.hidden.faces.insert(FaceRef::Polygon("base".into()));
    let faces = reference(&scene, &mut cache);
    assert!(Arc::ptr_eq(&faces, &reference(&scene, &mut cache)));
    let editing = scene
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .editing
        .as_mut()
        .unwrap();
    editing.preview = false;
    editing.mode = BTreeSet::from([Domain::Vertex]);
    editing.selected.faces.clear();
    editing.selected.vertices.insert("a".into());
    let disabled = reference(&scene, &mut cache);
    scene
        .entities
        .get_mut("camera")
        .unwrap()
        .transform
        .translation[0] += 1.0;
    assert!(Arc::ptr_eq(&disabled, &reference(&scene, &mut cache)));
    scene.annotations.push(Annotation {
        entity: None,
        position: [0.0, 0.0, 3.0],
        text: "Here".into(),
    });
    reference(&scene, &mut cache);
    scene.annotations[0].position[0] = -0.0;
    reference(&scene, &mut cache);
    scene.annotations.clear();
    reference(&scene, &mut cache);
}

#[test]
fn cache_rejects_invalid_inputs_and_recovers_after_geometry_errors_and_id_reuse() {
    let mut scene = scene();
    let mut cache = GeometryCache::default();
    let first = reference(&scene, &mut cache);
    let valid = scene.clone();
    scene.entities.get_mut("mesh").unwrap().parent = Some("missing".into());
    assert!(cache.vertices(&scene).is_err());
    scene = valid.clone();
    reference(&scene, &mut cache);
    scene
        .entities
        .get_mut("cube")
        .unwrap()
        .transform
        .translation[0] = f64::MAX / 8.0;
    assert!(geometry::vertices(&scene).is_err());
    assert!(cache.vertices(&scene).is_err());
    scene = valid.clone();
    let recovered = reference(&scene, &mut cache);
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(first.as_slice()),
        bytemuck::cast_slice::<Vertex, u8>(recovered.as_slice())
    );
    let mesh = scene.entities.remove("mesh").unwrap();
    reference(&scene, &mut cache);
    let mut replacement = mesh;
    replacement.transform.translation = [6.0, 2.0, 1.0];
    scene.entities.insert("mesh".into(), replacement);
    reference(&scene, &mut cache);
    let mut invalid = MeshAsset::default();
    invalid
        .triangles
        .insert("bad".into(), triangle(["missing", "also_missing", "no"]));
    scene.mesh_assets.insert("unused".into(), invalid);
    assert!(cache.vertices(&scene).is_err());
    scene.mesh_assets.remove("unused");
    reference(&scene, &mut cache);
}

#[test]
#[ignore = "performance test; execute only in CI"]
fn cache_benchmark_256() {
    use std::time::Instant;
    let mut scene = Scene::default();
    let mut asset = MeshAsset {
        material_slots: vec![None],
        ..MeshAsset::default()
    };
    asset.vertices.insert("top".into(), [0.0, 0.0, 2.0]);
    for i in 0..189 {
        let angle = (i as f64) * std::f64::consts::TAU / 189.0;
        asset
            .vertices
            .insert(format!("v{i}"), [angle.cos(), angle.sin(), 0.0]);
        asset.triangles.insert(
            format!("t{i}"),
            Triangle {
                corner_colors: None,
                vertices: ["top".into(), format!("v{i}"), format!("v{}", (i + 1) % 189)],
                uv_layers: BTreeMap::new(),
                corner_normals: None,
                material_slot: None,
            },
        );
    }
    scene.mesh_assets.insert("tree".into(), asset);
    for i in 0..256 {
        scene.entities.insert(
            format!("tree{i}"),
            Entity {
                name: "Repeated tree".into(),
                parent: None,
                transform: Transform {
                    translation: [(i % 16) as f64 * 3.0, (i / 16) as f64 * 3.0, 0.0],
                    ..Transform::default()
                },
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id: "tree".into() },
                    material: None,
                },
            },
        );
    }
    let mut cache = GeometryCache::default();
    let start = Instant::now();
    let expected = geometry::vertices(&scene).unwrap();
    let cold_legacy = start.elapsed().as_secs_f64() * 1000.0;
    let start = Instant::now();
    let actual = cache.vertices(&scene).unwrap();
    let cold_cache = start.elapsed().as_secs_f64() * 1000.0;
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(&expected),
        bytemuck::cast_slice::<Vertex, u8>(actual.as_slice())
    );
    for _ in 0..3 {
        reference(&scene, &mut cache);
    }
    let mut legacy = Vec::new();
    let mut warm = Vec::new();
    for _ in 0..8 {
        let start = Instant::now();
        let expected = geometry::vertices(std::hint::black_box(&scene)).unwrap();
        legacy.push(start.elapsed().as_secs_f64() * 1000.0);
        let start = Instant::now();
        let actual = cache.vertices(std::hint::black_box(&scene)).unwrap();
        warm.push(start.elapsed().as_secs_f64() * 1000.0);
        assert_eq!(expected.len(), 145152);
        assert_eq!(
            bytemuck::cast_slice::<Vertex, u8>(&expected),
            bytemuck::cast_slice::<Vertex, u8>(actual.as_slice())
        );
    }
    let median = |values: &[f64]| {
        let mut values = values.to_vec();
        values.sort_by(f64::total_cmp);
        (values[3] + values[4]) / 2.0
    };
    let ratio = median(&warm) / median(&legacy);
    println!(
        "{}",
        serde_json::json!({"entities":256,"asset_triangles":189,"vertices":145152,"cold_legacy_ms":cold_legacy,"cold_cache_ms":cold_cache,"legacy_ms":legacy,"warm_ms":warm,"median_ratio":ratio,"limit":0.25,"scope":"CPU preparation only; not GPU or full-frame acceptance"})
    );
    assert!(
        ratio <= 0.25,
        "warm preparation median exceeded fixed 25% ratio: {ratio}"
    );
}

#[test]
fn warm_validation_matches_full_scene_errors_and_recovers() {
    for case in 0..17 {
        let original = scene();
        let mut changed = original.clone();
        let mut cache = GeometryCache::default();
        let old = reference(&original, &mut cache);
        match case {
            0 => {
                changed
                    .mesh_assets
                    .get_mut("shape")
                    .unwrap()
                    .vertices
                    .get_mut("top")
                    .unwrap()[0] = f64::NAN
            }
            1 => {
                changed
                    .mesh_assets
                    .get_mut("shape")
                    .unwrap()
                    .triangles
                    .get_mut("t0")
                    .unwrap()
                    .uv_layers
                    .insert("uv".into(), [[f64::NAN, 0.]; 3]);
            }
            2 => {
                changed
                    .mesh_assets
                    .get_mut("shape")
                    .unwrap()
                    .triangles
                    .get_mut("t0")
                    .unwrap()
                    .corner_normals = Some([[0., 0., 2.]; 3])
            }
            3 => {
                changed
                    .mesh_assets
                    .get_mut("shape")
                    .unwrap()
                    .triangles
                    .get_mut("t0")
                    .unwrap()
                    .corner_colors = Some([[-1., 0., 0., 1.]; 3])
            }
            4 => {
                changed
                    .mesh_assets
                    .get_mut("shape")
                    .unwrap()
                    .triangles
                    .get_mut("t0")
                    .unwrap()
                    .material_slot = Some(99)
            }
            5 => {
                changed
                    .mesh_assets
                    .get_mut("shape")
                    .unwrap()
                    .triangles
                    .get_mut("t0")
                    .unwrap()
                    .vertices[0] = "missing".into()
            }
            6 => {
                changed.mesh_assets.get_mut("shape").unwrap().editing = Some(Editing {
                    selected: formora::mesh::selection::Elements {
                        vertices: BTreeSet::from(["missing".into()]),
                        ..Default::default()
                    },
                    ..Default::default()
                })
            }
            7 => {
                let EntityKind::Mesh { material, .. } =
                    &mut changed.entities.get_mut("mesh").unwrap().content
                else {
                    unreachable!()
                };
                *material = Some("missing".into());
            }
            8 => {
                changed
                    .entities
                    .get_mut("mesh")
                    .unwrap()
                    .transform
                    .translation[0] = f64::INFINITY
            }
            9 => {
                changed.entities.get_mut("parent").unwrap().content = EntityKind::Light {
                    color: [f64::NAN, 0., 0.],
                    intensity: 1.,
                };
            }
            10 => changed.active_camera = Some("missing".into()),
            11 => changed.entities.get_mut("parent").unwrap().parent = Some("mesh".into()),
            12 => {
                let mut unused = original.mesh_assets["shape"].clone();
                unused.vertices.get_mut("top").unwrap()[1] = f64::NAN;
                changed.mesh_assets.insert("unused".into(), unused);
            }
            13 => {
                changed.mesh_assets.remove("shape");
            }
            14 => changed.schema_version = 999,
            15 => changed.time_seconds = -1.,
            16 => {
                changed.materials.remove("paint");
            }
            _ => unreachable!(),
        }
        let expected = changed.validate().unwrap_err().to_string();
        assert_eq!(
            cache.vertices(&changed).err().unwrap().to_string(),
            expected,
            "case {case}"
        );
        assert_eq!(changed.revision, original.revision);
        let recovered = reference(&original, &mut cache);
        assert_eq!(
            bytemuck::cast_slice::<Vertex, u8>(old.as_slice()),
            bytemuck::cast_slice::<Vertex, u8>(recovered.as_slice())
        );
    }
}

#[test]
fn validation_key_includes_uv_bits_and_metadata_without_mutating_old_vertices() {
    let mut source = scene();
    let face = source
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .triangles
        .get_mut("t0")
        .unwrap();
    face.uv_layers.insert("uv".into(), [[0., 0.]; 3]);
    let mut cache = GeometryCache::default();
    let first = reference(&source, &mut cache);
    let before = bytemuck::cast_slice::<Vertex, u8>(first.as_slice()).to_vec();
    source
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .triangles
        .get_mut("t0")
        .unwrap()
        .uv_layers
        .get_mut("uv")
        .unwrap()[0][0] = -0.0;
    let changed = reference(&source, &mut cache);
    assert!(!Arc::ptr_eq(&first, &changed));
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(changed.as_slice()),
        before
    );
    source
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .diagnostics
        .push("explicit_source_marker".into());
    let metadata = reference(&source, &mut cache);
    assert!(!Arc::ptr_eq(&changed, &metadata));
    assert_eq!(bytemuck::cast_slice::<Vertex, u8>(first.as_slice()), before);
    assert_eq!(source.revision, 0);
}

#[test]
fn recipe_and_vertex_weight_assets_retain_full_validation_and_recovery() {
    for recipe in [false, true] {
        let mut scene = scene();
        let asset = scene.mesh_assets.get_mut("shape").unwrap();
        if recipe {
            asset.recipe = Some(formora::mesh::primitives::PrimitiveRecipe {
                primitive: serde_json::from_value(
                    serde_json::json!({"kind":"plane","size":2.,"calc_uvs":false}),
                )
                .unwrap(),
                max_components: 1000,
                edited: true,
                creation_frame: None,
            });
        } else {
            asset.vertex_groups = vec!["pin".into()];
            asset.vertex_weights =
                Some(formora::mesh::selection::VertexWeights(BTreeMap::from([(
                    "top".into(),
                    formora::mesh::selection::GroupWeights(BTreeMap::from([("pin".into(), 0.5)])),
                )])));
        }
        let valid = scene.clone();
        let mut cache = GeometryCache::default();
        reference(&scene, &mut cache);
        reference(&scene, &mut cache);
        let asset = scene.mesh_assets.get_mut("shape").unwrap();
        if recipe {
            asset.recipe.as_mut().unwrap().max_components = 0;
        } else {
            asset
                .vertex_weights
                .as_mut()
                .unwrap()
                .0
                .get_mut("top")
                .unwrap()
                .0
                .insert("pin".into(), f64::NAN);
        }
        let expected = scene.validate().unwrap_err().to_string();
        assert_eq!(cache.vertices(&scene).err().unwrap().to_string(), expected);
        reference(&valid, &mut cache);
    }
}

#[test]
#[ignore = "performance test; execute only in CI"]
fn cache_validation_benchmark_32_assets() {
    use std::time::Instant;
    let mut scene = Scene::default();
    for i in 0..32 {
        let id = format!("asset{i}");
        let asset = MeshAsset {
            vertices: BTreeMap::from([
                ("a".into(), [0., 0., 0.]),
                ("b".into(), [1., 0., 0.]),
                ("c".into(), [0., 1., 0.]),
            ]),
            triangles: (0..2048)
                .map(|face| {
                    (
                        format!("t{face}"),
                        Triangle {
                            vertices: ["a", "b", "c"].map(str::to_owned),
                            uv_layers: BTreeMap::new(),
                            corner_normals: Some([[0., 0., 1.]; 3]),
                            corner_colors: None,
                            material_slot: None,
                        },
                    )
                })
                .collect(),
            ..Default::default()
        };
        scene.mesh_assets.insert(id.clone(), asset);
        scene.entities.insert(
            format!("object{i}"),
            Entity {
                name: "Independent asset".into(),
                parent: None,
                transform: Transform::default(),
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id },
                    material: None,
                },
            },
        );
    }
    let mut cache = GeometryCache::default();
    let start = Instant::now();
    let first = reference(&scene, &mut cache);
    let cold_reference_and_prepare_ms = start.elapsed().as_secs_f64() * 1000.;
    assert_eq!(first.len(), 196608);
    for _ in 0..3 {
        cache.vertices(&scene).unwrap();
    }
    let mut full_plus_warm = Vec::new();
    let mut cached = Vec::new();
    for pair in 0..8 {
        for cached_only in if pair % 2 == 0 {
            [false, true]
        } else {
            [true, false]
        } {
            let start = Instant::now();
            if !cached_only {
                std::hint::black_box(&scene).validate().unwrap();
            }
            let vertices = cache.vertices(std::hint::black_box(&scene)).unwrap();
            let ms = start.elapsed().as_secs_f64() * 1000.;
            assert!(Arc::ptr_eq(&first, &vertices));
            if cached_only {
                cached.push(ms);
            } else {
                full_plus_warm.push(ms);
            }
        }
    }
    let median = |samples: &[f64]| {
        let mut s = samples.to_vec();
        s.sort_by(f64::total_cmp);
        (s[3] + s[4]) / 2.
    };
    let ratio = median(&cached) / median(&full_plus_warm);
    println!(
        "{}",
        serde_json::json!({"assets":32,"triangles_per_asset":2048,"vertices":196608,
        "cold_reference_and_prepare_ms":cold_reference_and_prepare_ms,"full_validation_plus_warm_ms":full_plus_warm,
        "cached_preparation_ms":cached,"median_ratio":ratio,"limit":0.75,
        "scope":"CPU cached preparation vs additional full Scene validation plus cached preparation; not old source, GPU or full frame"})
    );
    assert!(
        ratio <= 0.75,
        "cached preparation exceeded fixed 75% ratio: {ratio}"
    );
}

#[test]
fn cache_branches_survive_eviction_and_keep_every_old_snapshot() {
    let scene = scene();
    let mut base = GeometryCache::default();
    let original = reference(&scene, &mut base);
    let old_bytes = bytemuck::cast_slice::<Vertex, u8>(original.as_slice()).to_vec();
    let saved = base.clone();
    let mut unrelated = Scene::default();
    unrelated.entities.insert(
        "unrelated".into(),
        Entity {
            name: "Other".into(),
            parent: None,
            transform: Default::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Cube { size: [3.; 3] },
                material: None,
            },
        },
    );
    reference(&unrelated, &mut base);
    let mut same = saved.clone();
    assert!(Arc::ptr_eq(&original, &reference(&scene, &mut same)));
    assert!(!Arc::ptr_eq(&original, &reference(&scene, &mut base)));
    let mut first_scene = scene.clone();
    first_scene
        .entities
        .get_mut("mesh")
        .unwrap()
        .transform
        .translation[0] += 0.125;
    let mut first = saved.clone();
    let first_vertices = reference(&first_scene, &mut first);
    let first_bytes = bytemuck::cast_slice::<Vertex, u8>(first_vertices.as_slice()).to_vec();
    let mut second_scene = scene.clone();
    second_scene.materials.get_mut("paint").unwrap().base_color = [0.1, 0.9, 0.2, 0.5];
    let mut second = saved.clone();
    reference(&second_scene, &mut second);
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(original.as_slice()),
        old_bytes
    );
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(first_vertices.as_slice()),
        first_bytes
    );
    assert!(Arc::ptr_eq(
        &first_vertices,
        &reference(&first_scene, &mut first)
    ));
    assert!(Arc::ptr_eq(&original, &reference(&scene, &mut same)));
    assert_eq!(first_scene.revision, scene.revision);
    assert_eq!(second_scene.revision, scene.revision);
}

#[test]
fn cache_branch_invalid_input_and_signed_zero_do_not_corrupt_the_base() {
    let scene = scene();
    let mut base = GeometryCache::default();
    let original = reference(&scene, &mut base);
    let mut branch = base.clone();
    let mut bad = scene.clone();
    bad.mesh_assets.insert(
        "unused".into(),
        MeshAsset {
            vertices: BTreeMap::from([("bad".into(), [f64::NAN, 0., 0.])]),
            ..Default::default()
        },
    );
    assert_eq!(
        branch.vertices(&bad).err().unwrap().0,
        bad.validate().unwrap_err().0
    );
    assert!(Arc::ptr_eq(&original, &reference(&scene, &mut base)));
    reference(&scene, &mut branch);
    let mut changed = scene.clone();
    changed
        .mesh_assets
        .get_mut("shape")
        .unwrap()
        .vertices
        .get_mut("a")
        .unwrap()[2] = -0.;
    let updated = reference(&changed, &mut branch);
    assert!(!Arc::ptr_eq(&updated, &original));
    assert!(Arc::ptr_eq(&original, &reference(&scene, &mut base)));
    assert_eq!(changed.revision, scene.revision);
}

#[test]
#[ignore = "performance test; execute only in CI"]
fn cache_snapshot_branch_benchmark_256() {
    use std::time::Instant;
    // The same public 256-instance/189-face fixture as the original benchmark.
    let mut scene = Scene::default();
    let mut asset = MeshAsset {
        material_slots: vec![None],
        ..Default::default()
    };
    asset.vertices.insert("top".into(), [0., 0., 2.]);
    for i in 0..189 {
        let angle = (i as f64) * std::f64::consts::TAU / 189.;
        asset
            .vertices
            .insert(format!("v{i}"), [angle.cos(), angle.sin(), 0.]);
        asset.triangles.insert(
            format!("t{i}"),
            Triangle {
                corner_colors: None,
                vertices: ["top".into(), format!("v{i}"), format!("v{}", (i + 1) % 189)],
                uv_layers: BTreeMap::new(),
                corner_normals: None,
                material_slot: None,
            },
        );
    }
    scene.mesh_assets.insert("tree".into(), asset);
    for i in 0..256 {
        scene.entities.insert(
            format!("tree{i}"),
            Entity {
                name: "Repeated tree".into(),
                parent: None,
                transform: Transform {
                    translation: [(i % 16) as f64 * 3., (i / 16) as f64 * 3., 0.],
                    ..Default::default()
                },
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id: "tree".into() },
                    material: None,
                },
            },
        );
    }
    let mut base = GeometryCache::default();
    let start = Instant::now();
    reference(&scene, &mut base);
    let cold_reference_and_prepare_ms = start.elapsed().as_secs_f64() * 1000.;
    let mut changed = scene.clone();
    changed
        .entities
        .get_mut("tree0")
        .unwrap()
        .transform
        .translation[0] += 0.125;
    let expected = geometry::vertices(&changed).unwrap();
    assert_eq!(expected.len(), 145152);
    let dynamic = Scene::default();
    let branch = || {
        let start = Instant::now();
        let mut cache = base.clone();
        let clone_ms = start.elapsed().as_secs_f64() * 1000.;
        let actual = cache.vertices(std::hint::black_box(&changed)).unwrap();
        (actual, clone_ms, start.elapsed().as_secs_f64() * 1000.)
    };
    let evicted = || {
        let mut cache = base.clone();
        let eviction = Instant::now();
        cache.vertices(&dynamic).unwrap();
        let eviction_ms = eviction.elapsed().as_secs_f64() * 1000.;
        let start = Instant::now();
        let actual = cache.vertices(std::hint::black_box(&changed)).unwrap();
        (actual, eviction_ms, start.elapsed().as_secs_f64() * 1000.)
    };
    let verify = |data: &Arc<Vec<Vertex>>| {
        assert_eq!(
            bytemuck::cast_slice::<Vertex, u8>(data.as_slice()),
            bytemuck::cast_slice::<Vertex, u8>(&expected)
        )
    };
    for _ in 0..3 {
        verify(&branch().0);
        verify(&evicted().0);
    }
    let mut branch_ms = Vec::new();
    let mut clone_ms = Vec::new();
    let mut evicted_ms = Vec::new();
    let mut eviction_ms = Vec::new();
    for i in 0..8 {
        let (a, b) = if i % 2 == 0 {
            (branch(), evicted())
        } else {
            let b = evicted();
            let a = branch();
            (a, b)
        };
        verify(&a.0);
        verify(&b.0);
        branch_ms.push(a.2);
        clone_ms.push(a.1);
        evicted_ms.push(b.2);
        eviction_ms.push(b.1);
    }
    let median = |values: &[f64]| {
        let mut v = values.to_vec();
        v.sort_by(f64::total_cmp);
        (v[3] + v[4]) / 2.
    };
    let ratio = median(&branch_ms) / median(&evicted_ms);
    println!(
        "{}",
        serde_json::json!({"entities":256,"asset_triangles":189,"vertices":145152,
        "warmups":3,"pairs":8,"alternate_order":true,"cold_reference_and_prepare_ms":cold_reference_and_prepare_ms,
        "branch_clone_plus_prepare_ms":branch_ms,"clone_ms":clone_ms,"evicted_cache_prepare_ms":evicted_ms,
        "eviction_setup_ms":eviction_ms,"median_ratio":ratio,"limit":0.25,
        "scope":"CPU cache branch preparation only; not GPU, full-frame or FPS acceptance"})
    );
    assert!(
        ratio <= 0.25,
        "branch median exceeded fixed25% ratio: {ratio}"
    );
}

#[test]
#[ignore = "performance test; execute only in CI"]
fn store_transform_benchmark_32_assets() {
    use formora::scene_store::{SceneStore, SceneUpdate};
    use std::time::Instant;
    let mut scene = Scene::default();
    for i in 0..32 {
        let id = format!("asset{i}");
        let asset = MeshAsset {
            vertices: BTreeMap::from([
                ("a".into(), [0., 0., 0.]),
                ("b".into(), [1., 0., 0.]),
                ("c".into(), [0., 1., 0.]),
            ]),
            triangles: (0..2048)
                .map(|face| {
                    (
                        format!("t{face}"),
                        Triangle {
                            vertices: ["a", "b", "c"].map(str::to_owned),
                            uv_layers: BTreeMap::new(),
                            corner_normals: Some([[0., 0., 1.]; 3]),
                            corner_colors: None,
                            material_slot: None,
                        },
                    )
                })
                .collect(),
            ..Default::default()
        };
        scene.mesh_assets.insert(id.clone(), asset);
        scene.entities.insert(
            format!("object{i}"),
            Entity {
                name: "Independent asset".into(),
                parent: None,
                transform: Transform::default(),
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id },
                    material: None,
                },
            },
        );
    }

    let start = Instant::now();
    let mut store = SceneStore::new(scene.clone()).unwrap();
    let mut owned = GeometryCache::default();
    let first = owned.vertices_store(&store).unwrap();
    let cold_store_construct_prepare_ms = start.elapsed().as_secs_f64() * 1000.;
    let mut raw = GeometryCache::default();
    let start = Instant::now();
    let reference = raw.vertices(&scene).unwrap();
    let cold_raw_prepare_ms = start.elapsed().as_secs_f64() * 1000.;
    assert_eq!(first.len(), 196608);
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(&first),
        bytemuck::cast_slice::<Vertex, u8>(&reference)
    );
    let mut raw_ms = Vec::new();
    let mut owned_ms = Vec::new();
    for pair in 0..11 {
        let transform = Transform {
            translation: [pair as f64 * 0.01, 0., 0.],
            ..Default::default()
        };
        let mut outputs = Vec::new();
        for is_owned in if pair % 2 == 0 {
            [false, true]
        } else {
            [true, false]
        } {
            let start = Instant::now();
            let vertices = if is_owned {
                store
                    .apply(SceneUpdate {
                        transforms: BTreeMap::from([("object0".into(), transform.clone())]),
                        ..Default::default()
                    })
                    .unwrap();
                owned.vertices_store(&store).unwrap()
            } else {
                scene.entities.get_mut("object0").unwrap().transform = transform.clone();
                raw.vertices(&scene).unwrap()
            };
            let elapsed = start.elapsed().as_secs_f64() * 1000.;
            if pair >= 3 {
                if is_owned {
                    owned_ms.push(elapsed);
                } else {
                    raw_ms.push(elapsed);
                }
            }
            outputs.push(vertices);
        }
        assert_eq!(
            bytemuck::cast_slice::<Vertex, u8>(&outputs[0]),
            bytemuck::cast_slice::<Vertex, u8>(&outputs[1])
        );
        assert_eq!(store.scene().revision, scene.revision);
    }
    let median = |samples: &[f64]| {
        let mut sorted = samples.to_vec();
        sorted.sort_by(f64::total_cmp);
        (sorted[3] + sorted[4]) / 2.
    };
    let ratio = median(&owned_ms) / median(&raw_ms);
    println!(
        "{}",
        serde_json::json!({"assets":32,"triangles_per_asset":2048,"vertices":196608,"warmups":3,"alternating_pairs":8,"cold_store_construct_prepare_ms":cold_store_construct_prepare_ms,"cold_raw_prepare_ms":cold_raw_prepare_ms,"raw_transform_prepare_ms":raw_ms,"store_atomic_transform_prepare_ms":owned_ms,"median_ratio":ratio,"limit":0.25,"scope":"complete atomic entity transform update plus cached CPU frame; bitwise parity each pair; not FF total frame or GPU acceptance"})
    );
    assert!(
        ratio <= 0.25,
        "owned preparation exceeded fixed 25% ratio: {ratio}"
    );
}

#[test]
#[ignore = "performance test; execute only in CI"]
fn store_world_benchmark_32_assets() {
    use formora::scene_store::{SceneStore, SceneUpdate};
    use std::time::Instant;
    let mut scene = Scene::default();
    for i in 0..32 {
        let id = format!("asset{i}");
        let asset = MeshAsset {
            vertices: BTreeMap::from([
                ("a".into(), [0., 0., 0.]),
                ("b".into(), [1., 0., 0.]),
                ("c".into(), [0., 1., 0.]),
            ]),
            triangles: (0..2048)
                .map(|face| {
                    (
                        format!("t{face}"),
                        Triangle {
                            vertices: ["a", "b", "c"].map(str::to_owned),
                            uv_layers: BTreeMap::new(),
                            corner_normals: Some([[0., 0., 1.]; 3]),
                            corner_colors: None,
                            material_slot: None,
                        },
                    )
                })
                .collect(),
            ..Default::default()
        };
        scene.mesh_assets.insert(id.clone(), asset);
        scene.entities.insert(
            format!("object{i}"),
            Entity {
                name: "Independent asset".into(),
                parent: None,
                transform: Transform::default(),
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id },
                    material: None,
                },
            },
        );
    }

    let bits = |world: BTreeMap<String, glam::DMat4>| {
        world
            .into_iter()
            .map(|(id, matrix)| (id, matrix.to_cols_array().map(f64::to_bits)))
            .collect::<BTreeMap<_, _>>()
    };
    let start = Instant::now();
    let mut store = SceneStore::new(scene.clone()).unwrap();
    let cold_store_construct_ms = start.elapsed().as_secs_f64() * 1000.;
    let start = Instant::now();
    let first = geometry::world_transforms_store(&store).unwrap();
    let cold_owned_query_ms = start.elapsed().as_secs_f64() * 1000.;
    let start = Instant::now();
    let raw = geometry::world_transforms(&scene).unwrap();
    let cold_raw_query_ms = start.elapsed().as_secs_f64() * 1000.;
    assert_eq!(first.len(), 32);
    assert_eq!(bits(first), bits(raw));
    let mut raw_ms = Vec::new();
    let mut owned_ms = Vec::new();
    let mut raw_update_ms = Vec::new();
    let mut store_update_ms = Vec::new();
    for pair in 0..11 {
        let transform = Transform {
            translation: [pair as f64 * 0.01, -0., 0.],
            ..Default::default()
        };
        let start = Instant::now();
        store
            .apply(SceneUpdate {
                transforms: BTreeMap::from([("object0".into(), transform.clone())]),
                ..Default::default()
            })
            .unwrap();
        let update = start.elapsed().as_secs_f64() * 1000.;
        let start = Instant::now();
        scene.entities.get_mut("object0").unwrap().transform = transform;
        let raw_update = start.elapsed().as_secs_f64() * 1000.;
        if pair >= 3 {
            store_update_ms.push(update);
            raw_update_ms.push(raw_update);
        }
        let mut outputs = Vec::new();
        for owned in if pair % 2 == 0 {
            [false, true]
        } else {
            [true, false]
        } {
            let start = Instant::now();
            let world = if owned {
                geometry::world_transforms_store(std::hint::black_box(&store)).unwrap()
            } else {
                geometry::world_transforms(std::hint::black_box(&scene)).unwrap()
            };
            let elapsed = start.elapsed().as_secs_f64() * 1000.;
            if pair >= 3 {
                if owned {
                    owned_ms.push(elapsed);
                } else {
                    raw_ms.push(elapsed);
                }
            }
            outputs.push(bits(world));
        }
        assert_eq!(outputs[0], outputs[1]);
        assert_eq!(store.scene().revision, scene.revision);
    }
    let median = |samples: &[f64]| {
        let mut sorted = samples.to_vec();
        sorted.sort_by(f64::total_cmp);
        (sorted[3] + sorted[4]) / 2.
    };
    let ratio = median(&owned_ms) / median(&raw_ms);
    println!(
        "{}",
        serde_json::json!({"assets":32,"triangles_per_asset":2048,"world_matrices":32,"warmups":3,"alternating_pairs":8,"cold_store_construct_ms":cold_store_construct_ms,"cold_owned_query_ms":cold_owned_query_ms,"cold_raw_query_ms":cold_raw_query_ms,"raw_world_query_ms":raw_ms,"owned_world_query_ms":owned_ms,"raw_update_ms":raw_update_ms,"store_atomic_update_ms":store_update_ms,"median_ratio":ratio,"limit":0.10,"scope":"native f64 world queries only; bitwise matrix parity each pair; cold/updates separate and must be charged by host; not FF1.10ms input/pick or fullframe acceptance"})
    );
    assert!(
        ratio <= 0.10,
        "owned world query exceeded fixed 10% ratio: {ratio}"
    );
}
