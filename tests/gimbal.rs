use formora::mesh::{MeshAsset, selection::*};
use formora::rotation::{EulerOrder, RotationAngles, TransformRotation};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

fn orders() -> [EulerOrder; 6] {
    [
        EulerOrder::Xyz,
        EulerOrder::Xzy,
        EulerOrder::Yxz,
        EulerOrder::Yzx,
        EulerOrder::Zxy,
        EulerOrder::Zyx,
    ]
}
fn axes(order: EulerOrder) -> [usize; 3] {
    match order {
        EulerOrder::Xyz => [0, 1, 2],
        EulerOrder::Xzy => [0, 2, 1],
        EulerOrder::Yxz => [1, 0, 2],
        EulerOrder::Yzx => [1, 2, 0],
        EulerOrder::Zxy => [2, 0, 1],
        EulerOrder::Zyx => [2, 1, 0],
    }
}
fn euler(angles: [f64; 3], order: EulerOrder) -> TransformRotation {
    TransformRotation::Authored(RotationAngles::Euler { angles, order })
}
fn axis_angle(axis: [f64; 3], radians: f64) -> TransformRotation {
    TransformRotation::Authored(RotationAngles::AxisAngle { axis, radians })
}
fn near(a: [f64; 3], b: [f64; 3]) {
    for i in 0..3 {
        assert!((a[i] - b[i]).abs() <= 1e-6, "{a:?} != {b:?}");
    }
}
fn rotate_axis(mut p: [f64; 3], axis: usize, radians: f64) -> [f64; 3] {
    let (s, c) = radians.sin_cos();
    let j = (axis + 1) % 3;
    let k = (axis + 2) % 3;
    let (a, b) = (p[j], p[k]);
    p[j] = c * a - s * b;
    p[k] = s * a + c * b;
    p
}
fn cross(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|i| a[(i + 1) % 3] * b[(i + 2) % 3] - a[(i + 2) % 3] * b[(i + 1) % 3])
}
fn rotate_quaternion(q: [f64; 4], p: [f64; 3]) -> [f64; 3] {
    let v = [q[0], q[1], q[2]];
    let t = cross(v, p).map(|v| 2. * v);
    let extra = cross(v, t);
    std::array::from_fn(|i| p[i] + q[3] * t[i] + extra[i])
}
fn scene(rotation: TransformRotation) -> Scene {
    let mut mesh:MeshAsset=serde_json::from_value(json!({"vertices":{"a":[1,2,3],"b":[-1,0,2]},"edges":{},"triangles":{},"material_slots":[]})).unwrap();
    let mut editing = Editing::default();
    editing.selected.vertices = ["a".into(), "b".into()].into();
    set_editing(&mut mesh, Some(editing)).unwrap();
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(), mesh);
    scene.entities.insert(
        "target".into(),
        Entity {
            name: "Target".into(),
            parent: None,
            transform: Transform {
                rotation,
                ..Default::default()
            },
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "mesh".into() },
                material: None,
            },
        },
    );
    scene.validate().unwrap();
    scene
}
fn operation(change: Value, options: Value) -> Command {
    let mut t = json!({"entity":"target","orientation":{"kind":"gimbal"},"change":change});
    for (k, v) in options.as_object().unwrap() {
        t[k] = v.clone();
    }
    serde_json::from_value(json!({"operation":"transform_mesh","transform":t})).unwrap()
}
fn inspect_basis(scene: Scene) -> [[f64; 3]; 3] {
    let mut editor = Editor::new(scene).unwrap();
    editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0,0,0]}),
                json!({}),
            )],
            Some(0),
        )
        .unwrap()
        .transforms[0]
        .basis_world
}
fn column(m: [[f64; 3]; 3], c: usize) -> [f64; 3] {
    std::array::from_fn(|r| m[r][c])
}

#[test]
fn all_rotation_orders_resolve_the_same_physical_pose_as_sequential_axis_rotations() {
    let angles = [0.31, -0.47, 0.83];
    for order in orders() {
        let q = euler(angles, order).quaternion();
        assert!((q.iter().map(|v| v * v).sum::<f64>() - 1.).abs() < 1e-12);
        for p in [
            [1., 0., 0.],
            [0., 1., 0.],
            [0., 0., 1.],
            [0.37, -0.61, 1.43],
        ] {
            let mut expected = p;
            for axis in axes(order) {
                expected = rotate_axis(expected, axis, angles[axis]);
            }
            near(rotate_quaternion(q, p), expected);
        }
    }
}

#[test]
fn all_gimbal_orders_keep_first_local_second_partial_and_last_global_axes() {
    let angles = [0.31, -0.47, 0.83];
    for order in orders() {
        let basis = inspect_basis(scene(euler(angles, order)));
        let [first, second, last] = axes(order);
        let quantized = angles.map(|v| (v as f32) as f64);
        let mut expected = [0.; 3];
        expected[first] = 1.;
        for axis in axes(order) {
            expected = rotate_axis(expected, axis, quantized[axis]);
        }
        near(column(basis, first), expected);
        let mut expected = [0.; 3];
        expected[second] = 1.;
        expected = rotate_axis(expected, last, quantized[last]);
        near(column(basis, second), expected);
        near(
            column(basis, last),
            std::array::from_fn(|i| if i == last { 1. } else { 0. }),
        );
    }
}

#[test]
fn equivalent_physical_poses_keep_their_distinct_authored_gimbal_modes() {
    let authored = euler([0.31, -0.47, 0.83], EulerOrder::Xyz);
    let quaternion = authored.quaternion().into();
    let euler_scene = scene(authored);
    let quaternion_scene = scene(quaternion);
    assert_ne!(
        inspect_basis(euler_scene.clone()),
        inspect_basis(quaternion_scene.clone())
    );
    assert_eq!(
        inspect_basis(quaternion_scene.clone()),
        [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
    );
    for orientation in ["local", "gimbal"] {
        let mut a = Editor::new(euler_scene.clone()).unwrap();
        let mut b = Editor::new(quaternion_scene.clone()).unwrap();
        let command = operation(
            json!({"kind":"translate","value":[0.375,0,0]}),
            json!({"orientation":{"kind":orientation}}),
        );
        a.apply(&[command.clone()], Some(0)).unwrap();
        b.apply(&[command], Some(0)).unwrap();
        if orientation == "local" {
            near(
                a.scene().mesh_assets["mesh"].vertices["a"],
                b.scene().mesh_assets["mesh"].vertices["a"],
            );
        } else {
            assert_ne!(
                a.scene().mesh_assets["mesh"].vertices,
                b.scene().mesh_assets["mesh"].vertices
            );
        }
    }
}

#[test]
fn reflected_parent_columns_affect_gimbal_but_child_scale_and_translation_do_not() {
    let mut expected = None;
    for scale in [[1.; 3], [0.7, -1.4, 2.3]] {
        let mut before = scene(euler([0.; 3], EulerOrder::Xyz));
        before.entities.insert(
            "parent".into(),
            Entity {
                name: "Parent".into(),
                parent: None,
                transform: Transform {
                    translation: [17., -23., 9.],
                    rotation: euler([0., 0., std::f64::consts::FRAC_PI_2], EulerOrder::Xyz),
                    scale: [-2., 3., 4.],
                    ..Default::default()
                },
                content: EntityKind::Empty,
            },
        );
        let target = before.entities.get_mut("target").unwrap();
        target.parent = Some("parent".into());
        target.transform.scale = scale;
        let basis = inspect_basis(before);
        near(column(basis, 0), [0., -1., 0.]);
        near(column(basis, 1), [-1., 0., 0.]);
        near(column(basis, 2), [0., 0., 1.]);
        if let Some(previous) = expected {
            assert_eq!(basis, previous);
        } else {
            expected = Some(basis);
        }
    }
}

#[test]
fn sheared_parent_gimbal_axes_are_not_normalized_again_for_constrained_rotation() {
    let quarter = std::f64::consts::FRAC_PI_4;
    let mut before = scene(euler([0., 0., quarter], EulerOrder::Xyz));
    before.entities.insert(
        "grandparent".into(),
        Entity {
            name: "Grandparent".into(),
            parent: None,
            transform: Transform {
                scale: [2., 1., 1.],
                ..Default::default()
            },
            content: EntityKind::Empty,
        },
    );
    before.entities.insert(
        "parent".into(),
        Entity {
            name: "Parent".into(),
            parent: Some("grandparent".into()),
            transform: Transform {
                rotation: euler([0., 0., quarter], EulerOrder::Xyz),
                ..Default::default()
            },
            content: EntityKind::Empty,
        },
    );
    before.entities.get_mut("target").unwrap().parent = Some("parent".into());
    let basis = inspect_basis(before.clone());
    let a = 0.4_f64.sqrt();
    near(column(basis, 0), [0., a, 0.]);
    assert!((column(basis, 0).iter().map(|v| v * v).sum::<f64>() - 1.).abs() > 0.5);
    let angle = (0.4_f32) as f64;
    let (s, c) = angle.sin_cos();
    for constraint in [[true, false, false], [false; 3]] {
        let mut editor = Editor::new(before.clone()).unwrap();
        editor
            .apply(
                &[operation(
                    json!({"kind":"rotate","radians":0.4,"axis":"x"}),
                    json!({"constraint_axis":constraint,"center_override":[0,0,0]}),
                )],
                Some(0),
            )
            .unwrap();
        near(
            editor.scene().mesh_assets["mesh"].vertices["a"],
            [
                c + (1. - c) * a * a,
                2. * c - 1.5 * s * a,
                4. * s * a + 3. * c,
            ],
        );
    }
}

#[test]
fn axis_angle_gimbal_uses_its_authored_axis_and_rotation() {
    let axis = [1., 2., 3.];
    let radians = 0.37;
    let basis = inspect_basis(scene(axis_angle(axis, radians)));
    let length = 14_f64.sqrt();
    let n = axis.map(|v| v / length);
    let start = [7., -5., 1.].map(|v| v / 75_f64.sqrt());
    let x = rotate_quaternion(
        axis_angle(axis, (radians as f32) as f64).quaternion(),
        start,
    );
    near(column(basis, 0), x);
    near(column(basis, 1), cross(n, x));
    near(column(basis, 2), n);
}

#[test]
fn quaternion_mode_falls_back_to_actual_parent_orientation() {
    let mut before = scene(
        euler([0.31, -0.47, 0.83], EulerOrder::Xyz)
            .quaternion()
            .into(),
    );
    before.entities.insert(
        "parent".into(),
        Entity {
            name: "Parent".into(),
            parent: None,
            transform: Transform {
                rotation: axis_angle([1., 2., 3.], 0.57),
                scale: [-2., 3., 0.7],
                ..Default::default()
            },
            content: EntityKind::Empty,
        },
    );
    before.entities.get_mut("target").unwrap().parent = Some("parent".into());
    let gimbal = inspect_basis(before.clone());
    let mut editor = Editor::new(before).unwrap();
    let parent = editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0,0,0]}),
                json!({"orientation":{"kind":"parent"}}),
            )],
            Some(0),
        )
        .unwrap()
        .transforms[0]
        .basis_world;
    for c in 0..3 {
        near(column(gimbal, c), column(parent, c));
    }
}

#[test]
fn stored_rotations_reject_invalid_values_orders_and_mixed_fields_without_weakening_legacy_validation()
 {
    for value in [
        json!({"kind":"euler","angles":[0,0,0],"order":"unknown"}),
        json!({"kind":"euler","angles":[0,0,0],"axis":[0,0,1]}),
        json!({"kind":"axis_angle","axis":[1,0,0],"radians":0.5,"angles":[0,0,0]}),
        json!([0, 0, 1]),
    ] {
        assert!(serde_json::from_value::<TransformRotation>(value).is_err());
    }
    for rotation in [
        euler([f64::INFINITY, 0., 0.], EulerOrder::Xyz),
        axis_angle([0.; 3], 0.4),
        axis_angle([f64::NAN, 0., 1.], 0.4),
        axis_angle([1., 0., 0.], f64::INFINITY),
        [0.; 4].into(),
        [0., 0., 0., 2.].into(),
    ] {
        assert!(!rotation.valid());
        let mut before = scene(Default::default());
        before
            .entities
            .get_mut("target")
            .unwrap()
            .transform
            .rotation = rotation;
        assert!(before.validate().is_err());
    }
    assert_eq!(
        serde_json::to_value(Transform::default().rotation).unwrap(),
        json!([0.0, 0.0, 0.0, 1.0])
    );
}

#[test]
fn invalid_new_rotation_batch_and_unsafe_gimbal_frame_preserve_scene_and_undo() {
    let before = scene(Default::default());
    let mut editor = Editor::new(before.clone()).unwrap();
    let transform = Transform {
        rotation: axis_angle([0.; 3], 0.4),
        ..Default::default()
    };
    assert!(
        editor
            .apply(
                &[
                    operation(json!({"kind":"translate","value":[1,2,3]}), json!({})),
                    Command::SetTransform {
                        id: "target".into(),
                        transform
                    }
                ],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
    for rotation in [
        axis_angle([1.; 3], 0.4),
        euler([1e100, 0., 0.], EulerOrder::Xyz),
    ] {
        let before = scene(rotation);
        let mut editor = Editor::new(before.clone()).unwrap();
        assert!(
            editor
                .apply(
                    &[operation(
                        json!({"kind":"translate","value":[1,0,0]}),
                        json!({})
                    )],
                    Some(0)
                )
                .is_err()
        );
        assert_eq!(editor.scene(), &before);
        assert!(editor.undo(Some(0)).is_err());
    }
}

#[test]
fn full_turns_and_rotation_mode_survive_save_reload_and_undo_with_atomic_failed_save() {
    let angles = [
        4. * std::f64::consts::PI + 0.31,
        -6. * std::f64::consts::PI - 0.47,
        8. * std::f64::consts::PI + 0.83,
    ];
    let rotation = euler(angles, EulerOrder::Zyx);
    let before = scene(rotation);
    let folder = std::env::temp_dir().join(format!("formora-gimbal-save-{}", std::process::id()));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let mut session = Session::create(&path, before.clone()).unwrap();
    assert_eq!(
        Scene::load(&path).unwrap().entities["target"]
            .transform
            .rotation,
        rotation
    );
    let command = operation(
        json!({"kind":"translate","value":[0.375,-0.625,0.25]}),
        json!({}),
    );
    let original = std::fs::read(&path).unwrap();
    std::fs::rename(&path, folder.join("backup.json")).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        session
            .apply_with_result(ApplyRequest {
                expected_revision: 0,
                commands: vec![command.clone()]
            })
            .is_err()
    );
    assert_eq!(session.scene(), &before);
    assert!(
        session
            .undo(UndoRequest {
                expected_revision: 0
            })
            .is_err()
    );
    std::fs::remove_dir(&path).unwrap();
    std::fs::rename(folder.join("backup.json"), &path).unwrap();
    assert_eq!(std::fs::read(&path).unwrap(), original);
    session
        .apply_with_result(ApplyRequest {
            expected_revision: 0,
            commands: vec![command],
        })
        .unwrap();
    assert_eq!(Scene::load(&path).unwrap(), *session.scene());
    assert_eq!(
        session.scene().entities["target"].transform.rotation,
        rotation
    );
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    assert_eq!(session.scene().mesh_assets, before.mesh_assets);
    assert_eq!(session.scene().entities, before.entities);
    let q = rotation.quaternion();
    let simple = euler([0.31, -0.47, 0.83], EulerOrder::Zyx).quaternion();
    assert!((q.iter().zip(simple).map(|(a, b)| a * b).sum::<f64>().abs() - 1.).abs() < 1e-12);
    drop(session);
    std::fs::remove_dir_all(folder).unwrap();
}

#[test]
fn door_animation_replaces_equivalent_euler_state_with_its_actual_quaternion() {
    let mut before = room_demo().unwrap();
    before
        .entities
        .get_mut("door_hinge")
        .unwrap()
        .transform
        .rotation = euler([0., 0., 4. * std::f64::consts::PI], EulerOrder::Xyz);
    before.validate().unwrap();
    let mut editor = Editor::new(before.clone()).unwrap();
    editor
        .apply(
            &[
                Command::TriggerDoor {
                    id: "front_door".into(),
                    open: true,
                },
                Command::Advance { seconds: 0.25 },
            ],
            Some(before.revision),
        )
        .unwrap();
    assert!(matches!(
        editor.scene().entities["door_hinge"].transform.rotation,
        TransformRotation::Quaternion(_)
    ));
    assert_eq!(editor.scene().doors["front_door"].progress, 0.25);
    editor.undo(Some(before.revision + 1)).unwrap();
    assert_eq!(editor.scene().entities, before.entities);
    #[cfg(feature = "preview")]
    {
        let mut playback = formora::preview::Playback::new(&before);
        playback.toggle_door("front_door").unwrap();
        playback.advance(0.5).unwrap();
        assert!(matches!(
            playback.scene.entities["door_hinge"].transform.rotation,
            TransformRotation::Quaternion(_)
        ));
        assert_eq!(
            before.entities["door_hinge"].transform.rotation,
            euler([0., 0., 4. * std::f64::consts::PI], EulerOrder::Xyz)
        );
    }
}

#[cfg(feature = "preview")]
#[test]
fn preview_world_and_surface_picking_use_all_stored_rotation_modes() {
    use formora::preview::math;
    use glam::DVec3;
    let rotation = euler([std::f64::consts::FRAC_PI_2, 0., 0.], EulerOrder::Xyz);
    for mode in [
        rotation,
        rotation.quaternion().into(),
        axis_angle([5., 0., 0.], std::f64::consts::FRAC_PI_2),
    ] {
        let mut scene = scene(mode);
        let target = scene.entities.get_mut("target").unwrap();
        target.content = EntityKind::Mesh {
            geometry: Geometry::Cube { size: [2., 4., 6.] },
            material: None,
        };
        target.transform.translation = [3., 2., 1.];
        let world = math::world_transforms(&scene).unwrap()["target"];
        assert!(
            world
                .transform_point3(DVec3::Y)
                .abs_diff_eq(DVec3::new(3., 2., 2.), 1e-12)
        );
        let hit = math::pick(&scene, DVec3::new(3., 2., 10.), -DVec3::Z)
            .unwrap()
            .unwrap();
        assert_eq!(hit.entity, "target");
        assert!(hit.position.abs_diff_eq(DVec3::new(3., 2., 3.), 1e-12));
        assert!((hit.distance - 7.).abs() < 1e-12);
    }
}
