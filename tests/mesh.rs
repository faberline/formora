use formora::mesh::MeshAsset;
use formora::scene::*;
use formora::session::{ApplyRequest, InspectRequest, Session, UndoRequest};
use std::collections::BTreeMap;

fn asset() -> MeshAsset {
    serde_json::from_str(include_str!("fixtures/triangle-asset.json")).unwrap()
}
fn base() -> Scene {
    let mut scene = Scene::default();
    scene.materials.insert(
        "red".into(),
        Material {
            base_color: [1., 0., 0., 1.],
            roughness: 0.5,
            metallic: 0.,
        },
    );
    scene
}
fn entity() -> Entity {
    Entity {
        name: "Shared asset".into(),
        parent: None,
        transform: Transform::default(),
        content: EntityKind::Mesh {
            geometry: Geometry::Asset {
                id: "shared".into(),
            },
            material: None,
        },
    }
}
fn populated() -> Scene {
    let mut scene = base();
    scene.mesh_assets.insert("shared".into(), asset());
    scene.entities.insert("first".into(), entity());
    scene.entities.insert("second".into(), entity());
    scene.validate().unwrap();
    scene
}

#[test]
fn stable_ids_coincident_vertices_corner_attributes_and_shared_references_round_trip() {
    let scene = populated();
    let json = serde_json::to_string(&scene).unwrap();
    let restored: Scene = serde_json::from_str(&json).unwrap();
    restored.validate().unwrap();
    assert_eq!(scene, restored);
    assert_eq!(restored.mesh_assets["shared"].vertices.len(), 5);
    let mesh = InspectRequest {
        entity: None,
        mesh_asset: Some("shared".into()),
        tessellate: false,
        selection_topology: false,
        normals: false,
        world: false,
        object_state: false,
    }
    .inspect(&restored)
    .unwrap();
    assert_eq!(mesh["mesh_asset"], serde_json::to_value(asset()).unwrap());
    assert!(
        InspectRequest {
            entity: Some("first".into()),
            mesh_asset: Some("shared".into()),
            tessellate: false,
            selection_topology: false,
            normals: false,
            world: false,
            object_state: false,
        }
        .inspect(&restored)
        .is_err()
    );
    let mut editor = Editor::new(restored).unwrap();
    editor
        .apply(
            &[Command::SetMeshVertices {
                id: "shared".into(),
                positions: BTreeMap::from([("a".into(), [0., 0., 0.5])]),
            }],
            Some(0),
        )
        .unwrap();
    let mut expected = asset();
    expected.vertices.insert("a".into(), [0., 0., 0.5]);
    assert_eq!(editor.scene().mesh_assets["shared"], expected);
    assert_eq!(editor.scene().entities, scene.entities);
    editor.undo(Some(1)).unwrap();
    assert_eq!(editor.scene().mesh_assets, scene.mesh_assets);
}

#[test]
fn invalid_geometry_attributes_and_dangling_references_are_rejected() {
    let mut invalid = Vec::new();
    let mut a = asset();
    a.vertices.get_mut("a").unwrap()[0] = f64::NAN;
    invalid.push(a);
    let mut a = asset();
    a.triangles.get_mut("lower").unwrap().vertices[0] = "missing".into();
    invalid.push(a);
    let mut a = asset();
    a.triangles.get_mut("lower").unwrap().vertices[0] = "b".into();
    invalid.push(a);
    let mut a = asset();
    a.triangles.get_mut("lower").unwrap().material_slot = Some(2);
    invalid.push(a);
    let mut a = asset();
    a.triangles
        .get_mut("lower")
        .unwrap()
        .uv_layers
        .get_mut("UVMap")
        .unwrap()[0][0] = f64::INFINITY;
    invalid.push(a);
    let mut a = asset();
    a.triangles.get_mut("lower").unwrap().corner_normals = Some([[2., 0., 0.]; 3]);
    invalid.push(a);
    let mut a = asset();
    a.triangles.get_mut("lower").unwrap().corner_normals = Some([[f64::NAN, 0., 0.]; 3]);
    invalid.push(a);
    let mut a = asset();
    a.triangles.get_mut("lower").unwrap().corner_normals = Some([[1e-300, 0., 0.]; 3]);
    invalid.push(a);
    for asset in invalid {
        assert!(asset.validate().is_err());
    }
    let mut scene = populated();
    scene.materials.clear();
    assert!(scene.validate().is_err());
    let mut scene = populated();
    scene.mesh_assets.clear();
    assert!(scene.validate().is_err());
    let mut zero = asset();
    zero.triangles.get_mut("lower").unwrap().corner_normals = Some([[0.; 3]; 3]);
    zero.validate().unwrap();
    let mut json = serde_json::to_value(asset()).unwrap();
    json["triangles"]["lower"]["uv_layers"]["UVMap"] = serde_json::json!([[0., 0.], [1., 1.]]);
    assert!(serde_json::from_value::<MeshAsset>(json).is_err());
}

#[test]
fn duplicate_component_layer_asset_and_edit_ids_are_rejected() {
    for data in [
        r#"{"vertices":{"a":[0,0,0],"a":[1,0,0]},"triangles":{},"material_slots":[]}"#.to_owned(),
        serde_json::to_string(&asset()).unwrap().replace(
            "\"lower\":",
            &format!(
                "\"upper\":{},\"lower\":",
                serde_json::to_string(&asset().triangles["upper"]).unwrap()
            ),
        ),
        serde_json::to_string(&asset())
            .unwrap()
            .replace("\"UVMap\":", "\"UVMap\":[[0,0],[0,0],[0,0]],\"UVMap\":"),
    ] {
        assert!(serde_json::from_str::<MeshAsset>(&data).is_err());
    }
    let json = serde_json::to_string(&populated()).unwrap().replace(
        "\"shared\":",
        &format!(
            "\"shared\":{},\"shared\":",
            serde_json::to_string(&asset()).unwrap()
        ),
    );
    assert!(serde_json::from_str::<Scene>(&json).is_err());
    assert!(serde_json::from_str::<Command>(r#"{"operation":"set_mesh_vertices","id":"shared","positions":{"a":[0,0,0],"a":[1,1,1]}}"#).is_err());
}

#[test]
fn failure_preserves_disk_memory_and_undo_and_reference_deletion_is_atomic() {
    let path = std::env::temp_dir().join(format!("formora-mesh-{}.json", std::process::id()));
    let mut session = Session::create(&path, populated()).unwrap();
    let before = std::fs::read(&path).unwrap();
    for command in [
        Command::DeleteMeshAsset {
            id: "shared".into(),
        },
        Command::SetMeshVertices {
            id: "shared".into(),
            positions: BTreeMap::from([("a".into(), [9.; 3]), ("missing".into(), [0.; 3])]),
        },
        Command::SetMeshVertices {
            id: "shared".into(),
            positions: BTreeMap::new(),
        },
        Command::SetMeshAsset {
            id: "shared".into(),
            asset: Box::new(MeshAsset {
                material_slots: vec![Some("missing".into())],
                ..asset()
            }),
        },
    ] {
        assert!(
            session
                .apply(ApplyRequest {
                    expected_revision: 0,
                    commands: vec![command]
                })
                .is_err()
        );
        assert_eq!(session.scene(), &populated());
        assert_eq!(std::fs::read(&path).unwrap(), before);
        assert!(
            session
                .undo(UndoRequest {
                    expected_revision: 0
                })
                .is_err()
        );
    }
    session
        .apply(ApplyRequest {
            expected_revision: 0,
            commands: vec![Command::SetMeshVertices {
                id: "shared".into(),
                positions: BTreeMap::from([("a".into(), [0., 0., 1.])]),
            }],
        })
        .unwrap();
    assert_eq!(Scene::load(&path).unwrap(), *session.scene());
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    assert_eq!(session.scene().mesh_assets, populated().mesh_assets);
    session
        .apply(ApplyRequest {
            expected_revision: 2,
            commands: vec![
                Command::DeleteEntity { id: "first".into() },
                Command::DeleteEntity {
                    id: "second".into(),
                },
                Command::DeleteMeshAsset {
                    id: "shared".into(),
                },
            ],
        })
        .unwrap();
    assert!(Scene::load(&path).unwrap().mesh_assets.is_empty());
    drop(session);
    std::fs::remove_file(&path).unwrap();
    let _ = std::fs::remove_file(path.with_file_name(format!(
        ".{}.formora.lock",
        path.file_name().unwrap().to_string_lossy()
    )));
}

#[test]
fn fixed_blender_plane_and_cube_triangle_payloads_preserve_geometry_and_uvs() {
    for name in ["plane_default", "cube_default"] {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(format!(
            "baseline/reference/blender-5.2.3/mesh-primitives/{name}.json"
        ));
        let reference: serde_json::Value =
            serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
        let positions: Vec<[f64; 3]> =
            serde_json::from_value(reference["vertices"].clone()).unwrap();
        let faces: Vec<Vec<usize>> = serde_json::from_value(reference["faces"].clone()).unwrap();
        let mut asset = MeshAsset {
            vertices: positions
                .iter()
                .enumerate()
                .map(|(i, p)| (format!("v{i}"), *p))
                .collect(),
            ..MeshAsset::default()
        };
        for (i, t) in reference["triangles"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
        {
            let indices: [usize; 3] = serde_json::from_value(t.clone()).unwrap();
            let face = faces
                .iter()
                .position(|f| indices.iter().all(|v| f.contains(v)))
                .unwrap();
            let corners = indices.map(|v| faces[face].iter().position(|i| *i == v).unwrap());
            let layer = &reference["uv_layers"][0];
            let uv =
                corners.map(|c| serde_json::from_value(layer["faces"][face][c].clone()).unwrap());
            let offset: usize = faces[..face].iter().map(Vec::len).sum();
            let normals = corners.map(|c| {
                serde_json::from_value(reference["corner_normals"][offset + c].clone()).unwrap()
            });
            asset.triangles.insert(
                format!("t{i}"),
                formora::mesh::Triangle {
                    corner_colors: None,
                    vertices: indices.map(|v| format!("v{v}")),
                    uv_layers: BTreeMap::from([("UVMap".into(), uv)]),
                    corner_normals: Some(normals),
                    material_slot: None,
                },
            );
        }
        asset.validate().unwrap();
        let copy: MeshAsset =
            serde_json::from_str(&serde_json::to_string(&asset).unwrap()).unwrap();
        assert_eq!(copy, asset);
        let mut scene = Scene::default();
        scene.mesh_assets.insert("shared".into(), copy.clone());
        let mut instance = entity();
        instance.transform = Transform {
            translation: [3., -4., 2.],
            rotation: [
                0.,
                0.,
                std::f64::consts::FRAC_1_SQRT_2,
                std::f64::consts::FRAC_1_SQRT_2,
            ]
            .into(),
            scale: [2., 0.5, 1.5],
            ..Default::default()
        };
        scene.entities.insert("instance".into(), instance);
        scene.validate().unwrap();
        #[cfg(feature = "preview")]
        {
            let rendered = formora::preview::math::vertices(&scene).unwrap();
            let expected: Vec<[f64; 3]> = copy
                .triangles
                .values()
                .flat_map(|t| {
                    t.vertices.each_ref().map(|v| {
                        let [x, y, z] = copy.vertices[v];
                        [-0.5 * y + 3., 2. * x - 4., 1.5 * z + 2.]
                    })
                })
                .collect();
            assert_eq!(rendered.len(), expected.len());
            for (actual, expected) in rendered.iter().zip(expected) {
                for (a, e) in actual.position.into_iter().zip(expected) {
                    assert!((a as f64 - e).abs() <= 1e-6);
                }
            }
        }
        for (i, t) in reference["triangles"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
        {
            let expected: [usize; 3] = serde_json::from_value(t.clone()).unwrap();
            assert_eq!(
                copy.triangles[&format!("t{i}")]
                    .vertices
                    .each_ref()
                    .map(|v| copy.vertices[v]),
                expected.map(|i| positions[i])
            );
        }
    }
}
