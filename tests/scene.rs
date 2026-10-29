use formora::scene::*;
use std::fs;
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);

fn temp_scene() -> std::path::PathBuf {
    std::env::temp_dir().join(format!(
        "formora-scene-{}-{}.json",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ))
}
fn empty(name: &str) -> Entity {
    Entity {
        name: name.into(),
        parent: None,
        transform: Transform::default(),
        content: EntityKind::Empty,
    }
}
fn execute(editor: &mut Editor, command: Command) {
    let revision = editor.scene().revision;
    editor.apply(&[command], Some(revision)).unwrap();
}

#[test]
fn room_door_opens_slower_after_agent_edit_and_survives_reopening() {
    let scene = room_demo().unwrap();
    let walls = scene.entities["north_wall"].clone();
    let mut editor = Editor::new(scene).unwrap();
    execute(
        &mut editor,
        Command::SetDoorDuration {
            id: "front_door".into(),
            duration_seconds: 2.0,
        },
    );
    execute(
        &mut editor,
        Command::TriggerDoor {
            id: "front_door".into(),
            open: true,
        },
    );
    execute(&mut editor, Command::Advance { seconds: 1.0 });
    assert_eq!(editor.scene().doors["front_door"].progress, 0.5);
    assert_eq!(editor.scene().entities["north_wall"], walls);
    let path = temp_scene();
    editor.scene().save(&path).unwrap();
    let reopened = Scene::load(&path).unwrap();
    assert_eq!(reopened, *editor.scene());
    assert_eq!(reopened.doors["front_door"].duration_seconds, 2.0);
    let mut editor = Editor::new(reopened).unwrap();
    execute(&mut editor, Command::Advance { seconds: 1.0 });
    assert_eq!(editor.scene().doors["front_door"].progress, 1.0);
    editor.scene().save(&path).unwrap();
    assert_eq!(Scene::load(&path).unwrap(), *editor.scene());
    fs::remove_file(path).unwrap();
}

#[test]
fn invalid_batch_rolls_back_every_command_and_preserves_undo_history() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    execute(
        &mut editor,
        Command::CreateEntity {
            id: "before".into(),
            entity: empty("Before"),
        },
    );
    let before = editor.scene().clone();
    let result = editor.apply(
        &[
            Command::CreateEntity {
                id: "partial".into(),
                entity: empty("Partial"),
            },
            Command::SetTransform {
                id: "missing".into(),
                transform: Transform::default(),
            },
        ],
        Some(before.revision),
    );
    assert!(result.is_err());
    assert_eq!(editor.scene(), &before);
    editor.undo(Some(before.revision)).unwrap();
    assert!(editor.scene().entities.is_empty());
    assert_eq!(editor.scene().revision, before.revision + 1);
}

#[test]
fn stale_agent_revision_cannot_overwrite_newer_work() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    let revision = editor.scene().revision;
    execute(
        &mut editor,
        Command::TriggerDoor {
            id: "front_door".into(),
            open: true,
        },
    );
    let before = editor.scene().clone();
    assert!(
        editor
            .apply(
                &[Command::SetDoorDuration {
                    id: "front_door".into(),
                    duration_seconds: 3.0
                }],
                Some(revision)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(revision)).is_err());
    assert_eq!(editor.scene(), &before);
}

#[test]
fn parent_cycles_and_missing_parents_are_rejected() {
    let mut scene = Scene::default();
    let mut a = empty("A");
    a.parent = Some("b".into());
    scene.entities.insert("a".into(), a);
    assert!(scene.validate().is_err());
    let mut b = empty("B");
    b.parent = Some("a".into());
    scene.entities.insert("b".into(), b);
    assert!(scene.validate().unwrap_err().0.contains("cycle"));
}

#[test]
fn dangling_references_cannot_be_created_or_deleted() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    let before = editor.scene().clone();
    for id in ["camera", "door_hinge"] {
        assert!(
            editor
                .apply(&[Command::DeleteEntity { id: id.into() }], None)
                .is_err()
        );
        assert_eq!(editor.scene(), &before);
    }
    assert!(
        editor
            .apply(
                &[Command::SetActiveCamera {
                    id: Some("floor".into())
                }],
                None
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
}

#[test]
fn invalid_durations_and_time_steps_leave_scene_unchanged() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    let before = editor.scene().clone();
    for duration in [0.0, -1.0, f64::INFINITY, f64::NAN] {
        assert!(
            editor
                .apply(
                    &[Command::SetDoorDuration {
                        id: "front_door".into(),
                        duration_seconds: duration
                    }],
                    None
                )
                .is_err()
        );
        assert_eq!(editor.scene(), &before);
    }
    for seconds in [-1.0, f64::INFINITY, f64::NAN] {
        assert!(editor.apply(&[Command::Advance { seconds }], None).is_err());
        assert_eq!(editor.scene(), &before);
    }
}

#[test]
fn nonfinite_values_and_nonunit_rotations_are_rejected_before_saving() {
    let mut scene = room_demo().unwrap();
    scene
        .entities
        .get_mut("floor")
        .unwrap()
        .transform
        .translation[0] = f64::NAN;
    let path = temp_scene();
    assert!(scene.save(&path).is_err());
    assert!(!path.exists());
    scene
        .entities
        .get_mut("floor")
        .unwrap()
        .transform
        .translation[0] = 0.0;
    scene.entities.get_mut("floor").unwrap().transform.rotation = [0.0; 4].into();
    assert!(scene.validate().is_err());
}

#[test]
fn duplicate_ids_in_json_are_rejected_instead_of_silently_overwritten() {
    let path = temp_scene();
    let mut scene = Scene::default();
    scene.entities.insert("same".into(), empty("One"));
    let data = serde_json::to_string(&scene).unwrap();
    let entity = serde_json::to_string(&empty("Two")).unwrap();
    let duplicate = data.replacen(
        "\"entities\":{",
        &format!("\"entities\":{{\"same\":{entity},"),
        1,
    );
    fs::write(&path, duplicate).unwrap();
    assert!(Scene::load(&path).unwrap_err().0.contains("duplicate ID"));
    fs::remove_file(path).unwrap();
}

#[test]
fn duplicate_commands_cannot_replace_an_existing_entity() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    let before = editor.scene().clone();
    assert!(
        editor
            .apply(
                &[Command::CreateEntity {
                    id: "floor".into(),
                    entity: empty("Replacement")
                }],
                None
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
}

#[test]
fn schema_errors_and_unknown_fields_are_rejected() {
    let path = temp_scene();
    let mut json = serde_json::to_value(Scene::default()).unwrap();
    json["schema_version"] = serde_json::json!(2);
    fs::write(&path, serde_json::to_vec(&json).unwrap()).unwrap();
    assert!(Scene::load(&path).is_err());
    json["schema_version"] = serde_json::json!(1);
    json["silently_ignored"] = serde_json::json!(true);
    fs::write(&path, serde_json::to_vec(&json).unwrap()).unwrap();
    assert!(Scene::load(&path).unwrap_err().0.contains("unknown field"));
    fs::remove_file(path).unwrap();
}

#[test]
fn door_reversal_continues_from_current_progress_without_jumping() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    execute(
        &mut editor,
        Command::TriggerDoor {
            id: "front_door".into(),
            open: true,
        },
    );
    execute(&mut editor, Command::Advance { seconds: 0.75 });
    let rotation = editor.scene().entities["door_hinge"].transform.rotation;
    execute(
        &mut editor,
        Command::TriggerDoor {
            id: "front_door".into(),
            open: false,
        },
    );
    assert_eq!(
        editor.scene().entities["door_hinge"].transform.rotation,
        rotation
    );
    execute(&mut editor, Command::Advance { seconds: 0.25 });
    assert_eq!(editor.scene().doors["front_door"].progress, 0.5);
    execute(&mut editor, Command::Advance { seconds: 10.0 });
    assert_eq!(editor.scene().doors["front_door"].progress, 0.0);
}

#[test]
fn annotations_are_saved_and_invalid_targets_do_not_change_the_scene() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    execute(
        &mut editor,
        Command::Annotate {
            annotation: Annotation {
                entity: Some("door_panel".into()),
                position: [0.0, -3.0, 1.2],
                text: "門開慢一點".into(),
            },
        },
    );
    let before = editor.scene().clone();
    assert!(
        editor
            .apply(
                &[Command::Annotate {
                    annotation: Annotation {
                        entity: Some("missing".into()),
                        position: [0.0; 3],
                        text: "change".into()
                    }
                }],
                None
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    let path = temp_scene();
    editor.scene().save(&path).unwrap();
    assert_eq!(Scene::load(&path).unwrap(), before);
    fs::remove_file(path).unwrap();
}

#[test]
fn conflicting_door_controllers_and_inconsistent_saved_progress_are_rejected() {
    let mut scene = room_demo().unwrap();
    let duplicate = scene.doors["front_door"].clone();
    scene.doors.insert("other_door".into(), duplicate);
    assert!(scene.validate().is_err());
    scene.doors.remove("other_door");
    scene.doors.get_mut("front_door").unwrap().progress = 0.5;
    assert!(scene.validate().is_err());
}

#[test]
fn exhausted_revisions_do_not_modify_scene_or_undo_history() {
    let scene = Scene {
        revision: u64::MAX,
        ..Scene::default()
    };
    let mut editor = Editor::new(scene.clone()).unwrap();
    assert!(
        editor
            .apply(
                &[Command::CreateEntity {
                    id: "new".into(),
                    entity: empty("New")
                }],
                None
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &scene);
    assert!(editor.undo(None).is_err());
}

#[test]
fn persistence_preserves_finite_float_bits_instead_of_rounding_scene_data() {
    let values = [
        0.9238795325112867,
        0.5923364782216495,
        f64::MIN_POSITIVE,
        f64::MAX,
        f64::from_bits(1),
        -0.0,
        -1e-200,
        1e200,
    ];
    let path = temp_scene();
    for value in values {
        let mut scene = Scene::default();
        let mut entity = empty("Numeric fixture");
        entity.transform.translation = [value; 3];
        scene.entities.insert("numeric".into(), entity);
        scene.save(&path).unwrap();
        let loaded = Scene::load(&path).unwrap();
        assert_eq!(
            loaded.entities["numeric"].transform.translation[0].to_bits(),
            value.to_bits()
        );
    }
    fs::remove_file(path).unwrap();
}

#[test]
fn existing_version_one_door_scenes_load_without_a_trigger_counter() {
    let path = temp_scene();
    let mut value = serde_json::to_value(room_demo().unwrap()).unwrap();
    value["doors"]["front_door"]
        .as_object_mut()
        .unwrap()
        .remove("trigger_revision");
    fs::write(&path, serde_json::to_vec_pretty(&value).unwrap()).unwrap();
    let loaded = Scene::load(&path).unwrap();
    assert_eq!(loaded.doors["front_door"].trigger_revision, 0);
    let mut editor = Editor::new(loaded).unwrap();
    execute(
        &mut editor,
        Command::TriggerDoor {
            id: "front_door".into(),
            open: true,
        },
    );
    assert_eq!(editor.scene().doors["front_door"].trigger_revision, 1);
    editor.scene().save(&path).unwrap();
    assert_eq!(Scene::load(&path).unwrap(), *editor.scene());
    fs::remove_file(path).unwrap();
}
