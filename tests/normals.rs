use formora::mesh::{MeshAsset, Polygon, Triangle, normals, selection::*};
use formora::scene::*;
use formora::session::{ApplyRequest, InspectRequest, Session, UndoRequest};
use std::collections::BTreeMap;

fn polygon(vertices: &[&str], smooth: bool) -> Polygon {
    Polygon {
        vertices: vertices.iter().map(|s| (*s).into()).collect(),
        uv_layers: BTreeMap::new(),
        normal: None,
        corner_normals: None,
        smooth,
        material_slot: None,
    }
}

fn folded() -> MeshAsset {
    complete_edges(MeshAsset {
        vertices: [
            ("a", [0., 0., 0.]),
            ("b", [0., 1., 0.]),
            ("c", [-1., 1., 0.]),
            ("d", [-1., 0., 0.]),
            ("e", [0., 0., 1.]),
            ("f", [0., 1., 1.]),
        ]
        .into_iter()
        .map(|(id, p)| (id.into(), p))
        .collect(),
        polygons: BTreeMap::from([
            ("floor".into(), polygon(&["a", "b", "c", "d"], true)),
            ("wall".into(), polygon(&["a", "e", "f", "b"], true)),
        ]),
        edges: BTreeMap::from([("joint".into(), ["a".into(), "b".into()])]),
        ..Default::default()
    })
}

fn complete_edges(mut asset: MeshAsset) -> MeshAsset {
    let mut pairs: std::collections::BTreeSet<_> = asset
        .edges
        .values()
        .map(|pair| {
            let mut p = pair.clone();
            p.sort();
            p
        })
        .collect();
    for polygon in asset.polygons.values() {
        for i in 0..polygon.vertices.len() {
            let mut pair = [
                polygon.vertices[i].clone(),
                polygon.vertices[(i + 1) % polygon.vertices.len()].clone(),
            ];
            pair.sort();
            if pairs.insert(pair.clone()) {
                asset.edges.insert(format!("edge_{}", pairs.len()), pair);
            }
        }
    }
    asset
}

fn add_flat(asset: &mut MeshAsset) {
    for (id, p) in [
        ("x", [10., 0., 0.]),
        ("y", [11., 0., 0.]),
        ("z", [10., 1., 0.]),
    ] {
        asset.vertices.insert(id.into(), p);
    }
    asset
        .polygons
        .insert("unrelated".into(), polygon(&["x", "y", "z"], false));
    *asset = complete_edges(asset.clone());
}

fn corner(result: &normals::MeshNormals, id: &str, index: usize) -> [f64; 3] {
    result
        .faces
        .iter()
        .find(|face| face.face == FaceRef::Polygon(id.into()))
        .unwrap()
        .corner_normals[index]
}

fn near(actual: [f64; 3], expected: [f64; 3]) {
    for i in 0..3 {
        assert!(
            (actual[i] - expected[i]).abs() <= 1e-6,
            "{actual:?} != {expected:?}"
        );
    }
}

#[test]
fn smooth_joint_uses_angle_weighted_normals_with_or_without_unrelated_flat_faces() {
    for mixed in [false, true] {
        let mut asset = folded();
        if mixed {
            add_flat(&mut asset);
        }
        // A UV seam is not a sharp shading edge.
        asset.edge_seams.insert("joint".into());
        let before = asset.clone();
        let result = normals::automatic(&asset).unwrap();
        let half = 0.5_f64.sqrt();
        for (face, corners) in [("floor", [0, 1]), ("wall", [0, 3])] {
            for index in corners {
                near(corner(&result, face, index), [-half, 0., half]);
            }
        }
        near(corner(&result, "floor", 2), [0., 0., 1.]);
        near(corner(&result, "wall", 1), [-1., 0., 0.]);
        assert_eq!(asset, before);
    }
}

#[test]
fn flat_faces_wrong_winding_and_nonmanifold_edges_split_mixed_smooth_fans() {
    for boundary in ["flat", "winding", "nonmanifold"] {
        let mut asset = folded();
        add_flat(&mut asset);
        match boundary {
            "flat" => asset.polygons.get_mut("floor").unwrap().smooth = false,
            "winding" => asset.polygons.get_mut("wall").unwrap().vertices.reverse(),
            _ => {
                asset.vertices.insert("g".into(), [0., 1., -1.]);
                asset.vertices.insert("h".into(), [0., 0., -1.]);
                asset
                    .polygons
                    .insert("third".into(), polygon(&["a", "b", "g", "h"], true));
            }
        }
        let asset = complete_edges(asset);
        let result = normals::automatic(&asset).unwrap();
        near(corner(&result, "floor", 0), [0., 0., 1.]);
        near(
            corner(&result, "wall", 0),
            [if boundary == "winding" { 1. } else { -1. }, 0., 0.],
        );
    }
}

#[test]
fn all_smooth_point_domain_accumulates_disconnected_and_nonmanifold_incident_faces() {
    let mut asset = folded();
    asset.vertices.insert("g".into(), [0., 1., -1.]);
    asset.vertices.insert("h".into(), [0., 0., -1.]);
    asset
        .polygons
        .insert("third".into(), polygon(&["a", "b", "g", "h"], true));
    let mut asset = complete_edges(asset);
    let result = normals::automatic(&asset).unwrap();
    near(
        corner(&result, "floor", 0),
        [-2. / 5_f64.sqrt(), 0., 1. / 5_f64.sqrt()],
    );
    asset.polygons.remove("wall");
    asset.polygons.remove("third");
    asset.vertices.insert("i".into(), [0., -1., 0.]);
    asset.vertices.insert("j".into(), [0., -1., 1.]);
    asset.vertices.insert("k".into(), [0., 0., 1.]);
    asset
        .polygons
        .insert("bowtie".into(), polygon(&["a", "i", "j", "k"], true));
    let mut asset = complete_edges(asset);
    let result = normals::automatic(&asset).unwrap();
    let half = 0.5_f64.sqrt();
    near(corner(&result, "floor", 0), [-half, 0., half]);
    add_flat(&mut asset);
    let result = normals::automatic(&asset).unwrap();
    near(corner(&result, "floor", 0), [0., 0., 1.]);
    near(corner(&result, "bowtie", 0), [-1., 0., 0.]);
}

#[test]
fn degenerate_faces_keep_source_face_fallback_and_zero_angle_smooth_corners() {
    let mut asset = complete_edges(MeshAsset {
        vertices: BTreeMap::from([
            ("a".into(), [0., 0., 0.]),
            ("b".into(), [1., 0., 0.]),
            ("c".into(), [2., 0., 0.]),
        ]),
        polygons: BTreeMap::from([("line".into(), polygon(&["a", "b", "c"], true))]),
        ..Default::default()
    });
    let result = normals::automatic(&asset).unwrap();
    near(result.faces[0].normal, [0., 0., 1.]);
    near(corner(&result, "line", 0), [0.; 3]);
    near(corner(&result, "line", 1), [0., 0., 1.]);
    near(corner(&result, "line", 2), [0.; 3]);
    add_flat(&mut asset);
    let result = normals::automatic(&asset).unwrap();
    for index in 0..3 {
        near(corner(&result, "line", index), [0., 0., 1.]);
    }
}

#[test]
fn coincident_positions_and_equal_triangle_polygon_names_keep_distinct_identity() {
    let mut asset = folded();
    asset.polygons.get_mut("wall").unwrap().smooth = false;
    asset.polygons.get_mut("floor").unwrap().smooth = false;
    asset
        .vertices
        .insert("coincident".into(), asset.vertices["a"]);
    asset.triangles.insert(
        "floor".into(),
        Triangle {
            vertices: ["coincident".into(), "e".into(), "f".into()],
            uv_layers: BTreeMap::new(),
            corner_normals: None,
            material_slot: None,
        },
    );
    let before = asset.clone();
    let result = normals::automatic(&asset).unwrap();
    assert_eq!(result.faces.len(), 3);
    let polygon = result
        .faces
        .iter()
        .find(|f| f.face == FaceRef::Polygon("floor".into()))
        .unwrap();
    let triangle = result
        .faces
        .iter()
        .find(|f| f.face == FaceRef::Triangle("floor".into()))
        .unwrap();
    near(polygon.normal, [0., 0., 1.]);
    near(triangle.normal, [-1., 0., 0.]);
    assert_eq!(asset, before);
}

#[test]
fn explicit_corner_then_face_payloads_take_precedence_without_mutating_attributes() {
    let mut asset = folded();
    let p = asset.polygons.get_mut("floor").unwrap();
    p.normal = Some([0., 1., 0.]);
    p.corner_normals = Some(vec![[1., 0., 0.]; 4]);
    asset.polygons.get_mut("wall").unwrap().normal = Some([0., -1., 0.]);
    let before = asset.clone();
    let result = normals::resolved(&asset).unwrap();
    near(
        result
            .faces
            .iter()
            .find(|f| f.face == FaceRef::Polygon("floor".into()))
            .unwrap()
            .normal,
        [0., 1., 0.],
    );
    for index in 0..4 {
        near(corner(&result, "floor", index), [1., 0., 0.]);
        near(corner(&result, "wall", index), [0., -1., 0.]);
    }
    assert_eq!(asset, before);
    normals::apply_automatic(&mut asset).unwrap();
    let mut expected = before;
    for face in normals::automatic(&expected).unwrap().faces {
        let FaceRef::Polygon(id) = face.face else {
            unreachable!()
        };
        expected.polygons.get_mut(&id).unwrap().normal = Some(face.normal);
        expected.polygons.get_mut(&id).unwrap().corner_normals = Some(face.corner_normals);
    }
    assert_eq!(asset, expected);
}

fn scene(asset: MeshAsset) -> Scene {
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(), asset);
    scene.entities.insert(
        "surface".into(),
        Entity {
            name: "Surface".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "mesh".into() },
                material: None,
            },
        },
    );
    scene
}

#[test]
fn resolved_query_is_read_only_and_does_not_create_revision_disk_or_undo_changes() {
    let path =
        std::env::temp_dir().join(format!("formora-normal-query-{}.json", std::process::id()));
    let mut session = Session::create(&path, scene(folded())).unwrap();
    let disk = std::fs::read(&path).unwrap();
    let query = || InspectRequest {
        mesh_asset: Some("mesh".into()),
        normals: true,
        ..Default::default()
    };
    let first = session.inspect(query()).unwrap();
    assert_eq!(session.inspect(query()).unwrap(), first);
    assert_eq!(first["revision"], 0);
    assert_eq!(
        first["normals"],
        serde_json::to_value(normals::resolved(&folded()).unwrap()).unwrap()
    );
    assert_eq!(std::fs::read(&path).unwrap(), disk);
    assert!(
        session
            .undo(UndoRequest {
                expected_revision: 0
            })
            .is_err()
    );
    for request in [
        InspectRequest {
            normals: true,
            ..Default::default()
        },
        InspectRequest {
            entity: Some("surface".into()),
            ..query()
        },
        InspectRequest {
            mesh_asset: Some("missing".into()),
            ..query()
        },
    ] {
        assert!(session.inspect(request).is_err());
        assert_eq!(std::fs::read(&path).unwrap(), disk);
    }
    session
        .apply(ApplyRequest {
            expected_revision: 0,
            commands: vec![Command::SetMeshVertices {
                id: "mesh".into(),
                positions: BTreeMap::from([("c".into(), [-1., 1., 0.5])]),
            }],
        })
        .unwrap();
    assert_ne!(
        session.inspect(query()).unwrap()["normals"],
        first["normals"]
    );
    session
        .undo(UndoRequest {
            expected_revision: 1,
        })
        .unwrap();
    assert_eq!(
        session.inspect(query()).unwrap()["normals"],
        first["normals"]
    );
    drop(session);
    std::fs::remove_file(&path).unwrap();
    std::fs::remove_file(path.with_file_name(format!(
        ".{}.formora.lock",
        path.file_name().unwrap().to_str().unwrap()
    )))
    .unwrap();
}

#[test]
fn unsupported_float_range_and_arithmetic_overflow_fail_without_asset_changes() {
    for coordinate in [1e100, 1e30] {
        let mut asset = folded();
        asset.vertices.get_mut("c").unwrap()[0] = coordinate;
        asset.validate().unwrap();
        let before = asset.clone();
        assert!(normals::automatic(&asset).is_err());
        assert!(normals::apply_automatic(&mut asset).is_err());
        assert_eq!(asset, before);
    }
}

#[test]
#[cfg(feature = "preview")]
fn preview_uses_resolved_smooth_and_explicit_normals_without_changing_picking() {
    use formora::preview::math;
    use glam::DVec3;
    for explicit in [false, true] {
        let mut asset = folded();
        if explicit {
            asset.polygons.get_mut("floor").unwrap().corner_normals = Some(vec![[0., 1., 0.]; 4]);
            asset.polygons.get_mut("wall").unwrap().normal = Some([0., -1., 0.]);
        }
        let normals = normals::resolved(&asset).unwrap();
        let tessellation = asset.tessellate().unwrap();
        let mut scene = scene(asset);
        let before = serde_json::to_vec(&scene).unwrap();
        let vertices = math::vertices(&scene).unwrap();
        assert_eq!(vertices.len(), 12);
        for (index, triangle) in tessellation.triangles.iter().enumerate() {
            for i in 0..3 {
                near(
                    vertices[3 * index + i].normal.map(f64::from),
                    corner(&normals, &triangle.polygon, triangle.corners[i]),
                );
            }
        }
        let hit = math::pick(&scene, DVec3::new(-0.25, 0.25, 2.), -DVec3::Z)
            .unwrap()
            .unwrap();
        assert_eq!(hit.entity, "surface");
        assert_eq!(hit.position.to_array(), [-0.25, 0.25, 0.]);
        assert_eq!(serde_json::to_vec(&scene).unwrap(), before);
        let asset = scene.mesh_assets.get_mut("mesh").unwrap();
        let mut editing = Editing::default();
        editing.selected.vertices.insert("a".into());
        set_editing(asset, Some(editing)).unwrap();
        assert_eq!(math::vertices(&scene).unwrap().len(), 18);
        let marked_hit = math::pick(&scene, DVec3::new(-0.25, 0.25, 2.), -DVec3::Z)
            .unwrap()
            .unwrap();
        assert_eq!(hit.position, marked_hit.position);
        assert_eq!(hit.distance, marked_hit.distance);
    }
}
