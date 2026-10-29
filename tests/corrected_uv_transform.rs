use formora::mesh::{MeshAsset, selection::*};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

fn build(vertices: Value, faces: Vec<(&str, Vec<&str>, Value)>, triangle: bool) -> Scene {
    let mut asset:MeshAsset=serde_json::from_value(json!({"vertices":vertices,"edges":{},"polygons":{},"triangles":{},"material_slots":[],"vertex_groups":["pin"],"vertex_weights":{"a":{"pin":0.75}}})).unwrap();
    let mut pairs = std::collections::BTreeSet::new();
    for (name, vertices, uv) in faces {
        if triangle {
            asset.triangles.insert(
                name.into(),
                serde_json::from_value(json!({"vertices":vertices,"uv_layers":uv})).unwrap(),
            );
        } else {
            for i in 0..vertices.len() {
                let mut pair = [
                    vertices[i].to_string(),
                    vertices[(i + 1) % vertices.len()].to_string(),
                ];
                pair.sort();
                if pairs.insert(pair.clone()) {
                    asset.edges.insert(format!("e{}", asset.edges.len()), pair);
                }
            }
            asset.polygons.insert(
                name.into(),
                serde_json::from_value(json!({"vertices":vertices,"uv_layers":uv,"smooth":false}))
                    .unwrap(),
            );
        }
    }
    let layers: Vec<_> = asset
        .polygons
        .values()
        .flat_map(|p| p.uv_layers.keys().cloned())
        .chain(
            asset
                .triangles
                .values()
                .flat_map(|p| p.uv_layers.keys().cloned()),
        )
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter()
        .collect();
    asset.uv_layout = Some(formora::mesh::UvLayout {
        active: layers.first().cloned(),
        layers,
    });
    let mut editing = Editing::default();
    editing.selected.vertices.insert("a".into());
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
fn square() -> Scene {
    build(
        json!({"a":[0,0,0],"b":[1,0,0],"c":[1,1,0],"d":[0,1,0]}),
        vec![(
            "face",
            vec!["a", "b", "c", "d"],
            json!({"UV":[[0,0],[1,0],[1,1],[0,1]],"Other":[[2,3],[4,3],[4,6],[2,6]]}),
        )],
        false,
    )
}
fn command(delta: [f64; 3], options: Value) -> Command {
    let mut t = json!({"entity":"target","change":{"kind":"translate","value":delta},"correct_face_attributes":true});
    for (k, v) in options.as_object().unwrap() {
        t[k] = v.clone();
    }
    serde_json::from_value(json!({"operation":"transform_mesh","transform":t})).unwrap()
}
fn uv(scene: &Scene, face: &str, layer: &str, corner: usize) -> [f64; 2] {
    let a = &scene.mesh_assets["mesh"];
    if let Some(p) = a.polygons.get(face) {
        p.uv_layers[layer][corner]
    } else {
        a.triangles[face].uv_layers[layer][corner]
    }
}
fn near(a: [f64; 2], b: [f64; 2]) {
    for i in 0..2 {
        assert!((a[i] - b[i]).abs() <= 1e-6, "{a:?} != {b:?}");
    }
}
fn preserved(a: &Scene, b: &Scene) {
    assert_eq!(a.entities, b.entities);
    let a = &a.mesh_assets["mesh"];
    let b = &b.mesh_assets["mesh"];
    assert_eq!(a.editing, b.editing);
    assert_eq!(a.edges, b.edges);
    assert_eq!(a.edge_seams, b.edge_seams);
    assert_eq!(a.uv_layout, b.uv_layout);
    assert_eq!(a.vertex_groups, b.vertex_groups);
    assert_eq!(a.vertex_weights, b.vertex_weights);
    assert_eq!(a.material_slots, b.material_slots);
}

#[test]
fn original_face_projection_preserves_two_affine_uv_fields_and_ignores_stored_normals() {
    let mut before = square();
    before
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .polygons
        .get_mut("face")
        .unwrap()
        .normal = Some([1., 0., 0.]);
    let mut e = Editor::new(before.clone()).unwrap();
    let r = e
        .apply_with_outcomes(&[command([0.25, 0.125, 0.6], json!({}))], Some(0))
        .unwrap();
    near(uv(e.scene(), "face", "UV", 0), [0.25, 0.125]);
    near(uv(e.scene(), "face", "Other", 0), [2.5, 3.375]);
    assert_eq!(
        r.transforms[0].attribute_faces,
        [FaceRef::Polygon("face".into())].into()
    );
    assert_eq!(r.transforms[0].shared_instances, ["instance", "target"]);
    preserved(&before, e.scene());
    for corner in 1..4 {
        assert_eq!(
            uv(e.scene(), "face", "UV", corner),
            uv(&before, "face", "UV", corner)
        );
    }
    e.undo(Some(1)).unwrap();
    assert_eq!(e.scene().mesh_assets, before.mesh_assets);
}

#[test]
fn triangle_and_ngon_interpolation_reproduce_authored_affine_coordinates() {
    for triangle in [true, false] {
        let before = if triangle {
            build(
                json!({"a":[0,0,0],"b":[1,0,0],"d":[0,1,0]}),
                vec![(
                    "face",
                    vec!["a", "b", "d"],
                    json!({"UV":[[0,0],[1,0],[0,1]]}),
                )],
                true,
            )
        } else {
            build(
                json!({"a":[0,0,0],"b":[1,0,0],"c":[1,1,0],"d":[0,1,0],"e":[0.5,1.4,0]}),
                vec![(
                    "face",
                    vec!["a", "b", "c", "e", "d"],
                    json!({"UV":[[0,0],[1,0],[1,1],[0.5,1.4],[0,1]]}),
                )],
                false,
            )
        };
        for delta in [[0.2, 0.1, 0.], [1.2, -0.3, 0.]] {
            let mut e = Editor::new(before.clone()).unwrap();
            e.apply(&[command(delta, json!({"keep_connected":false}))], Some(0))
                .unwrap();
            near(uv(e.scene(), "face", "UV", 0), [delta[0], delta[1]]);
            preserved(&before, e.scene());
        }
    }
}

fn fan() -> Scene {
    build(
        json!({"a":[0,0,0],"b":[1,0,0],"c":[0,1,0],"d":[-1,0,0]}),
        vec![
            (
                "first",
                vec!["a", "b", "c"],
                json!({"UV":[[0,0],[1,0],[0,1]],"Separate":[[4,4],[5,4],[4,5]]}),
            ),
            (
                "second",
                vec!["a", "c", "d"],
                json!({"UV":[[0,0],[0,2],[2,0]],"Separate":[[9,9],[9,11],[11,9]]}),
            ),
        ],
        false,
    )
}

#[test]
fn connected_fans_reweight_inside_corner_and_keep_each_layer_independent() {
    for keep in [false, true] {
        let mut before = fan();
        let a = before.mesh_assets.get_mut("mesh").unwrap();
        let shared = a
            .edges
            .iter()
            .find(|(_, p)| p[0] == "a" && p[1] == "c")
            .unwrap()
            .0
            .clone();
        a.edge_seams.insert(shared);
        let mut e = Editor::new(before.clone()).unwrap();
        e.apply(
            &[command([0.2, 0.1, 0.], json!({"keep_connected":keep}))],
            Some(0),
        )
        .unwrap();
        near(uv(e.scene(), "first", "UV", 0), [0.2, 0.1]);
        near(
            uv(e.scene(), "second", "UV", 0),
            if keep { [0.2, 0.1] } else { [-0.4, 0.2] },
        );
        near(uv(e.scene(), "first", "Separate", 0), [4.2, 4.1]);
        near(uv(e.scene(), "second", "Separate", 0), [8.6, 9.2]);
        preserved(&before, e.scene());
    }
}

#[test]
fn equal_uvs_on_disconnected_vertices_do_not_join() {
    let before = build(
        json!({"a":[0,0,0],"b":[1,0,0],"c":[0,1,0],"d":[0,0,0],"e":[-1,0,0],"f":[0,-1,0]}),
        vec![
            (
                "first",
                vec!["a", "b", "c"],
                json!({"UV":[[0,0],[1,0],[0,1]]}),
            ),
            (
                "other",
                vec!["d", "e", "f"],
                json!({"UV":[[0,0],[3,0],[0,3]]}),
            ),
        ],
        false,
    );
    let mut e = Editor::new(before.clone()).unwrap();
    e.apply(&[command([0.2, 0.1, 0.], json!({}))], Some(0))
        .unwrap();
    near(uv(e.scene(), "first", "UV", 0), [0.2, 0.1]);
    assert_eq!(uv(e.scene(), "other", "UV", 0), [0., 0.]);
    assert_eq!(e.scene().mesh_assets["mesh"].vertices["d"], [0.; 3]);
}

#[test]
fn nonmanifold_radial_fan_merges_original_corner_angles() {
    let before = build(
        json!({"a":[0,0,0],"b":[1,0,0],"c":[0,1,0],"d":[0,2,0],"e":[1,1,0]}),
        vec![
            (
                "one",
                vec!["a", "b", "c"],
                json!({"UV":[[0,0],[1,0],[0,1]]}),
            ),
            (
                "two",
                vec!["a", "b", "d"],
                json!({"UV":[[0,0],[2,0],[0,4]]}),
            ),
            (
                "three",
                vec!["a", "b", "e"],
                json!({"UV":[[0,0],[3,0],[3,3]]}),
            ),
        ],
        false,
    );
    let mut e = Editor::new(before.clone()).unwrap();
    e.apply(&[command([0.2, 0.1, 0.], json!({}))], Some(0))
        .unwrap();
    for face in ["one", "two", "three"] {
        near(uv(e.scene(), face, "UV", 0), [0.36, 0.18]);
    }
}

#[test]
fn zero_area_face_uses_its_real_nondegenerate_neighbour_and_corrects_all_corners() {
    let mut before = build(
        json!({"a":[0,0,0],"b":[1,0,0],"c":[2,0,0],"d":[0,1,0]}),
        vec![
            (
                "flat",
                vec!["a", "b", "c"],
                json!({"UV":[[10,10],[20,20],[30,30]]}),
            ),
            (
                "surface",
                vec!["b", "a", "d"],
                json!({"UV":[[1,0],[0,0],[0,1]]}),
            ),
        ],
        false,
    );
    let asset = before.mesh_assets.get_mut("mesh").unwrap();
    let mut editing = Editing::default();
    editing.selected.vertices.insert("c".into());
    set_editing(asset, Some(editing)).unwrap();
    let mut e = Editor::new(before.clone()).unwrap();
    let r = e
        .apply_with_outcomes(
            &[command([0.2, 0.1, 0.], json!({"keep_connected":false}))],
            Some(0),
        )
        .unwrap();
    near(uv(e.scene(), "flat", "UV", 0), [0., 0.]);
    near(uv(e.scene(), "flat", "UV", 1), [1., 0.]);
    near(uv(e.scene(), "flat", "UV", 2), [2.2, 0.1]);
    assert_eq!(
        r.transforms[0].attribute_faces,
        [FaceRef::Polygon("flat".into())].into()
    );
    preserved(&before, e.scene());
}

#[test]
fn uv_only_float_storage_changes_are_reported_without_fake_geometry_changes() {
    let mut before = square();
    before
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .polygons
        .get_mut("face")
        .unwrap()
        .uv_layers
        .get_mut("UV")
        .unwrap()[0] = [0.1, 0.2];
    let mut e = Editor::new(before.clone()).unwrap();
    let r = e
        .apply_with_outcomes(&[command([0.; 3], json!({}))], Some(0))
        .unwrap();
    assert!(r.transforms[0].changed.vertices.is_empty());
    assert!(r.transforms[0].changed.edges.is_empty());
    assert_eq!(
        r.transforms[0].changed.faces,
        [FaceRef::Polygon("face".into())].into()
    );
    assert_eq!(
        uv(e.scene(), "face", "UV", 0),
        [f64::from(0.1_f32), f64::from(0.2_f32)]
    );
    assert_eq!(e.scene().mesh_assets["mesh"].polygons["face"].normal, None);
}

#[test]
fn no_uv_asset_matches_ordinary_transform_and_disabling_correction_preserves_uvs() {
    let before = square();
    let mut e = Editor::new(before.clone()).unwrap();
    e.apply(
        &[command(
            [0.2, 0.1, 0.],
            json!({"correct_face_attributes":false}),
        )],
        Some(0),
    )
    .unwrap();
    assert_eq!(
        e.scene().mesh_assets["mesh"].polygons["face"].uv_layers,
        before.mesh_assets["mesh"].polygons["face"].uv_layers
    );
    let mut before = before;
    before
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .polygons
        .get_mut("face")
        .unwrap()
        .uv_layers
        .clear();
    before.mesh_assets.get_mut("mesh").unwrap().uv_layout = Some(formora::mesh::UvLayout {
        layers: Vec::new(),
        active: None,
    });
    let mut a = Editor::new(before.clone()).unwrap();
    let mut b = Editor::new(before).unwrap();
    a.apply(&[command([0.2, 0.1, 0.], json!({}))], Some(0))
        .unwrap();
    b.apply(
        &[command(
            [0.2, 0.1, 0.],
            json!({"correct_face_attributes":false}),
        )],
        Some(0),
    )
    .unwrap();
    assert_eq!(a.scene(), b.scene());
}

#[test]
fn correction_runs_after_mirror_copy_and_reports_both_uv_faces() {
    let before = build(
        json!({"a":[1,0,0],"b":[2,0,0],"c":[2,1,0],"d":[1,1,0],"e":[-1,0,0],"f":[-2,0,0],"g":[-2,1,0],"h":[-1,1,0]}),
        vec![
            (
                "right",
                vec!["a", "b", "c", "d"],
                json!({"UV":[[0,0],[1,0],[1,1],[0,1]]}),
            ),
            (
                "left",
                vec!["e", "h", "g", "f"],
                json!({"UV":[[0,0],[0,1],[1,1],[1,0]]}),
            ),
        ],
        false,
    );
    let mut editor = Editor::new(before.clone()).unwrap();
    let r = editor
        .apply_with_outcomes(
            &[command([0.2, 0.1, 0.], json!({"mirror":{"axis":"x"}}))],
            Some(0),
        )
        .unwrap();
    for face in ["left", "right"] {
        near(uv(editor.scene(), face, "UV", 0), [0.2, 0.1]);
    }
    assert_eq!(r.transforms[0].mirror_sources["e"], "a");
    assert_eq!(r.transforms[0].attribute_faces.len(), 2);
    preserved(&before, editor.scene());
}

#[test]
fn hidden_neighbour_faces_still_contribute_to_the_visible_vertex_uv_fan() {
    let mut before = fan();
    let mesh = before.mesh_assets.get_mut("mesh").unwrap();
    let mut edit = mesh.editing.clone().unwrap();
    edit.hidden.faces.insert(FaceRef::Polygon("second".into()));
    set_editing(mesh, Some(edit)).unwrap();
    let mut editor = Editor::new(before.clone()).unwrap();
    editor
        .apply(&[command([0.2, 0.1, 0.], json!({}))], Some(0))
        .unwrap();
    near(uv(editor.scene(), "first", "UV", 0), [0.2, 0.1]);
    near(uv(editor.scene(), "second", "UV", 0), [0.2, 0.1]);
    preserved(&before, editor.scene());
}

#[test]
fn uv_arithmetic_overflow_rejects_the_entire_edit_without_an_undo_entry() {
    let mut before = square();
    before
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .polygons
        .get_mut("face")
        .unwrap()
        .uv_layers
        .get_mut("UV")
        .unwrap()[0] = [1e40, 0.];
    before.validate().unwrap();
    let mut editor = Editor::new(before.clone()).unwrap();
    assert!(
        editor
            .apply(&[command([0.2, 0.1, 0.], json!({}))], Some(0))
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    assert!(editor.undo(Some(0)).is_err());
}

#[test]
fn uv_edits_reopen_undo_and_roll_back_failed_saves_and_batches() {
    let before = square();
    let dir = std::env::temp_dir().join(format!("formora-uv-save-{}", std::process::id()));
    std::fs::create_dir(&dir).unwrap();
    let path = dir.join("scene.json");
    let mut s = Session::create(&path, before.clone()).unwrap();
    let op = command([0.2, 0.1, 0.], json!({}));
    s.apply(ApplyRequest {
        expected_revision: 0,
        commands: vec![op.clone()],
    })
    .unwrap();
    near(
        uv(&Scene::load(&path).unwrap(), "face", "UV", 0),
        [0.2, 0.1],
    );
    let saved = std::fs::read(&path).unwrap();
    assert!(
        s.apply(ApplyRequest {
            expected_revision: 1,
            commands: vec![
                op.clone(),
                Command::DeleteEntity {
                    id: "missing".into()
                }
            ]
        })
        .is_err()
    );
    assert_eq!(std::fs::read(&path).unwrap(), saved);
    s.undo(UndoRequest {
        expected_revision: 1,
    })
    .unwrap();
    assert_eq!(s.scene().mesh_assets, before.mesh_assets);
    std::fs::rename(&path, dir.join("backup.json")).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        s.apply(ApplyRequest {
            expected_revision: 2,
            commands: vec![op]
        })
        .is_err()
    );
    assert_eq!(s.scene().mesh_assets, before.mesh_assets);
    assert_eq!(s.scene().revision, 2);
    assert!(
        s.undo(UndoRequest {
            expected_revision: 2
        })
        .is_err()
    );
    drop(s);
    std::fs::remove_dir_all(dir).unwrap();
}
