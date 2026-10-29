use formora::mesh::{MeshAsset, selection::*};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

fn scene(vertices: Value, edges: Value, selected: &[&str], hidden: &[&str]) -> Scene {
    let mut asset: MeshAsset = serde_json::from_value(json!({
        "vertices":vertices,"edges":edges,"triangles":{},"material_slots":[],
        "vertex_groups":["pin"],"vertex_weights":{}
    }))
    .unwrap();
    let mut editing = Editing::default();
    editing.selected.vertices = selected.iter().map(|s| s.to_string()).collect();
    editing.hidden.vertices = hidden.iter().map(|s| s.to_string()).collect();
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
fn command(axis: &str, topology: bool, options: Value) -> Command {
    let mut transform = json!({"entity":"target","change":{"kind":"translate","value":[0.4,0.5,0.6]},"mirror":{"axis":axis,"topology":topology}});
    for (key, value) in options.as_object().unwrap() {
        transform[key] = value.clone();
    }
    serde_json::from_value(json!({"operation":"transform_mesh","transform":transform})).unwrap()
}
fn near(actual: [f64; 3], expected: [f64; 3]) {
    for i in 0..3 {
        assert!(
            (actual[i] - expected[i]).abs() <= 1e-6,
            "{actual:?} != {expected:?}"
        );
    }
}
fn preserved(before: &Scene, after: &Scene) {
    assert_eq!(before.entities, after.entities);
    let a = &before.mesh_assets["mesh"];
    let b = &after.mesh_assets["mesh"];
    assert_eq!(a.editing, b.editing);
    assert_eq!(a.edges, b.edges);
    assert_eq!(a.vertex_groups, b.vertex_groups);
    assert_eq!(a.vertex_weights, b.vertex_weights);
}

#[test]
fn each_local_axis_copies_the_source_result_and_reports_both_instances() {
    for (axis, name) in ["x", "y", "z"].iter().enumerate() {
        for selected in ["left", "right"] {
            let mut left = [0.; 3];
            left[axis] = -2.;
            let right = left.map(|v| -v);
            let before = scene(
                json!({"left":left,"right":right}),
                json!({}),
                &[selected],
                &[],
            );
            let mut editor = Editor::new(before.clone()).unwrap();
            let result = editor
                .apply_with_outcomes(&[command(name, false, json!({}))], Some(0))
                .unwrap();
            let source = if selected == "left" { left } else { right };
            let moved = std::array::from_fn(|i| source[i] + [0.4, 0.5, 0.6][i]);
            let mut reflected = moved;
            reflected[axis] *= -1.;
            let other = if selected == "left" { "right" } else { "left" };
            near(editor.scene().mesh_assets["mesh"].vertices[selected], moved);
            near(
                editor.scene().mesh_assets["mesh"].vertices[other],
                reflected,
            );
            let r = &result.transforms[0];
            assert_eq!(r.mirror_sources[other], selected);
            assert_eq!(r.shared_instances, ["instance", "target"]);
            assert_eq!(r.influence.len(), 2);
            assert_eq!(r.changed.vertices.len(), 2);
            preserved(&before, editor.scene());
            editor.undo(Some(1)).unwrap();
            assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
        }
    }
}

#[test]
fn selecting_both_sides_uses_positive_half_space_without_double_transform() {
    let before = scene(
        json!({"left":[-2,0,0],"right":[2,0,0]}),
        json!({}),
        &["left", "right"],
        &[],
    );
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(&[command("x", false, json!({}))], Some(0))
        .unwrap();
    near(
        editor.scene().mesh_assets["mesh"].vertices["left"],
        [-2.4, 0.5, 0.6],
    );
    near(
        editor.scene().mesh_assets["mesh"].vertices["right"],
        [2.4, 0.5, 0.6],
    );
    assert_eq!(r.transforms[0].mirror_sources["left"], "right");
    near(r.transforms[0].pivot_world, [0.; 3]);
    preserved(&before, editor.scene());
}

#[test]
fn hidden_partners_are_not_found_or_modified() {
    let before = scene(
        json!({"left":[-2,0,0],"right":[2,0,0]}),
        json!({}),
        &["right"],
        &["left"],
    );
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(&[command("x", false, json!({}))], Some(0))
        .unwrap();
    assert!(r.transforms[0].mirror_sources.is_empty());
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["left"],
        [-2., 0., 0.]
    );
    assert_eq!(r.transforms[0].changed.vertices, ["right".into()].into());
    preserved(&before, editor.scene());
}

#[test]
fn near_plane_clamp_is_strict_and_applies_outside_proportional_radius() {
    let epsilon = f64::from(0.00002_f32);
    let before = scene(
        json!({"inside":[epsilon/2.,20,0],"boundary":[epsilon,30,0],"seed":[2,0,0]}),
        json!({}),
        &["seed"],
        &[],
    );
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[command(
                "x",
                false,
                json!({"proportional":{"radius":1,"falloff":"linear"}}),
            )],
            Some(0),
        )
        .unwrap();
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["inside"],
        [0., 20., 0.]
    );
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["boundary"],
        [epsilon, 30., 0.]
    );
    assert_eq!(r.transforms[0].mirror_plane_vertices, ["inside"]);
    assert!(!r.transforms[0].influence.contains_key("inside"));
    assert!(r.transforms[0].changed.vertices.contains("inside"));
    preserved(&before, editor.scene());
}

#[test]
fn topology_pairs_use_edges_and_can_match_different_positions() {
    let before = scene(
        json!({"left":[-4,7,0],"middle":[0.3,1,0],"right":[2,0,0]}),
        json!({"a":["left","middle"],"b":["middle","right"]}),
        &["right"],
        &[],
    );
    let mut spatial = Editor::new(before.clone()).unwrap();
    let r = spatial
        .apply_with_outcomes(&[command("x", false, json!({}))], Some(0))
        .unwrap();
    assert!(r.transforms[0].mirror_sources.is_empty());
    let mut topology = Editor::new(before.clone()).unwrap();
    let r = topology
        .apply_with_outcomes(&[command("x", true, json!({}))], Some(0))
        .unwrap();
    assert_eq!(r.transforms[0].mirror_sources["left"], "right");
    near(
        topology.scene().mesh_assets["mesh"].vertices["left"],
        [-2.4, 0.5, 0.6],
    );
    assert_eq!(
        topology.scene().mesh_assets["mesh"].vertices["middle"],
        [0.3, 1., 0.]
    );
    preserved(&before, topology.scene());
}

#[test]
fn ambiguous_topology_groups_do_not_invent_pairs() {
    let before = scene(
        json!({"a":[-2,0,0],"b":[2,0,0],"c":[3,0,0]}),
        json!({}),
        &["b"],
        &[],
    );
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(&[command("x", true, json!({}))], Some(0))
        .unwrap();
    assert!(r.transforms[0].mirror_sources.is_empty());
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [-2., 0., 0.]
    );
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["c"],
        [3., 0., 0.]
    );
}

#[test]
fn proportional_destination_inherits_source_weight_instead_of_its_own_distance() {
    let before = scene(
        json!({"left":[-2,0,0],"right":[2,0,0]}),
        json!({}),
        &["right"],
        &[],
    );
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[command(
                "x",
                false,
                json!({"proportional":{"radius":1,"falloff":"linear"}}),
            )],
            Some(0),
        )
        .unwrap();
    near(
        editor.scene().mesh_assets["mesh"].vertices["left"],
        [-2.4, 0.5, 0.6],
    );
    assert_eq!(r.transforms[0].influence["left"], 1.);
    assert_eq!(r.transforms[0].mirror_sources["left"], "right");
}

#[test]
fn saved_mirror_changes_reopen_undo_and_roll_back_stale_or_failed_batches() {
    let before = scene(
        json!({"left":[-2,0,0],"right":[2,0,0]}),
        json!({}),
        &["right"],
        &[],
    );
    let dir = std::env::temp_dir().join(format!("formora-mirror-save-{}", std::process::id()));
    std::fs::create_dir(&dir).unwrap();
    let path = dir.join("scene.json");
    before.save(&path).unwrap();
    let mut session = Session::open(&path).unwrap();
    let operation = command(
        "x",
        false,
        json!({"change":{"kind":"rotate","radians":0.6},"pivot":"cursor"}),
    );
    session
        .apply(ApplyRequest {
            expected_revision: 0,
            commands: vec![operation.clone()],
        })
        .unwrap();
    let saved = std::fs::read(&path).unwrap();
    let after = Scene::load(&path).unwrap();
    let point = after.mesh_assets["mesh"].vertices["right"];
    near(
        after.mesh_assets["mesh"].vertices["left"],
        [-point[0], point[1], point[2]],
    );
    assert!(
        session
            .apply(ApplyRequest {
                expected_revision: 0,
                commands: vec![operation.clone()]
            })
            .is_err()
    );
    assert!(
        session
            .apply(ApplyRequest {
                expected_revision: 1,
                commands: vec![
                    operation.clone(),
                    Command::DeleteEntity {
                        id: "missing".into()
                    }
                ]
            })
            .is_err()
    );
    assert_eq!(std::fs::read(&path).unwrap(), saved);
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    assert_eq!(Scene::load(&path).unwrap().mesh_assets, before.mesh_assets);
    let original = std::fs::read(&path).unwrap();
    std::fs::rename(&path, dir.join("backup.json")).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        session
            .apply_with_result(ApplyRequest {
                expected_revision: 2,
                commands: vec![operation]
            })
            .is_err()
    );
    assert_eq!(session.scene().mesh_assets, before.mesh_assets);
    assert_eq!(session.scene().revision, 2);
    assert!(
        session
            .undo(UndoRequest {
                expected_revision: 2
            })
            .is_err()
    );
    std::fs::remove_dir(&path).unwrap();
    std::fs::rename(dir.join("backup.json"), &path).unwrap();
    assert_eq!(std::fs::read(&path).unwrap(), original);
    drop(session);
    std::fs::remove_dir_all(dir).unwrap();
}
