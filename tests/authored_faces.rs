#![cfg(feature = "headless")]
use formora::geometry::{self, GeometryCache, Vertex};
use formora::mesh::{MeshAsset, Triangle};
use formora::scene::{Entity, EntityKind, Geometry, Scene, Transform};
use std::collections::BTreeMap;
use std::sync::Arc;

fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.mesh_assets.insert(
        "mesh".into(),
        MeshAsset {
            vertices: BTreeMap::from([
                ("a".into(), [1., 1., 0.]),
                ("b".into(), [0., 0., 0.]),
                ("c".into(), [1. / (1_u64 << 60) as f64, 0., 0.]),
            ]),
            triangles: BTreeMap::from([(
                "face".into(),
                Triangle {
                    vertices: ["a", "b", "c"].map(str::to_owned),
                    uv_layers: BTreeMap::new(),
                    corner_normals: Some([[0., 0., 1.]; 3]),
                    corner_colors: Some([[1., 0., 0., 1.], [0., 1., 0., 1.], [0., 0., 1., 1.]]),
                    material_slot: None,
                },
            )]),
            ..Default::default()
        },
    );
    scene.entities.insert(
        "object".into(),
        Entity {
            name: "Object".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "mesh".into() },
                material: None,
            },
        },
    );
    scene
}

fn check(scene: &Scene, cache: &mut GeometryCache) -> Arc<Vec<Vertex>> {
    let before = serde_json::to_vec(scene).unwrap();
    let direct = geometry::vertices(scene).unwrap();
    let cached = cache.vertices(scene).unwrap();
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(&direct),
        bytemuck::cast_slice::<Vertex, u8>(cached.as_slice())
    );
    assert_eq!(serde_json::to_vec(scene).unwrap(), before);
    cached
}

#[test]
fn authored_normals_keep_binary_fraction_face_when_first_origin_cross_cancels() {
    let scene = scene();
    let points = &scene.mesh_assets["mesh"].vertices;
    let a = points["a"];
    let b = points["b"];
    let c = points["c"];
    // The exact signed 2D area is c.x = 2^-60, but subtracting from A
    // rounds both B-A and C-A to the identical pair (-1,-1).
    assert_eq!(b[0] - a[0], c[0] - a[0]);
    assert_eq!(b[1] - a[1], c[1] - a[1]);
    assert_ne!(c[0] as f32, b[0] as f32);
    let vertices = check(&scene, &mut GeometryCache::default());
    assert_eq!(vertices.len(), 3);
    for (i, id) in ["a", "b", "c"].iter().enumerate() {
        assert_eq!(
            vertices[i].position.map(f32::to_bits),
            points[*id].map(|n| (n as f32).to_bits())
        );
        assert_eq!(vertices[i].normal, [0., 0., 1.]);
        assert_eq!(
            vertices[i].color,
            scene.mesh_assets["mesh"].triangles["face"]
                .corner_colors
                .unwrap()[i]
                .map(|n| n as f32)
        );
    }
}

#[test]
fn coincident_authored_corners_stay_in_gpu_stream_and_singular_normals_still_skip() {
    let mut scene = scene();
    scene
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .vertices
        .insert("c".into(), [0., 0., 0.]);
    let mut cache = GeometryCache::default();
    assert_eq!(check(&scene, &mut cache).len(), 3);
    scene.entities.get_mut("object").unwrap().transform.scale = [0.; 3];
    assert!(check(&scene, &mut cache).is_empty());
    scene.entities.get_mut("object").unwrap().transform.scale = [1.; 3];
    assert_eq!(check(&scene, &mut cache).len(), 3);
}

#[test]
fn same_revision_normal_changes_do_not_mutate_retained_snapshot() {
    let mut scene = scene();
    let mut cache = GeometryCache::default();
    let first = check(&scene, &mut cache);
    assert_eq!(first.len(), 3);
    scene
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .triangles
        .get_mut("face")
        .unwrap()
        .corner_normals = Some([[0.; 3]; 3]);
    assert!(check(&scene, &mut cache).is_empty());
    assert_eq!(first.len(), 3);
    scene
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .triangles
        .get_mut("face")
        .unwrap()
        .corner_normals = Some([[0., 0., 1.]; 3]);
    let recovered = check(&scene, &mut cache);
    assert_eq!(
        bytemuck::cast_slice::<Vertex, u8>(first.as_slice()),
        bytemuck::cast_slice::<Vertex, u8>(recovered.as_slice())
    );
    assert_eq!(scene.revision, 0);
}

#[test]
fn ordinary_faces_and_missing_normal_fallback_keep_expected_attributes() {
    let mut scene = scene();
    let asset = scene.mesh_assets.get_mut("mesh").unwrap();
    asset.vertices.insert("a".into(), [1., 0., 0.]);
    asset.vertices.insert("b".into(), [0., 1., 0.]);
    asset.vertices.insert("c".into(), [0., 0., 0.]);
    asset.triangles.get_mut("face").unwrap().corner_normals = None;
    let vertices = check(&scene, &mut GeometryCache::default());
    assert_eq!(vertices.len(), 3);
    assert!(vertices.iter().all(|v| v.normal == [0., 0., 1.]));
    assert_eq!(
        scene.mesh_assets["mesh"].triangles["face"].corner_normals,
        None
    );
}

#[test]
fn analytic_camera_can_expand_the_retained_f32_face_to_visible_area() {
    let mut scene = scene();
    scene.entities.insert(
        "camera_parent".into(),
        Entity {
            name: "Camera parent".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Empty,
        },
    );
    scene.entities.insert(
        "camera".into(),
        Entity {
            name: "Camera".into(),
            parent: Some("camera_parent".into()),
            transform: Transform {
                translation: [0., 0., 6.],
                ..Default::default()
            },
            content: EntityKind::Camera {
                vertical_fov_degrees: 50.,
                near: 0.1,
                far: 100.,
            },
        },
    );
    scene.active_camera = Some("camera".into());
    scene.object_context = Some(formora::objects::Context {
        states: BTreeMap::from([(
            "camera".into(),
            formora::objects::State {
                parent_inverse: Some([
                    [1. / (1_u64 << 60) as f64, 2., 0., 0.],
                    [0., 2., 0., 0.],
                    [0., 0., 1., 0.],
                    [0., 0., 0., 1.],
                ]),
                ..Default::default()
            },
        )]),
        ..Default::default()
    });
    let camera = geometry::camera(&scene, 320, 240).unwrap();
    let vertices = check(&scene, &mut GeometryCache::default());
    let points: Vec<_> = vertices
        .iter()
        .map(|v| {
            let clip = camera.view_projection.as_mat4()
                * glam::Vec4::from_array([v.position[0], v.position[1], v.position[2], 1.]);
            clip.truncate() / clip.w
        })
        .collect();
    assert_eq!(points.len(), 3);
    assert!(points.iter().all(|p| p.is_finite()
        && p.x.abs() <= 1.
        && p.y.abs() <= 1.
        && p.z >= 0.
        && p.z <= 1.));
    assert!((points[1] - points[0]).cross(points[2] - points[0]).z.abs() > 0.01);
}
