//! Before-code property/query controls. All values are independent literals.
use formora::scene::{Command, Entity, EntityKind, Geometry, Scene, Transform};
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

const NAMES: [&str; 5] = ["parent", "a", "alias", "b", "untouched"];
static NEXT: AtomicU64 = AtomicU64::new(0);

fn path() -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "formora-object-state-{}-{}",
        std::process::id(),
        NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    std::fs::create_dir(&dir).unwrap();
    dir.join("scene.json")
}

fn scene(singular: bool) -> Scene {
    let mut scene = Scene::default();
    for id in ["mesh_a", "mesh_b", "outside"] {
        scene.mesh_assets.insert(
            id.into(),
            serde_json::from_value(json!({
                "vertices":{"v":[1.,2.,3.]},"triangles":{},"material_slots":[]
            }))
            .unwrap(),
        );
    }
    for name in NAMES {
        let transform = Transform {
            precision: formora::transforms::Precision::F32,
            scale: if singular && name == "parent" {
                [0., 2., 3.]
            } else {
                [1.; 3]
            },
            ..Transform::default()
        };
        let mesh = match name {
            "a" | "alias" => "mesh_a",
            "b" => "mesh_b",
            _ => "outside",
        };
        scene.entities.insert(
            name.into(),
            Entity {
                name: name.into(),
                parent: if name == "a" {
                    Some("parent".into())
                } else {
                    None
                },
                transform,
                content: if name == "parent" {
                    EntityKind::Empty
                } else {
                    EntityKind::Mesh {
                        geometry: Geometry::Asset { id: mesh.into() },
                        material: None,
                    }
                },
            },
        );
    }
    scene
}

fn command(id: &str, flags: [bool; 3]) -> Command {
    let mut states = serde_json::Map::new();
    states.insert(id.into(), json!({"lock_scale":flags,"lock_location":[true,false,false],"lock_rotation":[false,true,false]}));
    serde_json::from_value(json!({"operation":"set_object_context","context":{
        "order":NAMES,"selected":[],"active":null,"edit_objects":[],"states":states
    }}))
    .expect("the persistent three-axis scale state must be admitted")
}

fn inspect(session: &mut Session, id: &str) -> Value {
    formora::agent::dispatch(
        session,
        "scene_inspect",
        json!({"entity":id,"object_state":true}),
    )
    .expect("the explicit object state query must be admitted")
}

#[test]
fn defaults_are_explicit_read_only_and_do_not_create_object_context() {
    let p = path();
    let mut session = Session::create(&p, scene(false)).unwrap();
    let bytes = std::fs::read(&p).unwrap();
    for id in NAMES {
        let result = inspect(&mut session, id);
        assert_eq!(result["revision"], 0);
        assert_eq!(result["id"], id);
        assert_eq!(
            result["object_state"]["lock_scale"],
            json!([false, false, false])
        );
    }
    assert!(session.scene().object_context.is_none());
    assert_eq!(std::fs::read(&p).unwrap(), bytes);
}

#[test]
fn every_boolean_triple_is_per_object_persistent_and_freshly_reloaded() {
    for mask in 0..8 {
        let flags = std::array::from_fn(|axis| mask & (1 << axis) != 0);
        for target in NAMES {
            let p = path();
            let original = scene(false);
            let mut session = Session::create(&p, original.clone()).unwrap();
            session
                .apply(ApplyRequest {
                    expected_revision: 0,
                    commands: vec![command(target, flags)],
                })
                .unwrap();
            for id in NAMES {
                assert_eq!(
                    inspect(&mut session, id)["object_state"]["lock_scale"],
                    json!(if id == target { flags } else { [false; 3] })
                );
            }
            let value = serde_json::to_value(session.scene()).unwrap();
            let stored = &value["object_context"]["states"][target];
            if mask == 0 {
                assert!(stored.get("lock_scale").is_none());
            } else {
                assert_eq!(stored["lock_scale"], json!(flags));
            }
            assert_eq!(session.scene().entities, original.entities);
            assert_eq!(session.scene().mesh_assets, original.mesh_assets);
            drop(session);
            let mut fresh = Session::open(&p).unwrap();
            assert_eq!(
                inspect(&mut fresh, target)["object_state"]["lock_scale"],
                json!(flags)
            );
            assert_eq!(
                inspect(&mut fresh, target)["object_state"]["lock_location"],
                json!([true, false, false])
            );
            assert_eq!(
                inspect(&mut fresh, target)["object_state"]["lock_rotation"],
                json!([false, true, false])
            );
        }
    }
}

#[test]
fn undo_and_replay_restore_real_state_without_changing_shared_mesh_data() {
    let p = path();
    let original = scene(false);
    let mut session = Session::create(&p, original.clone()).unwrap();
    let change = command("alias", [true, false, true]);
    session
        .apply(ApplyRequest {
            expected_revision: 0,
            commands: vec![change.clone()],
        })
        .unwrap();
    assert_eq!(
        inspect(&mut session, "a")["object_state"]["lock_scale"],
        json!([false, false, false])
    );
    assert_eq!(
        inspect(&mut session, "alias")["object_state"]["lock_scale"],
        json!([true, false, true])
    );
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    assert!(session.scene().object_context.is_none());
    assert_eq!(
        inspect(&mut session, "alias")["object_state"]["lock_scale"],
        json!([false, false, false])
    );
    session
        .apply(ApplyRequest {
            expected_revision: 2,
            commands: vec![change],
        })
        .unwrap();
    assert_eq!(
        inspect(&mut session, "alias")["object_state"]["lock_scale"],
        json!([true, false, true])
    );
    assert_eq!(session.scene().entities, original.entities);
    assert_eq!(session.scene().mesh_assets, original.mesh_assets);
}

#[test]
fn stale_revision_and_late_invalid_command_do_not_publish_partial_state() {
    let p = path();
    let original = scene(false);
    let mut session = Session::create(&p, original.clone()).unwrap();
    let bytes = std::fs::read(&p).unwrap();
    let change = command("a", [true, true, true]);
    assert!(
        session
            .apply(ApplyRequest {
                expected_revision: 4,
                commands: vec![change.clone()]
            })
            .is_err()
    );
    let missing = Command::SetMeshVertices {
        id: "missing".into(),
        positions: [("v".into(), [0.; 3])].into_iter().collect(),
    };
    let error = session
        .apply(ApplyRequest {
            expected_revision: 0,
            commands: vec![change, missing],
        })
        .unwrap_err();
    assert!(
        error.0.contains("unknown mesh asset"),
        "late command not reached: {error:?}"
    );
    assert_eq!(session.scene(), &original);
    assert_eq!(std::fs::read(&p).unwrap(), bytes);
}

#[test]
fn failed_save_preserves_memory_file_and_undo_history() {
    let p = path();
    let original = scene(false);
    let mut session = Session::create(&p, original.clone()).unwrap();
    let change = command("b", [false, true, false]);
    let backup = p.with_file_name("original.json");
    std::fs::rename(&p, &backup).unwrap();
    std::fs::create_dir(&p).unwrap();
    assert!(
        session
            .apply(ApplyRequest {
                expected_revision: 0,
                commands: vec![change]
            })
            .is_err()
    );
    assert_eq!(session.scene(), &original);
    std::fs::remove_dir(&p).unwrap();
    std::fs::rename(&backup, &p).unwrap();
    assert_eq!(Scene::load(&p).unwrap(), original);
    assert!(
        session
            .undo(UndoRequest {
                expected_revision: 0
            })
            .is_err()
    );
    assert_eq!(
        inspect(&mut session, "b")["object_state"]["lock_scale"],
        json!([false, false, false])
    );
}

#[test]
fn metadata_query_works_under_singular_parent_and_rejects_mixed_queries() {
    let p = path();
    let mut session = Session::create(&p, scene(true)).unwrap();
    session
        .apply(ApplyRequest {
            expected_revision: 0,
            commands: vec![command("a", [true, false, true])],
        })
        .unwrap();
    let bytes = std::fs::read(&p).unwrap();
    assert_eq!(
        inspect(&mut session, "a")["object_state"]["lock_scale"],
        json!([true, false, true])
    );
    for args in [
        json!({"object_state":true}),
        json!({"entity":"a","mesh_asset":"mesh_a","object_state":true}),
        json!({"entity":"a","world":true,"object_state":true}),
        json!({"entity":"a","normals":true,"object_state":true}),
        json!({"entity":"a","tessellate":true,"object_state":true}),
        json!({"entity":"a","selection_topology":true,"object_state":true}),
    ] {
        let error = formora::agent::dispatch(&mut session, "scene_inspect", args).unwrap_err();
        assert!(
            error.contains("object state query requires only an entity"),
            "{error}"
        );
    }
    assert!(
        formora::agent::dispatch(
            &mut session,
            "scene_inspect",
            json!({"entity":"missing","object_state":true})
        )
        .unwrap_err()
        .contains("unknown entity")
    );
    assert_eq!(std::fs::read(&p).unwrap(), bytes);
}

#[test]
fn invalid_vectors_and_unknown_state_owners_are_atomic_errors() {
    let p = path();
    let original = scene(false);
    let mut session = Session::create(&p, original.clone()).unwrap();
    let valid = command("a", [true, false, false]);
    let mut value = serde_json::to_value(valid).unwrap();
    for flags in [
        json!([true, false]),
        json!([true, false, false, true]),
        json!([0, 0, 0]),
        json!([null, false, false]),
    ] {
        value["context"]["states"]["a"]["lock_scale"] = flags;
        assert!(serde_json::from_value::<Command>(value.clone()).is_err());
    }
    let unknown = command("missing", [true, false, false]);
    assert!(
        session
            .apply(ApplyRequest {
                expected_revision: 0,
                commands: vec![unknown]
            })
            .is_err()
    );
    assert_eq!(session.scene(), &original);
    assert_eq!(Scene::load(&p).unwrap(), original);
}

#[test]
fn legacy_entity_and_world_queries_keep_their_original_shapes() {
    let p = path();
    let mut session = Session::create(&p, scene(false)).unwrap();
    let result =
        formora::agent::dispatch(&mut session, "scene_inspect", json!({"entity":"a"})).unwrap();
    assert_eq!(
        result,
        json!({"revision":0,"id":"a","entity":session.scene().entities["a"]})
    );
    let world = formora::agent::dispatch(
        &mut session,
        "scene_inspect",
        json!({"entity":"a","world":true}),
    )
    .unwrap();
    assert!(world.get("object_state").is_none());
    assert!(world.get("world_matrix").is_some());
    assert!(session.scene().object_context.is_none());
}
