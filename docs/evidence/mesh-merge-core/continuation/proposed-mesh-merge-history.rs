//! Frozen controls for the pinned source's original-history overlap flags.
use formora::scene::{Command, Editor, Scene};
use serde_json::json;

fn editor(history: &[&str], disconnected: bool) -> Editor {
    let vertices = if disconnected {
        json!({"a":[0.,0.,0.],"b":[2.,0.,0.],"c":[10.,0.,0.],"d":[20.,0.,0.],"e":[24.,0.,0.]})
    } else {
        json!({"a":[0.,0.,0.],"b":[2.,0.,0.],"c":[10.,0.,0.]})
    };
    let edges = if disconnected {
        json!({"ab":["a","b"],"bc":["b","c"],"de":["d","e"]})
    } else {
        json!({"ab":["a","b"],"bc":["b","c"]})
    };
    let selected_vertices: Vec<_> = vertices.as_object().unwrap().keys().cloned().collect();
    let selected_edges: Vec<_> = edges.as_object().unwrap().keys().cloned().collect();
    let mut scene = serde_json::to_value(Scene::default()).unwrap();
    scene["mesh_assets"]["mesh"] = json!({"vertices":vertices,"edges":edges,"triangles":{},"material_slots":[],
        "editing":{"mode":["vertex"],"selected":{"vertices":selected_vertices,"edges":selected_edges,"faces":[]},
        "hidden":{"vertices":[],"edges":[],"faces":[]},
        "history":history.iter().map(|id|json!({"domain":"vertex","id":id})).collect::<Vec<_>>(),"active_face":null}});
    scene["entities"]["owner"] = json!({"name":"Owner","parent":null,
        "transform":{"translation":[0.,0.,0.],"rotation":{"kind":"euler","angles":[0.,0.,0.],"order":"xyz"},"scale":[1.,1.,1.]},
        "content":{"kind":"mesh","geometry":{"kind":"asset","id":"mesh"},"material":null}});
    Editor::new(serde_json::from_value(scene).unwrap()).unwrap()
}

fn apply(editor: &mut Editor, method: &str) -> Vec<String> {
    let command: Command = serde_json::from_value(json!({"operation":"merge_mesh","merge":{"entity":"owner","method":method}})).unwrap();
    editor.apply(&[command], Some(0)).unwrap();
    let editing = editor.scene().mesh_assets["mesh"].editing.as_ref().unwrap();
    editing.history.iter().map(|item| match item {
        formora::mesh::selection::Component::Vertex { id } => id.clone(),
        _ => panic!("this input has vertex history only"),
    }).collect()
}

#[test]
fn removed_only_history_does_not_create_a_center_survivor_entry() {
    let mut editor = editor(&["c"], false);
    assert!(apply(&mut editor, "center").is_empty());
    assert_eq!(editor.scene().mesh_assets["mesh"].vertices["a"], [4.,0.,0.]);
}

#[test]
fn removed_only_history_does_not_create_a_collapse_survivor_entry() {
    let mut editor = editor(&["c"], false);
    assert!(apply(&mut editor, "collapse").is_empty());
    assert_eq!(editor.scene().mesh_assets["mesh"].vertices["b"], [3.5,0.,0.]);
}

#[test]
fn an_original_survivor_history_flag_keeps_the_first_mapped_entry_once() {
    let mut editor = editor(&["c","a"], false);
    assert_eq!(apply(&mut editor, "center"), ["a"]);
}

#[test]
fn explicit_history_endpoint_keeps_its_actual_original_entry() {
    let mut editor = editor(&["c"], false);
    assert_eq!(apply(&mut editor, "first"), ["c"]);
    assert_eq!(editor.scene().mesh_assets["mesh"].vertices["c"], [10.,0.,0.]);
}

#[test]
fn disconnected_components_keep_only_the_original_survivor_history_flags() {
    let mut editor = editor(&["c","d"], true);
    assert_eq!(apply(&mut editor, "collapse"), ["d"]);
    let vertices = &editor.scene().mesh_assets["mesh"].vertices;
    assert_eq!(vertices["b"], [3.5,0.,0.]);
    assert_eq!(vertices["d"], [22.,0.,0.]);
}
