use formora::mesh::{
    MeshAsset,
    creation::AuthoringContext,
    selection::{Editing, Elements},
    snap::{Action, Request, Status},
    transform::Pivot,
};
use formora::scene::{Command, Editor, Entity, EntityKind, Geometry, Scene, Transform};
use std::collections::{BTreeMap, BTreeSet};

fn editor() -> Editor {
    let vertices = BTreeMap::from([
        ("a".into(), [-0.5, 0., 0.]),
        ("b".into(), [-1.5, 0., 0.]),
        ("c".into(), [0.4999999701976776, 0., 0.]),
        ("d".into(), [0.5, 0., 0.]),
        ("hidden".into(), [0.5, 0., 0.]),
    ]);
    let mut scene = Scene::default();
    scene.mesh_assets.insert(
        "mesh".into(),
        MeshAsset {
            vertices,
            editing: Some(Editing {
                selected: Elements {
                    vertices: BTreeSet::from(["a".into(), "b".into(), "c".into(), "d".into()]),
                    ..Elements::default()
                },
                hidden: Elements {
                    vertices: BTreeSet::from(["hidden".into()]),
                    ..Elements::default()
                },
                ..Editing::default()
            }),
            ..MeshAsset::default()
        },
    );
    let entity = Entity {
        name: "Mesh".into(),
        parent: None,
        transform: Transform::default(),
        content: EntityKind::Mesh {
            geometry: Geometry::Asset { id: "mesh".into() },
            material: None,
        },
    };
    scene.entities.insert("target".into(), entity.clone());
    scene.entities.insert("shared".into(), entity);
    Editor::new(scene).unwrap()
}
fn command(action: Action) -> Command {
    Command::SnapMesh {
        snap: Box::new(Request {
            entity: "target".into(),
            action,
            pivot: Pivot::Median,
            max_components: 100,
        }),
    }
}

#[test]
fn grid_uses_source_half_rounding_and_keeps_hidden_duplicates_and_shared_ids() {
    let mut editor = editor();
    let before = editor.scene().clone();
    let result = editor
        .apply_with_outcomes(&[command(Action::SelectedToGrid { spacing: 1. })], Some(0))
        .unwrap();
    let mesh = &editor.scene().mesh_assets["mesh"];
    assert_eq!(
        [
            mesh.vertices["a"][0],
            mesh.vertices["b"][0],
            mesh.vertices["c"][0],
            mesh.vertices["d"][0]
        ],
        [0., -1., 1., 1.]
    );
    assert_eq!(
        mesh.vertices["hidden"],
        before.mesh_assets["mesh"].vertices["hidden"]
    );
    assert_eq!(mesh.editing, before.mesh_assets["mesh"].editing);
    assert_eq!(editor.scene().entities, before.entities);
    let receipt = &result.snaps[0];
    assert_eq!(receipt.status, Status::Finished);
    assert_eq!(receipt.shared_instances, vec!["shared", "target"]);
    assert_eq!(receipt.grid_spacing_metres, Some(1.));
    assert_eq!(receipt.changed.vertices.len(), 4);
    editor.undo(Some(1)).unwrap();
    let mut restored = editor.scene().clone();
    restored.revision = 0;
    assert_eq!(restored, before);
}

#[test]
fn cursor_origin_clears_rotation_and_replays_without_changing_geometry() {
    let mut editor = editor();
    let context = AuthoringContext {
        cursor_location: [0.25, -0.5, 1.],
        cursor_rotation: [0.1, 0.2, 0.3],
        ..AuthoringContext::default()
    };
    editor
        .apply(
            &[Command::SetAuthoringContext {
                context: Some(context.clone()),
            }],
            Some(0),
        )
        .unwrap();
    let before = editor.scene().clone();
    let commands = [command(Action::CursorToCenter {})];
    let applied = editor.apply_with_outcomes(&commands, Some(1)).unwrap();
    let receipt = &applied.snaps[0];
    assert!(receipt.cursor_changed);
    assert_eq!(receipt.cursor_rotation_before, context.cursor_rotation);
    let after = editor.scene().clone();
    assert_eq!(after.mesh_assets, before.mesh_assets);
    assert_eq!(after.entities, before.entities);
    let cursor = after.authoring_context.as_ref().unwrap();
    assert_eq!(cursor.cursor_location, [0.; 3]);
    assert_eq!(cursor.cursor_rotation, [0.; 3]);
    editor.undo(Some(2)).unwrap();
    assert_eq!(editor.scene().authoring_context, Some(context));
    editor.apply(&commands, Some(3)).unwrap();
    let mut replay = editor.scene().clone();
    replay.revision = after.revision;
    assert_eq!(replay, after);
}

#[test]
fn missing_active_rejects_and_empty_cursor_selection_cancels_explicitly() {
    let mut editor = editor();
    let before = editor.scene().clone();
    assert!(
        editor
            .apply(&[command(Action::SelectedToActive {})], Some(0))
            .unwrap_err()
            .0
            .contains("no active")
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
    let result = editor
        .apply_with_outcomes(&[command(Action::CursorToActive {})], Some(0))
        .unwrap();
    assert_eq!(result.snaps[0].status, Status::Cancelled);
    assert!(result.snaps[0].changed.vertices.is_empty());
    assert!(!result.snaps[0].cursor_changed);
    editor
        .apply(
            &[Command::SetMeshEditing {
                id: "mesh".into(),
                editing: Some(Editing::default()),
            }],
            Some(1),
        )
        .unwrap();
    let result = editor
        .apply_with_outcomes(&[command(Action::CursorToSelected {})], Some(2))
        .unwrap();
    assert_eq!(result.snaps[0].status, Status::Cancelled);
}

#[test]
fn invalid_grid_budget_stale_and_late_batch_failure_are_atomic() {
    let mut editor = editor();
    let before = editor.scene().clone();
    for spacing in [
        0.,
        -1.,
        f64::INFINITY,
        f64::NAN,
        f64::MAX,
        f64::MIN_POSITIVE,
    ] {
        assert!(
            editor
                .apply(&[command(Action::SelectedToGrid { spacing })], Some(0))
                .is_err()
        );
        assert_eq!(editor.scene(), &before);
    }
    let mut limited = command(Action::CursorToCenter {});
    let Command::SnapMesh { snap } = &mut limited else {
        unreachable!()
    };
    snap.max_components = 1;
    assert!(editor.apply(&[limited], Some(0)).is_err());
    let first = command(Action::SelectedToGrid { spacing: 1. });
    assert!(editor.apply(std::slice::from_ref(&first), Some(1)).is_err());
    assert!(
        editor
            .apply(
                &[
                    first,
                    Command::DeleteEntity {
                        id: "missing".into()
                    }
                ],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
}

#[test]
fn edit_rotation_flag_is_explicitly_not_applied_and_receipt_index_is_real() {
    let mut editor = editor();
    let context = AuthoringContext {
        cursor_location: [0.25, 0.5, 0.75],
        cursor_rotation: [0.2, 0.3, 0.4],
        ..AuthoringContext::default()
    };
    let result = editor
        .apply_with_outcomes(
            &[
                Command::SetAuthoringContext {
                    context: Some(context.clone()),
                },
                command(Action::SelectedToCursor {
                    use_offset: false,
                    use_rotation: true,
                }),
            ],
            Some(0),
        )
        .unwrap();
    let receipt = &result.snaps[0];
    assert_eq!(receipt.command_index, 1);
    assert!(!receipt.rotation_applied);
    assert_eq!(receipt.cursor_before, context.cursor_location);
    assert_eq!(receipt.cursor_rotation_after, context.cursor_rotation);
    for id in ["a", "b", "c", "d"] {
        assert_eq!(
            editor.scene().mesh_assets["mesh"].vertices[id],
            context.cursor_location
        );
    }
}

#[test]
fn unknown_fields_and_nonfinite_json_are_rejected_before_dispatch() {
    for request in [
        r#"{"operation":"snap_mesh","snap":{"entity":"target","action":{"kind":"cursor_to_center","answer":[0,0,0]}}}"#,
        r#"{"operation":"snap_mesh","snap":{"entity":"target","action":{"kind":"selected_to_grid","spacing":1},"expected_positions":{}}}"#,
        r#"{"operation":"snap_mesh","snap":{"entity":"target","action":{"kind":"selected_to_grid","spacing":1e999}}}"#,
    ] {
        assert!(serde_json::from_str::<Command>(request).is_err());
    }
}

#[test]
fn saved_snap_receipts_reload_and_failed_save_preserves_scene_disk_and_undo() {
    use formora::session::{ApplyRequest, Session, UndoRequest};
    let folder = std::env::temp_dir().join(format!(
        "formora-snap-save-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let backup = folder.join("backup.json");
    let before = editor().scene().clone();
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
    assert_eq!(result.snaps.len(), 1);
    assert_eq!(result.revision, 1);
    assert_eq!(Scene::load(&path).unwrap(), *session.scene());
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    let mut restored = Scene::load(&path).unwrap();
    restored.revision = 0;
    assert_eq!(restored, before);
    drop(session);
    std::fs::remove_dir_all(folder).unwrap();
}

#[test]
fn missing_entity_asset_or_edit_state_rejects_without_a_receipt_or_mutation() {
    for kind in ["entity", "asset", "editing"] {
        let mut scene = editor().scene().clone();
        match kind {
            "entity" => {
                scene.entities.clear();
            }
            "asset" => {
                scene.mesh_assets.clear();
            }
            _ => {
                scene.mesh_assets.get_mut("mesh").unwrap().editing = None;
            }
        }
        let before = scene.clone();
        let request = Request {
            entity: "target".into(),
            action: Action::CursorToCenter {},
            pivot: Pivot::Median,
            max_components: 100,
        };
        assert!(formora::mesh::snap::execute(&mut scene, &request).is_err());
        assert_eq!(scene, before);
    }
}

#[test]
fn moving_cursor_preserves_actual_authored_rotation_without_unrelated_rounding() {
    use formora::mesh::selection::Component;
    let mut scene = editor().scene().clone();
    let rotation = [0.17, 0.23, 0.41];
    scene.authoring_context = Some(AuthoringContext {
        cursor_location: [0.37, -0.62, 0.87],
        cursor_rotation: rotation,
        ..Default::default()
    });
    scene
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .editing
        .as_mut()
        .unwrap()
        .history = vec![Component::Vertex { id: "b".into() }];
    let mut editor = Editor::new(scene).unwrap();
    let result = editor
        .apply_with_outcomes(&[command(Action::CursorToActive {})], Some(0))
        .unwrap();
    assert_eq!(
        editor
            .scene()
            .authoring_context
            .as_ref()
            .unwrap()
            .cursor_rotation,
        rotation
    );
    assert_eq!(result.snaps[0].cursor_rotation_before, rotation);
    assert_eq!(result.snaps[0].cursor_rotation_after, rotation);
    assert_eq!(result.snaps[0].cursor_after, [-1.5, 0., 0.]);
}
