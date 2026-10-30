//! Independent persistence and receipt gates for unfrozen numeric inputs.
use formora::scene::{Command, Editor, Scene};
use serde_json::{Value, json};

fn editor(point: [f64; 3], mode: &str, isolated: bool) -> Editor {
    let mut scene = serde_json::to_value(Scene::default()).unwrap();
    scene["mesh_assets"]["mesh"] = json!({
        "vertices":{"a":point,"b":[2.,0.,0.],"c":[3.,2.,0.]},
        "triangles":{},"edges":if isolated {json!({})} else {json!({"ab":["a","b"],"ac":["a","c"],"bc":["b","c"]})},
        "material_slots":[],
        "editing":{"mode":[mode],"selected":{"vertices":if isolated {json!(["a"])} else {json!(["a","b"])},"edges":if isolated {json!([])} else {json!(["ab"])},"faces":[]},
        "hidden":{"vertices":[],"edges":[],"faces":[]},
        "history":[{"domain":"vertex","id":"a"}],"active_face":null}
    });
    scene["entities"]["owner"] = json!({"name":"Owner","parent":null,
        "transform":{"translation":[0.,0.,0.],"rotation":{"kind":"euler","angles":[0.,0.,0.],"order":"xyz"},"scale":[1.,1.,1.]},
        "content":{"kind":"mesh","geometry":{"kind":"asset","id":"mesh"},"material":null}});
    Editor::new(serde_json::from_value(scene).unwrap()).unwrap()
}

fn merge(method: &str) -> Command {
    serde_json::from_value(
        json!({"operation":"merge_mesh","merge":{"entity":"owner","method":method}}),
    )
    .unwrap()
}

#[test]
fn explicit_endpoint_keeps_its_stored_f64_position_without_an_extra_round_trip() {
    let point = [0.123456789012345, -0.234567890123456, 0.345678901234567];
    let mut editor = editor(point, "vertex", false);
    editor.apply(&[merge("first")], Some(0)).unwrap();
    assert_eq!(editor.scene().mesh_assets["mesh"].vertices["a"], point);
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["c"],
        [3., 2., 0.]
    );
}

#[test]
fn an_existing_survivor_edge_reports_its_real_geometric_change() {
    let mut editor = editor([0.; 3], "vertex", false);
    let result = editor
        .apply_with_outcomes(&[merge("center")], Some(0))
        .unwrap();
    assert_eq!(editor.scene().mesh_assets["mesh"].edges["ac"], ["a", "c"]);
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [1., 0., 0.]
    );
    assert!(result.merges[0].changed.edges.contains("ac"));
    assert!(!result.merges[0].created.edges.contains("ac"));
    assert!(!result.merges[0].removed.edges.contains("ac"));
}

#[test]
fn successful_collapse_without_selected_edges_clears_nonvertex_mode_flags() {
    let mut editor = editor([0.; 3], "edge", true);
    let before = editor.scene().mesh_assets["mesh"].vertices.clone();
    let result = editor
        .apply_with_outcomes(&[merge("collapse")], Some(0))
        .unwrap();
    let asset = &editor.scene().mesh_assets["mesh"];
    assert_eq!(asset.vertices, before);
    assert!(asset.editing.as_ref().unwrap().selected.vertices.is_empty());
    assert!(asset.editing.as_ref().unwrap().history.is_empty());
    assert!(result.merges[0].changed.vertices.contains("a"));
    let receipt: Value = serde_json::to_value(&result.merges[0]).unwrap();
    assert_eq!(receipt["status"], "finished");
    assert!(
        receipt["removed"]["vertices"]
            .as_array()
            .unwrap()
            .is_empty()
    );
}
