use formora::mesh::{
    MeshAsset,
    creation::AuthoringContext,
    selection::{Editing, Elements},
    snap::{Action, Status},
    transform::Pivot,
};
use formora::objects::{Context, State, identity, snap::Request};
use formora::rotation::{EulerOrder, RotationAngles, TransformRotation};
use formora::scene::{Command, Editor, Entity, EntityKind, Geometry, Scene, Transform};
use std::collections::{BTreeMap, BTreeSet};

fn object(parent: Option<&str>, translation: [f64; 3], mesh: bool) -> Entity {
    Entity {
        name: "Object".into(),
        parent: parent.map(str::to_owned),
        transform: Transform {
            translation,
            rotation: TransformRotation::Authored(RotationAngles::Euler {
                angles: [0.; 3],
                order: EulerOrder::Xyz,
            }),
            ..Transform::default()
        },
        content: if mesh {
            EntityKind::Mesh {
                geometry: Geometry::Asset { id: "mesh".into() },
                material: None,
            }
        } else {
            EntityKind::Empty
        },
    }
}
fn scene() -> Scene {
    let mut s = Scene::default();
    s.entities
        .insert("target".into(), object(None, [0.25, -0.5, 0.75], true));
    s.entities
        .insert("secondary".into(), object(None, [2., 0., 0.], true));
    s.entities
        .insert("child".into(), object(Some("target"), [1., 2., 3.], false));
    s.mesh_assets.insert(
        "mesh".into(),
        MeshAsset {
            vertices: BTreeMap::from([("a".into(), [0.5, 0., 0.]), ("b".into(), [0., 1., 0.])]),
            editing: Some(Editing {
                selected: Elements {
                    vertices: BTreeSet::from(["a".into(), "b".into()]),
                    ..Elements::default()
                },
                ..Editing::default()
            }),
            ..MeshAsset::default()
        },
    );
    s.object_context = Some(Context {
        order: vec!["target".into(), "secondary".into(), "child".into()],
        selected: BTreeSet::from(["target".into()]),
        active: Some("target".into()),
        ..Context::default()
    });
    s.authoring_context = Some(AuthoringContext {
        cursor_location: [4., 5., 6.],
        cursor_rotation: [0.17, 0.23, 0.41],
        ..AuthoringContext::default()
    });
    s
}
fn command(action: Action) -> Command {
    Command::SnapScene {
        snap: Box::new(Request {
            action,
            pivot: Pivot::Median,
            max_components: 100,
            max_objects: 10,
        }),
    }
}

#[test]
fn object_grid_respects_locks_and_reports_actual_changes_and_undo() {
    let mut s = scene();
    s.object_context.as_mut().unwrap().states.insert(
        "target".into(),
        State {
            lock_location: [true, false, false],
            ..State::default()
        },
    );
    let before = s.clone();
    let mut e = Editor::new(s).unwrap();
    let out = e
        .apply_with_outcomes(&[command(Action::SelectedToGrid { spacing: 1. })], Some(0))
        .unwrap();
    assert_eq!(
        e.scene().entities["target"].transform.translation,
        [0.25, 0., 1.]
    );
    assert_eq!(e.scene().mesh_assets, before.mesh_assets);
    assert_eq!(e.scene().authoring_context, before.authoring_context);
    assert_eq!(out.scene_snaps[0].objects.len(), 1);
    assert_eq!(out.scene_snaps[0].objects[0].entity, "target");
    e.undo(Some(1)).unwrap();
    let mut restored = e.scene().clone();
    restored.revision = 0;
    assert_eq!(restored, before);
}

#[test]
fn skip_children_changes_real_parent_inverse_and_query_frame() {
    let mut s = scene();
    s.object_context.as_mut().unwrap().skip_children = true;
    let child_before = formora::transforms::world(&s, "child").unwrap();
    let mut e = Editor::new(s).unwrap();
    let out = e
        .apply_with_outcomes(&[command(Action::SelectedToGrid { spacing: 1. })], Some(0))
        .unwrap();
    assert_eq!(
        formora::transforms::world(e.scene(), "child").unwrap(),
        child_before
    );
    assert_eq!(
        e.scene().entities["child"].transform.translation,
        [1., 2., 3.]
    );
    let frames = formora::objects::frames(e.scene(), "child").unwrap();
    assert_ne!(frames.matrix_parent_inverse, identity());
    assert_eq!(
        out.scene_snaps[0]
            .objects
            .iter()
            .map(|c| c.entity.as_str())
            .collect::<Vec<_>>(),
        ["target", "child"]
    );
    let value = serde_json::to_value(e.scene()).unwrap();
    let saved: Scene = serde_json::from_value(value).unwrap();
    saved.validate().unwrap();
    assert_eq!(
        formora::transforms::world(&saved, "child").unwrap(),
        child_before
    );
}

#[test]
fn origins_only_edits_shared_data_once_and_keeps_other_users_shared() {
    let mut s = scene();
    s.object_context.as_mut().unwrap().origins_only = true;
    let world = formora::transforms::point(
        formora::transforms::world(&s, "target").unwrap(),
        s.mesh_assets["mesh"].vertices["a"],
        s.entities["target"].transform.precision,
    )
    .unwrap();
    let mut e = Editor::new(s).unwrap();
    let out = e
        .apply_with_outcomes(&[command(Action::SelectedToGrid { spacing: 1. })], Some(0))
        .unwrap();
    let after = formora::transforms::point(
        formora::transforms::world(e.scene(), "target").unwrap(),
        e.scene().mesh_assets["mesh"].vertices["a"],
        e.scene().entities["target"].transform.precision,
    )
    .unwrap();
    assert_eq!(after, world);
    assert_eq!(out.scene_snaps[0].meshes.len(), 1);
    assert_eq!(
        out.scene_snaps[0].meshes[0].shared_instances,
        ["secondary", "target"]
    );
    assert_eq!(
        e.scene().entities["secondary"].transform.translation,
        [2., 0., 0.]
    );
    assert_ne!(e.scene().mesh_assets["mesh"].vertices["a"], [0.5, 0., 0.]);
}

#[test]
fn multi_edit_unique_data_uses_active_representative_and_common_centre() {
    let mut s = scene();
    let c = s.object_context.as_mut().unwrap();
    c.selected.insert("secondary".into());
    c.edit_objects = BTreeSet::from(["secondary".into()]);
    c.active = Some("secondary".into());
    let mut e = Editor::new(s).unwrap();
    let out = e
        .apply_with_outcomes(&[command(Action::SelectedToGrid { spacing: 1. })], Some(0))
        .unwrap();
    assert_eq!(out.scene_snaps[0].edit_meshes.len(), 1);
    assert_eq!(out.scene_snaps[0].edit_meshes[0].entity, "secondary");
    assert_eq!(e.scene().mesh_assets["mesh"].vertices["a"], [1., 0., 0.]);
}

#[test]
fn no_active_error_empty_selection_cancel_and_late_batch_failure_are_atomic() {
    let mut s = scene();
    let c = s.object_context.as_mut().unwrap();
    c.active = None;
    c.selected.clear();
    let mut e = Editor::new(s.clone()).unwrap();
    assert!(
        e.apply(&[command(Action::SelectedToActive {})], Some(0))
            .is_err()
    );
    assert_eq!(e.scene(), &s);
    let out = e
        .apply_with_outcomes(&[command(Action::CursorToSelected {})], Some(0))
        .unwrap();
    assert_eq!(out.scene_snaps[0].status, Status::Cancelled);
    assert_eq!(e.scene().authoring_context, s.authoring_context);
    assert!(!out.scene_snaps[0].cursor_changed);
    let before = e.scene().clone();
    assert!(
        e.apply(
            &[
                command(Action::CursorToCenter {}),
                Command::DeleteEntity {
                    id: "missing".into()
                }
            ],
            Some(1)
        )
        .is_err()
    );
    assert_eq!(e.scene(), &before);
}

#[test]
fn bad_context_and_budgets_reject_without_mutation() {
    let mut s = scene();
    s.entities.get_mut("target").unwrap().transform.rotation = TransformRotation::default();
    let mut e = Editor::new(s.clone()).unwrap();
    for (objects, components) in [(0, 100), (2, 100), (10, 0)] {
        let cmd = Command::SnapScene {
            snap: Box::new(Request {
                action: Action::CursorToCenter {},
                pivot: Pivot::Median,
                max_objects: objects,
                max_components: components,
            }),
        };
        assert!(e.apply(&[cmd], Some(0)).is_err());
        assert_eq!(e.scene(), &s);
    }
    let mut context = s.object_context.clone().unwrap();
    context.order.push("target".into());
    assert!(
        e.apply(
            &[Command::SetObjectContext {
                context: Some(context)
            }],
            Some(0)
        )
        .is_err()
    );
    assert_eq!(e.scene(), &s);
    let malformed = r#"{"operation":"snap_scene","snap":{"action":{"kind":"cursor_to_center","answer":[1,2,3]}}}"#;
    assert!(serde_json::from_str::<Command>(malformed).is_err());
    let duplicate = r#"{"selected":["target","target"]}"#;
    assert!(serde_json::from_str::<Context>(duplicate).is_err());
}

#[test]
fn legacy_unit_quaternion_now_snaps_through_the_same_physical_core() {
    let mut s = scene();
    s.entities.get_mut("target").unwrap().transform.rotation = TransformRotation::default();
    let expected = Transform {
        translation: [4., 5., 6.],
        rotation: TransformRotation::Authored(RotationAngles::Euler {
            angles: s.authoring_context.as_ref().unwrap().cursor_rotation,
            order: EulerOrder::Xyz,
        }),
        ..Transform::default()
    };
    let expected = formora::transforms::local(&expected).unwrap();
    let mut e = Editor::new(s).unwrap();
    e.apply(
        &[command(Action::SelectedToCursor {
            use_offset: false,
            use_rotation: true,
        })],
        Some(0),
    )
    .unwrap();
    let actual = formora::transforms::world(e.scene(), "target").unwrap();
    for r in 0..4 {
        for c in 0..4 {
            assert!((actual[r][c] - expected[r][c]).abs() <= 1e-6);
        }
    }
    assert!(matches!(
        e.scene().entities["target"].transform.rotation,
        TransformRotation::Quaternion(_)
    ));
}

#[test]
fn parent_conversion_refreshes_the_evaluated_snapshot_before_later_siblings() {
    let mut s = scene();
    s.entities.get_mut("secondary").unwrap().parent = Some("target".into());
    let c = s.object_context.as_mut().unwrap();
    c.selected.extend(["secondary".into(), "child".into()]);
    let mut e = Editor::new(s).unwrap();
    e.apply(
        &[command(Action::SelectedToCursor {
            use_offset: false,
            use_rotation: false,
        })],
        Some(0),
    )
    .unwrap();
    // First child uses the previous evaluated world position. Its parent
    // conversion refreshes the snapshot. The later sibling uses that refresh.
    assert_eq!(
        e.scene().entities["secondary"].transform.translation,
        [3.75, 5.5, 5.25]
    );
    assert_eq!(
        e.scene().entities["child"].transform.translation,
        [0., 0., 0.]
    );
}

#[test]
fn origins_only_compensates_a_selected_descendant_suppressed_by_offset() {
    let mut s = scene();
    let secondary = s.mesh_assets["mesh"].clone();
    s.mesh_assets.insert("secondary_mesh".into(), secondary);
    let second = s.entities.get_mut("secondary").unwrap();
    second.parent = Some("target".into());
    second.content = EntityKind::Mesh {
        geometry: Geometry::Asset {
            id: "secondary_mesh".into(),
        },
        material: None,
    };
    let c = s.object_context.as_mut().unwrap();
    c.selected.insert("secondary".into());
    c.origins_only = true;
    let old = formora::transforms::point(
        formora::transforms::world(&s, "secondary").unwrap(),
        s.mesh_assets["secondary_mesh"].vertices["a"],
        s.entities["secondary"].transform.precision,
    )
    .unwrap();
    let mut e = Editor::new(s).unwrap();
    let result = e
        .apply_with_outcomes(
            &[command(Action::SelectedToCursor {
                use_offset: true,
                use_rotation: false,
            })],
            Some(0),
        )
        .unwrap();
    let actual = formora::transforms::point(
        formora::transforms::world(e.scene(), "secondary").unwrap(),
        e.scene().mesh_assets["secondary_mesh"].vertices["a"],
        e.scene().entities["secondary"].transform.precision,
    )
    .unwrap();
    assert_eq!(actual, old);
    assert_eq!(result.scene_snaps[0].meshes.len(), 2);
}

#[test]
fn aggregate_budget_counts_each_unique_mesh_and_does_not_mutate_on_failure() {
    let mut s = scene();
    let second = s.mesh_assets["mesh"].clone();
    s.mesh_assets.insert("second".into(), second);
    s.entities.get_mut("secondary").unwrap().content = EntityKind::Mesh {
        geometry: Geometry::Asset {
            id: "second".into(),
        },
        material: None,
    };
    let c = s.object_context.as_mut().unwrap();
    c.selected.insert("secondary".into());
    c.edit_objects = c.selected.clone();
    let before = s.clone();
    let mut e = Editor::new(s).unwrap();
    let request = Command::SnapScene {
        snap: Box::new(Request {
            action: Action::SelectedToGrid { spacing: 1. },
            pivot: Pivot::Median,
            max_objects: 10,
            max_components: 3,
        }),
    };
    assert!(
        e.apply(&[request], Some(0))
            .unwrap_err()
            .0
            .contains("component budget")
    );
    assert_eq!(e.scene(), &before);
}

#[test]
fn save_failure_keeps_scene_undo_and_original_disk_then_replays_after_recovery() {
    use formora::session::{ApplyRequest, Session, UndoRequest};
    let folder = std::env::temp_dir().join(format!(
        "formora-scene-snap-save-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let backup = folder.join("backup.json");
    let before = scene();
    let mut session = Session::create(&path, before.clone()).unwrap();
    let original = std::fs::read(&path).unwrap();
    std::fs::rename(&path, &backup).unwrap();
    std::fs::create_dir(&path).unwrap();
    let request = || ApplyRequest {
        expected_revision: 0,
        commands: vec![command(Action::SelectedToGrid { spacing: 1. })],
    };
    assert!(session.apply_with_result(request()).is_err());
    assert_eq!(session.scene(), &before);
    assert_eq!(std::fs::read(&backup).unwrap(), original);
    assert!(
        session
            .undo(UndoRequest {
                expected_revision: 0
            })
            .is_err()
    );
    std::fs::remove_dir(&path).unwrap();
    std::fs::rename(&backup, &path).unwrap();
    let result = session.apply_with_result(request()).unwrap();
    assert_eq!(result.scene_snaps.len(), 1);
    let after = Scene::load(&path).unwrap();
    assert_eq!(&after, session.scene());
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    let mut restored = Scene::load(&path).unwrap();
    restored.revision = 0;
    assert_eq!(restored, before);
    session
        .apply_with_result(ApplyRequest {
            expected_revision: 2,
            commands: request().commands,
        })
        .unwrap();
    let mut replay = Scene::load(&path).unwrap();
    replay.revision = after.revision;
    assert_eq!(replay, after);
    drop(session);
    std::fs::remove_dir_all(folder).unwrap();
}

#[test]
fn origin_rotation_reuses_incidence_but_computes_normals_from_changed_positions() {
    let mut s = scene();
    let mesh = s.mesh_assets.get_mut("mesh").unwrap();
    mesh.vertices = BTreeMap::from([
        ("a".into(), [0., 0., 0.]),
        ("b".into(), [1., 0., 0.]),
        ("c".into(), [0., 1., 0.]),
    ]);
    mesh.triangles.insert(
        "face".into(),
        formora::mesh::Triangle {
            corner_colors: None,
            vertices: ["a".into(), "b".into(), "c".into()],
            uv_layers: BTreeMap::new(),
            corner_normals: None,
            material_slot: None,
        },
    );
    let context = s.object_context.as_mut().unwrap();
    context.origins_only = true;
    s.authoring_context.as_mut().unwrap().cursor_rotation = [std::f64::consts::FRAC_PI_2, 0., 0.];
    let mut e = Editor::new(s).unwrap();
    e.apply(
        &[command(Action::SelectedToCursor {
            use_offset: false,
            use_rotation: true,
        })],
        Some(0),
    )
    .unwrap();
    let mesh = &e.scene().mesh_assets["mesh"];
    let fresh = formora::mesh::normals::automatic(mesh).unwrap();
    let resolved = formora::mesh::normals::resolved(mesh).unwrap();
    assert_eq!(fresh, resolved);
    let normal = fresh.faces[0].normal;
    assert!(
        normal[0].abs() < 1e-6 && (normal[1] - 1.).abs() < 1e-6 && normal[2].abs() < 1e-6,
        "{normal:?}"
    );
}

#[test]
fn multi_edit_normal_overflow_rejects_without_publishing_scene_revision_or_undo() {
    let mut s = scene();
    let mesh = s.mesh_assets.get_mut("mesh").unwrap();
    mesh.vertices = BTreeMap::from([
        ("a".into(), [1e20, 0., 0.]),
        ("b".into(), [0., 1e20, 0.]),
        ("c".into(), [0., 0., 1e20]),
    ]);
    mesh.triangles.insert(
        "face".into(),
        formora::mesh::Triangle {
            corner_colors: None,
            vertices: ["a".into(), "b".into(), "c".into()],
            uv_layers: BTreeMap::new(),
            corner_normals: None,
            material_slot: None,
        },
    );
    mesh.editing
        .as_mut()
        .unwrap()
        .selected
        .vertices
        .insert("c".into());
    s.object_context
        .as_mut()
        .unwrap()
        .edit_objects
        .insert("target".into());
    let before = s.clone();
    let mut editor = Editor::new(s).unwrap();
    let error = editor
        .apply_with_outcomes(&[command(Action::SelectedToGrid { spacing: 1. })], Some(0))
        .err()
        .expect("normal overflow must reject the operation");
    assert!(error.0.contains("automatic normal"), "{error}");
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
}
