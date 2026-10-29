use formora::mesh::{creation::AuthoringContext, snap::Action, transform::Pivot};
use formora::objects::{Context, State, snap::Request};
use formora::rotation::{Channels, Mode, RotationAngles, TransformRotation};
use formora::scene::{Command, Editor, Entity, EntityKind, Geometry, Scene, Transform};
use formora::transforms::Precision;
use std::collections::BTreeSet;

fn channels(mode: Mode) -> Channels {
    Channels {
        mode,
        euler: [0.2, -0.4, 0.6],
        quaternion_wxyz: [0.5, -0.5, 0.5, 0.5],
        axis_angle: [0.65, -2., 1., 3.],
    }
}
fn rotation(channels: Channels) -> TransformRotation {
    TransformRotation::Authored(RotationAngles::Channels { channels })
}
fn scene(object: Channels, cursor: Channels) -> Scene {
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(),serde_json::from_value(serde_json::json!({
        "vertices":{"a":[1,0,0],"b":[0,1,0],"c":[0,0,1]},
        "triangles":{},"material_slots":[],"editing":{},
        "edges":{"ab":["a","b"],"ac":["a","c"],"bc":["b","c"]},
        "polygons":{"face":{"vertices":["a","b","c"],"material_slot":null,"smooth":false,"uv_layers":{}}}
    })).unwrap());
    for id in ["target", "linked"] {
        scene.entities.insert(
            id.into(),
            Entity {
                name: id.into(),
                parent: None,
                transform: Transform {
                    rotation: rotation(object),
                    precision: Precision::F32,
                    ..Transform::default()
                },
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id: "mesh".into() },
                    material: None,
                },
            },
        );
    }
    scene.object_context = Some(Context {
        order: vec!["target".into(), "linked".into()],
        selected: BTreeSet::from(["target".into()]),
        active: Some("target".into()),
        ..Context::default()
    });
    scene.authoring_context = Some(AuthoringContext {
        cursor_orientation: Some(cursor),
        cursor_rotation: cursor.euler,
        ..AuthoringContext::default()
    });
    scene
}
fn snap(action: Action) -> Command {
    Command::SnapScene {
        snap: Box::new(Request {
            action,
            pivot: Pivot::Median,
            max_components: 100,
            max_objects: 10,
        }),
    }
}
fn selected() -> Command {
    snap(Action::SelectedToCursor {
        use_offset: false,
        use_rotation: true,
    })
}
fn stored(scene: &Scene) -> Channels {
    match scene.entities["target"].transform.rotation {
        TransformRotation::Authored(RotationAngles::Channels { channels }) => channels,
        _ => panic!("raw channels were replaced"),
    }
}

#[test]
fn explicit_raw_storage_does_not_relax_legacy_unit_quaternion_validation() {
    let raw = channels(Mode::Quaternion);
    let mut raw = raw;
    raw.quaternion_wxyz = [0.8, -0.5, 0., 0.6];
    assert!(rotation(raw).valid());
    assert!(!TransformRotation::Quaternion([-0.5, 0., 0.6, 0.8]).valid());
    let value = serde_json::to_value(rotation(raw)).unwrap();
    assert_eq!(
        serde_json::from_value::<TransformRotation>(value.clone()).unwrap(),
        rotation(raw)
    );
    let mut invalid = value;
    invalid["channels"]["answer"] = serde_json::json!([1, 2, 3]);
    assert!(serde_json::from_value::<TransformRotation>(invalid).is_err());
}

#[test]
fn raw_quaternion_quarter_turn_preserves_inactive_channels_and_shared_asset() {
    let object = channels(Mode::Quaternion);
    let mut cursor = object;
    cursor.quaternion_wxyz = [
        std::f64::consts::FRAC_1_SQRT_2,
        0.,
        0.,
        std::f64::consts::FRAC_1_SQRT_2,
    ];
    let mut s = scene(object, cursor);
    s.entities.get_mut("target").unwrap().transform.rotation = rotation(Channels {
        euler: [0.12345678901234567, -0.2, 0.3],
        ..object
    });
    let old = stored(&s);
    let asset = s.mesh_assets["mesh"].clone();
    let linked = s.entities["linked"].clone();
    let mut editor = Editor::new(s).unwrap();
    let result = editor.apply_with_outcomes(&[selected()], Some(0)).unwrap();
    let next = stored(editor.scene());
    assert_eq!(next.euler, old.euler);
    assert_eq!(next.axis_angle, old.axis_angle);
    assert_eq!(
        next.quaternion_wxyz,
        cursor.quaternion_wxyz.map(|v| f64::from(v as f32))
    );
    let world = formora::transforms::world(editor.scene(), "target").unwrap();
    let p = formora::transforms::point(world, [1., 0., 0.], Precision::F32).unwrap();
    assert!(p[0].abs() <= 1e-6 && (p[1] - 1.).abs() <= 1e-6 && p[2].abs() <= 1e-6);
    assert_eq!(editor.scene().mesh_assets["mesh"], asset);
    assert_eq!(editor.scene().entities["linked"], linked);
    assert_eq!(result.scene_snaps[0].objects.len(), 1);
    assert_eq!(result.scene_snaps[0].objects[0].entity, "target");
}

#[test]
fn partial_locks_store_nonunit_raw_quaternion_and_survive_undo_replay() {
    let object = channels(Mode::Quaternion);
    let mut cursor = object;
    cursor.quaternion_wxyz = [0.8, 0., 0., 0.6];
    let mut s = scene(object, cursor);
    s.object_context.as_mut().unwrap().states.insert(
        "target".into(),
        State {
            lock_rotation: [true, false, false],
            lock_rotations_4d: true,
            ..State::default()
        },
    );
    let mut editor = Editor::new(s.clone()).unwrap();
    editor.apply(&[selected()], Some(0)).unwrap();
    let after = editor.scene().clone();
    let q = stored(&after).quaternion_wxyz;
    assert_eq!(q, [f64::from(0.8f32), -0.5, 0., f64::from(0.6f32)]);
    assert!(q.iter().map(|v| v * v).sum::<f64>() > 1.2);
    assert!(after.validate().is_ok());
    assert_eq!(
        serde_json::from_slice::<Scene>(&serde_json::to_vec(&after).unwrap()).unwrap(),
        after
    );
    editor.undo(Some(1)).unwrap();
    let mut restored = editor.scene().clone();
    restored.revision = 0;
    assert_eq!(restored, s);
    let revision = editor.scene().revision;
    editor.apply(&[selected()], Some(revision)).unwrap();
    let mut replay = editor.scene().clone();
    replay.revision = after.revision;
    assert_eq!(replay, after);
}

#[test]
fn legacy_partial_quaternion_assignment_promotes_explicit_raw_state() {
    let object = channels(Mode::Quaternion);
    let mut cursor = object;
    cursor.quaternion_wxyz = [0.8, 0., 0., 0.6];
    let mut s = scene(object, cursor);
    s.entities.get_mut("target").unwrap().transform.rotation =
        TransformRotation::Quaternion([-0.5, 0.5, 0.5, 0.5]);
    s.object_context.as_mut().unwrap().states.insert(
        "target".into(),
        State {
            lock_rotation: [true, false, false],
            ..State::default()
        },
    );
    let mut editor = Editor::new(s).unwrap();
    editor.apply(&[selected()], Some(0)).unwrap();
    assert_eq!(
        stored(editor.scene()).quaternion_wxyz,
        [f64::from(0.8f32), -0.5, 0., f64::from(0.6f32)]
    );
}

#[test]
fn w_lock_is_separate_from_xyz_and_ui_flag_does_not_change_setter() {
    let object = channels(Mode::Quaternion);
    let mut cursor = object;
    cursor.quaternion_wxyz = [0.8, 0., 0., 0.6];
    let mut outputs = Vec::new();
    for flag in [false, true] {
        let mut s = scene(object, cursor);
        s.object_context.as_mut().unwrap().states.insert(
            "target".into(),
            State {
                lock_rotation_w: true,
                lock_rotations_4d: flag,
                ..State::default()
            },
        );
        let mut e = Editor::new(s).unwrap();
        e.apply(&[selected()], Some(0)).unwrap();
        outputs.push(stored(e.scene()));
    }
    assert_eq!(outputs[0], outputs[1]);
    assert_eq!(outputs[0].quaternion_wxyz, [0.5, 0., 0., f64::from(0.6f32)]);
}

#[test]
fn axis_angle_angle_and_axis_locks_preserve_raw_nonunit_axis() {
    let object = channels(Mode::AxisAngle);
    let mut cursor = object;
    cursor.axis_angle = [1.2, 3., 4., -2.];
    let mut s = scene(object, cursor);
    s.object_context.as_mut().unwrap().states.insert(
        "target".into(),
        State {
            lock_rotation: [true, false, false],
            lock_rotation_w: true,
            ..State::default()
        },
    );
    let mut e = Editor::new(s).unwrap();
    e.apply(&[selected()], Some(0)).unwrap();
    assert_eq!(stored(e.scene()).axis_angle, [0.65, -2., 4., -2.]);
    assert_eq!(stored(e.scene()).euler, object.euler);
}

#[test]
fn cursor_origin_clears_only_the_active_representation_for_all_modes() {
    for mode in [
        Mode::Xyz,
        Mode::Xzy,
        Mode::Yxz,
        Mode::Yzx,
        Mode::Zxy,
        Mode::Zyx,
        Mode::Quaternion,
        Mode::AxisAngle,
    ] {
        let input = channels(mode);
        let mut s = scene(input, input);
        s.authoring_context.as_mut().unwrap().cursor_location = [1., 2., 3.];
        let assets = s.mesh_assets.clone();
        let entities = s.entities.clone();
        let mut e = Editor::new(s).unwrap();
        let r = e
            .apply_with_outcomes(&[snap(Action::CursorToCenter {})], Some(0))
            .unwrap();
        let context = e.scene().authoring_context.as_ref().unwrap();
        let after = context.cursor_orientation.unwrap();
        assert_eq!(after.mode, mode);
        assert_eq!(context.cursor_location, [0.; 3]);
        assert!(r.scene_snaps[0].cursor_changed);
        if mode == Mode::Quaternion {
            assert_eq!(after.quaternion_wxyz, [1., 0., 0., 0.]);
            assert_eq!(after.euler, input.euler);
            assert_eq!(after.axis_angle, input.axis_angle);
        } else if mode == Mode::AxisAngle {
            assert_eq!(after.axis_angle, [0., 0., 1., 0.]);
            assert_eq!(after.euler, input.euler);
            assert_eq!(after.quaternion_wxyz, input.quaternion_wxyz);
        } else {
            assert_eq!(after.euler, [0.; 3]);
            assert_eq!(after.quaternion_wxyz, input.quaternion_wxyz);
            assert_eq!(after.axis_angle, input.axis_angle);
        }
        assert_eq!(e.scene().entities, entities);
        assert_eq!(e.scene().mesh_assets, assets);
        let query = formora::session::InspectRequest::default()
            .inspect(e.scene())
            .unwrap();
        for row in 0..4 {
            for col in 0..4 {
                let expected = if row == col { 1. } else { 0. };
                assert!(
                    (query["cursor_matrix"][row][col].as_f64().unwrap() - expected).abs() <= 1e-6
                );
            }
        }
    }
}

#[test]
fn disabled_rotation_preserves_complete_raw_state_and_real_receipts() {
    let object = channels(Mode::Quaternion);
    let cursor = channels(Mode::AxisAngle);
    let mut s = scene(object, cursor);
    s.authoring_context.as_mut().unwrap().cursor_location = [2., 3., 4.];
    let mut e = Editor::new(s).unwrap();
    let result = e
        .apply_with_outcomes(
            &[snap(Action::SelectedToCursor {
                use_offset: false,
                use_rotation: false,
            })],
            Some(0),
        )
        .unwrap();
    assert_eq!(stored(e.scene()), object);
    assert_eq!(
        e.scene().entities["target"].transform.translation,
        [2., 3., 4.]
    );
    assert!(!result.scene_snaps[0].cursor_changed);
    assert_eq!(
        result.scene_snaps[0].cursor_orientation_before,
        Some(cursor)
    );
    assert_eq!(result.scene_snaps[0].cursor_orientation_after, Some(cursor));
}

#[test]
fn late_failure_stale_revision_and_source_range_are_atomic() {
    let input = channels(Mode::Quaternion);
    let s = scene(input, input);
    let mut e = Editor::new(s.clone()).unwrap();
    assert!(
        e.apply(
            &[
                selected(),
                Command::DeleteEntity {
                    id: "missing".into()
                }
            ],
            Some(0)
        )
        .is_err()
    );
    assert_eq!(e.scene(), &s);
    assert!(e.apply(&[selected()], Some(4)).is_err());
    assert_eq!(e.scene(), &s);
    let mut context = s.authoring_context.clone().unwrap();
    context.cursor_orientation = Some(Channels {
        quaternion_wxyz: [1e200, 0., 0., 0.],
        ..input
    });
    assert!(
        e.apply(
            &[
                selected(),
                Command::SetAuthoringContext {
                    context: Some(context)
                }
            ],
            Some(0)
        )
        .is_err()
    );
    assert_eq!(e.scene(), &s);
}

#[test]
fn invalid_inactive_channels_and_conflicting_cursor_state_are_rejected() {
    let input = channels(Mode::Quaternion);
    let mut s = scene(input, input);
    s.authoring_context.as_mut().unwrap().cursor_rotation[0] = 99.;
    assert!(Editor::new(s).is_err());
    let mut raw = input;
    raw.axis_angle[0] = f64::NAN;
    assert!(!rotation(raw).valid());
}

#[test]
fn zero_source_quaternion_evaluates_pinned_half_turn_without_rewriting_it() {
    let input = Channels {
        quaternion_wxyz: [0.; 4],
        ..channels(Mode::Quaternion)
    };
    let s = scene(input, input);
    s.validate().unwrap();
    let matrix = formora::transforms::world(&s, "target").unwrap();
    let p = formora::transforms::point(matrix, [1., 2., 3.], Precision::F32).unwrap();
    for (actual, expected) in p.into_iter().zip([1., -2., -3.]) {
        assert!((actual - expected).abs() <= 1e-6);
    }
    assert_eq!(stored(&s), input);
}

#[test]
fn cursor_only_single_mesh_path_clears_quaternion_without_losing_inactive_euler() {
    let input = channels(Mode::Quaternion);
    let s = scene(input, input);
    let mut e = Editor::new(s).unwrap();
    let command:Command=serde_json::from_value(serde_json::json!({"operation":"snap_mesh","snap":{"entity":"target","action":{"kind":"cursor_to_center"}}})).unwrap();
    let result = e.apply_with_outcomes(&[command], Some(0)).unwrap();
    assert_eq!(
        e.scene()
            .authoring_context
            .as_ref()
            .unwrap()
            .cursor_rotation,
        input.euler
    );
    assert_eq!(
        result.snaps[0]
            .cursor_orientation_after
            .unwrap()
            .quaternion_wxyz,
        [1., 0., 0., 0.]
    );
    assert!(result.snaps[0].cursor_changed);
}
