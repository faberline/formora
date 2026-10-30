//! Preserve the fixed source's exact-zero parent inverse, with no projection.
use formora::objects::{Context, State};
use formora::scene::{Command, Editor, Entity, EntityKind, Geometry, Scene, Transform};
use formora::session::InspectRequest;
use formora::transforms::Precision;
use serde_json::{Value, json};

fn scene() -> Scene {
    let mut scene = Scene {
        object_context: Some(Context {
            order: vec!["target".into(), "child".into()],
            selected: ["target".into()].into(),
            active: Some("target".into()),
            skip_children: true,
            ..Context::default()
        }),
        ..Scene::default()
    };
    scene.entities.insert(
        "target".into(),
        Entity {
            name: "Singular parent".into(),
            parent: None,
            transform: Transform {
                translation: [0.25, -0.5, 0.75],
                scale: [0., 1., 1.],
                precision: Precision::F32,
                ..Transform::default()
            },
            content: EntityKind::Empty,
        },
    );
    scene.entities.insert(
        "child".into(),
        Entity {
            name: "Real child geometry".into(),
            parent: Some("target".into()),
            transform: Transform {
                translation: [1., 2., 3.],
                precision: Precision::F32,
                ..Transform::default()
            },
            content: EntityKind::Mesh {
                geometry: Geometry::Plane { size: [2., 3.] },
                material: None,
            },
        },
    );
    scene
}

fn query(scene: &Scene) -> Value {
    InspectRequest {
        entity: Some("child".into()),
        world: true,
        ..InspectRequest::default()
    }
    .inspect(scene)
    .unwrap()
}

fn command() -> Command {
    serde_json::from_value(json!({"operation":"snap_scene","snap":{
        "action":{"kind":"selected_to_cursor","use_offset":false,"use_rotation":false}}}))
    .unwrap()
}

#[test]
fn exact_zero_parent_inverse_is_persisted_and_queried_without_fabricated_affine_row() {
    let mut scene = scene();
    scene.object_context.as_mut().unwrap().states.insert(
        "child".into(),
        State {
            parent_inverse: Some([[0.; 4]; 4]),
            ..State::default()
        },
    );
    scene.validate().unwrap();
    let value = serde_json::to_value(&scene).unwrap();
    assert_eq!(
        value["object_context"]["states"]["child"]["parent_inverse"],
        json!([
            [0., 0., 0., 0.],
            [0., 0., 0., 0.],
            [0., 0., 0., 0.],
            [0., 0., 0., 0.]
        ])
    );
    let restored: Scene = serde_json::from_value(value).unwrap();
    restored.validate().unwrap();
    assert_eq!(scene, restored);
    let world = query(&restored);
    assert_eq!(
        world["world_matrix"],
        serde_json::to_value([[0.; 4]; 4]).unwrap()
    );
    assert_eq!(
        world["object_frames"]["matrix_local"],
        serde_json::to_value([[0.; 4]; 4]).unwrap()
    );
    assert!(world["object_frames"].get("matrix_local_error").is_none());
    assert_eq!(world["world_vertices"].as_object().unwrap().len(), 4);
    assert!(
        world["world_vertices"]
            .as_object()
            .unwrap()
            .values()
            .all(|p| p == &json!([0., 0., 0.]))
    );
}

#[test]
fn singular_skip_children_keeps_successful_receipts_and_the_actual_source_zero_world() {
    let input = scene();
    input.validate().unwrap();
    let child = input.entities["child"].clone();
    let mut editor = Editor::new(input).unwrap();
    let outcome = editor.apply_with_outcomes(&[command()], Some(0)).unwrap();
    assert_eq!(editor.scene().revision, 1);
    assert_eq!(editor.scene().entities["child"], child);
    let receipt = &outcome.scene_snaps[0];
    assert_eq!(serde_json::to_value(receipt.status).unwrap(), "finished");
    assert!(receipt.meshes.is_empty() && receipt.edit_meshes.is_empty());
    let item = receipt
        .objects
        .iter()
        .find(|item| item.entity == "child")
        .unwrap();
    assert_eq!(item.parent_inverse_before, formora::objects::identity());
    assert_eq!(item.parent_inverse_after, [[0.; 4]; 4]);
    let world = query(editor.scene());
    assert_eq!(
        world["world_matrix"],
        serde_json::to_value([[0.; 4]; 4]).unwrap()
    );
    assert_eq!(
        world["object_frames"]["matrix_parent_inverse"],
        serde_json::to_value([[0.; 4]; 4]).unwrap()
    );
    assert_eq!(editor.scene().revision, 1);
}

#[test]
fn zero_compensation_undo_replay_and_fresh_file_reload_preserve_real_values() {
    let input = scene();
    let mut editor = Editor::new(input.clone()).unwrap();
    editor.apply(&[command()], Some(0)).unwrap();
    let committed = editor.scene().clone();
    editor.undo(Some(1)).unwrap();
    let mut expected = input;
    expected.revision = 2;
    assert_eq!(editor.scene(), &expected);
    editor.apply(&[command()], Some(2)).unwrap();
    let mut expected = committed;
    expected.revision = 3;
    assert_eq!(editor.scene(), &expected);
    let path = std::env::temp_dir().join(format!(
        "formora-zero-parent-{}-{}.json",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    assert!(!path.exists());
    expected.save(&path).unwrap();
    let fresh = Scene::load(&path).unwrap();
    assert_eq!(fresh, expected);
    assert_eq!(query(&fresh), query(&expected));
    std::fs::remove_file(path).unwrap();
}

#[test]
fn projective_near_zero_and_nonfinite_parent_inverses_remain_rejected() {
    let mut invalid = Vec::new();
    let mut projective = formora::objects::identity();
    projective[3] = [0.; 4];
    invalid.push(projective);
    let mut near_zero = [[0.; 4]; 4];
    near_zero[0][0] = 1e-300;
    invalid.push(near_zero);
    for bad in [f64::NAN, f64::INFINITY, 1e300] {
        let mut matrix = formora::objects::identity();
        matrix[0][0] = bad;
        invalid.push(matrix);
    }
    for matrix in invalid {
        let mut scene = scene();
        scene.object_context.as_mut().unwrap().states.insert(
            "child".into(),
            State {
                parent_inverse: Some(matrix),
                ..State::default()
            },
        );
        assert!(scene.validate().is_err());
    }
}
