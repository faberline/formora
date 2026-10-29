use formora::mesh::{MeshAsset, normals, selection::*};
use formora::scene::*;
use serde_json::{Value, json};

fn asset() -> MeshAsset {
    let mut asset:MeshAsset=serde_json::from_value(json!({
        "vertices":{"a":[0,0,0],"b":[1,0,0],"c":[1,1,0],"d":[0,1,0],"hidden":[3,2,1]},
        "edges":{"ab":["a","b"],"bc":["b","c"],"cd":["c","d"],"da":["d","a"]},
        "triangles":{"legacy":{"vertices":["a","c","d"],"uv_layers":{"UV":[[0,0],[1,1],[0,1]]}}},
        "polygons":{"surface":{"vertices":["a","b","c","d"],"uv_layers":{"UV":[[0,0],[1,0],[1,1],[0,1]]},"smooth":true}},
        "uv_layout":{"layers":["UV"],"active":"UV"},"material_slots":[],
        "vertex_groups":["keep"],"vertex_weights":{"a":{"keep":0.75}},"edge_seams":["ab"],"smooth_triangles":["legacy"]
    })).unwrap();
    let mut editing = Editing::default();
    editing.selected.vertices = ["a".into(), "b".into()].into();
    editing.hidden.vertices.insert("hidden".into());
    set_editing(&mut asset, Some(editing)).unwrap();
    asset.validate().unwrap();
    asset
}
fn scene(asset: MeshAsset) -> Scene {
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(), asset);
    scene.entities.insert(
        "target".into(),
        Entity {
            name: "Target".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "mesh".into() },
                material: None,
            },
        },
    );
    scene
}
fn request() -> formora::mesh::transform::Request {
    serde_json::from_value(
        json!({"entity":"target","change":{"kind":"translate","value":[0.2,-0.1,0.3]}}),
    )
    .unwrap()
}

#[test]
fn transform_and_normal_entries_keep_every_metadata_rejection_and_transform_atomicity() {
    let original = serde_json::to_value(asset()).unwrap();
    let faults: [(&str, Value); 14] = [
        ("vertex_groups", json!(["keep", "keep"])),
        ("vertex_weights", json!({"missing":{"keep":0.5}})),
        ("vertex_weights", json!({"a":{"unknown":0.5}})),
        ("vertex_weights", json!({"a":{"keep":1.1}})),
        ("edge_seams", json!(["missing"])),
        ("smooth_triangles", json!(["missing"])),
        ("active_material_index", json!(1)),
        ("diagnostics", json!([""])),
        ("editing", json!({"mode":[],"selected":{"vertices":["a"]}})),
        ("editing", json!({"selected":{"vertices":["missing"]}})),
        (
            "editing",
            json!({"selected":{"vertices":["a"]},"hidden":{"vertices":["a"]}}),
        ),
        (
            "editing",
            json!({"selected":{"vertices":["a"]},"history":[{"domain":"vertex","id":"a"},{"domain":"vertex","id":"a"}]}),
        ),
        (
            "editing",
            json!({"selected":{"vertices":["a"]},"active_face":{"kind":"polygon","id":"missing"}}),
        ),
        (
            "uv_layout",
            json!({"layers":["UV","Other"],"active":"Other"}),
        ),
    ];
    for (field, value) in faults {
        let mut changed = original.clone();
        changed[field] = value;
        let asset: MeshAsset = serde_json::from_value(changed).unwrap();
        let error = asset.validate().unwrap_err();
        assert_eq!(
            normals::automatic(&asset).unwrap_err(),
            error,
            "normal: {field}"
        );
        let mut scene = scene(asset);
        let before = scene.clone();
        assert_eq!(
            formora::mesh::transform::execute(&mut scene, &request()).unwrap_err(),
            error,
            "transform: {field}"
        );
        assert_eq!(scene, before);
    }
}

#[test]
fn geometry_border_and_normal_payload_checks_remain_before_topology_reuse() {
    let mut missing_border = asset();
    missing_border.edges.remove("ab");
    let mut invalid_vertex = asset();
    invalid_vertex.vertices.insert("".into(), [0.; 3]);
    let mut invalid_normal = asset();
    invalid_normal.polygons.get_mut("surface").unwrap().normal = Some([2., 0., 0.]);
    let mut invalid_uv = asset();
    invalid_uv
        .polygons
        .get_mut("surface")
        .unwrap()
        .uv_layers
        .get_mut("UV")
        .unwrap()
        .pop();
    for asset in [missing_border, invalid_vertex, invalid_normal, invalid_uv] {
        let error = asset.validate().unwrap_err();
        assert_eq!(normals::automatic(&asset).unwrap_err(), error);
        let mut scene = scene(asset);
        let before = scene.clone();
        assert_eq!(
            formora::mesh::transform::execute(&mut scene, &request()).unwrap_err(),
            error
        );
        assert_eq!(scene, before);
    }
}

#[test]
fn successive_transforms_derive_normals_from_current_positions_without_a_stale_graph() {
    let before = scene(asset());
    let mut editor = Editor::new(before.clone()).unwrap();
    for revision in 0..3 {
        let command = Command::TransformMesh {
            transform: Box::new(request()),
        };
        editor.apply(&[command], Some(revision)).unwrap();
        let asset = &editor.scene().mesh_assets["mesh"];
        let automatic = normals::automatic(asset).unwrap();
        let resolved = normals::resolved(asset).unwrap();
        assert_eq!(automatic, resolved);
        assert_eq!(asset.editing, before.mesh_assets["mesh"].editing);
        assert_eq!(asset.edges, before.mesh_assets["mesh"].edges);
        assert_eq!(
            asset.vertex_weights,
            before.mesh_assets["mesh"].vertex_weights
        );
        assert_eq!(
            asset.polygons["surface"].uv_layers,
            before.mesh_assets["mesh"].polygons["surface"].uv_layers
        );
    }
    editor.undo(Some(3)).unwrap();
    editor.undo(Some(4)).unwrap();
    editor.undo(Some(5)).unwrap();
    assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
}
