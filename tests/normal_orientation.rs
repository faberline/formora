use formora::mesh::{MeshAsset, selection::*};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

fn scene(vertices: Value, mut faces: Value, mut edges: Value, editing: Value) -> Scene {
    for face in faces.as_object_mut().unwrap().values_mut() {
        let face = face.as_object_mut().unwrap();
        face.entry("uv_layers").or_insert(json!({}));
        face.entry("smooth").or_insert(json!(false));
    }
    for face in faces.as_object().unwrap().values() {
        let vertices = face["vertices"].as_array().unwrap();
        for i in 0..vertices.len() {
            let pair = [
                vertices[i].clone(),
                vertices[(i + 1) % vertices.len()].clone(),
            ];
            if !edges
                .as_object()
                .unwrap()
                .values()
                .any(|p| p == &json!(pair) || p == &json!([pair[1], pair[0]]))
            {
                let id = format!("e{:06}", edges.as_object().unwrap().len());
                edges.as_object_mut().unwrap().insert(id, json!(pair));
            }
        }
    }
    let layers: Vec<_> = faces
        .as_object()
        .unwrap()
        .values()
        .next()
        .map(|f| {
            f["uv_layers"]
                .as_object()
                .unwrap()
                .keys()
                .cloned()
                .collect()
        })
        .unwrap_or_default();
    let uv_layout = if layers.is_empty() {
        Value::Null
    } else {
        json!({"layers":layers,"active":layers[0]})
    };
    let mut mesh: MeshAsset = serde_json::from_value(json!({
        "vertices":vertices,"polygons":faces,"edges":edges,"triangles":{},"material_slots":[],"uv_layout":uv_layout
    }))
    .unwrap();
    set_editing(&mut mesh, Some(serde_json::from_value(editing).unwrap())).unwrap();
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(), mesh);
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
fn sheet() -> Scene {
    scene(
        json!({"a":[0,0,0],"b":[2,0,0],"c":[2,1,0],"d":[0,1,0],"apart":[0,0,0]}),
        json!({"sheet":{"vertices":["a","b","c","d"],"uv_layers":{"UV":[[0,0],[1,0],[1,1],[0,1]]}}}),
        json!({}),
        json!({"mode":["face"],"selected":{"faces":[{"kind":"polygon","id":"sheet"}]},"history":[{"domain":"face","face":{"kind":"polygon","id":"sheet"}}],"active_face":{"kind":"polygon","id":"sheet"}}),
    )
}
fn operation(change: Value, options: Value) -> Command {
    let mut t = json!({"entity":"target","orientation":{"kind":"normal"},"change":change});
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
fn z(b: [[f64; 3]; 3]) -> [f64; 3] {
    [b[0][2], b[1][2], b[2][2]]
}

#[test]
fn face_orientation_uses_actual_geometry_and_ignores_shading_payloads_and_smoothing() {
    for shading in [false, true] {
        let mut before = sheet();
        let mesh = before.mesh_assets.get_mut("mesh").unwrap();
        for id in ["c", "d"] {
            mesh.vertices.get_mut(id).unwrap()[2] = 1.;
        }
        let face = mesh.polygons.get_mut("sheet").unwrap();
        face.smooth = shading;
        face.normal = Some([1., 0., 0.]);
        face.corner_normals = Some(vec![[1., 0., 0.]; 4]);
        let editing = mesh.editing.clone().unwrap();
        let uv = face.uv_layers.clone();
        let mut editor = Editor::new(before.clone()).unwrap();
        let result = editor
            .apply_with_outcomes(
                &[operation(
                    json!({"kind":"translate","value":[0,0,0.5]}),
                    json!({}),
                )],
                Some(0),
            )
            .unwrap();
        let s = 0.5_f64.sqrt();
        near(z(result.transforms[0].basis_world), [0., -s, s]);
        for id in ["a", "b", "c", "d"] {
            let p = before.mesh_assets["mesh"].vertices[id];
            near(
                editor.scene().mesh_assets["mesh"].vertices[id],
                [p[0], p[1] - 0.5 * s, p[2] + 0.5 * s],
            );
        }
        assert_eq!(
            editor.scene().mesh_assets["mesh"].vertices["apart"],
            [0.; 3]
        );
        assert_eq!(editor.scene().mesh_assets["mesh"].editing, Some(editing));
        assert_eq!(
            editor.scene().mesh_assets["mesh"].polygons["sheet"].uv_layers,
            uv
        );
        assert_eq!(
            result.transforms[0].shared_instances,
            ["instance", "target"]
        );
        assert!(result.transforms[0].component_basis_local.is_empty());
        editor.undo(Some(1)).unwrap();
        assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
    }
}

#[test]
fn active_vertex_uses_all_incident_geometry_including_hidden_flat_faces() {
    let mut before = scene(
        json!({"a":[0,0,0],"b":[2,0,0],"c":[0,1,0],"d":[0,0,1]}),
        json!({"xy":{"vertices":["a","b","c"]},"xz":{"vertices":["a","d","b"],"smooth":false}}),
        json!({}),
        json!({"mode":["vertex"],"selected":{"vertices":["a"]},"hidden":{"faces":[{"kind":"polygon","id":"xz"}]},"history":[{"domain":"vertex","id":"a"}]}),
    );
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0,0,0.5]}),
                json!({"pivot":"active"}),
            )],
            Some(0),
        )
        .unwrap();
    let s = 0.5_f64.sqrt();
    near(z(r.transforms[0].basis_world), [0., s, s]);
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [0., s * 0.5, s * 0.5],
    );
    for id in ["b", "c", "d"] {
        assert_eq!(
            editor.scene().mesh_assets["mesh"].vertices[id],
            before.mesh_assets["mesh"].vertices[id]
        );
    }
    // Explicit shading values cannot redirect an active vertex either.
    before
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .polygons
        .get_mut("xy")
        .unwrap()
        .normal = Some([1., 0., 0.]);
    let mut second = Editor::new(before).unwrap();
    let r2 = second
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0,0,0.5]}),
                json!({"pivot":"active"}),
            )],
            Some(0),
        )
        .unwrap();
    assert_eq!(r.transforms[0].basis_world, r2.transforms[0].basis_world);
}

#[test]
fn active_face_takes_precedence_over_last_face_history() {
    let before = scene(
        json!({"a":[0,0,0],"b":[2,0,0],"c":[0,1,0],"d":[3,0,0],"e":[3,2,0],"f":[3,0,1]}),
        json!({"xy":{"vertices":["a","b","c"]},"yz":{"vertices":["d","e","f"]}}),
        json!({}),
        json!({"mode":["face"],"selected":{"faces":[{"kind":"polygon","id":"xy"},{"kind":"polygon","id":"yz"}]},"history":[{"domain":"face","face":{"kind":"polygon","id":"yz"}},{"domain":"face","face":{"kind":"polygon","id":"xy"}}],"active_face":{"kind":"polygon","id":"yz"}}),
    );
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0,0,0.25]}),
                json!({"pivot":"active"}),
            )],
            Some(0),
        )
        .unwrap();
    near(z(r.transforms[0].basis_world), [1., 0., 0.]);
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [0.25, 0., 0.],
    );
    near(r.transforms[0].pivot_world, [3., 2. / 3., 1. / 3.]);
}

#[test]
fn normal_frame_uses_inverse_transpose_under_reflected_nonuniform_scale() {
    let mut before = sheet();
    let mesh = before.mesh_assets.get_mut("mesh").unwrap();
    for id in ["c", "d"] {
        mesh.vertices.get_mut(id).unwrap()[2] = 1.;
    }
    before.entities.get_mut("target").unwrap().transform.scale = [-2., 3., 0.5];
    let mut editor = Editor::new(before).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0,0,0.25]}),
                json!({}),
            )],
            Some(0),
        )
        .unwrap();
    let length = (1_f64 / 9. + 4.).sqrt();
    let n = [0., -1. / 3. / length, 2. / length];
    near(z(r.transforms[0].basis_world), n);
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [0., n[1] * 0.25 / 3., n[2] * 0.25 / 0.5],
    );
}

#[test]
fn loose_edge_alignment_uses_orthogonal_fallback_and_active_degenerate_uses_identity() {
    for active in [false, true] {
        let before = scene(
            json!({"a":[1,0,0],"b":[2,0,0],"apart":[1,0,0]}),
            json!({}),
            json!({"edge":["b","a"]}),
            json!({"mode":["edge"],"selected":{"edges":["edge"]},"history":[{"domain":"edge","id":"edge"}]}),
        );
        let mut editor = Editor::new(before).unwrap();
        let r = editor
            .apply_with_outcomes(
                &[operation(
                    json!({"kind":"translate","value":[0,0,1]}),
                    json!({"pivot":if active {"active"} else {"median"}}),
                )],
                Some(0),
            )
            .unwrap();
        let s = 0.5_f64.sqrt();
        near(
            z(r.transforms[0].basis_world),
            if active { [0., 0., 1.] } else { [0., -s, -s] },
        );
        assert_eq!(
            editor.scene().mesh_assets["mesh"].vertices["apart"],
            [1., 0., 0.]
        );
    }
}

#[test]
fn individual_face_axes_have_their_own_tangent_and_connected_vertices_inherit_it() {
    let mut before = sheet();
    let mesh = before.mesh_assets.get_mut("mesh").unwrap();
    mesh.vertices.insert("extension".into(), [3., 0., 0.]);
    mesh.edges
        .insert("wire".into(), ["b".into(), "extension".into()]);
    let mut editor = Editor::new(before.clone()).unwrap();
    let r=editor.apply_with_outcomes(&[operation(json!({"kind":"translate","value":[0.5,0,0]}),json!({"pivot":"individual","proportional":{"radius":10,"falloff":"constant","connected":true}}))],Some(0)).unwrap();
    let receipt = &r.transforms[0];
    assert_eq!(
        receipt.component_basis_local["a"],
        [[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]]
    );
    assert_eq!(
        receipt.component_basis_local["extension"],
        receipt.component_basis_local["a"]
    );
    near(receipt.centres_local["extension"], [1., 0.5, 0.]);
    near(
        editor.scene().mesh_assets["mesh"].vertices["extension"],
        [3., 0.5, 0.],
    );
    assert!(!receipt.component_basis_local.contains_key("apart"));
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["apart"],
        [0.; 3]
    );
}

#[test]
fn zero_normal_and_coincident_pair_fall_back_without_merging_identity() {
    let before = scene(
        json!({"a":[0,0,0],"b":[0,0,0],"c":[0,0,0]}),
        json!({}),
        json!({}),
        json!({"selected":{"vertices":["a","b"]},"history":[{"domain":"vertex","id":"a"},{"domain":"vertex","id":"b"}]}),
    );
    let mut editor = Editor::new(before).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0.2,0.3,0.4]}),
                json!({}),
            )],
            Some(0),
        )
        .unwrap();
    assert_eq!(
        r.transforms[0].basis_world,
        [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
    );
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [0.2, 0.3, 0.4],
    );
    assert_eq!(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        editor.scene().mesh_assets["mesh"].vertices["b"]
    );
    assert_eq!(editor.scene().mesh_assets["mesh"].vertices["c"], [0.; 3]);
}

#[test]
fn normal_overflow_and_failed_batch_leave_no_change_or_undo_entry() {
    let mut before = sheet();
    before
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .vertices
        .get_mut("c")
        .unwrap()[0] = 1e30;
    let mut editor = Editor::new(before.clone()).unwrap();
    let command = operation(json!({"kind":"translate","value":[0,0,1]}), json!({}));
    assert!(
        editor
            .apply_with_outcomes(&[command.clone()], Some(0))
            .err()
            .unwrap()
            .0
            .contains("normal orientation arithmetic")
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
    let before = sheet();
    let mut editor = Editor::new(before.clone()).unwrap();
    assert!(
        editor
            .apply_with_outcomes(
                &[
                    command,
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
}

#[test]
fn normal_results_save_reload_undo_and_failed_save_are_atomic() {
    let folder = std::env::temp_dir().join(format!(
        "formora-normal-orientation-save-{}",
        std::process::id()
    ));
    std::fs::create_dir(&folder).unwrap();
    let path = folder.join("scene.json");
    let before = sheet();
    let mut session = Session::create(&path, before.clone()).unwrap();
    let command = operation(
        json!({"kind":"translate","value":[0.5,0,0]}),
        json!({"pivot":"individual"}),
    );
    let original = std::fs::read(&path).unwrap();
    std::fs::rename(&path, folder.join("backup.json")).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        session
            .apply_with_result(ApplyRequest {
                expected_revision: 0,
                commands: vec![command.clone()]
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
    let r = session
        .apply_with_result(ApplyRequest {
            expected_revision: 0,
            commands: vec![command],
        })
        .unwrap();
    near(r.transforms[0].component_basis_local["a"][1], [1., 0., 0.]);
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

#[test]
fn three_vertex_plane_uses_complete_reverse_history_and_keeps_disconnected_identity() {
    for history in [
        json!([]),
        json!([{"domain":"vertex","id":"a"},{"domain":"vertex","id":"b"},{"domain":"vertex","id":"c"}]),
    ] {
        let reverse = !history.as_array().unwrap().is_empty();
        let before = scene(
            json!({"a":[0,0,0],"b":[1,0,0],"c":[0,1,0],"apart":[0,0,0]}),
            json!({}),
            json!({}),
            json!({"selected":{"vertices":["a","b","c"]},"history":history}),
        );
        let mut editor = Editor::new(before).unwrap();
        let r = editor
            .apply_with_outcomes(
                &[operation(
                    json!({"kind":"translate","value":[0,0,0.25]}),
                    json!({}),
                )],
                Some(0),
            )
            .unwrap();
        near(
            z(r.transforms[0].basis_world),
            [0., 0., if reverse { -1. } else { 1. }],
        );
        near(
            editor.scene().mesh_assets["mesh"].vertices["a"],
            [0., 0., if reverse { -0.25 } else { 0.25 }],
        );
        assert_eq!(
            editor.scene().mesh_assets["mesh"].vertices["apart"],
            [0.; 3]
        );
    }
}

#[test]
fn ngon_uses_longest_edge_and_legacy_triangle_keeps_its_typed_face_identity() {
    let before = scene(
        json!({"a":[0,0,0],"b":[3,0,0],"c":[3,1,0],"d":[2,2,0],"e":[0,1,0]}),
        json!({"ngon":{"vertices":["a","b","c","d","e"]}}),
        json!({}),
        json!({"mode":["face"],"selected":{"faces":[{"kind":"polygon","id":"ngon"}]}}),
    );
    let mut editor = Editor::new(before).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0.25,0,0]}),
                json!({}),
            )],
            Some(0),
        )
        .unwrap();
    near(z(r.transforms[0].basis_world), [0., 0., 1.]);
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [0., -0.25, 0.],
    );
    let mut before = scene(
        json!({"a":[0,0,0],"b":[0,2,0],"c":[0,0,1]}),
        json!({}),
        json!({}),
        json!({}),
    );
    let mesh = before.mesh_assets.get_mut("mesh").unwrap();
    mesh.triangles.insert(
        "legacy".into(),
        serde_json::from_value(json!({"vertices":["a","b","c"],"uv_layers":{}})).unwrap(),
    );
    let mut editing = Editing {
        mode: [Domain::Face].into(),
        ..Editing::default()
    };
    editing
        .selected
        .faces
        .insert(FaceRef::Triangle("legacy".into()));
    set_editing(mesh, Some(editing)).unwrap();
    let mut editor = Editor::new(before).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0,0,0.25]}),
                json!({}),
            )],
            Some(0),
        )
        .unwrap();
    near(z(r.transforms[0].basis_world), [1., 0., 0.]);
    near(
        editor.scene().mesh_assets["mesh"].vertices["a"],
        [0.25, 0., 0.],
    );
    assert_eq!(
        r.transforms[0].changed.faces,
        [FaceRef::Triangle("legacy".into())].into()
    );
}

#[test]
fn more_than_three_loose_vertices_use_their_geometric_normal_sum() {
    let before = scene(
        json!({"a":[1,0,1],"b":[-1,0,1],"c":[0,1,1],"d":[0,-1,1]}),
        json!({}),
        json!({}),
        json!({"selected":{"vertices":["a","b","c","d"]}}),
    );
    let mut editor = Editor::new(before).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[operation(
                json!({"kind":"translate","value":[0,0,0.25]}),
                json!({}),
            )],
            Some(0),
        )
        .unwrap();
    near(z(r.transforms[0].basis_world), [0., 0., 1.]);
    for id in ["a", "b", "c", "d"] {
        assert_eq!(editor.scene().mesh_assets["mesh"].vertices[id][2], 1.25);
    }
}
