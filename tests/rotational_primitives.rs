use formora::mesh::primitives::{DEFAULT_MAX_COMPONENTS, Primitive};
use formora::scene::{Command, Editor, Scene};
use serde_json::{Value, json};

fn spec(value: Value) -> Primitive {
    serde_json::from_value(value).unwrap()
}

#[test]
fn rotational_shapes_generate_real_polygons_and_persist_recipes() {
    for (kind, counts, triangles) in [
        ("uv_sphere", (482, 992, 512), 960),
        ("cylinder", (64, 96, 34), 124),
        ("cone", (33, 64, 33), 62),
        ("torus", (576, 1152, 576), 1152),
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
        assert_eq!(asset.tessellate().unwrap().triangles.len(), triangles);
        assert_eq!(asset.recipe.as_ref().unwrap().primitive, primitive);
        assert_eq!(asset, primitive.generate(DEFAULT_MAX_COMPONENTS).unwrap());
        assert_eq!(
            asset,
            serde_json::from_value(serde_json::to_value(&asset).unwrap()).unwrap()
        );
        for polygon in asset.polygons.values() {
            assert!(!polygon.smooth);
            assert_eq!(polygon.uv_layers["UVMap"].len(), polygon.vertices.len());
            assert_eq!(
                polygon.corner_normals.as_ref().unwrap().len(),
                polygon.vertices.len()
            );
            assert!(polygon.normal.unwrap().iter().all(|n| n.is_finite()));
        }
        let flag = if kind == "torus" {
            "generate_uvs"
        } else {
            "calc_uvs"
        };
        let mut request = json!({"kind":kind});
        request[flag] = json!(false);
        let without_uv = spec(request).generate(DEFAULT_MAX_COMPONENTS).unwrap();
        assert!(without_uv.polygons.values().all(|p| p.uv_layers.is_empty()));
        assert_eq!(without_uv.vertices, asset.vertices);
    }
}

#[test]
fn conic_fill_modes_apices_and_resource_estimates_agree() {
    for fill in ["nothing", "ngon", "trifan"] {
        for (bottom, top) in [(1., 1.), (1., 0.), (0., 1.), (0., 0.)] {
            let primitive = spec(
                json!({"kind":"cone","radius1":bottom,"radius2":top,"vertices":7,"end_fill_type":fill}),
            );
            let asset = primitive.generate(DEFAULT_MAX_COMPONENTS).unwrap();
            let components = asset.vertices.len()
                + asset.edges.len()
                + asset.polygons.len()
                + asset
                    .polygons
                    .values()
                    .map(|p| p.vertices.len())
                    .sum::<usize>();
            assert_eq!(primitive.component_count().unwrap(), components);
            assert!(primitive.generate(components - 1).is_err());
            assert!(primitive.generate(components).is_ok());
            if bottom == 0. && top == 0. {
                assert_eq!(
                    (
                        asset.vertices.len(),
                        asset.edges.len(),
                        asset.polygons.len()
                    ),
                    (2, 1, 0)
                );
            }
        }
    }
    for (kind, field) in [("uv_sphere", "radius"), ("cylinder", "radius")] {
        let asset = spec(json!({"kind":kind,field:0}))
            .generate(DEFAULT_MAX_COMPONENTS)
            .unwrap();
        assert_eq!(
            asset.vertices.len(),
            if kind == "uv_sphere" { 1 } else { 2 }
        );
        assert!(asset.polygons.is_empty());
    }
}

#[test]
fn torus_preserves_coincident_ids_and_converts_external_internal_radii() {
    let zero = spec(json!({"kind":"torus","major_segments":6,"minor_segments":4,"major_radius":0,"minor_radius":0})).generate(DEFAULT_MAX_COMPONENTS).unwrap();
    assert_eq!(
        (zero.vertices.len(), zero.edges.len(), zero.polygons.len()),
        (24, 48, 24)
    );
    assert!(zero.vertices.values().all(|v| *v == [0.; 3]));
    assert!(zero.tessellate().unwrap().triangles.is_empty());
    let external =
        spec(json!({"kind":"torus","mode":"ext_int","abso_major_rad":2,"abso_minor_rad":1}))
            .generate(DEFAULT_MAX_COMPONENTS)
            .unwrap();
    let direct = spec(json!({"kind":"torus","major_radius":1.5,"minor_radius":0.5}))
        .generate(DEFAULT_MAX_COMPONENTS)
        .unwrap();
    assert_eq!(external.vertices, direct.vertices);
    assert_eq!(external.polygons, direct.polygons);
    let inverted =
        spec(json!({"kind":"torus","mode":"ext_int","abso_major_rad":1,"abso_minor_rad":2}))
            .generate(DEFAULT_MAX_COMPONENTS)
            .unwrap();
    assert_eq!(inverted.vertices["v000000"], [1.5, 0., 0.]);
}

#[test]
fn invalid_rotational_parameters_and_budgets_fail_without_partial_changes() {
    for value in [
        json!({"kind":"uv_sphere","segments":2}),
        json!({"kind":"uv_sphere","ring_count":100001}),
        json!({"kind":"uv_sphere","radius":-1}),
        json!({"kind":"cylinder","vertices":10000001}),
        json!({"kind":"cone","depth":-1}),
        json!({"kind":"cone","radius2":-1}),
        json!({"kind":"uv_sphere","creation_rotation":[1e300,0,0]}),
        json!({"kind":"torus","minor_segments":257}),
        json!({"kind":"torus","major_radius":10001}),
    ] {
        assert!(spec(value).generate(DEFAULT_MAX_COMPONENTS).is_err());
    }
    for value in [
        json!({"kind":"uv_sphere","segments":100000,"ring_count":100000}),
        json!({"kind":"cylinder","vertices":10000000}),
        json!({"kind":"cone","vertices":10000000}),
        json!({"kind":"torus","major_segments":256,"minor_segments":256}),
    ] {
        let mut editor = Editor::new(Scene::default()).unwrap();
        let before = editor.scene().clone();
        assert!(
            editor
                .apply(
                    &[Command::CreateMeshPrimitive {
                        id: "huge".into(),
                        primitive: spec(value),
                        max_components: 100,
                    }],
                    Some(0)
                )
                .is_err()
        );
        assert_eq!(editor.scene(), &before);
    }
}

#[test]
fn each_rotational_shape_rebuilds_saves_reloads_and_undoes() {
    for kind in ["uv_sphere", "cylinder", "cone", "torus"] {
        let initial = if kind == "torus" {
            spec(json!({"kind":kind}))
        } else {
            spec(json!({"kind":kind,"scale":[1.5,0.75,2.0],"creation_rotation":[0.25,-0.5,1.0]}))
        };
        let mut editor = Editor::new(Scene::default()).unwrap();
        editor
            .apply(
                &[Command::CreateMeshPrimitive {
                    id: "shape".into(),
                    primitive: initial,
                    max_components: DEFAULT_MAX_COMPONENTS,
                }],
                Some(0),
            )
            .unwrap();
        let original = editor.scene().mesh_assets["shape"].clone();
        let changed = if kind == "torus" {
            json!({"kind":kind,"minor_radius":0.6})
        } else if kind == "cone" {
            json!({"kind":kind,"radius1":2.5})
        } else {
            json!({"kind":kind,"radius":2.5})
        };
        editor
            .apply(
                &[Command::RegenerateMeshPrimitive {
                    id: "shape".into(),
                    primitive: Some(spec(changed)),
                    max_components: None,
                }],
                Some(1),
            )
            .unwrap();
        assert_ne!(
            editor.scene().mesh_assets["shape"].vertices,
            original.vertices
        );
        let rebuilt = editor.scene().clone();
        assert!(
            editor
                .apply(
                    &[Command::RegenerateMeshPrimitive {
                        id: "shape".into(),
                        primitive: None,
                        max_components: Some(0)
                    }],
                    Some(2)
                )
                .is_err()
        );
        assert_eq!(editor.scene(), &rebuilt);
        let path = std::env::temp_dir().join(format!(
            "formora-rotational-{}-{kind}.json",
            std::process::id()
        ));
        editor.scene().save(&path).unwrap();
        assert_eq!(Scene::load(&path).unwrap(), rebuilt);
        std::fs::remove_file(path).unwrap();
        editor.undo(Some(2)).unwrap();
        assert_eq!(editor.scene().mesh_assets["shape"], original);
    }
}
