use formora::mesh::primitives::{DEFAULT_MAX_COMPONENTS, Primitive};
use formora::scene::*;
use serde_json::json;
use std::collections::BTreeMap;
fn spec(value: serde_json::Value) -> Primitive {
    serde_json::from_value(value).unwrap()
}
fn generate(value: serde_json::Value) -> formora::mesh::MeshAsset {
    spec(value).generate(DEFAULT_MAX_COMPONENTS).unwrap()
}

#[test]
fn defaults_generate_real_topology_uv_and_saved_parameters() {
    for (kind, counts) in [
        ("plane", (4, 4, 1)),
        ("cube", (8, 12, 6)),
        ("grid", (121, 220, 100)),
        ("circle", (32, 32, 0)),
    ] {
        let primitive = spec(json!({"kind":kind}));
        let asset = primitive.generate(DEFAULT_MAX_COMPONENTS).unwrap();
        assert_eq!(
            (
                asset.vertices.len(),
                asset.edges.len(),
                asset.polygons.len()
            ),
            counts
        );
        assert_eq!(asset.recipe.as_ref().unwrap().primitive, primitive);
        assert!(!asset.recipe.as_ref().unwrap().edited);
        assert_eq!(asset.uv_layout.as_ref().unwrap().layers, vec!["UVMap"]);
        assert_eq!(asset, primitive.generate(DEFAULT_MAX_COMPONENTS).unwrap());
        assert_eq!(
            asset,
            serde_json::from_str(&serde_json::to_string(&asset).unwrap()).unwrap()
        );
    }
}

#[test]
fn zero_dimension_behavior_and_undefined_circle_uv_are_explicit() {
    let plane = generate(json!({"kind":"plane","size":0}));
    assert_eq!(plane.vertices.len(), 4);
    assert!(plane.vertices.values().all(|p| *p == [0.; 3]));
    assert_eq!(plane.polygons["p000000"].normal, Some([0., 0., 1.]));
    let cube = generate(json!({"kind":"cube","size":0}));
    assert!(cube.vertices.values().flatten().all(|n| n.abs() == 0.5));
    let grid = generate(json!({"kind":"grid","size":0}));
    assert_eq!(grid.vertices.len(), 121);
    assert!(grid.vertices.values().all(|p| *p == [0.; 3]));
    for fill in ["ngon", "trifan"] {
        let circle = generate(json!({"kind":"circle","vertices":7,"radius":0,"fill_type":fill}));
        assert!(circle.vertices.values().all(|p| *p == [0.; 3]));
        assert_eq!(circle.diagnostics, vec!["degenerate_default_uv"]);
        assert!(
            circle
                .polygons
                .values()
                .flat_map(|p| p.uv_layers["UVMap"].iter())
                .all(|uv| *uv == [0.; 2])
        );
        assert!(circle.tessellate().unwrap().triangles.is_empty());
    }
    for kind in ["plane", "cube", "grid", "circle"] {
        let asset = generate(json!({"kind":kind,"calc_uvs":false}));
        assert!(asset.uv_layout.as_ref().unwrap().layers.is_empty());
        assert!(asset.polygons.values().all(|p| p.uv_layers.is_empty()));
    }
}

#[test]
fn bad_parameters_and_huge_requests_fail_before_allocation() {
    for value in [
        json!({"kind":"plane","size":-1}),
        json!({"kind":"cube","size":1e20}),
        json!({"kind":"grid","x_subdivisions":0}),
        json!({"kind":"circle","vertices":2}),
        json!({"kind":"circle","vertices":10000001}),
    ] {
        assert!(spec(value).generate(DEFAULT_MAX_COMPONENTS).is_err());
    }
    for size in [f64::NAN, f64::INFINITY] {
        assert!(
            Primitive::Plane {
                size,
                calc_uvs: true
            }
            .generate(DEFAULT_MAX_COMPONENTS)
            .is_err()
        );
    }
    assert!(
        Primitive::Cube {
            size: 2.,
            scale: [f64::NAN, 1., 1.],
            calc_uvs: true
        }
        .generate(DEFAULT_MAX_COMPONENTS)
        .is_err()
    );
    let mut editor = Editor::new(Scene::default()).unwrap();
    let error = editor
        .apply(
            &[Command::CreateMeshPrimitive {
                id: "invalid/id".into(),
                primitive: spec(json!({"kind":"cube"})),
                max_components: 0,
            }],
            Some(0),
        )
        .unwrap_err();
    assert!(error.0.contains("invalid mesh asset ID"));
    assert_eq!(editor.scene().revision, 0);
    let huge = spec(json!({"kind":"grid","x_subdivisions":10000000,"y_subdivisions":10000000}));
    let error = huge.generate(DEFAULT_MAX_COMPONENTS).unwrap_err();
    assert!(error.0.contains("budget"));
    assert!(spec(json!({"kind":"plane"})).generate(12).is_err());
    assert!(spec(json!({"kind":"plane"})).generate(13).is_ok());
    assert!(serde_json::from_value::<Primitive>(json!({"kind":"cube","radius":1})).is_err());
}

fn instance() -> Entity {
    Entity {
        name: "Shared".into(),
        parent: None,
        transform: Transform::default(),
        content: EntityKind::Mesh {
            geometry: Geometry::Asset {
                id: "generated".into(),
            },
            material: None,
        },
    }
}

#[test]
fn edits_mark_the_recipe_and_regeneration_preserves_shared_asset_identity_and_undo() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    let primitive = spec(json!({"kind":"cube"}));
    let original = primitive.generate(DEFAULT_MAX_COMPONENTS).unwrap();
    editor
        .apply(
            &[
                Command::CreateMeshPrimitive {
                    id: "generated".into(),
                    primitive: primitive.clone(),
                    max_components: DEFAULT_MAX_COMPONENTS,
                },
                Command::CreateEntity {
                    id: "a".into(),
                    entity: instance(),
                },
                Command::CreateEntity {
                    id: "b".into(),
                    entity: instance(),
                },
            ],
            Some(0),
        )
        .unwrap();
    let entities = editor.scene().entities.clone();
    editor
        .apply(
            &[Command::SetMeshVertices {
                id: "generated".into(),
                positions: BTreeMap::from([("v000000".into(), [9., 0., 0.])]),
            }],
            Some(1),
        )
        .unwrap();
    assert!(
        editor.scene().mesh_assets["generated"]
            .recipe
            .as_ref()
            .unwrap()
            .edited
    );
    let edited = editor.scene().mesh_assets["generated"].clone();
    editor
        .apply(
            &[Command::RegenerateMeshPrimitive {
                id: "generated".into(),
                primitive: None,
                max_components: None,
            }],
            Some(2),
        )
        .unwrap();
    assert_eq!(editor.scene().mesh_assets["generated"], original);
    assert_eq!(editor.scene().entities, entities);
    editor.undo(Some(3)).unwrap();
    assert_eq!(editor.scene().mesh_assets["generated"], edited);
    let before = editor.scene().clone();
    for command in [
        Command::CreateMeshPrimitive {
            id: "generated".into(),
            primitive: primitive.clone(),
            max_components: DEFAULT_MAX_COMPONENTS,
        },
        Command::RegenerateMeshPrimitive {
            id: "generated".into(),
            primitive: None,
            max_components: Some(0),
        },
    ] {
        assert!(editor.apply(&[command], Some(4)).is_err());
        assert_eq!(editor.scene(), &before);
    }
    editor
        .apply(
            &[Command::RegenerateMeshPrimitive {
                id: "generated".into(),
                primitive: Some(spec(
                    json!({"kind":"grid","x_subdivisions":3,"y_subdivisions":5}),
                )),
                max_components: None,
            }],
            Some(4),
        )
        .unwrap();
    assert_eq!(editor.scene().mesh_assets["generated"].polygons.len(), 15);
    assert_eq!(editor.scene().entities, entities);
}

#[test]
fn raw_assets_need_explicit_generation_parameters_and_rejected_recipes_do_not_commit() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    editor
        .apply(
            &[Command::SetMeshAsset {
                id: "raw".into(),
                asset: Box::default(),
            }],
            Some(0),
        )
        .unwrap();
    assert!(
        editor
            .apply(
                &[Command::RegenerateMeshPrimitive {
                    id: "raw".into(),
                    primitive: None,
                    max_components: None
                }],
                Some(1)
            )
            .is_err()
    );
    editor
        .apply(
            &[Command::RegenerateMeshPrimitive {
                id: "raw".into(),
                primitive: Some(spec(json!({"kind":"plane"}))),
                max_components: None,
            }],
            Some(1),
        )
        .unwrap();
    assert_eq!(editor.scene().mesh_assets["raw"].polygons.len(), 1);
    let before = editor.scene().clone();
    let mut invalid = before.mesh_assets["raw"].clone();
    invalid.recipe.as_mut().unwrap().max_components = 0;
    assert!(
        editor
            .apply(
                &[Command::SetMeshAsset {
                    id: "raw".into(),
                    asset: Box::new(invalid)
                }],
                Some(2)
            )
            .is_err()
    );
    assert_eq!(editor.scene(), &before);
}
