//! Before-code controls for context-wide merge; inputs are authored literals.
use formora::mesh::creation::AuthoringContext;
use formora::objects::Context;
use formora::scene::{Command, Editor, Entity, EntityKind, Geometry, Scene, Transform};
use formora::transforms::Precision;
use serde_json::{Value, json};

fn asset(points: [f64; 3], edit: bool) -> Value {
    let mut value = json!({
        "vertices":{"a":[points[0],0.,0.],"b":[points[1],0.,0.],"c":[points[2],0.,0.]},
        "edges":{"ab":["a","b"],"bc":["b","c"]},"triangles":{},"material_slots":[]
    });
    if edit {
        value["editing"] = json!({
            "mode":["vertex"],
            "selected":{"vertices":["a","b","c"],"edges":["ab","bc"],"faces":[]},
            "hidden":{"vertices":[],"edges":[],"faces":[]},
            "history":[{"domain":"vertex","id":"a"},{"domain":"vertex","id":"c"}],
            "active_face":null
        });
    }
    value
}

fn editor(active: &str, order: &[&str]) -> Editor {
    let mut scene = Scene::default();
    for (name, points, edit) in [
        ("mesh_a", [0., 2., 10.], true),
        ("mesh_b", [20., 22., 34.], true),
        ("mesh_outside", [90., 92., 100.], false),
    ] {
        scene.mesh_assets.insert(
            name.into(),
            serde_json::from_value(asset(points, edit)).unwrap(),
        );
    }
    for (name, mesh, translation, scale) in [
        ("a", "mesh_a", [2., 0., 0.], [2., 1., 1.]),
        ("alias", "mesh_a", [40., 0., 0.], [1., 1., 1.]),
        ("b", "mesh_b", [0., 4., 0.], [1., 2., 1.]),
        ("outside", "mesh_outside", [9., 9., 9.], [1., 1., 1.]),
    ] {
        scene.entities.insert(
            name.into(),
            Entity {
                name: name.into(),
                parent: None,
                transform: Transform {
                    translation,
                    scale,
                    precision: Precision::F32,
                    ..Transform::default()
                },
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id: mesh.into() },
                    material: None,
                },
            },
        );
    }
    let a_owner = if active == "a" || active == "alias" {
        active
    } else {
        order
            .iter()
            .copied()
            .find(|name| matches!(*name, "a" | "alias"))
            .unwrap()
    };
    scene.object_context = Some(Context {
        order: order.iter().map(|id| (*id).into()).collect(),
        selected: ["a", "alias", "b"].into_iter().map(String::from).collect(),
        active: Some(active.into()),
        edit_objects: [a_owner, "b"].into_iter().map(String::from).collect(),
        ..Context::default()
    });
    scene.authoring_context = Some(AuthoringContext {
        cursor_location: [8., 12., 16.],
        ..AuthoringContext::default()
    });
    Editor::new(scene).unwrap()
}

fn request(method: &str, budget: usize) -> Command {
    serde_json::from_value(json!({"operation":"merge_edit_meshes","merge":{
        "method":method,"uvs":false,"max_components":budget
    }}))
    .expect("the frozen context-wide merge command must be admitted")
}

fn result(editor: &mut Editor, method: &str) -> Value {
    serde_json::to_value(
        editor
            .apply_with_outcomes(&[request(method, 1000)], Some(0))
            .unwrap(),
    )
    .unwrap()
}

fn point(editor: &Editor, mesh: &str) -> [f64; 3] {
    let asset = &editor.scene().mesh_assets[mesh];
    assert_eq!(asset.vertices.len(), 1);
    *asset.vertices.values().next().unwrap()
}

fn near(actual: [f64; 3], expected: [f64; 3]) {
    for (a, b) in actual.into_iter().zip(expected) {
        assert!((a - b).abs() <= 1e-6, "{actual:?} != {expected:?}");
    }
}

#[test]
fn center_processes_both_assets_once_and_preserves_context_and_outside() {
    let mut editor = editor("a", &["a", "alias", "b", "outside"]);
    let before = editor.scene().clone();
    let outcome = result(&mut editor, "center");
    near(point(&editor, "mesh_a"), [4., 0., 0.]);
    near(
        point(&editor, "mesh_b"),
        [f64::from(76_f32 * (1_f32 / 3_f32)), 0., 0.],
    );
    assert_eq!(editor.scene().entities, before.entities);
    assert_eq!(editor.scene().object_context, before.object_context);
    assert_eq!(
        editor.scene().mesh_assets["mesh_outside"],
        before.mesh_assets["mesh_outside"]
    );
    let receipt = &outcome["edit_merges"][0];
    assert_eq!(receipt["command_index"], 0);
    assert_eq!(receipt["active_entity"], "a");
    assert_eq!(receipt["provider_order"], json!(["a", "b"]));
    assert_eq!(receipt["before"]["vertices"], 6);
    assert_eq!(receipt["after"]["vertices"], 2);
    assert_eq!(receipt["providers"].as_array().unwrap().len(), 2);
    assert_eq!(
        receipt["providers"][0]["shared_instances"],
        json!(["a", "alias"])
    );
    for row in receipt["providers"].as_array().unwrap() {
        assert_eq!(row["outcome"], "merged");
        assert_eq!(row["merge"]["status"], "finished");
    }
}

#[test]
fn cursor_uses_each_actual_provider_including_an_active_or_secondary_alias() {
    for (active, order, expected_a, expected_order) in [
        (
            "alias",
            vec!["a", "b", "alias", "outside"],
            [-32., 12., 16.],
            vec!["alias", "b"],
        ),
        (
            "b",
            vec!["b", "alias", "a", "outside"],
            [-32., 12., 16.],
            vec!["b", "alias"],
        ),
        (
            "b",
            vec!["b", "a", "alias", "outside"],
            [3., 12., 16.],
            vec!["b", "a"],
        ),
    ] {
        let mut editor = editor(active, &order);
        let outcome = result(&mut editor, "cursor");
        near(point(&editor, "mesh_a"), expected_a);
        near(point(&editor, "mesh_b"), [8., 4., 16.]);
        assert_eq!(
            outcome["edit_merges"][0]["provider_order"],
            json!(expected_order)
        );
    }
}

#[test]
fn first_last_stop_after_active_success_and_leave_other_data_exact() {
    for active in ["a", "alias", "b"] {
        for (method, endpoint) in [("first", "a"), ("last", "c")] {
            let mut editor = editor(active, &["b", "alias", "a", "outside"]);
            let before = editor.scene().clone();
            let active_mesh = if active == "b" { "mesh_b" } else { "mesh_a" };
            let other_mesh = if active_mesh == "mesh_a" {
                "mesh_b"
            } else {
                "mesh_a"
            };
            let outcome = result(&mut editor, method);
            near(
                point(&editor, active_mesh),
                before.mesh_assets[active_mesh].vertices[endpoint],
            );
            assert_eq!(
                editor.scene().mesh_assets[other_mesh],
                before.mesh_assets[other_mesh]
            );
            let receipt = &outcome["edit_merges"][0];
            assert_eq!(receipt["provider_order"][0], active);
            assert_eq!(receipt["providers"][0]["outcome"], "merged");
            assert_eq!(
                receipt["providers"][1]["outcome"],
                "not_processed_after_success"
            );
            assert!(receipt["providers"][1]["merge"].is_null());
        }
    }
}

#[test]
fn unavailable_active_history_rejects_without_other_history_fallback() {
    for method in ["first", "last"] {
        for scenario in [
            "no_history",
            "edge_endpoint",
            "no_vertex_mode",
            "empty_active",
        ] {
            let initial = editor("a", &["b", "a", "alias", "outside"]);
            let mut value = serde_json::to_value(initial.scene()).unwrap();
            let edit = &mut value["mesh_assets"]["mesh_a"]["editing"];
            match scenario {
                "no_history" => edit["history"] = json!([]),
                "edge_endpoint" => edit["history"] = json!([{"domain":"edge","id":"ab"}]),
                "no_vertex_mode" => edit["mode"] = json!(["edge"]),
                _ => {
                    edit["selected"] = json!({"vertices":[],"edges":[],"faces":[]});
                    edit["history"] = json!([]);
                }
            }
            let mut editor = Editor::new(serde_json::from_value(value).unwrap()).unwrap();
            let before = editor.scene().clone();
            let error = editor.apply(&[request(method, 1000)], Some(0)).unwrap_err();
            assert!(error.0.contains("unavailable"), "{error:?}");
            assert_eq!(editor.scene(), &before);
        }
    }
}

#[test]
fn all_empty_inputs_finish_with_explicit_skips_and_no_asset_mutation() {
    let initial = editor("a", &["a", "alias", "b", "outside"]);
    let mut value = serde_json::to_value(initial.scene()).unwrap();
    for mesh in ["mesh_a", "mesh_b"] {
        value["mesh_assets"][mesh]["editing"]["selected"] =
            json!({"vertices":[],"edges":[],"faces":[]});
        value["mesh_assets"][mesh]["editing"]["history"] = json!([]);
    }
    let mut editor = Editor::new(serde_json::from_value(value).unwrap()).unwrap();
    let before = editor.scene().clone();
    let outcome = result(&mut editor, "center");
    assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
    assert_eq!(outcome["edit_merges"][0]["status"], "finished");
    for row in outcome["edit_merges"][0]["providers"].as_array().unwrap() {
        assert_eq!(row["outcome"], "skipped_empty_selection");
        assert!(row["merge"].is_null());
    }
}

#[test]
fn aggregate_budget_stale_revision_and_late_batch_failure_are_atomic() {
    let mut editor = editor("a", &["a", "alias", "b", "outside"]);
    let before = editor.scene().clone();
    // Each asset has five components. Seven admits either single asset,
    // but must reject the ten-component unique-data aggregate.
    let error = editor.apply(&[request("center", 7)], Some(0)).unwrap_err();
    assert!(error.0.contains("budget"), "{error:?}");
    assert_eq!(editor.scene(), &before);
    assert!(editor.apply(&[request("center", 1000)], Some(5)).is_err());
    assert_eq!(editor.scene(), &before);
    let invalid = Command::SetMeshVertices {
        id: "definitely-missing".into(),
        positions: [("a".into(), [1., 2., 3.])].into_iter().collect(),
    };
    let error = editor
        .apply(&[request("center", 1000), invalid], Some(0))
        .unwrap_err();
    assert!(
        error.0.contains("unknown mesh asset"),
        "late command was not reached: {error:?}"
    );
    assert_eq!(editor.scene(), &before);
}

#[test]
fn undo_replay_and_fresh_scene_load_preserve_all_context_and_results() {
    let mut editor = editor("alias", &["b", "a", "alias", "outside"]);
    let mut before = editor.scene().clone();
    editor.apply(&[request("center", 1000)], Some(0)).unwrap();
    let mut after = editor.scene().clone();
    editor.undo(Some(1)).unwrap();
    before.revision = 2;
    assert_eq!(editor.scene(), &before);
    editor.apply(&[request("center", 1000)], Some(2)).unwrap();
    after.revision = 3;
    assert_eq!(editor.scene(), &after);
    let decoded: Scene =
        serde_json::from_slice(&serde_json::to_vec(editor.scene()).unwrap()).unwrap();
    let fresh = Editor::new(decoded).unwrap();
    assert_eq!(fresh.scene(), editor.scene());
}

#[test]
fn legacy_entity_merge_still_only_changes_its_explicit_asset() {
    let mut editor = editor("a", &["a", "alias", "b", "outside"]);
    let before = editor.scene().clone();
    let command: Command = serde_json::from_value(json!({"operation":"merge_mesh","merge":{
        "entity":"a","method":"center","uvs":false,"max_components":1000
    }}))
    .unwrap();
    editor.apply(&[command], Some(0)).unwrap();
    near(point(&editor, "mesh_a"), [4., 0., 0.]);
    assert_eq!(
        editor.scene().mesh_assets["mesh_b"],
        before.mesh_assets["mesh_b"]
    );
    assert_eq!(
        editor.scene().mesh_assets["mesh_outside"],
        before.mesh_assets["mesh_outside"]
    );
}
