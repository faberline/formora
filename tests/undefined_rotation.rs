use formora::mesh::{MeshAsset, selection::*, transform};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

const ERROR: &str = "mesh transform rotation cannot constrain all three axes: undefined Blender 5.2.3 source behavior";

fn scene(selected: bool) -> Scene {
    let mut asset: MeshAsset = serde_json::from_value(json!({
        "vertices":{"a":[-1,0,0],"b":[1,0,0],"c":[0,1,0]},
        "triangles":{"face":{"vertices":["a","b","c"],
            "uv_layers":{"UV":[[0,0],[1,0],[0.5,1]]},
            "corner_normals":null,"material_slot":null}},"material_slots":[]
    }))
    .unwrap();
    let mut editing = Editing::default();
    if selected {
        editing.selected.vertices = ["a".into(), "b".into()].into();
        editing.history = vec![Component::Vertex { id: "b".into() }];
    }
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

fn request(change: Value, mask: [bool; 3]) -> transform::Request {
    serde_json::from_value(json!({"entity":"target","change":change,"constraint_axis":mask}))
        .unwrap()
}

fn bad() -> Command {
    Command::TransformMesh {
        transform: Box::new(request(
            json!({"kind":"rotate","radians":0.61,"axis":"z"}),
            [true; 3],
        )),
    }
}

fn good() -> Command {
    Command::TransformMesh {
        transform: Box::new(request(
            json!({"kind":"translate","value":[0.25,0.5,0.75]}),
            [true; 3],
        )),
    }
}

#[test]
fn every_all_axis_rotation_is_rejected_before_scene_work_for_all_frames_and_centres() {
    for selected in [false, true] {
        for radians in [0.0, 0.61, -0.61, std::f64::consts::TAU] {
            for kind in [
                "global", "local", "parent", "cursor", "view", "normal", "gimbal", "custom",
            ] {
                for pivot in ["median", "bounds", "cursor", "active", "individual"] {
                    let orientation = if kind == "custom" {
                        json!({"kind":kind,"matrix":[[1,0,0],[0,1,0],[0,0,1]]})
                    } else {
                        json!({"kind":kind})
                    };
                    let r: transform::Request = serde_json::from_value(json!({
                        "entity":"target","change":{"kind":"rotate","radians":radians,"axis":"z"},
                        "constraint_axis":[true,true,true],"orientation":orientation,"pivot":pivot
                    }))
                    .unwrap();
                    let before = scene(selected);
                    let mut direct = before.clone();
                    assert_eq!(transform::execute(&mut direct, &r).unwrap_err().0, ERROR);
                    assert_eq!(direct, before);
                }
            }
        }
    }
    for axis in ["x", "y"] {
        let mut direct = scene(true);
        let before = direct.clone();
        let r = request(
            json!({"kind":"rotate","radians":0.61,"axis":axis}),
            [true; 3],
        );
        assert_eq!(transform::execute(&mut direct, &r).unwrap_err().0, ERROR);
        assert_eq!(direct, before);
    }
}

#[test]
fn defined_axis_masks_and_non_rotation_commands_keep_their_existing_behavior() {
    for bits in 0..7 {
        let mask = std::array::from_fn(|axis| bits & (1 << axis) != 0);
        let mut editor = Editor::new(scene(true)).unwrap();
        let result = editor
            .apply_with_outcomes(
                &[Command::TransformMesh {
                    transform: Box::new(request(
                        json!({"kind":"rotate","radians":0.375,"axis":"z"}),
                        mask,
                    )),
                }],
                Some(0),
            )
            .unwrap();
        assert_eq!(result.transforms.len(), 1);
        assert_eq!(result.revision, 1);
    }
    for (change, expected) in [
        (
            json!({"kind":"translate","value":[0.25,0.5,0.75]}),
            [-0.75, 0.5, 0.75],
        ),
        (json!({"kind":"resize","value":[-2,0.5,1]}), [2., 0., 0.]),
    ] {
        let mut editor = Editor::new(scene(true)).unwrap();
        editor
            .apply(
                &[Command::TransformMesh {
                    transform: Box::new(request(change, [true; 3])),
                }],
                Some(0),
            )
            .unwrap();
        assert_eq!(editor.scene().mesh_assets["mesh"].vertices["a"], expected);
    }
}

#[test]
fn failed_batch_preserves_an_existing_undo_entry_and_shared_scene() {
    let before = scene(true);
    let mut editor = Editor::new(before.clone()).unwrap();
    editor.apply(&[good()], Some(0)).unwrap();
    let saved = editor.scene().clone();
    let error = editor
        .apply_with_outcomes(&[good(), bad()], Some(1))
        .err()
        .expect("undefined rotation must fail");
    assert_eq!(error.0, ERROR);
    assert_eq!(editor.scene(), &saved);
    editor.undo(Some(1)).unwrap();
    let mut undone = editor.scene().clone();
    undone.revision = 0;
    assert_eq!(undone, before);
    assert!(editor.undo(Some(2)).is_err());
}

#[test]
fn rejected_saved_operation_keeps_exact_file_bytes_and_undo_history() {
    let folder =
        std::env::temp_dir().join(format!("formora-undefined-rotation-{}", std::process::id()));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let before = scene(true);
    {
        let mut session = Session::create(&path, before.clone()).unwrap();
        session
            .apply(ApplyRequest {
                expected_revision: 0,
                commands: vec![good()],
            })
            .unwrap();
        let saved_scene = session.scene().clone();
        let bytes = std::fs::read(&path).unwrap();
        for commands in [vec![bad()], vec![good(), bad()]] {
            let error = session
                .apply_with_result(ApplyRequest {
                    expected_revision: 1,
                    commands,
                })
                .unwrap_err();
            assert_eq!(error.0, ERROR);
            assert_eq!(session.scene(), &saved_scene);
            assert_eq!(std::fs::read(&path).unwrap(), bytes);
            assert_eq!(Scene::load(&path).unwrap(), saved_scene);
        }
        session
            .undo(UndoRequest {
                expected_revision: 1,
            })
            .unwrap();
        assert_eq!(session.scene().mesh_assets, before.mesh_assets);
    }
    std::fs::remove_dir_all(folder).unwrap();
}
