use formora::rotation::{EulerOrder, RotationAngles, TransformRotation};
use formora::scene::*;
use formora::session::{ApplyRequest, InspectRequest, Session, UndoRequest};
use formora::transforms::{self, Precision};
use serde_json::{Value, json};
fn entity(transform: Transform) -> Entity {
    Entity {
        name: "Target".into(),
        parent: None,
        transform,
        content: EntityKind::Mesh {
            geometry: Geometry::Cube { size: [2., 4., 6.] },
            material: None,
        },
    }
}
fn query(scene: &Scene, id: &str) -> Value {
    InspectRequest {
        entity: Some(id.into()),
        world: true,
        ..Default::default()
    }
    .inspect(scene)
    .unwrap()
}
fn rotate(mut p: [f64; 3], axis: usize, angle: f64) -> [f64; 3] {
    let (s, c) = angle.sin_cos();
    let j = (axis + 1) % 3;
    let k = (axis + 2) % 3;
    let (a, b) = (p[j], p[k]);
    p[j] = c * a - s * b;
    p[k] = s * a + c * b;
    p
}
fn near(a: [f64; 3], b: [f64; 3]) {
    for i in 0..3 {
        assert!((a[i] - b[i]).abs() <= 1e-6, "{a:?} != {b:?}");
    }
}

#[test]
fn native_default_keeps_legacy_json_and_high_precision_world_coordinates() {
    let legacy = json!({"translation":[1.000000000003,2.0,3.0],"rotation":[0.0,0.0,0.0,1.0],"scale":[1.0,1.0,1.0]});
    let t: Transform = serde_json::from_value(legacy.clone()).unwrap();
    assert_eq!(t.precision, Precision::F64);
    assert_eq!(serde_json::to_value(&t).unwrap(), legacy);
    let mut scene = Scene::default();
    scene.entities.insert("target".into(), entity(t));
    scene.validate().unwrap();
    let r = query(&scene, "target");
    assert_eq!(r["world_matrix"][0][3], json!(1.000000000003));
    assert!(
        serde_json::from_value::<Transform>(
            json!({"translation":[0,0,0],"rotation":[0,0,0,1],"scale":[1,1,1],"precision":"f16"})
        )
        .is_err()
    );
}

#[test]
fn all_euler_orders_keep_authored_angles_and_match_sequential_physical_rotations() {
    for (order, axes) in [
        (EulerOrder::Xyz, [0, 1, 2]),
        (EulerOrder::Xzy, [0, 2, 1]),
        (EulerOrder::Yxz, [1, 0, 2]),
        (EulerOrder::Yzx, [1, 2, 0]),
        (EulerOrder::Zxy, [2, 0, 1]),
        (EulerOrder::Zyx, [2, 1, 0]),
    ] {
        let angles = [0.31, -0.27, 0.43];
        let t = Transform {
            precision: Precision::F32,
            rotation: TransformRotation::Authored(RotationAngles::Euler { angles, order }),
            scale: [1.2, -0.7, 1.1],
            translation: [0.17, -0.23, 0.31],
        };
        let matrix = transforms::local(&t).unwrap();
        let mut expected = [0.24, 0.21, 0.44];
        for axis in axes {
            expected = rotate(expected, axis, f64::from(angles[axis] as f32));
        }
        for (v, offset) in expected.iter_mut().zip(t.translation) {
            *v += offset;
        }
        near(
            transforms::point(matrix, [0.2, -0.3, 0.4], Precision::F32).unwrap(),
            expected,
        );
        let saved = serde_json::to_value(&t).unwrap();
        assert_eq!(saved["rotation"]["angles"], json!(angles));
        assert_eq!(saved["precision"], "f32");
    }
}

#[test]
fn single_precision_quaternion_and_axis_angle_frames_share_the_expected_axes() {
    for rotation in [
        TransformRotation::Quaternion([
            0.,
            0.,
            std::f64::consts::FRAC_1_SQRT_2,
            std::f64::consts::FRAC_1_SQRT_2,
        ]),
        TransformRotation::Authored(RotationAngles::AxisAngle {
            axis: [0., 0., 5.],
            radians: std::f64::consts::FRAC_PI_2,
        }),
    ] {
        let t = Transform {
            rotation,
            precision: Precision::F32,
            ..Default::default()
        };
        near(
            transforms::point(transforms::local(&t).unwrap(), [1., 2., 3.], Precision::F32)
                .unwrap(),
            [-2., 1., 3.],
        );
    }
}

#[test]
fn balanced_parent_products_and_observed_point_accumulation_have_distinct_rounding() {
    let a = [
        [2e10, 1., -2e10, 1.],
        [0., 1., 0., 0.],
        [0., 0., 1., 0.],
        [0., 0., 0., 1.],
    ];
    let b = [
        [1., 0., 0., 0.],
        [1., 1., 0., 0.],
        [1., 0., 1., 0.],
        [1., 0., 0., 1.],
    ];
    assert_eq!(transforms::compose(a, b, Precision::F32).unwrap()[0][0], 0.);
    assert_eq!(transforms::compose(a, b, Precision::F64).unwrap()[0][0], 2.);
    assert_eq!(
        transforms::point(a, [1.; 3], Precision::F32).unwrap()[0],
        2.
    );
}

#[test]
fn shared_asset_queries_use_actual_instance_precision_parent_and_zero_scale() {
    let mesh=serde_json::from_value(json!({"vertices":{"one":[0.31,0.41,0.53],"apart":[0.31,0.41,0.53]},"edges":{},"triangles":{},"material_slots":[]})).unwrap();
    let mut scene = Scene::default();
    scene.mesh_assets.insert("shared".into(), mesh);
    let mut parent = entity(Transform {
        translation: [2., 3., 4.],
        scale: [-2., 0., 0.5],
        precision: Precision::F32,
        ..Default::default()
    });
    parent.content = EntityKind::Empty;
    scene.entities.insert("parent".into(), parent);
    for (id, precision, parent) in [
        ("first", Precision::F32, Some("parent".into())),
        ("other", Precision::F64, None),
    ] {
        let mut e = entity(Transform {
            translation: [1., 2., 3.],
            precision,
            ..Default::default()
        });
        e.content = EntityKind::Mesh {
            geometry: Geometry::Asset {
                id: "shared".into(),
            },
            material: None,
        };
        e.parent = parent;
        scene.entities.insert(id.into(), e);
    }
    scene.validate().unwrap();
    let before = scene.clone();
    let a = query(&scene, "first");
    let b = query(&scene, "other");
    assert_eq!(a["world_vertices"]["one"], a["world_vertices"]["apart"]);
    near(
        serde_json::from_value(a["world_vertices"]["one"].clone()).unwrap(),
        [-0.62, 3., 5.765],
    );
    near(
        serde_json::from_value(b["world_vertices"]["one"].clone()).unwrap(),
        [1.31, 2.41, 3.53],
    );
    assert_eq!(scene, before);
}

#[test]
fn world_query_rejects_ambiguous_options_and_handles_builtin_and_empty_entities() {
    let mut scene = Scene::default();
    scene
        .entities
        .insert("cube".into(), entity(Transform::default()));
    let mut plane = entity(Transform::default());
    plane.content = EntityKind::Mesh {
        geometry: Geometry::Plane { size: [2., 4.] },
        material: None,
    };
    scene.entities.insert("plane".into(), plane);
    let mut empty = entity(Transform::default());
    empty.content = EntityKind::Empty;
    scene.entities.insert("empty".into(), empty);
    scene.validate().unwrap();
    assert_eq!(
        query(&scene, "cube")["world_vertices"]
            .as_object()
            .unwrap()
            .len(),
        8
    );
    assert_eq!(
        query(&scene, "plane")["world_vertices"]
            .as_object()
            .unwrap()
            .len(),
        4
    );
    assert!(query(&scene, "empty").get("world_vertices").is_none());
    for value in [
        json!({"world":true}),
        json!({"world":true,"mesh_asset":"shared"}),
        json!({"world":true,"entity":"cube","normals":true}),
        json!({"world":true,"entity":"missing"}),
    ] {
        let request: InspectRequest = serde_json::from_value(value).unwrap();
        assert!(request.inspect(&scene).is_err());
    }
}

#[test]
fn precision_changes_save_reopen_undo_and_reject_overflow_or_failed_saves_atomically() {
    let mut before = Scene::default();
    before
        .entities
        .insert("target".into(), entity(Transform::default()));
    let dir = std::env::temp_dir().join(format!("formora-frame-save-{}", std::process::id()));
    std::fs::create_dir(&dir).unwrap();
    let path = dir.join("scene.json");
    let mut s = Session::create(&path, before.clone()).unwrap();
    let saved = std::fs::read(&path).unwrap();
    let req = InspectRequest {
        entity: Some("target".into()),
        world: true,
        ..Default::default()
    };
    s.inspect(req).unwrap();
    assert_eq!(std::fs::read(&path).unwrap(), saved);
    assert!(
        s.undo(UndoRequest {
            expected_revision: 0
        })
        .is_err()
    );
    let transform = Transform {
        precision: Precision::F32,
        translation: [0.31, -0.27, 0.13],
        ..Default::default()
    };
    let command = Command::SetTransform {
        id: "target".into(),
        transform: transform.clone(),
    };
    s.apply(ApplyRequest {
        expected_revision: 0,
        commands: vec![command.clone()],
    })
    .unwrap();
    let reloaded = Scene::load(&path).unwrap();
    assert_eq!(reloaded.entities["target"].transform, transform);
    assert_eq!(query(&reloaded, "target"), query(s.scene(), "target"));
    s.undo(UndoRequest {
        expected_revision: 1,
    })
    .unwrap();
    assert_eq!(s.scene().entities, before.entities);
    let bad = Command::SetTransform {
        id: "target".into(),
        transform: Transform {
            precision: Precision::F32,
            scale: [1e40, 1., 1.],
            ..Default::default()
        },
    };
    assert!(
        s.apply(ApplyRequest {
            expected_revision: 2,
            commands: vec![command.clone(), bad]
        })
        .is_err()
    );
    assert_eq!(s.scene().entities, before.entities);
    assert_eq!(s.scene().revision, 2);
    std::fs::rename(&path, dir.join("backup.json")).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        s.apply(ApplyRequest {
            expected_revision: 2,
            commands: vec![command]
        })
        .is_err()
    );
    assert_eq!(s.scene().entities, before.entities);
    assert!(
        s.undo(UndoRequest {
            expected_revision: 2
        })
        .is_err()
    );
    drop(s);
    std::fs::remove_dir_all(dir).unwrap();
}

#[cfg(feature = "preview")]
#[test]
fn preview_and_world_query_share_single_precision_frames_for_parented_objects() {
    let mut scene = Scene::default();
    let mut p = entity(Transform {
        precision: Precision::F32,
        rotation: TransformRotation::Authored(RotationAngles::Euler {
            angles: [0.37, -0.23, 0.51],
            order: EulerOrder::Xyz,
        }),
        scale: [1.2, 0.7, 1.6],
        ..Default::default()
    });
    p.content = EntityKind::Empty;
    scene.entities.insert("parent".into(), p);
    let mut e = entity(Transform {
        precision: Precision::F32,
        translation: [-0.7, 0.35, 0.6],
        ..Default::default()
    });
    e.parent = Some("parent".into());
    scene.entities.insert("child".into(), e);
    scene.validate().unwrap();
    let query = query(&scene, "child");
    let matrix: transforms::Matrix = serde_json::from_value(query["world_matrix"].clone()).unwrap();
    let preview =
        formora::preview::math::world_transforms(&scene).unwrap()["child"].to_cols_array_2d();
    for (r, row) in matrix.iter().enumerate() {
        for (c, column) in preview.iter().enumerate() {
            assert_eq!(column[r], row[c]);
        }
    }
}
