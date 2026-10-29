use formora::mesh::{MeshAsset, selection::*, transform};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

fn scene() -> Scene {
    let mut asset: MeshAsset = serde_json::from_value(json!({
        "vertices": {
            "z_selected":[0,0,0], "h_depth":[0,0,2], "g_coincident":[0,0,0],
            "e_near":[0.5,0,0], "d_boundary":[1,0,0], "c_outside":[2,0,0],
            "b_hidden":[0.125,0,0], "a_selected":[0,0,0]
        },
        "edges":{"a_near":["a_selected","e_near"],
                 "near_boundary":["e_near","d_boundary"]},
        "triangles":{}, "material_slots":[]
    }))
    .unwrap();
    let mut editing = Editing::default();
    editing.selected.vertices = ["a_selected".into(), "z_selected".into()].into();
    editing.hidden.vertices.insert("b_hidden".into());
    set_editing(&mut asset, Some(editing)).unwrap();
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(), asset);
    for id in ["target", "instance"] {
        scene.entities.insert(
            id.into(),
            Entity {
                name: id.into(),
                parent: None,
                transform: Transform::default(),
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id: "mesh".into() },
                    material: None,
                },
            },
        );
    }
    scene.validate().unwrap();
    scene
}

fn command(options: Value) -> Command {
    let mut p = json!({"radius":1,"falloff":"random","seed":0,"random_algorithm":"blender_5_2"});
    for (key, value) in options.as_object().unwrap() {
        p[key] = value.clone();
    }
    serde_json::from_value(json!({"operation":"transform_mesh","transform":{
        "entity":"target", "change":{"kind":"translate","value":[0,0,1]},
        "proportional":p
    }}))
    .unwrap()
}

fn source_draw(index: usize) -> f32 {
    let raw =
        include_bytes!("../baseline/reference/blender-5.2.3/random-falloff/first-sequence.bin");
    f32::from_le_bytes(raw[index * 4..index * 4 + 4].try_into().unwrap())
}

#[test]
fn actual_geometry_uses_source_draws_in_sorted_identity_order_with_boundary_consumption() {
    let before = scene();
    let mut editor = Editor::new(before.clone()).unwrap();
    let result = editor
        .apply_with_outcomes(&[command(json!({}))], Some(0))
        .unwrap();
    let receipt = &result.transforms[0];
    assert_eq!(receipt.random_seed, Some(0));
    assert_eq!(
        receipt.random_algorithm,
        Some(transform::RandomAlgorithm::Blender52)
    );
    assert_eq!(receipt.shared_instances, ["instance", "target"]);
    let asset = &editor.scene().mesh_assets["mesh"];
    for (id, draw, ratio) in [("e_near", 1, 0.5), ("g_coincident", 2, 1.)] {
        let expected = f64::from(source_draw(draw) * ratio);
        assert_eq!(asset.vertices[id][2], expected);
        assert_eq!(receipt.influence[id], expected);
    }
    for id in ["b_hidden", "c_outside", "d_boundary", "h_depth"] {
        assert_eq!(asset.vertices[id], before.mesh_assets["mesh"].vertices[id]);
        assert!(!receipt.influence.contains_key(id));
    }
    for id in ["a_selected", "z_selected"] {
        assert_eq!(asset.vertices[id], [0., 0., 1.]);
    }
    assert_eq!(asset.edges, before.mesh_assets["mesh"].edges);
    assert_eq!(asset.editing, before.mesh_assets["mesh"].editing);
    assert_eq!(editor.scene().entities, before.entities);
    editor.undo(Some(1)).unwrap();
    let mut restored = editor.scene().clone();
    restored.revision = before.revision;
    assert_eq!(restored, before);
}

#[test]
fn connected_and_projected_influence_keep_their_distance_rules_and_skip_unreachable_draws() {
    for (connected, projected) in [(true, false), (false, true), (true, true)] {
        let mut editor = Editor::new(scene()).unwrap();
        let result = editor
            .apply_with_outcomes(
                &[command(
                    json!({"connected":connected,"projected":projected}),
                )],
                Some(0),
            )
            .unwrap();
        let weights = &result.transforms[0].influence;
        assert_eq!(weights["e_near"], f64::from(source_draw(1) * 0.5));
        if connected {
            assert!(!weights.contains_key("g_coincident"));
            assert!(!weights.contains_key("h_depth"));
        } else {
            assert_eq!(weights["g_coincident"], f64::from(source_draw(2)));
            assert_eq!(weights["h_depth"], f64::from(source_draw(3)));
        }
    }
}

#[test]
fn explicit_legacy_option_preserves_full_width_seeds_and_omitted_receipt_shape() {
    for seed in [0, u32::MAX as u64, 1_u64 << 32, u64::MAX] {
        let mut omitted = Editor::new(scene()).unwrap();
        let mut explicit = Editor::new(scene()).unwrap();
        let a = omitted
            .apply_with_outcomes(
                &[command(json!({"seed":seed,"random_algorithm":null}))],
                Some(0),
            )
            .unwrap();
        let b = explicit
            .apply_with_outcomes(
                &[command(
                    json!({"seed":seed,"random_algorithm":"splitmix64_v1"}),
                )],
                Some(0),
            )
            .unwrap();
        assert_eq!(omitted.scene(), explicit.scene());
        assert_eq!(a.transforms[0].influence, b.transforms[0].influence);
        let old = serde_json::to_value(&a.transforms[0]).unwrap();
        assert!(old.get("random_algorithm").is_none());
        assert_eq!(
            b.transforms[0].random_algorithm,
            Some(transform::RandomAlgorithm::Splitmix64V1)
        );
    }
}

#[test]
fn invalid_algorithm_and_seed_requests_and_failed_batches_are_atomic() {
    let before = scene();
    let mut editor = Editor::new(before.clone()).unwrap();
    for options in [
        json!({"seed":4294967296_u64}),
        json!({"seed":u64::MAX}),
        json!({"seed":null}),
        json!({"falloff":"linear","seed":null}),
        json!({"falloff":"linear","seed":1}),
    ] {
        assert!(
            editor
                .apply_with_outcomes(&[command(options)], Some(0))
                .is_err()
        );
        assert_eq!(editor.scene(), &before);
        assert!(editor.undo(Some(0)).is_err());
    }
    assert!(
        editor
            .apply_with_outcomes(
                &[command(json!({})), command(json!({"seed":4294967296_u64}))],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
    assert!(
        serde_json::from_value::<transform::Proportional>(json!({
            "radius":1,"falloff":"random","seed":0,"random_algorithm":"unversioned"
        }))
        .is_err()
    );
}

#[test]
fn saved_requests_replay_exactly_and_failed_saves_publish_no_state() {
    let folder =
        std::env::temp_dir().join(format!("formora-random-falloff-{}", std::process::id()));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let before = scene();
    let encoded = serde_json::to_vec(&ApplyRequest {
        expected_revision: 0,
        commands: vec![command(json!({"seed":2147483648_u64}))],
    })
    .unwrap();
    let after;
    let influence;
    {
        let mut session = Session::create(&path, before.clone()).unwrap();
        let result = session
            .apply_with_result(serde_json::from_slice(&encoded).unwrap())
            .unwrap();
        influence = result.transforms[0].influence.clone();
        after = session.scene().clone();
        assert_eq!(Scene::load(&path).unwrap(), after);
        session
            .undo(UndoRequest {
                expected_revision: 1,
            })
            .unwrap();
        let mut undone = session.scene().clone();
        undone.revision = before.revision;
        assert_eq!(undone, before);
    }
    let mut replay = Editor::new(before.clone()).unwrap();
    let request: ApplyRequest = serde_json::from_slice(&encoded).unwrap();
    let result = replay
        .apply_with_outcomes(&request.commands, Some(0))
        .unwrap();
    assert_eq!(result.transforms[0].influence, influence);
    assert_eq!(replay.scene(), &after);
    let failed = folder.join("failed.json");
    {
        let mut session = Session::create(&failed, before.clone()).unwrap();
        std::fs::remove_file(&failed).unwrap();
        std::fs::create_dir(&failed).unwrap();
        assert!(
            session
                .apply(serde_json::from_slice(&encoded).unwrap())
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
    }
    std::fs::remove_dir_all(folder).unwrap();
}
