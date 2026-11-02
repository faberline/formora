#![cfg(feature = "headless")]
use formora::headless::{DebugRequest, diagnose};
use formora::scene::{Entity, EntityKind, Geometry, Material, Scene, Transform};
use serde_json::Value;

fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.materials.insert(
        "paint".into(),
        Material {
            base_color: [0.7, 0.2, 0.1, 1.0],
            roughness: 0.6,
            metallic: 0.0,
        },
    );
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
        "box".into(),
        Entity {
            name: "Box".into(),
            parent: Some("parent".into()),
            transform: Transform {
                translation: [1.0, 0.0, 0.0],
                ..Transform::default()
            },
            content: EntityKind::Mesh {
                geometry: Geometry::Cube { size: [2.0; 3] },
                material: Some("paint".into()),
            },
        },
    );
    scene
}

fn request() -> DebugRequest {
    DebugRequest {
        geometry: true,
        include_world: true,
        ..DebugRequest::default()
    }
}
fn status<'a>(report: &'a Value, name: &str) -> &'a str {
    report["checks"]
        .as_array()
        .unwrap()
        .iter()
        .find(|c| c["name"] == name)
        .unwrap()["status"]
        .as_str()
        .unwrap()
}

#[test]
fn empty_scene_and_unrequested_geometry_are_explicit() {
    let report = diagnose(&Scene::default(), &DebugRequest::default());
    assert_eq!(report["passed"], true);
    assert_eq!(report["mode"], "headless_cpu");
    assert_eq!(status(&report, "geometry"), "not_requested");
    assert!(report["geometry"].is_null());
    let full = diagnose(&Scene::default(), &request());
    assert_eq!(full["geometry"]["vertices"], 0);
    assert!(full["geometry"]["bounds"].is_null());
}

#[test]
fn world_matrices_and_render_bounds_include_parent_transform() {
    let scene = scene();
    let before = scene.clone();
    let report = diagnose(&scene, &request());
    assert_eq!(report["passed"], true);
    assert_eq!(
        report["world_matrices"]["box"],
        serde_json::json!([
            [2.0, 0.0, 0.0, 5.0],
            [0.0, 1.0, 0.0, 4.0],
            [0.0, 0.0, 1.0, 5.0],
            [0.0, 0.0, 0.0, 1.0]
        ])
    );
    assert_eq!(report["geometry"]["vertices"], 36);
    assert_eq!(report["geometry"]["triangles"], 12);
    assert_eq!(
        report["geometry"]["bounds"]["min"],
        serde_json::json!([3.0, 3.0, 4.0])
    );
    assert_eq!(
        report["geometry"]["bounds"]["max"],
        serde_json::json!([7.0, 5.0, 6.0])
    );
    assert_eq!(scene, before);
}

#[test]
fn digests_repeat_and_detect_same_revision_material_geometry_and_transform_changes() {
    let mut scene = scene();
    let first = diagnose(&scene, &request());
    let repeat = diagnose(&scene, &request());
    for key in ["scene_sha256", "world_sha256", "geometry"] {
        assert_eq!(first[key], repeat[key]);
    }
    scene.materials.get_mut("paint").unwrap().base_color = [0.1, 0.2, 0.7, 1.0];
    let color = diagnose(&scene, &request());
    assert_eq!(first["world_sha256"], color["world_sha256"]);
    assert_ne!(first["scene_sha256"], color["scene_sha256"]);
    assert_ne!(first["geometry"]["sha256"], color["geometry"]["sha256"]);
    let EntityKind::Mesh { geometry, .. } = &mut scene.entities.get_mut("box").unwrap().content
    else {
        unreachable!()
    };
    *geometry = Geometry::Cube {
        size: [4.0, 2.0, 2.0],
    };
    let shape = diagnose(&scene, &request());
    assert_ne!(color["geometry"]["sha256"], shape["geometry"]["sha256"]);
    scene
        .entities
        .get_mut("parent")
        .unwrap()
        .transform
        .translation[0] += 1.0;
    let moved = diagnose(&scene, &request());
    assert_ne!(shape["world_sha256"], moved["world_sha256"]);
    assert_eq!(first["revision"], moved["revision"]);
}

#[test]
fn invalid_scene_and_zero_dimensions_fail_before_dependent_checks() {
    let mut scene = scene();
    scene.entities.get_mut("box").unwrap().parent = Some("missing".into());
    let invalid = diagnose(&scene, &request());
    assert_eq!(invalid["passed"], false);
    assert_eq!(status(&invalid, "validation"), "failed");
    assert_eq!(status(&invalid, "transforms"), "skipped");
    assert_eq!(status(&invalid, "geometry"), "skipped");
    let zero = diagnose(
        &scene,
        &DebugRequest {
            width: 0,
            ..request()
        },
    );
    assert_eq!(zero["passed"], false);
    assert_eq!(status(&zero, "request"), "failed");
    assert_eq!(status(&zero, "validation"), "skipped");
}

#[test]
fn f32_projection_failure_is_reported_and_does_not_modify_source() {
    let mut scene = scene();
    scene
        .entities
        .get_mut("parent")
        .unwrap()
        .transform
        .translation[0] = f64::MAX / 8.0;
    let before = scene.clone();
    let report = diagnose(&scene, &request());
    assert_eq!(report["passed"], false);
    assert_eq!(status(&report, "validation"), "passed");
    assert_eq!(status(&report, "geometry"), "failed");
    assert_eq!(scene, before);
    scene
        .entities
        .get_mut("parent")
        .unwrap()
        .transform
        .translation[0] = 3.0;
    assert_eq!(diagnose(&scene, &request())["passed"], true);
}

#[test]
fn singular_camera_is_a_camera_failure_and_world_output_is_optional() {
    let mut scene = scene();
    scene.entities.insert(
        "camera".into(),
        Entity {
            name: "Camera".into(),
            parent: None,
            transform: Transform {
                scale: [0.0, 1.0, 1.0],
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
    let report = diagnose(&scene, &request());
    assert_eq!(report["passed"], false);
    assert_eq!(status(&report, "camera"), "failed");
    assert_eq!(status(&report, "geometry"), "skipped");
    scene.active_camera = None;
    scene.entities.remove("camera");
    let compact = diagnose(&scene, &DebugRequest::default());
    let full = diagnose(&scene, &request());
    assert!(compact["world_matrices"].is_null());
    assert_eq!(compact["world_sha256"], full["world_sha256"]);
}
