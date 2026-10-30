//! A failed derived local getter must not discard a valid committed world.
use formora::objects::Context;
use formora::rotation::{EulerOrder, RotationAngles, TransformRotation};
use formora::scene::{Command, Editor, Entity, EntityKind, Geometry, Scene, Transform};
use formora::session::InspectRequest;
use formora::transforms::{Delta, Precision};
use serde_json::{Value, json};

fn euler(angles: [f64; 3], order: EulerOrder) -> TransformRotation {
    TransformRotation::Authored(RotationAngles::Euler { angles, order })
}

fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.object_context = Some(Context::default());
    scene.entities.insert(
        "parent".into(),
        Entity {
            name: "Parent".into(),
            parent: None,
            transform: Transform {
                translation: [1.25, -0.75, 2.],
                rotation: euler([0.37, -0.23, 0.51], EulerOrder::Xyz),
                scale: [-1.2, 0.7, 0.],
                precision: Precision::F32,
                delta: Delta {
                    translation: [0.125, -0.25, 0.375],
                    ..Delta::default()
                },
            },
            content: EntityKind::Empty,
        },
    );
    scene.entities.insert(
        "target".into(),
        Entity {
            name: "Target".into(),
            parent: Some("parent".into()),
            transform: Transform {
                translation: [0.25, -0.5, 0.75],
                rotation: euler([0.; 3], EulerOrder::Yxz),
                scale: [0.9, 1.4, 0.8],
                precision: Precision::F32,
                delta: Delta {
                    translation: [0.125, -0.25, 0.375],
                    ..Delta::default()
                },
            },
            content: EntityKind::Empty,
        },
    );
    scene.entities.insert(
        "child".into(),
        Entity {
            name: "Child".into(),
            parent: Some("target".into()),
            transform: Transform {
                translation: [0.25, -0.75, 0.5],
                precision: Precision::F32,
                delta: Delta {
                    translation: [-0.25, 0.125, 0.0625],
                    ..Delta::default()
                },
                ..Transform::default()
            },
            content: EntityKind::Mesh {
                geometry: Geometry::Plane { size: [2., 3.] },
                material: None,
            },
        },
    );
    scene.validate().unwrap();
    scene
}

fn world(scene: &Scene) -> Value {
    InspectRequest {
        entity: Some("child".into()),
        world: true,
        ..InspectRequest::default()
    }
    .inspect(scene)
    .unwrap()
}

fn after_quarter_turn() -> Editor {
    let mut editor = Editor::new(scene()).unwrap();
    let mut transform = editor.scene().entities["target"].transform.clone();
    transform.rotation = euler([std::f64::consts::FRAC_PI_2, -0., -0.], EulerOrder::Yxz);
    editor
        .apply(
            &[Command::SetTransform {
                id: "target".into(),
                transform,
            }],
            Some(0),
        )
        .unwrap();
    editor
}

#[test]
fn unavailable_local_query_preserves_the_committed_operation_and_valid_world() {
    let mut editor = after_quarter_turn();
    let committed = editor.scene().clone();
    let value = world(editor.scene());
    assert_eq!(value["revision"], 1);
    assert_eq!(value["id"], "child");
    assert_eq!(value["object_frames"]["matrix_local"], Value::Null);
    assert_eq!(
        value["object_frames"]["matrix_local_error"],
        "cannot_invert"
    );
    let matrix = value["world_matrix"].as_array().unwrap();
    assert_eq!(matrix.len(), 4);
    assert!(
        matrix
            .iter()
            .flat_map(|r| r.as_array().unwrap())
            .all(|v| v.as_f64().unwrap().is_finite())
    );
    let vertices = value["world_vertices"].as_object().unwrap();
    assert_eq!(vertices.len(), 4);
    assert!(
        vertices
            .values()
            .flat_map(|p| p.as_array().unwrap())
            .all(|v| v.as_f64().unwrap().is_finite())
    );
    assert_eq!(editor.scene(), &committed);
    editor.undo(Some(1)).unwrap();
    let mut before = scene();
    before.revision = 2;
    assert_eq!(editor.scene(), &before);
}

#[test]
fn finite_source_zero_fallback_is_still_a_numeric_matrix() {
    let value = world(&scene());
    assert_eq!(value["object_frames"]["matrix_local"], json!([[0.; 4]; 4]));
    assert!(value["object_frames"].get("matrix_local_error").is_none());
}

#[test]
fn available_frame_json_keeps_its_existing_shape_and_missing_ids_still_fail() {
    let mut scene = scene();
    scene.entities.get_mut("parent").unwrap().transform.scale[2] = 1.;
    let value = world(&scene);
    assert!(value["object_frames"]["matrix_local"].is_array());
    assert!(value["object_frames"].get("matrix_local_error").is_none());
    assert!(formora::objects::frames(&scene, "missing").is_err());
    scene.object_context = None;
    assert!(world(&scene).get("object_frames").is_none());
}

#[test]
fn library_local_getter_reports_unavailability_without_an_object_context() {
    let mut scene = after_quarter_turn().scene().clone();
    scene.object_context = None;
    let value = serde_json::to_value(formora::objects::frames(&scene, "child").unwrap()).unwrap();
    assert_eq!(value["matrix_local"], Value::Null);
    assert_eq!(value["matrix_local_error"], "cannot_invert");
    assert!(value["matrix_basis"].is_array());
    assert!(value["matrix_parent_inverse"].is_array());
}
