//! Unseen analytic data. No source capture or expected-output file is read.
use formora::scene::{Command, Editor, Scene};
use formora::session::InspectRequest;
use serde_json::json;

fn editor() -> Editor {
    let mut scene = serde_json::to_value(Scene::default()).unwrap();
    let mut asset = json!({
        "vertices":{"a":[0.,0.,0.],"b":[1.,-1.,0.],"c":[2.,0.,0.],"d":[2.,1.,0.],"e":[1.,2.,0.],"f":[0.,1.,0.],"g":[-2.,0.,0.],"h":[-1.,0.,0.],"i":[-2.,1.,0.]},
        "edges":{"ab":["a","b"],"bc":["b","c"],"cd":["c","d"],"de":["d","e"],"ef":["e","f"],"fa":["f","a"],"gh":["g","h"],"hi":["h","i"],"ig":["i","g"]},
        "polygons":{"p":{"vertices":["a","b","c","d","e","f"],
            "uv_layers":{"Layout":[[-2.,1.],[-1.,3.],[0.,-1.],[0.123456789012345,0.5],[1.,0.25],[-0.5,2.]],"Detail":[[2.,2.],[3.,1.],[-2.,-2.],[1.,0.],[0.,1.],[-1.,0.]]},
            "corner_normals":[[0.,0.,1.],[0.,0.,1.],[0.,0.,1.],[0.,0.,1.],[0.,0.,1.],[0.,0.,1.]],"normal":[0.,0.,1.],"smooth":false,"material_slot":null}},
        "triangles":{"t":{"vertices":["g","h","i"],"uv_layers":{"Layout":[[0.111111111111111,0.222222222222222],[1.,0.],[0.,1.]],"Detail":[[0.,0.],[1.,0.],[0.,1.]]},"corner_normals":[[0.,0.,1.],[0.,0.,1.],[0.,0.,1.]],"material_slot":null}},
        "uv_layout":{"layers":["Layout","Detail"],"active":"Detail"},"material_slots":[],"edge_seams":["bc"],
        "vertex_groups":["pin","soft"],"vertex_weights":{"a":{"pin":0.,"soft":0.25},"c":{"pin":1.,"soft":0.75}},
        "integer_attributes":{"vertices":{"signed":{"a":-1,"b":2,"c":0,"d":3,"e":4,"f":5,"g":6,"h":8,"i":9},"tag":{"a":7,"b":7,"c":7,"d":3,"e":4,"f":5,"g":6,"h":8,"i":9}},"edges":{"tag":{"ab":11,"bc":22,"cd":33,"de":44,"ef":55,"fa":66,"gh":77,"hi":88,"ig":99}},"polygons":{"tag":{"p":42}},"triangles":{"tag":{"t":77}}},
        "editing":{"mode":["vertex"],"selected":{"vertices":["a","c"],"edges":[],"faces":[]},"hidden":{"vertices":[],"edges":[],"faces":[]},"history":[{"domain":"vertex","id":"c"}],"active_face":null}
    });
    // Keep the input as authored values. No captured state enters this test.
    scene["mesh_assets"]["mesh"] = asset.take();
    scene["entities"]["parent"] = json!({"name":"Parent","parent":null,"transform":{"translation":[1.,2.,3.],"rotation":{"kind":"euler","angles":[0.,0.,std::f64::consts::FRAC_PI_2],"order":"xyz"},"scale":[2.,3.,4.]},"content":{"kind":"empty"}});
    let owner = json!({"name":"Owner","parent":"parent","transform":{"translation":[0.5,-0.25,0.125],"rotation":{"kind":"euler","angles":[std::f64::consts::FRAC_PI_2,0.,0.],"order":"xyz"},"scale":[1.,1.,1.]},"content":{"kind":"mesh","geometry":{"kind":"asset","id":"mesh"},"material":null}});
    scene["entities"]["owner"] = owner.clone();
    scene["entities"]["shared"] = owner;
    Editor::new(serde_json::from_value(scene).unwrap()).unwrap()
}

fn merge() -> Command {
    serde_json::from_value(json!({"operation":"merge_mesh","merge":{"entity":"owner","method":"center","uvs":true}})).unwrap()
}

#[test]
fn unselected_surviving_polygon_uv_keeps_its_stored_f64_value() {
    let mut editor = editor();
    let expected = editor.scene().mesh_assets["mesh"].polygons["p"].uv_layers["Layout"][3];
    editor.apply(&[merge()], Some(0)).unwrap();
    let mesh = &editor.scene().mesh_assets["mesh"];
    assert_eq!(mesh.polygons["p"].vertices, ["a","d","e","f"]);
    assert_eq!(mesh.polygons["p"].uv_layers["Layout"][1], expected);
}

#[test]
fn untouched_triangle_uv_normals_and_integer_data_remain_exact() {
    let mut editor = editor();
    let before = editor.scene().mesh_assets["mesh"].clone();
    editor.apply(&[merge()], Some(0)).unwrap();
    let mesh = &editor.scene().mesh_assets["mesh"];
    assert_eq!(mesh.triangles["t"], before.triangles["t"]);
    assert_eq!(mesh.integer_attributes.as_ref().unwrap().triangles, before.integer_attributes.as_ref().unwrap().triangles);
}

#[test]
fn heldout_split_attributes_shared_frames_and_undo_use_the_actual_core() {
    let mut editor = editor();
    let before = editor.scene().clone();
    let result = editor.apply_with_outcomes(&[merge()], Some(0)).unwrap();
    let mesh = &editor.scene().mesh_assets["mesh"];
    assert_eq!(mesh.vertices.len(), 8);
    assert_eq!(mesh.vertices["a"], [1.,0.,0.]);
    assert!(mesh.vertices.contains_key("b"));
    assert!(!mesh.vertices.contains_key("c"));
    assert_eq!(mesh.polygons["p"].uv_layers["Layout"][0], [-1.,0.]);
    assert_eq!(mesh.polygons["p"].uv_layers["Detail"][0], [0.,0.]);
    let attrs = mesh.integer_attributes.as_ref().unwrap();
    assert_eq!(attrs.vertices["signed"].0["a"], -1);
    assert_eq!(attrs.vertices["tag"].0["a"], attrs.vertices["tag"].0["b"]);
    assert_eq!(mesh.vertex_weights.as_ref().unwrap().0["a"].0["pin"], 0.5);
    assert_eq!(mesh.vertex_weights.as_ref().unwrap().0["a"].0["soft"], 0.5);
    assert_eq!(editor.scene().entities, before.entities);
    assert_eq!(result.merges[0].shared_instances, ["owner","shared"]);
    assert!(mesh.editing.as_ref().unwrap().history.is_empty());
    let query = InspectRequest { entity:Some("owner".into()), world:true, ..InspectRequest::default() }.inspect(editor.scene()).unwrap();
    let actual: [f64;3] = serde_json::from_value(query["world_vertices"]["a"].clone()).unwrap();
    for (value, expected) in actual.into_iter().zip([1.75,5.,3.5]) { assert!((value-expected).abs()<=1e-6); }
    let after = editor.scene().clone();
    let loaded: Scene = serde_json::from_slice(&serde_json::to_vec(&after).unwrap()).unwrap();
    loaded.validate().unwrap();
    assert_eq!(loaded, after);
    editor.undo(Some(1)).unwrap();
    let mut expected = before;expected.revision=2;assert_eq!(editor.scene(), &expected);
    editor.apply(&[merge()], Some(2)).unwrap();
    let mut expected = after;expected.revision=3;assert_eq!(editor.scene(), &expected);
}

#[test]
fn an_unselected_triangle_outside_f32_uv_range_remains_untouched() {
    let original = editor();
    let mut scene = original.scene().clone();
    scene.mesh_assets.get_mut("mesh").unwrap().triangles.get_mut("t").unwrap().uv_layers.get_mut("Layout").unwrap()[0] = [1e100,-1e100];
    let before = scene.mesh_assets["mesh"].triangles["t"].clone();
    let mut editor = Editor::new(scene).unwrap();
    editor.apply(&[merge()], Some(0)).unwrap();
    assert_eq!(editor.scene().mesh_assets["mesh"].triangles["t"], before);
}
