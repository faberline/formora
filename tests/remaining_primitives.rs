use formora::mesh::primitives::{DEFAULT_MAX_COMPONENTS, Primitive};
use formora::mesh::selection::{self, Domain, Selector};
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};
use std::collections::BTreeMap;

fn primitive(value: Value) -> Primitive {
    serde_json::from_value(value).unwrap()
}
fn create(id: &str, primitive: Primitive) -> Command {
    Command::CreateMeshPrimitive {
        id: id.into(),
        primitive,
        max_components: DEFAULT_MAX_COMPONENTS,
    }
}
fn rebuild(id: &str, primitive: Option<Primitive>) -> Command {
    Command::RegenerateMeshPrimitive {
        id: id.into(),
        primitive,
        max_components: None,
    }
}

#[test]
fn defaults_preserve_real_source_topology_uvs_and_suzanne_mirror_identity() {
    for (kind, expected) in [
        ("ico_sphere", (42, 120, 80, 240)),
        ("monkey", (507, 1005, 500, 1968)),
    ] {
        let p = primitive(json!({"kind":kind}));
        let mesh = p.generate(DEFAULT_MAX_COMPONENTS).unwrap();
        assert_eq!(
            (
                mesh.vertices.len(),
                mesh.edges.len(),
                mesh.polygons.len(),
                mesh.polygons
                    .values()
                    .map(|f| f.vertices.len())
                    .sum::<usize>()
            ),
            expected
        );
        assert_eq!(
            p.component_count().unwrap(),
            expected.0 + expected.1 + expected.2 + expected.3
        );
        assert!(
            mesh.polygons
                .values()
                .all(|face| !face.smooth && face.uv_layers["UVMap"].len() == face.vertices.len())
        );
        assert_eq!(mesh.recipe.as_ref().unwrap().primitive, p);
        assert_eq!(mesh, p.generate(DEFAULT_MAX_COMPONENTS).unwrap());
        if kind == "monkey" {
            let key =
                |point: [f64; 3]| point.map(|v| if v == 0. { 0 } else { (v as f32).to_bits() });
            let mut counts = BTreeMap::new();
            for point in mesh.vertices.values() {
                *counts.entry(key(*point)).or_insert(0usize) += 1;
            }
            assert!(
                counts.len() < mesh.vertices.len(),
                "coincident authored vertices must remain distinct"
            );
            for point in mesh.vertices.values() {
                assert_eq!(
                    counts[&key(*point)],
                    counts[&key([-point[0], point[1], point[2]])]
                );
            }
        }
    }
}

#[test]
fn subdivision_estimates_cover_the_rna_range_and_reject_over_budget_before_allocation() {
    for level in 1..=10 {
        let n = 1usize << (level - 1);
        let p = primitive(json!({"kind":"ico_sphere","subdivisions":level}));
        assert_eq!(p.component_count().unwrap(), 120 * n * n + 2);
        if level <= 4 {
            let mesh = p.generate(DEFAULT_MAX_COMPONENTS).unwrap();
            assert_eq!(
                (mesh.vertices.len(), mesh.edges.len(), mesh.polygons.len()),
                (10 * n * n + 2, 30 * n * n, 20 * n * n)
            );
            assert_eq!(
                mesh.vertices.len() + mesh.polygons.len(),
                mesh.edges.len() + 2
            );
            assert!(mesh.polygons.values().all(|face| face.vertices.len() == 3));
        } else if level >= 8 {
            assert!(
                p.generate(DEFAULT_MAX_COMPONENTS)
                    .unwrap_err()
                    .0
                    .contains("generation budget")
            );
        }
    }
    let p = primitive(json!({"kind":"monkey"}));
    assert!(p.generate(3979).is_err());
    assert!(p.generate(3980).is_ok());
}

#[test]
fn invalid_parameters_and_failed_multi_command_batches_leave_scene_and_history_unchanged() {
    let mut invalid = vec![];
    for value in [
        json!({"kind":"ico_sphere","subdivisions":0}),
        json!({"kind":"ico_sphere","subdivisions":11}),
        json!({"kind":"ico_sphere","radius":-1}),
        json!({"kind":"monkey","size":-1}),
    ] {
        invalid.push(primitive(value));
    }
    invalid.push(Primitive::IcoSphere {
        subdivisions: 2,
        radius: f64::NAN,
        calc_uvs: true,
        scale: [1.; 3],
        creation_rotation: [0.; 3],
    });
    invalid.push(Primitive::IcoSphere {
        subdivisions: 2,
        radius: 1.,
        calc_uvs: true,
        scale: [f64::INFINITY; 3],
        creation_rotation: [0.; 3],
    });
    invalid.push(Primitive::Monkey {
        size: 2.,
        calc_uvs: true,
        creation_rotation: [f64::NAN; 3],
    });
    for p in invalid {
        assert!(p.generate(DEFAULT_MAX_COMPONENTS).is_err());
    }
    let mut editor = Editor::new(Scene::default()).unwrap();
    assert!(
        editor
            .apply(
                &[
                    create("valid", primitive(json!({"kind":"monkey"}))),
                    create(
                        "invalid",
                        primitive(json!({"kind":"ico_sphere","subdivisions":11}))
                    )
                ],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &Scene::default());
    assert!(editor.undo(Some(0)).is_err());
    editor
        .apply(
            &[create("mesh", primitive(json!({"kind":"ico_sphere"})))],
            Some(0),
        )
        .unwrap();
    let before = editor.scene().clone();
    assert!(
        editor
            .apply(
                &[create("mesh", primitive(json!({"kind":"monkey"})))],
                Some(1)
            )
            .is_err()
    );
    assert!(
        editor
            .apply(
                &[rebuild("mesh", Some(primitive(json!({"kind":"monkey"}))))],
                Some(0)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
}

#[test]
fn recipes_rebuild_save_reload_and_undo_for_both_models() {
    for kind in ["ico_sphere", "monkey"] {
        let folder =
            std::env::temp_dir().join(format!("formora-remaining-{kind}-{}", std::process::id()));
        std::fs::create_dir(&folder).unwrap();
        let path = folder.join("scene.json");
        let mut session = Session::create(&path, Scene::default()).unwrap();
        session
            .apply(ApplyRequest {
                expected_revision: 0,
                commands: vec![create("mesh", primitive(json!({"kind":kind})))],
            })
            .unwrap();
        let original = session.scene().mesh_assets["mesh"].clone();
        let mut changed = json!({"kind":kind});
        changed[if kind == "monkey" { "size" } else { "radius" }] = json!(3.);
        session
            .apply(ApplyRequest {
                expected_revision: 1,
                commands: vec![rebuild("mesh", Some(primitive(changed)))],
            })
            .unwrap();
        assert_ne!(
            session.scene().mesh_assets["mesh"].vertices,
            original.vertices
        );
        assert_eq!(Scene::load(&path).unwrap(), *session.scene());
        session
            .undo(UndoRequest {
                expected_revision: 2,
            })
            .unwrap();
        assert_eq!(session.scene().mesh_assets["mesh"], original);
        session
            .apply(ApplyRequest {
                expected_revision: 3,
                commands: vec![Command::SetMeshVertices {
                    id: "mesh".into(),
                    positions: BTreeMap::from([("v000000".into(), [9.; 3])]),
                }],
            })
            .unwrap();
        assert!(
            session.scene().mesh_assets["mesh"]
                .recipe
                .as_ref()
                .unwrap()
                .edited
        );
        session
            .apply(ApplyRequest {
                expected_revision: 4,
                commands: vec![rebuild("mesh", None)],
            })
            .unwrap();
        assert_eq!(session.scene().mesh_assets["mesh"], original);
        assert_eq!(Scene::load(&path).unwrap(), *session.scene());
        drop(session);
        std::fs::remove_dir_all(folder).unwrap();
    }
}

#[test]
fn zero_dimensions_and_axis_scaling_preserve_authored_ids_and_topology() {
    for (normal, zero) in [
        (
            json!({"kind":"ico_sphere","subdivisions":1}),
            json!({"kind":"ico_sphere","subdivisions":1,"radius":0}),
        ),
        (json!({"kind":"monkey"}), json!({"kind":"monkey","size":0})),
    ] {
        let base = primitive(normal).generate(DEFAULT_MAX_COMPONENTS).unwrap();
        let zero = primitive(zero).generate(DEFAULT_MAX_COMPONENTS).unwrap();
        assert_eq!(
            base.vertices.keys().collect::<Vec<_>>(),
            zero.vertices.keys().collect::<Vec<_>>()
        );
        assert_eq!(base.edges, zero.edges);
        assert!(zero.vertices.values().all(|point| *point == [0.; 3]));
        for (id, face) in &zero.polygons {
            assert_eq!(base.polygons[id].vertices, face.vertices);
            assert_eq!(base.polygons[id].uv_layers, face.uv_layers);
        }
    }
    let base = primitive(json!({"kind":"ico_sphere"}))
        .generate(DEFAULT_MAX_COMPONENTS)
        .unwrap();
    for scale in [[-1.25, 0.75, 2.], [1., 0., 1.]] {
        let changed = primitive(json!({"kind":"ico_sphere","scale":scale}))
            .generate(DEFAULT_MAX_COMPONENTS)
            .unwrap();
        assert_eq!(base.edges, changed.edges);
        for (id, point) in &base.vertices {
            for i in 0..3 {
                assert_eq!(
                    changed.vertices[id][i],
                    ((point[i] as f32) * (scale[i] as f32)) as f64
                );
            }
        }
    }
}

#[test]
fn shared_instances_and_selection_survive_undo_of_recipe_replacement() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    editor
        .apply(
            &[create("shared", primitive(json!({"kind":"monkey"})))],
            Some(0),
        )
        .unwrap();
    for id in ["first", "second"] {
        editor
            .apply(
                &[Command::CreateEntity {
                    id: id.into(),
                    entity: Entity {
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
                }],
                None,
            )
            .unwrap();
    }
    editor
        .apply(
            &[Command::SelectMesh {
                id: "shared".into(),
                selector: Selector::FacesBySides {
                    count: 4,
                    comparison: selection::CountComparison::Equal,
                    extend: false,
                },
            }],
            None,
        )
        .unwrap();
    let before = editor.scene().clone();
    assert!(
        !before.mesh_assets["shared"]
            .editing
            .as_ref()
            .unwrap()
            .selected
            .faces
            .is_empty()
    );
    editor
        .apply(
            &[rebuild(
                "shared",
                Some(primitive(json!({"kind":"ico_sphere","subdivisions":1}))),
            )],
            None,
        )
        .unwrap();
    assert_eq!(editor.scene().entities, before.entities);
    assert!(editor.scene().mesh_assets["shared"].editing.is_none());
    editor
        .apply(
            &[Command::SelectMesh {
                id: "shared".into(),
                selector: Selector::Mode {
                    domain: Domain::Face,
                    action: selection::ModeAction::Enable,
                    extend: false,
                    expand: false,
                },
            }],
            None,
        )
        .unwrap();
    editor.undo(None).unwrap();
    editor.undo(None).unwrap();
    assert_eq!(editor.scene().mesh_assets, before.mesh_assets);
    assert_eq!(editor.scene().entities, before.entities);
}
