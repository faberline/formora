use formora::mesh::{MeshAsset, selection::*};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

fn scene(surface: bool) -> Scene {
    let mut asset: MeshAsset = serde_json::from_value(json!({
        "vertices":{"a":[0,0,0],"b":[1,0,0],"c":[1,1,0],"d":[0,1,0],"apart":[0,0,0]},
        "edges":{"ab":["a","b"],"bc":["b","c"],"cd":["c","d"]},"triangles":{},"material_slots":[]
    }))
    .unwrap();
    if surface {
        asset.edges.insert("da".into(), ["d".into(), "a".into()]);
        asset.polygons.insert(
            "quad".into(),
            formora::mesh::Polygon {
                corner_colors: None,
                vertices: vec!["a".into(), "b".into(), "c".into(), "d".into()],
                uv_layers: Default::default(),
                normal: None,
                corner_normals: None,
                smooth: false,
                material_slot: None,
            },
        );
    }
    let mut editing = Editing::default();
    editing.selected.vertices.insert("a".into());
    set_editing(&mut asset, Some(editing)).unwrap();
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
    scene.validate().unwrap();
    scene
}
fn command(change: Value, options: Value) -> Command {
    let mut transform = json!({"entity":"target","change":change,"proportional":{"radius":2,"falloff":"linear","connected":true}});
    for (key, value) in options.as_object().unwrap() {
        transform[key] = value.clone();
    }
    serde_json::from_value(json!({"operation":"transform_mesh","transform":transform})).unwrap()
}
fn near(actual: f64, expected: f64) {
    assert!((actual - expected).abs() <= 1e-6, "{actual} != {expected}");
}

#[test]
fn surface_crosses_quad_interior_while_wire_walks_edges_and_coincident_disconnected_ids_stay_fixed()
{
    for surface in [false, true] {
        let before = scene(surface);
        let mut editor = Editor::new(before.clone()).unwrap();
        let result = editor
            .apply_with_outcomes(
                &[command(
                    json!({"kind":"translate","value":[0,0,1]}),
                    json!({}),
                )],
                Some(0),
            )
            .unwrap();
        let mesh = &editor.scene().mesh_assets["mesh"];
        near(
            mesh.vertices["c"][2],
            if surface { 1. - 2_f64.sqrt() / 2. } else { 0. },
        );
        near(mesh.vertices["d"][2], if surface { 0.5 } else { 0. });
        assert_eq!(
            mesh.vertices["apart"],
            before.mesh_assets["mesh"].vertices["apart"]
        );
        assert!(!result.transforms[0].influence.contains_key("apart"));
        editor.undo(Some(1)).unwrap();
        assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
    }
}

#[test]
fn hidden_face_blocks_surface_shortcut_hidden_edge_forces_detour_and_hidden_vertex_blocks_incident_edges()
 {
    for barrier in ["face", "edge", "vertex"] {
        let mut before = scene(true);
        let asset = before.mesh_assets.get_mut("mesh").unwrap();
        let mut editing = asset.editing.clone().unwrap();
        match barrier {
            "face" => {
                editing.hidden.faces.insert(FaceRef::Polygon("quad".into()));
            }
            "edge" => {
                editing.hidden.edges.insert("ab".into());
            }
            _ => {
                editing.hidden.vertices.insert("d".into());
            }
        }
        set_editing(asset, Some(editing)).unwrap();
        let mut editor = Editor::new(before).unwrap();
        let result = editor
            .apply_with_outcomes(
                &[command(
                    json!({"kind":"translate","value":[0,0,1]}),
                    json!({"proportional":{"radius":4,"falloff":"linear","connected":true}}),
                )],
                Some(0),
            )
            .unwrap();
        let mesh = &editor.scene().mesh_assets["mesh"];
        near(mesh.vertices["c"][2], 0.5);
        near(
            mesh.vertices["b"][2],
            if barrier == "edge" { 0.25 } else { 0.75 },
        );
        if barrier == "vertex" {
            near(mesh.vertices["d"][2], 0.);
            assert!(!result.transforms[0].influence.contains_key("d"));
        }
    }
}

#[test]
fn connected_distance_uses_reflected_nonuniform_world_scale_and_ignores_translation_and_projection()
{
    let mut weights = None;
    for (translation, projected) in [
        ([0.; 3], false),
        ([1048576., -1048576., 524288.], false),
        ([2.25, -1.75, 0.625], true),
    ] {
        let mut before = scene(true);
        before.entities.get_mut("target").unwrap().transform = Transform {
            translation,
            scale: [-2., 3., 1.],
            ..Default::default()
        };
        before.authoring_context =
            Some(serde_json::from_value(json!({"view_rotation":[0.35,-0.25,0.6]})).unwrap());
        let mut editor = Editor::new(before).unwrap();
        let result=editor.apply_with_outcomes(&[command(json!({"kind":"translate","value":[0,0,1]}),json!({"proportional":{"radius":10,"falloff":"linear","connected":true,"projected":projected}}))],Some(0)).unwrap();
        let influence = &result.transforms[0].influence;
        near(influence["c"], 1. - 13_f64.sqrt() / 10.);
        near(influence["b"], 0.8);
        near(influence["d"], 0.7);
        if let Some(previous) = &weights {
            assert_eq!(influence, previous);
        } else {
            weights = Some(influence.clone());
        }
    }
}

#[test]
fn individual_centres_follow_selected_islands_and_vertex_mode_singletons() {
    for grouped in [false, true] {
        let mut before = scene(false);
        let mesh = before.mesh_assets.get_mut("mesh").unwrap();
        mesh.vertices.insert("c".into(), [2., 0., 0.]);
        mesh.vertices.insert("d".into(), [3., 0., 0.]);
        let mut editing = mesh.editing.clone().unwrap();
        if grouped {
            editing.selected.vertices.insert("b".into());
        }
        set_editing(mesh, Some(editing)).unwrap();
        let mut editor = Editor::new(before).unwrap();
        let result=editor.apply_with_outcomes(&[command(json!({"kind":"rotate","axis":"z","radians":std::f64::consts::FRAC_PI_2}),json!({"pivot":"individual","proportional":{"radius":5,"falloff":"constant","connected":true}}))],Some(0)).unwrap();
        let centre = if grouped { 0.5 } else { 0. };
        near(result.transforms[0].centres_local["c"][0], centre);
        near(editor.scene().mesh_assets["mesh"].vertices["c"][0], centre);
        near(
            editor.scene().mesh_assets["mesh"].vertices["c"][1],
            2. - centre,
        );
        near(editor.scene().mesh_assets["mesh"].vertices["d"][0], centre);
        near(
            editor.scene().mesh_assets["mesh"].vertices["d"][1],
            3. - centre,
        );
    }
}

#[test]
fn edge_mode_without_a_selected_island_keeps_the_source_per_vertex_centre_fallback() {
    let mut before = scene(false);
    let mesh = before.mesh_assets.get_mut("mesh").unwrap();
    let mut editing = mesh.editing.clone().unwrap();
    editing.mode = [Domain::Edge].into();
    set_editing(mesh, Some(editing)).unwrap();
    let original = mesh.vertices.clone();
    let mut editor = Editor::new(before).unwrap();
    let result=editor.apply_with_outcomes(&[command(json!({"kind":"rotate","radians":0.61}),json!({"pivot":"individual","proportional":{"radius":5,"falloff":"constant","connected":true}}))],Some(0)).unwrap();
    assert_eq!(editor.scene().mesh_assets["mesh"].vertices, original);
    assert_eq!(result.transforms[0].centres_local["c"], original["c"]);
}

#[test]
fn seeded_connected_replay_is_exact_and_distance_overflow_is_atomic() {
    let operation = command(
        json!({"kind":"translate","value":[0,0,1]}),
        json!({"proportional":{"radius":3,"falloff":"random","seed":73913,"connected":true}}),
    );
    let mut first = Editor::new(scene(true)).unwrap();
    let mut second = Editor::new(scene(true)).unwrap();
    let a = first
        .apply_with_outcomes(&[operation.clone()], Some(0))
        .unwrap();
    let b = second.apply_with_outcomes(&[operation], Some(0)).unwrap();
    assert_eq!(first.scene(), second.scene());
    assert_eq!(a.transforms[0].influence, b.transforms[0].influence);
    assert_eq!(a.transforms[0].random_seed, Some(73913));
    let mut before = scene(false);
    before
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .vertices
        .insert("b".into(), [1e30, 0., 0.]);
    let mut editor = Editor::new(before.clone()).unwrap();
    let error = editor
        .apply_with_outcomes(
            &[command(
                json!({"kind":"translate","value":[0,0,1]}),
                json!({}),
            )],
            Some(0),
        )
        .err()
        .unwrap();
    assert!(error.0.contains("surface distance arithmetic"));
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
}

#[test]
fn connected_results_save_reload_undo_and_roll_back_when_save_fails() {
    let folder =
        std::env::temp_dir().join(format!("formora-connected-save-{}", std::process::id()));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let before = scene(true);
    let mut session = Session::create(&path, before.clone()).unwrap();
    let operation = || command(json!({"kind":"translate","value":[0,0,1]}), json!({}));
    let original = std::fs::read(&path).unwrap();
    std::fs::rename(&path, folder.join("backup.json")).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        session
            .apply_with_result(ApplyRequest {
                expected_revision: 0,
                commands: vec![operation()]
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
            commands: vec![operation()],
        })
        .unwrap();
    near(result.transforms[0].influence["c"], 1. - 2_f64.sqrt() / 2.);
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
