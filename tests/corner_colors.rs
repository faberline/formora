use formora::mesh::{MeshAsset, Polygon, Triangle};
use formora::scene::{Entity, EntityKind, Geometry, Material, Scene, Transform};
use std::collections::BTreeMap;

const COLORS: [[f64; 4]; 3] = [
    [0.25, 0.5, 0.75, 1.0],
    [0.125, 0.75, 0.375, 1.0],
    [0.0, 0.0, 1.0, 1.0],
];

fn scene() -> Scene {
    let mut scene = Scene::default();
    scene.mesh_assets.insert(
        "mesh".into(),
        MeshAsset {
            vertices: BTreeMap::from([
                ("a".into(), [-1., -1., 0.]),
                ("b".into(), [1., -1., 0.]),
                ("c".into(), [0., 1., 0.]),
            ]),
            triangles: BTreeMap::from([(
                "face".into(),
                Triangle {
                    vertices: ["a", "b", "c"].map(str::to_owned),
                    uv_layers: BTreeMap::new(),
                    corner_normals: Some([[0., 0., 1.]; 3]),
                    corner_colors: Some(COLORS),
                    material_slot: None,
                },
            )]),
            ..Default::default()
        },
    );
    scene.materials.insert(
        "paint".into(),
        Material {
            base_color: [0.9, 0.8, 0.7, 0.5],
            roughness: 0.25,
            metallic: 0.5,
        },
    );
    scene.entities.insert(
        "object".into(),
        Entity {
            name: "Object".into(),
            parent: None,
            transform: Transform::default(),
            content: EntityKind::Mesh {
                geometry: Geometry::Asset { id: "mesh".into() },
                material: Some("paint".into()),
            },
        },
    );
    scene
}

fn polygon_scene() -> Scene {
    let mut scene = scene();
    let asset = scene.mesh_assets.get_mut("mesh").unwrap();
    asset.triangles.clear();
    asset.vertices.insert("d".into(), [-1., 1., 0.]);
    asset.edges = BTreeMap::from([
        ("ab".into(), ["a".into(), "b".into()]),
        ("bc".into(), ["b".into(), "c".into()]),
        ("cd".into(), ["c".into(), "d".into()]),
        ("da".into(), ["d".into(), "a".into()]),
    ]);
    asset.polygons.insert(
        "face".into(),
        Polygon {
            vertices: ["a", "b", "c", "d"].map(str::to_owned).to_vec(),
            uv_layers: BTreeMap::new(),
            corner_normals: None,
            normal: None,
            smooth: false,
            corner_colors: Some(vec![COLORS[0], COLORS[1], COLORS[2], [1., 0., 0., 0.5]]),
            material_slot: None,
        },
    );
    scene
}

#[test]
fn native_json_round_trip_and_omitted_legacy_color() {
    for mut scene in [scene(), polygon_scene()] {
        scene.validate().unwrap();
        let value = serde_json::to_value(&scene).unwrap();
        let round: Scene = serde_json::from_value(value.clone()).unwrap();
        assert_eq!(scene, round);
        for face in scene
            .mesh_assets
            .get_mut("mesh")
            .unwrap()
            .triangles
            .values_mut()
        {
            face.corner_colors = None;
        }
        for face in scene
            .mesh_assets
            .get_mut("mesh")
            .unwrap()
            .polygons
            .values_mut()
        {
            face.corner_colors = None;
        }
        let legacy = serde_json::to_string(&scene).unwrap();
        assert!(!legacy.contains("corner_colors"));
        let round: Scene = serde_json::from_str(&legacy).unwrap();
        assert_eq!(legacy, serde_json::to_string(&round).unwrap());
    }
    let mut value = serde_json::to_value(scene()).unwrap();
    value["mesh_assets"]["mesh"]["triangles"]["face"]["corner_colors"] = serde_json::Value::Null;
    let parsed: Scene = serde_json::from_value(value).unwrap();
    assert!(
        parsed.mesh_assets["mesh"].triangles["face"]
            .corner_colors
            .is_none()
    );
}

#[test]
fn invalid_color_values_and_corner_counts_are_rejected() {
    for value in [-0.001, 1.001, f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        let mut scene = scene();
        scene
            .mesh_assets
            .get_mut("mesh")
            .unwrap()
            .triangles
            .get_mut("face")
            .unwrap()
            .corner_colors
            .as_mut()
            .unwrap()[1][2] = value;
        assert!(scene.validate().is_err());
        let mut polygon = polygon_scene();
        polygon
            .mesh_assets
            .get_mut("mesh")
            .unwrap()
            .polygons
            .get_mut("face")
            .unwrap()
            .corner_colors
            .as_mut()
            .unwrap()[3][3] = value;
        assert!(polygon.validate().is_err());
    }
    let mut value = serde_json::to_value(scene()).unwrap();
    value["mesh_assets"]["mesh"]["triangles"]["face"]["corner_colors"] =
        serde_json::json!([[1, 0, 0, 1]]);
    assert!(serde_json::from_value::<Scene>(value).is_err());
    let mut polygon = polygon_scene();
    polygon
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .polygons
        .get_mut("face")
        .unwrap()
        .corner_colors
        .as_mut()
        .unwrap()
        .pop();
    assert!(polygon.validate().is_err());
}

#[test]
fn usd_projection_rejects_color_instead_of_silently_losing_it() {
    for scene in [scene(), polygon_scene()] {
        let error = formora::usd::project(&scene, "object").unwrap_err();
        assert!(error.to_string().contains("corner colors"), "{error}");
    }
}

#[test]
fn weld_keeps_surviving_corner_colors_without_averaging() {
    let mut scene = polygon_scene();
    let asset = scene.mesh_assets.get_mut("mesh").unwrap();
    asset.uv_layout = Some(formora::mesh::UvLayout {
        layers: vec!["uv".into()],
        active: Some("uv".into()),
    });
    asset
        .polygons
        .get_mut("face")
        .unwrap()
        .uv_layers
        .insert("uv".into(), vec![[0., 0.], [1., 0.], [1., 1.], [0., 1.]]);
    scene.mesh_assets.get_mut("mesh").unwrap().editing = Some(
        serde_json::from_value(serde_json::json!({
            "mode":["vertex"], "selected":{"vertices":["a","b"],"edges":[],"faces":[]},
            "hidden":{"vertices":[],"edges":[],"faces":[]},"history":[],"active_face":null
        }))
        .unwrap(),
    );
    let mut editor = formora::scene::Editor::new(scene).unwrap();
    let command = serde_json::from_value(serde_json::json!({"operation":"merge_mesh","merge":{
        "entity":"object","method":"center","uvs":false,"max_components":1000
    }}))
    .unwrap();
    editor.apply(&[command], Some(0)).unwrap();
    let asset = &editor.scene().mesh_assets["mesh"];
    let face = &asset.polygons["face"];
    assert_eq!(face.vertices, ["a", "c", "d"]);
    assert_eq!(
        face.corner_colors.as_ref().unwrap(),
        &vec![COLORS[1], COLORS[2], [1., 0., 0., 0.5]]
    );
    assert_eq!(face.uv_layers["uv"], vec![[1., 0.], [1., 1.], [0., 1.]]);
}

#[cfg(feature = "headless")]
mod cpu {
    use super::*;
    use formora::geometry::{self, GeometryCache, Vertex};
    use std::sync::Arc;

    fn check(scene: &Scene, cache: &mut GeometryCache) -> Arc<Vec<Vertex>> {
        let before = serde_json::to_vec(scene).unwrap();
        let direct = geometry::vertices(scene).unwrap();
        let cached = cache.vertices(scene).unwrap();
        assert_eq!(
            bytemuck::cast_slice::<Vertex, u8>(&direct),
            bytemuck::cast_slice::<Vertex, u8>(cached.as_slice())
        );
        assert_eq!(before, serde_json::to_vec(scene).unwrap());
        cached
    }

    #[test]
    fn independent_corner_values_replace_color_and_keep_material_surface() {
        let mut scene = scene();
        let mut cache = GeometryCache::default();
        let vertices = check(&scene, &mut cache);
        assert_eq!(vertices.len(), 3);
        for (i, vertex) in vertices.iter().enumerate() {
            assert_eq!(
                vertex.color.map(f32::to_bits),
                COLORS[i].map(|c| (c as f32).to_bits())
            );
            assert_eq!(vertex.surface, [0.25, 0.5]);
        }
        scene
            .mesh_assets
            .get_mut("mesh")
            .unwrap()
            .triangles
            .get_mut("face")
            .unwrap()
            .corner_colors = None;
        let legacy = check(&scene, &mut cache);
        assert!(legacy.iter().all(|v| v.color == [0.9, 0.8, 0.7, 0.5]));
    }

    #[test]
    fn polygon_tessellation_preserves_original_corner_mapping() {
        let scene = polygon_scene();
        let mut cache = GeometryCache::default();
        let vertices = check(&scene, &mut cache);
        let asset = &scene.mesh_assets["mesh"];
        let face = &asset.polygons["face"];
        assert_eq!(vertices.len(), 6);
        for vertex in vertices.iter() {
            let index = face
                .vertices
                .iter()
                .position(|id| asset.vertices[id].map(|v| v as f32) == vertex.position)
                .unwrap();
            assert_eq!(
                vertex.color,
                face.corner_colors.as_ref().unwrap()[index].map(|c| c as f32)
            );
        }
    }

    #[test]
    fn edit_selection_highlight_still_overrides_authored_colors() {
        let mut scene = scene();
        scene.mesh_assets.get_mut("mesh").unwrap().editing = Some(serde_json::from_value(serde_json::json!({
            "mode":["face"],"selected":{"vertices":[],"edges":[],"faces":[{"kind":"triangle","id":"face"}]},
            "hidden":{"vertices":[],"edges":[],"faces":[]},"history":[],"active_face":null,"preview":true
        })).unwrap());
        let data = check(&scene, &mut GeometryCache::default());
        assert_eq!(data.len(), 3);
        assert!(data.iter().all(|v| v.color == [1.0, 0.55, 0.03, 1.0]));
    }

    #[test]
    fn same_revision_color_and_signed_zero_invalidate_cache_and_diagnostic_hash() {
        for mut scene in [scene(), polygon_scene()] {
            let mut cache = GeometryCache::default();
            let first = check(&scene, &mut cache);
            assert!(Arc::ptr_eq(&first, &check(&scene, &mut cache)));
            let request = formora::headless::DebugRequest {
                geometry: true,
                ..Default::default()
            };
            let before = formora::headless::diagnose(&scene, &request);
            let asset = scene.mesh_assets.get_mut("mesh").unwrap();
            let colors = if let Some(face) = asset.triangles.get_mut("face") {
                face.corner_colors.as_mut().unwrap().as_mut_slice()
            } else {
                asset
                    .polygons
                    .get_mut("face")
                    .unwrap()
                    .corner_colors
                    .as_mut()
                    .unwrap()
                    .as_mut_slice()
            };
            colors[0][0] = 0.5;
            colors[2][0] = -0.0;
            let after = check(&scene, &mut cache);
            assert!(!Arc::ptr_eq(&first, &after));
            let changed = formora::headless::diagnose(&scene, &request);
            assert_eq!(before["world_sha256"], changed["world_sha256"]);
            assert_ne!(before["geometry"]["sha256"], changed["geometry"]["sha256"]);
            assert_eq!(
                changed["geometry"],
                formora::headless::diagnose(&scene, &request)["geometry"]
            );
            // A bit-only color change also invalidates; derived PartialEq considers +/-0 equal.
            let old_asset = scene.mesh_assets["mesh"].clone();
            let asset = scene.mesh_assets.get_mut("mesh").unwrap();
            if let Some(face) = asset.triangles.get_mut("face") {
                face.corner_colors.as_mut().unwrap()[2][0] = 0.0;
            } else {
                asset
                    .polygons
                    .get_mut("face")
                    .unwrap()
                    .corner_colors
                    .as_mut()
                    .unwrap()[2][0] = 0.0;
            }
            assert_eq!(old_asset, scene.mesh_assets["mesh"]);
            assert!(!Arc::ptr_eq(&after, &check(&scene, &mut cache)));
            assert_eq!(scene.revision, 0);
        }
    }
}
