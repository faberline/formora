use formora::mesh::{MeshAsset, selection::*, transform};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};
use std::collections::BTreeMap;

fn asset() -> MeshAsset {
    serde_json::from_value(json!({
        "vertices":{"a":[-1,0,0],"b":[1,0,0],"near":[0,1,0],"coincident":[-1,0,0],"hidden":[2,0,0],"far":[5,0,0]},
        "triangles":{"face":{"vertices":["a","b","near"],"uv_layers":{"UV":[[0,0],[1,0],[0.5,1]]},"corner_normals":null,"material_slot":null}},
        "material_slots":[],"vertex_groups":["pin"],"vertex_weights":{"a":{"pin":0.75}}
    })).unwrap()
}
fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.materials.insert(
        "unrelated".into(),
        Material {
            base_color: [0.1, 0.3, 0.7, 1.],
            roughness: 0.5,
            metallic: 0.3,
        },
    );
    let mut asset = asset();
    let mut editing = Editing::default();
    editing.selected.vertices = ["a".into(), "b".into()].into();
    editing.hidden.vertices.insert("hidden".into());
    editing.history = vec![Component::Vertex { id: "b".into() }];
    set_editing(&mut asset, Some(editing)).unwrap();
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
fn request(change: Value, options: Value) -> transform::Request {
    let mut object = json!({"entity":"target","change":change});
    for (key, value) in options.as_object().unwrap() {
        object[key] = value.clone();
    }
    serde_json::from_value(object).unwrap()
}
fn command(change: Value, options: Value) -> Command {
    Command::TransformMesh {
        transform: Box::new(request(change, options)),
    }
}
fn near(actual: [f64; 3], expected: [f64; 3]) {
    for i in 0..3 {
        assert!(
            (actual[i] - expected[i]).abs() <= 1e-6,
            "{actual:?} != {expected:?}"
        );
    }
}

#[test]
fn basic_changes_edit_real_shared_geometry_preserve_other_data_and_publish_actual_receipts() {
    for (change, a, b) in [
        (
            json!({"kind":"translate","value":[0.5,-0.25,1]}),
            [-0.5, -0.25, 1.],
            [1.5, -0.25, 1.],
        ),
        (
            json!({"kind":"rotate","radians":std::f64::consts::FRAC_PI_2,"axis":"z"}),
            [0., -1., 0.],
            [0., 1., 0.],
        ),
        (
            json!({"kind":"resize","value":[-2,0.5,0]}),
            [2., 0., 0.],
            [-2., 0., 0.],
        ),
    ] {
        let before = scene();
        let mut editor = Editor::new(before.clone()).unwrap();
        let result = editor
            .apply_with_outcomes(&[command(change, json!({}))], Some(0))
            .unwrap();
        assert_eq!(result.revision, 1);
        assert_eq!(result.transforms.len(), 1);
        let receipt = &result.transforms[0];
        assert_eq!(receipt.entity, "target");
        assert_eq!(receipt.mesh_asset, "mesh");
        assert_eq!(receipt.shared_instances, ["instance", "target"]);
        assert_eq!(receipt.changed.vertices, ["a".into(), "b".into()].into());
        assert_eq!(
            receipt.changed.faces,
            [FaceRef::Triangle("face".into())].into()
        );
        assert_eq!(
            receipt.influence,
            BTreeMap::from([("a".into(), 1.), ("b".into(), 1.)])
        );
        near(receipt.pivot_world, [0.; 3]);
        let after = &editor.scene().mesh_assets["mesh"];
        near(after.vertices["a"], a);
        near(after.vertices["b"], b);
        for id in ["near", "coincident", "hidden", "far"] {
            assert_eq!(after.vertices[id], before.mesh_assets["mesh"].vertices[id]);
        }
        assert_eq!(after.editing, before.mesh_assets["mesh"].editing);
        assert_eq!(
            after.vertex_groups,
            before.mesh_assets["mesh"].vertex_groups
        );
        assert_eq!(
            after.vertex_weights,
            before.mesh_assets["mesh"].vertex_weights
        );
        assert_eq!(
            after.triangles["face"].uv_layers,
            before.mesh_assets["mesh"].triangles["face"].uv_layers
        );
        assert_eq!(
            after.triangles["face"].vertices,
            before.mesh_assets["mesh"].triangles["face"].vertices
        );
        assert_eq!(editor.scene().entities, before.entities);
        assert_eq!(editor.scene().materials, before.materials);
        editor.undo(Some(1)).unwrap();
        assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
    }
}

#[test]
fn created_recipes_are_marked_edited_and_receipts_keep_batch_indices() {
    let create:Command=serde_json::from_value(json!({"operation":"create_mesh_object","creation":{"id":"target","asset":"mesh","name":"Cube","primitive":{"kind":"cube","size":2}}})).unwrap();
    let mut editor = Editor::new(Scene::default()).unwrap();
    let result = editor
        .apply_with_outcomes(
            &[
                create,
                command(json!({"kind":"translate","value":[0.5,-0.25,1]}), json!({})),
            ],
            Some(0),
        )
        .unwrap();
    assert_eq!(result.creation[0].command_index, 0);
    assert_eq!(result.transforms[0].command_index, 1);
    let asset = &editor.scene().mesh_assets["mesh"];
    assert!(asset.recipe.as_ref().unwrap().edited);
    assert_eq!(asset.vertices.len(), 8);
    for p in asset.vertices.values() {
        assert!([-0.5, 1.5].contains(&p[0]));
        assert!([-1.25, 0.75].contains(&p[1]));
        assert!([0., 2.].contains(&p[2]));
    }
    let saved = asset.clone();
    let identity = editor
        .apply_with_outcomes(
            &[command(
                json!({"kind":"translate","value":[0,0,0]}),
                json!({}),
            )],
            Some(1),
        )
        .unwrap();
    assert!(identity.transforms[0].changed.vertices.is_empty());
    assert_eq!(editor.scene().mesh_assets["mesh"], saved);
}

#[test]
fn mixed_face_kinds_keep_separate_identity_with_an_authored_world_pivot() {
    let mut before = scene();
    let original_uv = before.mesh_assets["mesh"].triangles["face"]
        .uv_layers
        .clone();
    let asset = before.mesh_assets.get_mut("mesh").unwrap();
    asset.edges = topology(asset).unwrap().edges;
    asset.polygons.insert(
        "face".into(),
        formora::mesh::Polygon {
            corner_colors: None,
            vertices: vec!["near".into(), "b".into(), "a".into()],
            uv_layers: BTreeMap::new(),
            normal: None,
            corner_normals: None,
            smooth: false,
            material_slot: None,
        },
    );
    let mut editor = Editor::new(before).unwrap();
    let result = editor
        .apply_with_outcomes(
            &[command(
                json!({"kind":"resize","value":[2,1,1]}),
                json!({"center_override":[3,-2,1]}),
            )],
            Some(0),
        )
        .unwrap();
    assert_eq!(
        result.transforms[0].changed.faces,
        [
            FaceRef::Polygon("face".into()),
            FaceRef::Triangle("face".into())
        ]
        .into()
    );
    near(result.transforms[0].pivot_world, [3., -2., 1.]);
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [-5., 0., 0.],
    );
    near(
        editor.scene().mesh_assets["mesh"].vertices["b"],
        [-1., 0., 0.],
    );
    assert_eq!(
        editor.scene().mesh_assets["mesh"].triangles["face"].uv_layers,
        original_uv
    );
}

#[test]
fn global_local_parent_cursor_view_and_custom_frames_are_derived_from_actual_state() {
    let half = 0.5_f64.sqrt();
    for orientation in [
        json!({"kind":"global"}),
        json!({"kind":"local"}),
        json!({"kind":"parent"}),
        json!({"kind":"cursor"}),
        json!({"kind":"view"}),
        json!({"kind":"custom","matrix":[[0,-1,0],[1,0,0],[0,0,1]]}),
    ] {
        let mut before = scene();
        let kind = orientation["kind"].as_str().unwrap();
        before.authoring_context=Some(serde_json::from_value(json!({"cursor_rotation":[0,0,std::f64::consts::FRAC_PI_2],"view_rotation":[0,0,std::f64::consts::FRAC_PI_2]})).unwrap());
        if kind == "local" {
            before
                .entities
                .get_mut("target")
                .unwrap()
                .transform
                .rotation = [0., 0., half, half].into();
            before.entities.get_mut("target").unwrap().transform.scale = [2., 3., 1.];
        }
        if kind == "parent" {
            before.entities.insert(
                "parent".into(),
                Entity {
                    name: "Parent".into(),
                    parent: None,
                    transform: Transform {
                        rotation: [0., 0., half, half].into(),
                        ..Default::default()
                    },
                    content: EntityKind::Empty,
                },
            );
            before.entities.get_mut("target").unwrap().parent = Some("parent".into());
            before
                .entities
                .get_mut("target")
                .unwrap()
                .transform
                .rotation = [0., 0., -half, half].into();
        }
        let mut editor = Editor::new(before).unwrap();
        let result = editor
            .apply_with_outcomes(
                &[command(
                    json!({"kind":"translate","value":[1,0,0]}),
                    json!({"orientation":orientation}),
                )],
                Some(0),
            )
            .unwrap();
        let a = editor.scene().mesh_assets["mesh"].vertices["a"];
        near(
            a,
            match kind {
                "global" => [0., 0., 0.],
                "local" => [-0.5, 0., 0.],
                _ => [-1., 1., 0.],
            },
        );
        let basis = result.transforms[0].basis_world;
        near(
            [basis[0][0], basis[1][0], basis[2][0]],
            if kind == "global" {
                [1., 0., 0.]
            } else {
                [0., 1., 0.]
            },
        );
    }
}

#[test]
fn median_bounds_active_and_cursor_pivots_have_independent_geometric_results() {
    for (pivot, centre) in [
        ("median", 2. / 3.),
        ("bounds", 1.),
        ("active", 4.),
        ("cursor", 2.),
    ] {
        let mut before = scene();
        let asset = before.mesh_assets.get_mut("mesh").unwrap();
        asset.vertices.insert("a".into(), [-2., 0., 0.]);
        asset.vertices.insert("b".into(), [0., 0., 0.]);
        asset.vertices.insert("far".into(), [4., 0., 0.]);
        let mut editing = asset.editing.clone().unwrap();
        editing.selected.vertices.insert("far".into());
        editing.history = vec![Component::Vertex { id: "far".into() }];
        set_editing(asset, Some(editing)).unwrap();
        before.authoring_context =
            Some(serde_json::from_value(json!({"cursor_location":[2,0,0]})).unwrap());
        let mut editor = Editor::new(before).unwrap();
        let result = editor
            .apply_with_outcomes(
                &[command(
                    json!({"kind":"resize","value":[2,1,1]}),
                    json!({"pivot":pivot}),
                )],
                Some(0),
            )
            .unwrap();
        near(result.transforms[0].pivot_world, [centre, 0., 0.]);
        for (id, x) in [("a", -2.), ("b", 0.), ("far", 4.)] {
            near(
                editor.scene().mesh_assets["mesh"].vertices[id],
                [2. * x - centre, 0., 0.],
            );
        }
    }
}

#[test]
fn individual_edge_island_uses_element_centres_and_keeps_an_isolated_vertex_fixed() {
    let mut before = scene();
    let asset = before.mesh_assets.get_mut("mesh").unwrap();
    asset.triangles.clear();
    asset.vertices = BTreeMap::from([
        ("a".into(), [0.; 3]),
        ("b".into(), [2., 0., 0.]),
        ("c".into(), [8., 0., 0.]),
        ("isolated".into(), [10., 0., 0.]),
    ]);
    asset.edges = BTreeMap::from([
        ("ab".into(), ["a".into(), "b".into()]),
        ("bc".into(), ["b".into(), "c".into()]),
    ]);
    asset.vertex_weights = None;
    asset.vertex_groups.clear();
    let mut editing = Editing::default();
    editing.selected.vertices = asset.vertices.keys().cloned().collect();
    set_editing(asset, Some(editing)).unwrap();
    let mut editor = Editor::new(before).unwrap();
    let result = editor
        .apply_with_outcomes(
            &[command(
                json!({"kind":"resize","value":[2,1,1]}),
                json!({"pivot":"individual"}),
            )],
            Some(0),
        )
        .unwrap();
    let asset = &editor.scene().mesh_assets["mesh"];
    for (id, x) in [("a", -3.), ("b", 1.), ("c", 13.), ("isolated", 10.)] {
        near(asset.vertices[id], [x, 0., 0.]);
    }
    near(result.transforms[0].centres_local["a"], [3., 0., 0.]);
    near(
        result.transforms[0].centres_local["isolated"],
        [10., 0., 0.],
    );
}

#[test]
fn native_axis_and_plane_constraints_apply_to_actual_displacement_rotation_and_scale() {
    for (change, mask, expected) in [
        (
            json!({"kind":"translate","value":[0.5,4,8]}),
            [true, false, false],
            [-0.5, 0., 0.],
        ),
        (
            json!({"kind":"rotate","radians":std::f64::consts::FRAC_PI_2,"axis":"x"}),
            [true, true, false],
            [0., -1., 0.],
        ),
        (
            json!({"kind":"resize","value":[2,9,7]}),
            [true, false, false],
            [-2., 0., 0.],
        ),
    ] {
        let mut editor = Editor::new(scene()).unwrap();
        editor
            .apply(&[command(change, json!({"constraint_axis":mask}))], Some(0))
            .unwrap();
        near(editor.scene().mesh_assets["mesh"].vertices["a"], expected);
    }
}

fn proportional_scene() -> Scene {
    let mut scene = scene();
    let asset = scene.mesh_assets.get_mut("mesh").unwrap();
    asset.triangles.clear();
    asset.vertex_groups.clear();
    asset.vertex_weights = None;
    asset.vertices = BTreeMap::from([
        ("a".into(), [0.; 3]),
        ("near".into(), [0.5, 0., 0.]),
        ("boundary".into(), [1., 0., 0.]),
        ("far".into(), [2., 0., 0.]),
        ("hidden".into(), [0.25, 0., 0.]),
        ("depth".into(), [0., 0., 2.]),
    ]);
    let mut editing = Editing::default();
    editing.selected.vertices.insert("a".into());
    editing.hidden.vertices.insert("hidden".into());
    set_editing(asset, Some(editing)).unwrap();
    scene
}

#[test]
fn proportional_falloffs_preserve_hidden_vertices_and_apply_fixed_radius_boundaries() {
    for (falloff, weight) in [
        ("smooth", 0.5),
        ("sphere", 0.75_f64.sqrt()),
        ("root", 0.5_f64.sqrt()),
        ("sharp", 0.25),
        ("linear", 0.5),
        ("constant", 1.),
        ("inverse_square", 0.75),
    ] {
        let mut editor = Editor::new(proportional_scene()).unwrap();
        let result = editor
            .apply_with_outcomes(
                &[command(
                    json!({"kind":"translate","value":[0,0,1]}),
                    json!({"proportional":{"radius":1,"falloff":falloff}}),
                )],
                Some(0),
            )
            .unwrap();
        let asset = &editor.scene().mesh_assets["mesh"];
        near(asset.vertices["near"], [0.5, 0., weight]);
        near(asset.vertices["a"], [0., 0., 1.]);
        near(asset.vertices["hidden"], [0.25, 0., 0.]);
        near(asset.vertices["far"], [2., 0., 0.]);
        near(asset.vertices["depth"], [0., 0., 2.]);
        near(
            asset.vertices["boundary"],
            [1., 0., if falloff == "constant" { 1. } else { 0. }],
        );
        assert!(!result.transforms[0].influence.contains_key("hidden"));
    }
}

#[test]
fn projected_distance_uses_actual_view_and_random_seed_replays_exactly() {
    let operation = |projected, seed| {
        command(
            json!({"kind":"translate","value":[0,0,1]}),
            json!({"proportional":{"radius":1,"falloff":"random","seed":seed,"projected":projected}}),
        )
    };
    for projected in [false, true] {
        let mut a = Editor::new(proportional_scene()).unwrap();
        let mut b = Editor::new(proportional_scene()).unwrap();
        let first = a
            .apply_with_outcomes(&[operation(projected, 1234567)], Some(0))
            .unwrap();
        let second = b
            .apply_with_outcomes(&[operation(projected, 1234567)], Some(0))
            .unwrap();
        assert_eq!(a.scene(), b.scene());
        assert_eq!(
            first.transforms[0].influence,
            second.transforms[0].influence
        );
        assert_eq!(first.transforms[0].random_seed, Some(1234567));
        let depth = a.scene().mesh_assets["mesh"].vertices["depth"][2];
        assert_eq!(depth > 2., projected);
        let z = a.scene().mesh_assets["mesh"].vertices["near"][2];
        assert!((0. ..=0.5).contains(&z));
    }
}

#[test]
fn invalid_unsupported_stale_and_failed_batch_requests_have_no_effect_or_undo_entry() {
    let before = scene();
    let mut editor = Editor::new(before.clone()).unwrap();
    let change = json!({"kind":"translate","value":[0,0,1]});
    for options in [
        json!({"max_components":0}),
        json!({"max_components":1}),
        json!({"orientation":{"kind":"custom","matrix":[[0,0,0],[0,0,0],[0,0,0]]}}),
        json!({"proportional":{"radius":0,"falloff":"linear"}}),
        json!({"proportional":{"radius":1,"falloff":"random"}}),
        json!({"proportional":{"radius":1,"falloff":"linear","seed":1}}),
    ] {
        assert!(
            editor
                .apply_with_outcomes(&[command(change.clone(), options)], Some(0))
                .is_err()
        );
        assert_eq!(editor.scene(), &before);
        assert!(editor.undo(Some(0)).is_err());
    }
    assert!(
        editor
            .apply_with_outcomes(&[command(change.clone(), json!({}))], Some(1))
            .is_err()
    );
    assert!(
        editor
            .apply_with_outcomes(
                &[
                    command(change, json!({})),
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
fn saved_receipts_reload_and_failed_save_are_atomic() {
    let folder = std::env::temp_dir().join(format!("formora-transform-{}", std::process::id()));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let before = scene();
    let mut session = Session::create(&path, before.clone()).unwrap();
    let change = || command(json!({"kind":"translate","value":[0.5,0,1]}), json!({}));
    let original = std::fs::read(&path).unwrap();
    std::fs::rename(&path, folder.join("backup.json")).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        session
            .apply_with_result(ApplyRequest {
                expected_revision: 0,
                commands: vec![change()]
            })
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
    std::fs::remove_dir(&path).unwrap();
    std::fs::rename(folder.join("backup.json"), &path).unwrap();
    assert_eq!(std::fs::read(&path).unwrap(), original);
    let result = session
        .apply_with_result(ApplyRequest {
            expected_revision: 0,
            commands: vec![change()],
        })
        .unwrap();
    assert_eq!(result.transforms[0].command_index, 0);
    assert_eq!(result.revision, 1);
    assert_eq!(Scene::load(&path).unwrap(), *session.scene());
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    assert_eq!(session.scene().mesh_assets, before.mesh_assets);
    drop(session);
    std::fs::remove_dir_all(folder).unwrap();
}
