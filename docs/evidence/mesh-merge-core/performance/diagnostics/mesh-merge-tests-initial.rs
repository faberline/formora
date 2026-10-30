//! Before-code behavior tests for the persistent merge operation.
use formora::mesh::MeshAsset;
use formora::mesh::creation::AuthoringContext;
use formora::scene::{Command, Editor, Entity, EntityKind, Geometry, Scene, Transform};
use serde_json::{Value, json};

fn asset() -> Value {
    json!({
        "vertices":{"a":[0.,0.,0.],"b":[2.,0.,0.],"c":[3.,2.,0.]},
        "triangles":{},"edges":{"ab":["a","b"],"ac":["a","c"],"bc":["b","c"]},
        "polygons":{"face":{"vertices":["a","b","c"],
            "uv_layers":{"Detail":[[0.,0.],[1.,0.],[1.,1.]],"Layout":[[0.,0.],[-1.,0.],[-1.,1.]]},
            "corner_normals":null,"normal":null,"smooth":true,"material_slot":0}},
        "uv_layout":{"layers":["Detail","Layout"],"active":"Layout"},
        "material_slots":[null],"edge_seams":["bc"],"vertex_groups":["pin","soft"],
        "vertex_weights":{"a":{"pin":0.,"soft":0.25},"b":{"pin":1.,"soft":0.75},"c":{"pin":0.}},
        "integer_attributes":{
            "vertices":{"capture":{"a":0,"b":1,"c":2},"signed":{"a":-1,"b":0,"c":7}},
            "edges":{"capture":{"ab":0,"ac":1,"bc":2}},
            "polygons":{"capture":{"face":5}},"triangles":{}},
        "editing":{"mode":["vertex"],"selected":{"vertices":["a","b"],"edges":["ab"],"faces":[]},
            "hidden":{"vertices":[],"edges":[],"faces":[]},
            "history":[{"domain":"vertex","id":"a"},{"domain":"vertex","id":"b"}],"active_face":null}
    })
}

fn editor(value: Value) -> Editor {
    let asset: MeshAsset = serde_json::from_value(value).unwrap();
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(), asset);
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
    scene.authoring_context = Some(AuthoringContext {
        cursor_location: [8., 9., 10.],
        ..AuthoringContext::default()
    });
    Editor::new(scene).unwrap()
}

fn command(method: &str, uvs: bool) -> Command {
    serde_json::from_value(json!({"operation":"merge_mesh","merge":{
        "entity":"target","method":method,"uvs":uvs,"max_components":1000}}))
    .unwrap()
}

fn saved(editor: &Editor) -> Value {
    serde_json::to_value(&editor.scene().mesh_assets["mesh"]).unwrap()
}

#[test]
fn center_welds_topology_and_interpolates_real_signed_integer_and_group_data() {
    let mut editor = editor(asset());
    let before = editor.scene().clone();
    let result = editor
        .apply_with_outcomes(&[command("center", false)], Some(0))
        .unwrap();
    let mesh = saved(&editor);
    assert_eq!(mesh["vertices"], json!({"a":[1.,0.,0.],"c":[3.,2.,0.]}));
    assert_eq!(mesh["edges"], json!({"ac":["a","c"]}));
    assert!(
        mesh.get("polygons")
            .is_none_or(|v| v.as_object().unwrap().is_empty())
    );
    assert_eq!(
        mesh["integer_attributes"]["vertices"]["capture"],
        json!({"a":1,"c":2})
    );
    assert_eq!(
        mesh["integer_attributes"]["vertices"]["signed"],
        json!({"a":-1,"c":7})
    );
    assert_eq!(
        mesh["integer_attributes"]["edges"]["capture"],
        json!({"ac":1})
    );
    assert_eq!(mesh["vertex_weights"]["a"], json!({"pin":0.5,"soft":0.5}));
    assert_eq!(mesh["vertex_weights"]["c"], json!({"pin":0.}));
    assert_eq!(mesh["uv_layout"], asset()["uv_layout"]);
    assert_eq!(mesh["edge_seams"], json!(["ac"]));
    assert_eq!(editor.scene().entities, before.entities);
    let result = serde_json::to_value(result).unwrap();
    assert_eq!(result["merges"].as_array().unwrap().len(), 1);
    assert_eq!(result["merges"][0]["status"], "finished");
    assert_eq!(result["merges"][0]["mesh_asset"], "mesh");
    assert_eq!(
        result["merges"][0]["shared_instances"],
        json!(["shared", "target"])
    );
}

#[test]
fn first_last_preserve_endpoint_data_and_zero_weights() {
    for (method, id, point, weights) in [
        ("first", "a", [0., 0., 0.], json!({"pin":0.,"soft":0.25})),
        ("last", "b", [2., 0., 0.], json!({"pin":1.,"soft":0.75})),
    ] {
        let mut editor = editor(asset());
        editor.apply(&[command(method, true)], Some(0)).unwrap();
        let mesh = saved(&editor);
        assert_eq!(mesh["vertices"][id], json!(point));
        assert_eq!(mesh["vertex_weights"][id], weights);
        assert_eq!(mesh["vertices"].as_object().unwrap().len(), 2);
        assert_eq!(
            mesh["integer_attributes"]["vertices"]["capture"][id],
            asset()["integer_attributes"]["vertices"]["capture"][id]
        );
    }
}

#[test]
fn cursor_uses_actual_context_and_changes_the_shared_asset_once() {
    let mut editor = editor(asset());
    editor.apply(&[command("cursor", false)], Some(0)).unwrap();
    let mesh = saved(&editor);
    assert_eq!(mesh["vertices"]["a"], json!([8., 9., 10.]));
    assert_eq!(mesh["vertices"]["c"], json!([3., 2., 0.]));
    assert_eq!(
        editor.scene().entities["target"].content,
        editor.scene().entities["shared"].content
    );
}

#[test]
fn collapse_counts_every_edge_endpoint_in_the_component_mean() {
    let mut value = asset();
    value["vertices"]["c"] = json!([10., 0., 0.]);
    value["edges"].as_object_mut().unwrap().remove("ac");
    value["polygons"] = json!({});
    value["integer_attributes"]["edges"]["capture"]
        .as_object_mut()
        .unwrap()
        .remove("ac");
    value["integer_attributes"]["polygons"]["capture"] = json!({});
    value["editing"]["selected"]["vertices"] = json!(["a", "b", "c"]);
    value["editing"]["selected"]["edges"] = json!(["ab", "bc"]);
    let mut editor = editor(value);
    editor
        .apply(&[command("collapse", false)], Some(0))
        .unwrap();
    let mesh = saved(&editor);
    let points = mesh["vertices"].as_object().unwrap();
    assert_eq!(points.len(), 1);
    assert_eq!(points.values().next().unwrap(), &json!([3.5, 0., 0.]));
}

#[test]
fn an_empty_first_request_is_atomic_and_center_is_an_explicit_noop() {
    let mut value = asset();
    value["editing"]["selected"] = json!({"vertices":[],"edges":[],"faces":[]});
    value["editing"]["history"] = json!([]);
    let mut editor = editor(value);
    let before = editor.scene().clone();
    assert!(editor.apply(&[command("first", false)], Some(0)).is_err());
    assert_eq!(editor.scene(), &before);
    let result = editor
        .apply_with_outcomes(&[command("center", false)], Some(0))
        .unwrap();
    let mut expected = before;
    expected.revision = 1;
    assert_eq!(editor.scene(), &expected);
    assert_eq!(
        serde_json::to_value(result).unwrap()["merges"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
}

#[test]
fn stale_budget_and_late_batch_failures_do_not_publish_a_partial_weld() {
    let mut editor = editor(asset());
    let before = editor.scene().clone();
    assert!(editor.apply(&[command("center", false)], Some(5)).is_err());
    assert_eq!(editor.scene(), &before);
    let low: Command = serde_json::from_value(json!({"operation":"merge_mesh","merge":{
        "entity":"target","method":"center","max_components":1}}))
    .unwrap();
    assert!(editor.apply(&[low], Some(0)).is_err());
    assert_eq!(editor.scene(), &before);
    let invalid = Command::SetMeshVertices {
        id: "missing".into(),
        positions: [("a".into(), [1., 2., 3.])].into_iter().collect(),
    };
    assert!(
        editor
            .apply(&[command("center", false), invalid], Some(0))
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
}

#[test]
fn undo_replay_and_json_reload_preserve_actual_topology_and_attribute_values() {
    let mut editor = editor(asset());
    let before = editor.scene().clone();
    editor.apply(&[command("center", true)], Some(0)).unwrap();
    let after = editor.scene().clone();
    let loaded: Scene = serde_json::from_slice(&serde_json::to_vec(&after).unwrap()).unwrap();
    loaded.validate().unwrap();
    assert_eq!(loaded, after);
    editor.undo(Some(1)).unwrap();
    let mut expected = before;
    expected.revision = 2;
    assert_eq!(editor.scene(), &expected);
    editor.apply(&[command("center", true)], Some(2)).unwrap();
    let mut expected = after;
    expected.revision = 3;
    assert_eq!(editor.scene(), &expected);
}

#[test]
fn unselected_triangle_storage_and_explicit_normals_remain_exact() {
    let mut value = asset();
    for (id, point, tag) in [
        ("d", [5., 0., 0.], 3),
        ("e", [6., 0., 0.], 4),
        ("f", [5., 1., 0.], 5),
    ] {
        value["vertices"][id] = json!(point);
        value["integer_attributes"]["vertices"]["capture"][id] = json!(tag);
        value["integer_attributes"]["vertices"]["signed"][id] = json!(-tag);
        value["vertex_weights"][id] = json!({});
    }
    for (id, endpoints, tag) in [
        ("de", ["d", "e"], 3),
        ("df", ["d", "f"], 4),
        ("ef", ["e", "f"], 5),
    ] {
        value["edges"][id] = json!(endpoints);
        value["integer_attributes"]["edges"]["capture"][id] = json!(tag);
    }
    let triangle = json!({"vertices":["d","e","f"],
        "uv_layers":{"Detail":[[0.,0.],[1.,0.],[0.,1.]],"Layout":[[0.,0.],[-1.,0.],[0.,1.]]},
        "corner_normals":[[0.,0.,1.],[0.,0.,1.],[0.,0.,1.]],"material_slot":0});
    value["triangles"]["untouched"] = triangle.clone();
    value["smooth_triangles"] = json!(["untouched"]);
    value["integer_attributes"]["triangles"]["capture"] = json!({"untouched":10});
    let mut editor = editor(value);
    editor.apply(&[command("center", true)], Some(0)).unwrap();
    let mesh = saved(&editor);
    assert_eq!(mesh["triangles"]["untouched"], triangle);
    assert_eq!(
        mesh["integer_attributes"]["triangles"]["capture"],
        json!({"untouched":10})
    );
    assert_eq!(mesh["smooth_triangles"], json!(["untouched"]));
}

#[test]
fn integer_attribute_coverage_and_unknown_fields_are_validated() {
    for mutate in [
        |v: &mut Value| {
            v["integer_attributes"]["vertices"]["signed"]
                .as_object_mut()
                .unwrap()
                .remove("c");
        },
        |v: &mut Value| {
            v["integer_attributes"]["edges"]["capture"]["missing"] = json!(1);
        },
        |v: &mut Value| {
            v["integer_attributes"]["vertices"][""] = json!({"a":0,"b":1,"c":2});
        },
        |v: &mut Value| {
            v["integer_attributes"]["extra"] = json!({});
        },
    ] {
        let mut value = asset();
        mutate(&mut value);
        let parsed = serde_json::from_value::<MeshAsset>(value);
        assert!(parsed.is_err() || parsed.unwrap().validate().is_err());
    }
    let before: MeshAsset = serde_json::from_value(asset()).unwrap();
    let raw = serde_json::to_vec(&before).unwrap();
    let duplicate = String::from_utf8(raw)
        .unwrap()
        .replace("\"a\":-1", "\"a\":-1,\"a\":0");
    assert!(serde_json::from_str::<MeshAsset>(&duplicate).is_err());
}
