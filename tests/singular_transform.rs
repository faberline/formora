use formora::mesh::{MeshAsset, selection::*};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

fn scene(scale: [f64; 3]) -> Scene {
    let mut mesh:MeshAsset=serde_json::from_value(json!({
        "vertices":{"a":[1,2,3],"b":[-1,0,2],"c":[1,3,1],"hidden":[1,2,3]},"edges":{},
        "triangles":{"surface":{"vertices":["a","b","c"],"uv_layers":{"UV":[[0,0],[1,0],[0,1]]}}},"material_slots":[],"vertex_groups":["pin"],"vertex_weights":{"a":{"pin":0.75}}
    })).unwrap();
    let mut editing = Editing::default();
    editing.selected.vertices = ["a".into(), "b".into()].into();
    editing.hidden.vertices.insert("hidden".into());
    set_editing(&mut mesh, Some(editing)).unwrap();
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(), mesh);
    for id in ["target", "instance"] {
        scene.entities.insert(
            id.into(),
            Entity {
                name: id.into(),
                parent: None,
                transform: Transform {
                    scale: if id == "target" { scale } else { [1.; 3] },
                    ..Default::default()
                },
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
fn command(change: Value, options: Value) -> Command {
    let mut t = json!({"entity":"target","change":change});
    for (k, v) in options.as_object().unwrap() {
        t[k] = v.clone();
    }
    serde_json::from_value(json!({"operation":"transform_mesh","transform":t})).unwrap()
}
fn near(a: [f64; 3], b: [f64; 3]) {
    for i in 0..3 {
        assert!((a[i] - b[i]).abs() <= 1e-6, "{a:?} != {b:?}");
    }
}
fn preserved(before: &Scene, after: &Scene) {
    assert_eq!(before.entities, after.entities);
    let a = &before.mesh_assets["mesh"];
    let b = &after.mesh_assets["mesh"];
    assert_eq!(a.editing, b.editing);
    assert_eq!(a.vertex_groups, b.vertex_groups);
    assert_eq!(a.vertex_weights, b.vertex_weights);
    assert_eq!(
        a.triangles["surface"].vertices,
        b.triangles["surface"].vertices
    );
    assert_eq!(
        a.triangles["surface"].uv_layers,
        b.triangles["surface"].uv_layers
    );
    for id in ["c", "hidden"] {
        assert_eq!(a.vertices[id], b.vertices[id]);
    }
}

#[test]
fn zero_scale_translation_changes_only_representable_world_directions() {
    let before = scene([2., 0., 0.5]);
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[command(
                json!({"kind":"translate","value":[0.4,7,0.6]}),
                json!({}),
            )],
            Some(0),
        )
        .unwrap();
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [1.2, 2., 4.2],
    );
    near(
        editor.scene().mesh_assets["mesh"].vertices["b"],
        [-0.8, 0., 3.2],
    );
    assert_eq!(r.transforms[0].shared_instances, ["instance", "target"]);
    assert_eq!(
        r.transforms[0].changed.vertices,
        ["a".into(), "b".into()].into()
    );
    preserved(&before, editor.scene());
    editor.undo(Some(1)).unwrap();
    assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
}

#[test]
fn singular_rotation_and_resize_use_the_actual_affine_pivot_path() {
    for (change, a, b) in [
        (
            json!({"kind":"rotate","radians":std::f64::consts::FRAC_PI_2}),
            [0., 1., 3.],
            [0., 1., 2.],
        ),
        (
            json!({"kind":"resize","value":[2,3,0.5]}),
            [2., 1., 2.75],
            [-2., 1., 2.25],
        ),
    ] {
        let mut before = scene([1., 0., 1.]);
        before
            .entities
            .get_mut("target")
            .unwrap()
            .transform
            .translation = [2., 3., 4.];
        let mut editor = Editor::new(before.clone()).unwrap();
        let r = editor
            .apply_with_outcomes(&[command(change, json!({}))], Some(0))
            .unwrap();
        near(r.transforms[0].pivot_world, [2., 3., 6.5]);
        near(r.transforms[0].centres_local["a"], [0., 1., 2.5]);
        near(editor.scene().mesh_assets["mesh"].vertices["a"], a);
        near(editor.scene().mesh_assets["mesh"].vertices["b"], b);
        preserved(&before, editor.scene());
    }
}

#[test]
fn missing_local_axis_is_filled_from_the_actual_reflected_frame() {
    let before = scene([-2., 0., 0.5]);
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[command(
                json!({"kind":"translate","value":[0.4,7,0.6]}),
                json!({"orientation":{"kind":"local"}}),
            )],
            Some(0),
        )
        .unwrap();
    assert_eq!(
        r.transforms[0].basis_world,
        [[-1., 0., 0.], [0., -1., 0.], [0., 0., 1.]]
    );
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [1.2, 2., 4.2],
    );
    preserved(&before, editor.scene());
}

#[test]
fn rank_one_and_zero_targets_keep_translation_finite_without_inventing_an_axis() {
    for (scale, a) in [([2., 0., 0.], [1.2, 2., 3.]), ([0.; 3], [1., 2., 3.])] {
        let before = scene(scale);
        let mut editor = Editor::new(before.clone()).unwrap();
        let r = editor
            .apply_with_outcomes(
                &[command(
                    json!({"kind":"translate","value":[0.4,7,0.6]}),
                    json!({}),
                )],
                Some(0),
            )
            .unwrap();
        near(editor.scene().mesh_assets["mesh"].vertices["a"], a);
        preserved(&before, editor.scene());
        if scale == [0.; 3] {
            assert!(r.transforms[0].changed.vertices.is_empty());
        }
    }
}

#[test]
fn parent_rank_loss_projects_motion_into_the_surviving_world_subspace() {
    let mut before = scene([1.; 3]);
    before.entities.insert(
        "parent".into(),
        Entity {
            name: "Parent".into(),
            parent: None,
            transform: Transform {
                scale: [2., 0., 1.],
                ..Default::default()
            },
            content: EntityKind::Empty,
        },
    );
    let target = before.entities.get_mut("target").unwrap();
    target.parent = Some("parent".into());
    target.transform.rotation = serde_json::from_value(
        json!({"kind":"euler","angles":[0,0,std::f64::consts::FRAC_PI_4],"order":"xyz"}),
    )
    .unwrap();
    let mut editor = Editor::new(before.clone()).unwrap();
    editor
        .apply(
            &[command(
                json!({"kind":"translate","value":[0.5,7,0.6]}),
                json!({}),
            )],
            Some(0),
        )
        .unwrap();
    let s = 0.5_f64.sqrt();
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [1. + 0.25 * s, 2. - 0.25 * s, 3.6],
    );
    preserved(&before, editor.scene());
}

#[test]
fn native_explicit_individual_centres_remain_distinct_from_source_operator_mapping() {
    let mut before = scene([1.; 3]);
    let mesh = before.mesh_assets.get_mut("mesh").unwrap();
    mesh.triangles.clear();
    mesh.edges.clear();
    let mut editing = Editing::default();
    editing.selected.vertices = ["a".into(), "b".into()].into();
    set_editing(mesh, Some(editing)).unwrap();
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[command(
                json!({"kind":"resize","value":[2,3,4]}),
                json!({"pivot":"individual","center_override":[0.375,-0.625,0.875]}),
            )],
            Some(0),
        )
        .unwrap();
    assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
    near(r.transforms[0].centres_local["a"], [1., 2., 3.]);
    near(r.transforms[0].centres_local["b"], [-1., 0., 2.]);
}

#[test]
fn singular_batches_stale_requests_and_inverse_overflow_have_no_partial_effect() {
    let before = scene([1., 0., 1.]);
    let mut editor = Editor::new(before.clone()).unwrap();
    let operation = command(json!({"kind":"translate","value":[0.4,7,0.6]}), json!({}));
    assert!(
        editor
            .apply_with_outcomes(&[operation.clone()], Some(1))
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    assert!(
        editor
            .apply_with_outcomes(
                &[
                    operation,
                    Command::DeleteEntity {
                        id: "absent".into()
                    }
                ],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
    let before = scene([1e30, 1e30, 0.]);
    let mut editor = Editor::new(before.clone()).unwrap();
    assert!(
        editor
            .apply(
                &[command(
                    json!({"kind":"translate","value":[1,0,0]}),
                    json!({})
                )],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
}

#[test]
fn singular_edits_save_reload_undo_and_roll_back_after_a_failed_save() {
    let before = scene([2., 0., 0.5]);
    let folder = std::env::temp_dir().join(format!("formora-singular-save-{}", std::process::id()));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let mut session = Session::create(&path, before.clone()).unwrap();
    let operation = command(json!({"kind":"translate","value":[0.4,7,0.6]}), json!({}));
    let original = std::fs::read(&path).unwrap();
    std::fs::rename(&path, folder.join("backup.json")).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        session
            .apply_with_result(ApplyRequest {
                expected_revision: 0,
                commands: vec![operation.clone()]
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
    session
        .apply_with_result(ApplyRequest {
            expected_revision: 0,
            commands: vec![operation],
        })
        .unwrap();
    near(
        session.scene().mesh_assets["mesh"].vertices["a"],
        [1.2, 2., 4.2],
    );
    assert_eq!(Scene::load(&path).unwrap(), *session.scene());
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    assert_eq!(session.scene().mesh_assets, before.mesh_assets);
    assert_eq!(session.scene().entities, before.entities);
    drop(session);
    std::fs::remove_dir_all(folder).unwrap();
}
