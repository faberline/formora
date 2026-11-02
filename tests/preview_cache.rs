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
