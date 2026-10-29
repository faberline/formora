use formora::rotation::{EulerOrder, RotationAngles, TransformRotation};
use formora::scene::{Command, Editor, Entity, EntityKind, Scene, Transform};
use formora::transforms::{self, Delta, Precision};

fn euler(angles: [f64; 3]) -> TransformRotation {
    TransformRotation::Authored(RotationAngles::Euler {
        angles,
        order: EulerOrder::Xyz,
    })
}
fn near(a: [f64; 3], b: [f64; 3]) {
    for (a, b) in a.into_iter().zip(b) {
        assert!((a - b).abs() <= 1e-6, "{a} != {b}");
    }
}
fn scene(transform: Transform) -> Scene {
    let mut scene = Scene::default();
    scene.entities.insert(
        "target".into(),
        Entity {
            name: "Target".into(),
            parent: None,
            transform,
            content: EntityKind::Empty,
        },
    );
    scene
}

#[test]
fn identity_keeps_legacy_json_and_signed_zero_delta_is_saved() {
    let old = serde_json::json!({"translation":[0,0,0],"rotation":[0,0,0,1],"scale":[1,1,1]});
    let transform: Transform = serde_json::from_value(old).unwrap();
    assert!(
        serde_json::to_value(&transform)
            .unwrap()
            .get("delta")
            .is_none()
    );
    let mut transform = transform;
    transform.delta.euler[1] = -0.;
    let bytes = serde_json::to_vec(&transform).unwrap();
    let loaded: Transform = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(loaded.delta.euler[1].to_bits(), (-0.0f64).to_bits());
    assert!(!loaded.delta.is_identity());
}

#[test]
fn delta_precedes_normal_rotation_in_both_precisions() {
    for precision in [Precision::F32, Precision::F64] {
        let transform = Transform {
            precision,
            rotation: euler([std::f64::consts::FRAC_PI_2, 0., 0.]),
            delta: Delta {
                euler: [0., 0., std::f64::consts::FRAC_PI_2],
                ..Delta::default()
            },
            ..Transform::default()
        };
        let matrix = transforms::local(&transform).unwrap();
        near(
            transforms::point(matrix, [0., 1., 0.], precision).unwrap(),
            [0., 0., 1.],
        );
        near(
            transforms::point(matrix, [1., 0., 0.], precision).unwrap(),
            [0., 1., 0.],
        );
    }
}

#[test]
fn delta_translation_and_negative_scale_compose_once() {
    for precision in [Precision::F32, Precision::F64] {
        let transform = Transform {
            translation: [1., 2., 3.],
            scale: [2., 3., 4.],
            precision,
            delta: Delta {
                translation: [0.25, -0.5, 1.],
                scale: [-2., 0.5, 3.],
                ..Delta::default()
            },
            ..Transform::default()
        };
        near(
            transforms::point(
                transforms::local(&transform).unwrap(),
                [1., 2., 3.],
                precision,
            )
            .unwrap(),
            [-2.75, 4.5, 40.],
        );
    }
}

#[test]
fn nonunit_signed_delta_keeps_saved_channels_and_legacy_validation() {
    let transform = Transform {
        delta: Delta {
            quaternion_wxyz: [-2., 0., 0., -2.],
            euler: [0.123456789012345, 0., 0.],
            ..Delta::default()
        },
        ..Transform::default()
    };
    let before = transform.clone();
    for precision in [Precision::F32, Precision::F64] {
        let mut transform = transform.clone();
        transform.precision = precision;
        near(
            transforms::point(
                transforms::local(&transform).unwrap(),
                [1., 0., 0.],
                precision,
            )
            .unwrap(),
            [0., 1., 0.],
        );
    }
    assert_eq!(transform, before);
    assert!(!TransformRotation::Quaternion([0., 0., -2., -2.]).valid());
    assert_eq!(
        serde_json::from_slice::<Transform>(&serde_json::to_vec(&transform).unwrap()).unwrap(),
        transform
    );
}

#[test]
fn public_axis_angle_ignores_inactive_delta_rotations() {
    for precision in [Precision::F32, Precision::F64] {
        let transform = Transform {
            precision,
            rotation: TransformRotation::Authored(RotationAngles::AxisAngle {
                axis: [0., 0., 1.],
                radians: std::f64::consts::FRAC_PI_2,
            }),
            delta: Delta {
                euler: [0.4, 0.2, -0.7],
                quaternion_wxyz: [-1., 1., 1., -1.],
                ..Delta::default()
            },
            ..Transform::default()
        };
        near(
            transforms::point(
                transforms::local(&transform).unwrap(),
                [1., 0., 0.],
                precision,
            )
            .unwrap(),
            [0., 1., 0.],
        );
    }
}

#[test]
fn invalid_inactive_delta_and_late_failure_are_atomic() {
    let original = scene(Transform::default());
    let mut invalid = original.clone();
    invalid
        .entities
        .get_mut("target")
        .unwrap()
        .transform
        .delta
        .euler[0] = f64::NAN;
    assert!(invalid.validate().is_err());
    let mut transform = Transform::default();
    transform.delta.translation[0] = 1.;
    let mut editor = Editor::new(original.clone()).unwrap();
    assert!(
        editor
            .apply(
                &[
                    Command::SetTransform {
                        id: "target".into(),
                        transform: transform.clone()
                    },
                    Command::SetTransform {
                        id: "missing".into(),
                        transform
                    },
                ],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &original);
    assert!(editor.undo(Some(0)).is_err());
}

#[test]
fn finite_f64_delta_that_overflows_physical_frame_cannot_publish() {
    let original = scene(Transform::default());
    let mut editor = Editor::new(original.clone()).unwrap();
    let mut transform = Transform::default();
    transform.translation[0] = 1e308;
    transform.delta.translation[0] = 1e308;
    assert!(
        editor
            .apply(
                &[Command::SetTransform {
                    id: "target".into(),
                    transform
                }],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &original);
    assert!(editor.undo(Some(0)).is_err());
}

#[test]
fn direct_snap_sets_normal_channels_without_removing_delta_and_replays() {
    use formora::mesh::{creation::AuthoringContext, snap::Action, transform::Pivot};
    use formora::objects::{Context, State, snap::Request};
    let mut original = scene(Transform {
        precision: Precision::F32,
        translation: [2., 3., 4.],
        rotation: euler([0.1, 0.2, 0.3]),
        delta: Delta {
            translation: [0.125, -0.25, 0.375],
            euler: [0., 0., std::f64::consts::FRAC_PI_2],
            quaternion_wxyz: [-2., 0., 0., -2.],
            ..Delta::default()
        },
        ..Transform::default()
    });
    let mut context = Context {
        selected: ["target".into()].into_iter().collect(),
        active: Some("target".into()),
        ..Context::default()
    };
    context.states.insert(
        "target".into(),
        State {
            lock_location: [true, false, false],
            ..State::default()
        },
    );
    original.object_context = Some(context);
    original.authoring_context = Some(AuthoringContext::default());
    let command = Command::SnapScene {
        snap: Box::new(Request {
            action: Action::SelectedToCursor {
                use_offset: false,
                use_rotation: true,
            },
            pivot: Pivot::Median,
            max_components: 100,
            max_objects: 10,
        }),
    };
    let mut editor = Editor::new(original.clone()).unwrap();
    let receipt = editor
        .apply_with_outcomes(&[command.clone()], Some(0))
        .unwrap();
    let actual = &editor.scene().entities["target"].transform;
    assert_eq!(actual.rotation, euler([0., 0., 0.]));
    assert_eq!(actual.delta, original.entities["target"].transform.delta);
    assert_eq!(actual.translation, [2., 0.25, -0.375]);
    near(
        transforms::point(
            transforms::world(editor.scene(), "target").unwrap(),
            [1., 0., 0.],
            Precision::F32,
        )
        .unwrap(),
        [2.125, 1., 0.],
    );
    assert_eq!(receipt.scene_snaps[0].objects.len(), 1);
    assert_eq!(receipt.scene_snaps[0].objects[0].transform_after, *actual);
    let saved = editor.scene().clone();
    assert_eq!(
        serde_json::from_slice::<Scene>(&serde_json::to_vec(&saved).unwrap()).unwrap(),
        saved
    );
    editor.undo(Some(saved.revision)).unwrap();
    let revision = editor.scene().revision;
    editor.apply(&[command], Some(revision)).unwrap();
    let mut replay = editor.scene().clone();
    replay.revision = saved.revision;
    assert_eq!(replay, saved);
}
