use formora::mesh::{MeshAsset, Polygon};
use formora::scene::*;
use formora::session::InspectRequest;
use std::collections::BTreeMap;

fn fixture() -> MeshAsset {
    serde_json::from_str(include_str!("fixtures/polygon-asset.json")).unwrap()
}
fn ring(points: &[[f64; 3]]) -> MeshAsset {
    MeshAsset {
        vertices: points
            .iter()
            .enumerate()
            .map(|(i, p)| (format!("v{i}"), *p))
            .collect(),
        edges: (0..points.len())
            .map(|i| {
                (
                    format!("e{i}"),
                    [format!("v{i}"), format!("v{}", (i + 1) % points.len())],
                )
            })
            .collect(),
        polygons: BTreeMap::from([(
            "face".into(),
            Polygon {
                vertices: (0..points.len()).map(|i| format!("v{i}")).collect(),
                uv_layers: BTreeMap::new(),
                corner_normals: None,
                normal: None,
                smooth: false,
                material_slot: None,
            },
        )]),
        ..MeshAsset::default()
    }
}
fn signed_area(points: &[[f64; 2]]) -> f64 {
    (0..points.len())
        .map(|i| {
            points[i][0] * points[(i + 1) % points.len()][1]
                - points[i][1] * points[(i + 1) % points.len()][0]
        })
        .sum::<f64>()
        / 2.
}
fn in_u([x, y]: [f64; 2]) -> bool {
    (0. ..=3.).contains(&x) && (0. ..=3.).contains(&y) && (y <= 1. || x <= 1. || x >= 2.)
}

#[test]
fn concave_faces_keep_winding_area_and_notch_across_planes_scales_and_order() {
    let shape = [
        [0., 0.],
        [3., 0.],
        [3., 3.],
        [2., 3.],
        [2., 1.],
        [1., 1.],
        [1., 3.],
        [0., 3.],
    ];
    for scale in [1e-9, 1., 1e6] {
        for plane in 0..4 {
            for reverse in [false, true] {
                let mut source = shape.to_vec();
                if reverse {
                    source.reverse();
                }
                let points: Vec<_> = source
                    .iter()
                    .map(|[x, y]| {
                        let (x, y) = (x * scale, y * scale);
                        match plane {
                            0 => [x, y, 0.],
                            1 => [1., x, y],
                            2 => [x, 2., y],
                            _ => [0.6 * x - 0.64 * y, 0.8 * x + 0.48 * y, 0.6 * y],
                        }
                    })
                    .collect();
                let asset = ring(&points);
                let before = asset.clone();
                let output = asset.tessellate().unwrap();
                assert_eq!(output.triangles.len(), source.len() - 2);
                assert!(output.diagnostics.is_empty());
                let mut total = 0.;
                for triangle in &output.triangles {
                    let p = triangle.corners.map(|i| source[i]);
                    let area = signed_area(&p);
                    assert!(if reverse { area < 0. } else { area > 0. });
                    total += area;
                    // Sample the full interior and every edge, not only the centroid.
                    for a in 0..=10 {
                        for b in 0..=10 - a {
                            let weights = [a, b, 10 - a - b];
                            let point = std::array::from_fn(|i| {
                                p.iter()
                                    .zip(weights)
                                    .map(|(p, w)| p[i] * w as f64)
                                    .sum::<f64>()
                                    / 10.
                            });
                            assert!(in_u(point), "triangle fills notch: {p:?} -> {point:?}");
                        }
                    }
                }
                assert!((total - signed_area(&source)).abs() <= 1e-10);
                for x in 0..30 {
                    for y in 0..30 {
                        let point = [(x as f64 + 0.37) / 10., (y as f64 + 0.61) / 10.];
                        let sign = if reverse { -1. } else { 1. };
                        let covering = output
                            .triangles
                            .iter()
                            .filter(|t| {
                                let p = t.corners.map(|i| source[i]);
                                (0..3).all(|i| {
                                    sign * signed_area(&[p[i], p[(i + 1) % 3], point]) > 0.
                                })
                            })
                            .count();
                        assert_eq!(
                            covering,
                            usize::from(in_u(point)),
                            "missing or overlapping interior at {point:?}"
                        );
                    }
                }
                assert_eq!(asset, before);
            }
        }
    }
}

#[test]
fn collinear_and_coincident_corners_are_only_removed_from_preview() {
    for points in [
        vec![
            [0., 0., 0.],
            [1., 0., 0.],
            [2., 0., 0.],
            [2., 2., 0.],
            [0., 2., 0.],
        ],
        vec![
            [0., 0., 0.],
            [0., 0., 0.],
            [2., 0., 0.],
            [2., 2., 0.],
            [0., 2., 0.],
        ],
    ] {
        let asset = ring(&points);
        let before = asset.clone();
        let output = asset.tessellate().unwrap();
        assert_eq!(output.triangles.len(), 2);
        assert_eq!(output.diagnostics[0].code, "collapsed_polygon_corners");
        assert_eq!(asset, before);
    }
    for points in [vec![[0.; 3]; 8], vec![[0.; 3], [1., 0., 0.], [2., 0., 0.]]] {
        let asset = ring(&points);
        let output = asset.tessellate().unwrap();
        assert!(output.triangles.is_empty());
        assert_eq!(output.diagnostics[0].code, "degenerate_polygon");
        assert_eq!(asset.vertices.len(), points.len());
    }
}

#[test]
fn crossing_projection_fails_instead_of_publishing_partial_triangles() {
    // The second loop has positive signed area, so checking area alone is insufficient.
    for points in [
        vec![[0., 0., 0.], [2., 2., 0.], [0., 2., 0.], [2., 0., 0.]],
        vec![
            [0., 0., 0.],
            [3., 3., 0.],
            [0., 3., 0.],
            [2., 0., 0.],
            [3., 0., 0.],
        ],
    ] {
        let asset = ring(&points);
        asset.validate().unwrap();
        let before = asset.clone();
        let error = asset.tessellate().unwrap_err();
        assert!(error.0.contains("self-intersecting"), "{error}");
        assert_eq!(asset, before);
    }
}

#[test]
fn topology_uv_order_loose_edges_and_nonmanifold_connections_round_trip_and_undo() {
    let mut asset = fixture();
    asset
        .polygons
        .insert("shared_edge_second".into(), asset.polygons["u"].clone());
    asset
        .polygons
        .insert("shared_edge_third".into(), asset.polygons["u"].clone());
    asset.validate().unwrap();
    let mut editor = Editor::new(Scene::default()).unwrap();
    editor
        .apply(
            &[Command::SetMeshAsset {
                id: "shared".into(),
                asset: asset.clone(),
            }],
            Some(0),
        )
        .unwrap();
    editor
        .apply(
            &[Command::SetMeshVertices {
                id: "shared".into(),
                positions: BTreeMap::from([("v0".into(), [0., 0., 1.])]),
            }],
            Some(1),
        )
        .unwrap();
    assert_eq!(
        editor.scene().mesh_assets["shared"].polygons,
        asset.polygons
    );
    assert_eq!(
        editor.scene().mesh_assets["shared"]
            .uv_layout
            .as_ref()
            .unwrap()
            .layers,
        vec!["SeedUV", "OtherUV"]
    );
    editor.undo(Some(2)).unwrap();
    let copy: Scene =
        serde_json::from_str(&serde_json::to_string(editor.scene()).unwrap()).unwrap();
    assert_eq!(copy.mesh_assets["shared"], asset);
    assert_eq!(
        copy.mesh_assets["shared"].edges["loose"],
        ["loose_a", "loose_b"]
    );
    assert_eq!(copy.mesh_assets["shared"].vertices["coincident"], [0.; 3]);
    let query = InspectRequest {
        mesh_asset: Some("shared".into()),
        tessellate: true,
        ..Default::default()
    }
    .inspect(&copy)
    .unwrap();
    assert_eq!(
        query["tessellation"]["triangles"].as_array().unwrap().len(),
        18
    );
    assert!(
        InspectRequest {
            tessellate: true,
            ..Default::default()
        }
        .inspect(&copy)
        .is_err()
    );
}

#[test]
fn polygon_validation_rejects_broken_topology_corner_data_and_uv_layout() {
    let mut bad = Vec::new();
    let mut a = fixture();
    a.edges.remove("e0");
    bad.push(a);
    let mut a = fixture();
    a.edges
        .insert("duplicate".into(), ["v1".into(), "v0".into()]);
    bad.push(a);
    let mut a = fixture();
    a.edges.get_mut("e0").unwrap()[0] = "missing".into();
    bad.push(a);
    let mut a = fixture();
    a.polygons.get_mut("u").unwrap().vertices[1] = "v0".into();
    bad.push(a);
    let mut a = fixture();
    a.polygons
        .get_mut("u")
        .unwrap()
        .corner_normals
        .as_mut()
        .unwrap()
        .pop();
    bad.push(a);
    let mut a = fixture();
    a.polygons.get_mut("u").unwrap().normal = Some([2., 0., 0.]);
    bad.push(a);
    let mut a = fixture();
    a.polygons
        .get_mut("u")
        .unwrap()
        .uv_layers
        .get_mut("SeedUV")
        .unwrap()
        .pop();
    bad.push(a);
    let mut a = fixture();
    a.uv_layout.as_mut().unwrap().layers.push("SeedUV".into());
    bad.push(a);
    let mut a = fixture();
    a.uv_layout.as_mut().unwrap().active = Some("missing".into());
    bad.push(a);
    let mut a = fixture();
    a.uv_layout = None;
    bad.push(a);
    for asset in bad {
        assert!(asset.validate().is_err());
    }
    let json = serde_json::to_string(&fixture()).unwrap();
    for text in [
        json.replace("\"e0\":", "\"e0\":[\"v0\",\"v1\"],\"e0\":"),
        json.replace(
            "\"u\":",
            &format!(
                "\"u\":{},\"u\":",
                serde_json::to_string(&fixture().polygons["u"]).unwrap()
            ),
        ),
    ] {
        assert!(serde_json::from_str::<MeshAsset>(&text).is_err());
    }
}

#[cfg(feature = "preview")]
#[test]
fn preview_and_picking_share_concave_surface_and_preserve_corner_normals() {
    let mut scene = Scene::default();
    scene.mesh_assets.insert("u".into(), fixture());
    scene.entities.insert(
        "surface".into(),
        Entity {
            name: "U".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "u".into() },
                material: None,
            },
        },
    );
    let vertices = formora::preview::math::vertices(&scene).unwrap();
    assert_eq!(vertices.len(), 18);
    assert!(vertices.iter().all(|v| v.normal == [0., 0., 1.]));
    for [x, y] in [[0.5, 2.], [2.5, 2.], [1.5, 0.5]] {
        let hit = formora::preview::math::pick(&scene, glam::DVec3::new(x, y, 5.), -glam::DVec3::Z)
            .unwrap()
            .unwrap();
        assert!((hit.distance - 5.).abs() <= 1e-6);
    }
    assert!(
        formora::preview::math::pick(&scene, glam::DVec3::new(1.5, 2., 5.), -glam::DVec3::Z)
            .unwrap()
            .is_none()
    );
}

#[cfg(feature = "preview")]
#[test]
fn tessellation_maps_each_original_corner_normal_to_its_render_vertex() {
    let mut asset = fixture();
    let r = std::f64::consts::FRAC_1_SQRT_2;
    let normals = vec![
        [1., 0., 0.],
        [0., 1., 0.],
        [0., 0., 1.],
        [-1., 0., 0.],
        [0., -1., 0.],
        [0., 0., -1.],
        [r, r, 0.],
        [0., r, r],
    ];
    asset.polygons.get_mut("u").unwrap().corner_normals = Some(normals.clone());
    let triangles = asset.tessellate().unwrap().triangles;
    let mut scene = Scene::default();
    scene.mesh_assets.insert("u".into(), asset.clone());
    scene.entities.insert(
        "surface".into(),
        Entity {
            name: "U".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "u".into() },
                material: None,
            },
        },
    );
    let vertices = formora::preview::math::vertices(&scene).unwrap();
    for (triangle, rendered) in triangles.iter().zip(vertices.chunks_exact(3)) {
        for (corner, vertex) in triangle.corners.into_iter().zip(rendered) {
            assert_eq!(
                vertex.position,
                asset.vertices[&asset.polygons["u"].vertices[corner]].map(|n| n as f32)
            );
            for (actual, expected) in vertex.normal.into_iter().zip(normals[corner]) {
                assert!((actual as f64 - expected).abs() <= 1e-6);
            }
        }
    }
}
