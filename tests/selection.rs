use formora::mesh::{MeshAsset, selection::*};
use formora::scene::*;
use formora::session::{ApplyRequest, InspectRequest, Session, UndoRequest};
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};

fn asset() -> MeshAsset {
    serde_json::from_value(json!({
        "vertices":{"a":[0,0,0],"b":[1,0,0],"c":[0,1,0],"isolated":[0,0,0]},
        "triangles":{"face":{"vertices":["a","b","c"],"uv_layers":{},"corner_normals":null,"material_slot":null}},
        "material_slots":[]
    })).unwrap()
}
fn select(selector: Selector) -> Command {
    Command::SelectMesh {
        id: "shared".into(),
        selector,
    }
}
fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.mesh_assets.insert("shared".into(), asset());
    for id in ["first", "second"] {
        scene.entities.insert(
            id.into(),
            Entity {
                name: id.into(),
                parent: None,
                transform: Transform::default(),
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset {
                        id: "shared".into(),
                    },
                    material: None,
                },
            },
        );
    }
    scene
}

#[test]
fn legacy_edges_are_stable_queries_are_read_only_and_face_kinds_do_not_alias() {
    let mut mesh = asset();
    let first = topology(&mesh).unwrap();
    assert_eq!(first.edges.len(), 3);
    mesh.edges = first.edges.clone();
    mesh.polygons.insert(
        "face".into(),
        formora::mesh::Polygon {
            corner_colors: None,
            vertices: vec!["a".into(), "b".into(), "c".into()],
            uv_layers: BTreeMap::new(),
            corner_normals: None,
            normal: None,
            smooth: false,
            material_slot: None,
        },
    );
    mesh.validate().unwrap();
    let second = topology(&mesh).unwrap();
    assert_eq!(first.edges, second.edges);
    assert_eq!(second.faces.len(), 2);
    assert_ne!(second.faces[0].face, second.faces[1].face);
    let mut authored = scene();
    authored.mesh_assets.insert("shared".into(), mesh);
    let before = serde_json::to_vec(&authored).unwrap();
    let query = InspectRequest {
        mesh_asset: Some("shared".into()),
        selection_topology: true,
        ..Default::default()
    };
    let a = query.inspect(&authored).unwrap();
    let b = query.inspect(&authored).unwrap();
    assert_eq!(a, b);
    assert_eq!(serde_json::to_vec(&authored).unwrap(), before);
    assert!(
        InspectRequest {
            selection_topology: true,
            ..Default::default()
        }
        .inspect(&authored)
        .is_err()
    );
    let old = serde_json::to_value(asset()).unwrap();
    for key in [
        "editing",
        "vertex_groups",
        "vertex_weights",
        "edge_seams",
        "smooth_triangles",
    ] {
        assert!(old.get(key).is_none());
    }
}

#[test]
fn zero_weight_is_membership_and_missing_layer_is_distinct_from_empty_layer() {
    let mut mesh = asset();
    mesh.vertex_groups = vec!["Group".into()];
    let selector = Selector::Ungrouped { extend: false };
    assert!(
        apply(&mut mesh, &selector)
            .unwrap_err()
            .0
            .starts_with("missing_vertex_weights:")
    );
    assert!(mesh.editing.is_none());
    mesh.vertex_weights = Some(VertexWeights::default());
    apply(&mut mesh, &selector).unwrap();
    assert_eq!(mesh.editing.as_ref().unwrap().selected.vertices.len(), 4);
    mesh.vertex_weights.as_mut().unwrap().0.insert(
        "a".into(),
        GroupWeights(BTreeMap::from([("Group".into(), 0.)])),
    );
    apply(&mut mesh, &selector).unwrap();
    assert!(
        !mesh
            .editing
            .as_ref()
            .unwrap()
            .selected
            .vertices
            .contains("a")
    );
    assert_eq!(mesh.editing.as_ref().unwrap().selected.vertices.len(), 3);
    let saved = serde_json::to_vec(&mesh).unwrap();
    let restored: MeshAsset = serde_json::from_slice(&saved).unwrap();
    assert_eq!(mesh, restored);
}

#[test]
fn invalid_component_references_groups_weights_and_duplicate_input_are_rejected() {
    for raw in [
        r#"{"mode":["vertex","vertex"]}"#,
        r#"{"selected":{"vertices":["a","a"]}}"#,
        r#"{"selected":{"faces":[{"kind":"triangle","id":"face"},{"kind":"triangle","id":"face"}]}}"#,
    ] {
        assert!(serde_json::from_str::<Editing>(raw).is_err());
    }
    assert!(serde_json::from_str::<VertexWeights>(r#"{"a":{},"a":{}}"#).is_err());
    assert!(serde_json::from_str::<GroupWeights>(r#"{"Group":0,"Group":1}"#).is_err());
    for editing in [
        Editing {
            mode: BTreeSet::new(),
            ..Default::default()
        },
        Editing {
            selected: Elements {
                vertices: BTreeSet::from(["missing".into()]),
                ..Default::default()
            },
            ..Default::default()
        },
        Editing {
            active_face: Some(FaceRef::Polygon("face".into())),
            ..Default::default()
        },
        Editing {
            history: vec![Component::Vertex { id: "a".into() }],
            ..Default::default()
        },
    ] {
        let mut mesh = asset();
        assert!(set_editing(&mut mesh, Some(editing)).is_err());
        assert!(mesh.editing.is_none());
    }
    for (vertex, group, weight) in [
        ("missing", "Group", 0.),
        ("a", "Unknown", 0.),
        ("a", "Group", -0.1),
        ("a", "Group", 1.1),
        ("a", "Group", f64::NAN),
    ] {
        let mut mesh = asset();
        mesh.vertex_groups = vec!["Group".into()];
        mesh.vertex_weights = Some(VertexWeights(BTreeMap::from([(
            vertex.into(),
            GroupWeights(BTreeMap::from([(group.into(), weight)])),
        )])));
        assert!(mesh.validate().is_err());
    }
    let mut mesh = asset();
    mesh.vertex_groups = vec!["Group".into(), "Group".into()];
    assert!(mesh.validate().is_err());
    let mut mesh = asset();
    mesh.edge_seams.insert("missing".into());
    assert!(mesh.validate().is_err());
}

#[test]
fn no_op_and_mode_conversion_preserve_isolated_vertices_and_history_rules() {
    let mut mesh = asset();
    assert_eq!(
        apply(
            &mut mesh,
            &Selector::Mode {
                domain: Domain::Vertex,
                action: ModeAction::Enable,
                extend: false,
                expand: false
            }
        )
        .unwrap(),
        Outcome::Unchanged
    );
    assert!(mesh.editing.is_none());
    let editing = Editing {
        selected: Elements {
            vertices: BTreeSet::from(["isolated".into()]),
            ..Default::default()
        },
        history: vec![Component::Vertex {
            id: "isolated".into(),
        }],
        ..Default::default()
    };
    set_editing(&mut mesh, Some(editing)).unwrap();
    apply(
        &mut mesh,
        &Selector::Mode {
            domain: Domain::Face,
            action: ModeAction::Enable,
            extend: false,
            expand: false,
        },
    )
    .unwrap();
    let editing = mesh.editing.as_ref().unwrap();
    assert_eq!(editing.mode, BTreeSet::from([Domain::Face]));
    assert_eq!(
        editing.selected.vertices,
        BTreeSet::from(["isolated".into()])
    );
    assert!(editing.history.is_empty());
}

#[test]
fn unmatched_additive_trait_preserves_independent_flags_from_prior_operations() {
    // A face-only flag state can result from the interior operation.
    let mut mesh = asset();
    mesh.editing = Some(Editing {
        selected: Elements {
            vertices: BTreeSet::from(["a".into()]),
            faces: BTreeSet::from([FaceRef::Triangle("face".into())]),
            ..Default::default()
        },
        ..Default::default()
    });
    let before = mesh.clone();
    apply(
        &mut mesh,
        &Selector::FacesBySides {
            count: 10,
            comparison: CountComparison::Equal,
            extend: true,
        },
    )
    .unwrap();
    assert_eq!(mesh, before);
}

#[test]
fn ordered_receipts_shared_assets_and_multi_command_failure_are_atomic() {
    let mut editor = Editor::new(scene()).unwrap();
    let initial = editor.scene().clone();
    let result = editor
        .apply_with_outcomes(
            &[
                select(Selector::Loose { extend: false }),
                select(Selector::Mode {
                    domain: Domain::Vertex,
                    action: ModeAction::Enable,
                    extend: false,
                    expand: false,
                }),
            ],
            Some(0),
        )
        .unwrap();
    assert_eq!(result.revision, 1);
    assert_eq!(result.selection.len(), 2);
    assert_eq!(result.selection[0].command_index, 0);
    assert_eq!(result.selection[0].outcome, Outcome::Completed);
    assert_eq!(result.selection[1].command_index, 1);
    assert_eq!(result.selection[1].outcome, Outcome::Unchanged);
    assert_eq!(editor.scene().entities, initial.entities);
    assert_eq!(
        editor.scene().mesh_assets["shared"]
            .editing
            .as_ref()
            .unwrap()
            .selected
            .vertices,
        BTreeSet::from(["isolated".into()])
    );
    let before = editor.scene().clone();
    assert!(
        editor
            .apply_with_outcomes(&[select(Selector::Loose { extend: false })], Some(0))
            .is_err()
    );
    assert!(
        editor
            .apply_with_outcomes(
                &[
                    select(Selector::FacesBySides {
                        count: 3,
                        comparison: CountComparison::Equal,
                        extend: false
                    }),
                    select(Selector::Ungrouped { extend: false })
                ],
                Some(1)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
    editor.undo(Some(1)).unwrap();
    assert_eq!(editor.scene().mesh_assets, initial.mesh_assets);
    assert!(editor.undo(Some(2)).is_err());
}

#[test]
fn failed_persistence_does_not_emit_receipts_change_memory_or_push_undo() {
    let root =
        std::env::temp_dir().join(format!("formora-selection-persist-{}", std::process::id()));
    std::fs::create_dir(&root).unwrap();
    let path = root.join("scene.json");
    let backup = root.join("backup.json");
    let mut session = Session::create(&path, scene()).unwrap();
    let before = session.scene().clone();
    std::fs::rename(&path, &backup).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        session
            .apply_with_result(ApplyRequest {
                expected_revision: 0,
                commands: vec![select(Selector::Loose { extend: false })]
            })
            .is_err()
    );
    assert_eq!(session.scene(), &before);
    std::fs::remove_dir(&path).unwrap();
    std::fs::rename(&backup, &path).unwrap();
    assert!(
        session
            .undo(UndoRequest {
                expected_revision: 0
            })
            .is_err()
    );
    assert_eq!(Scene::load(&path).unwrap(), before);
    session
        .apply_with_result(ApplyRequest {
            expected_revision: 0,
            commands: vec![select(Selector::Loose { extend: false })],
        })
        .unwrap();
    assert_eq!(Scene::load(&path).unwrap(), *session.scene());
    drop(session);
    std::fs::remove_dir_all(root).unwrap();
}
