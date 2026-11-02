#![cfg(feature = "preview")]
use formora::mesh::{MeshAsset, selection::*};
use formora::preview::math;
use formora::scene::*;
use glam::DVec3;
use std::collections::BTreeSet;

fn scene() -> Scene {
    let asset:MeshAsset=serde_json::from_value(serde_json::json!({"vertices":{"a":[0,0,0],"b":[1,0,0],"c":[0,1,0]},
        "triangles":{"face":{"vertices":["a","b","c"],"uv_layers":{},"corner_normals":null,"material_slot":null}},"material_slots":[]})).unwrap();
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
fn hit(scene: &Scene) -> Option<math::Hit> {
    math::pick(scene, DVec3::new(0.2, 0.2, 5.), -DVec3::Z).unwrap()
}

#[test]
fn markers_and_face_tint_do_not_change_authored_materials_or_surface_picking() {
    let original = scene();
    let expected = hit(&original).unwrap();
    assert_eq!(math::vertices(&original).unwrap().len(), 3);
    for domain in [Domain::Vertex, Domain::Edge, Domain::Face] {
        let mut scene = original.clone();
        let mesh = scene.mesh_assets.get_mut("mesh").unwrap();
        let mut editing = Editing {
            mode: [domain].into(),
            ..Default::default()
        };
        match domain {
            Domain::Vertex => {
                editing.selected.vertices.insert("a".into());
            }
            Domain::Edge => {
                editing
                    .selected
                    .edges
                    .insert(topology(mesh).unwrap().edges.keys().next().unwrap().clone());
            }
            Domain::Face => {
                editing
                    .selected
                    .faces
                    .insert(FaceRef::Triangle("face".into()));
            }
        }
        set_editing(mesh, Some(editing)).unwrap();
        let saved = serde_json::to_vec(&scene).unwrap();
        let rendered = math::vertices(&scene).unwrap();
        assert!(
            rendered
                .iter()
                .any(|v| v.color[0] == 1. && v.color[2] < 0.04)
        );
        assert_eq!(rendered.len(), if domain == Domain::Face { 3 } else { 9 });
        let actual = hit(&scene).unwrap();
        assert_eq!(actual.entity, expected.entity);
        assert_eq!(actual.position, expected.position);
        assert_eq!(actual.distance, expected.distance);
        assert!(
            math::pick(&scene, DVec3::new(-0.001, -0.001, 5.), -DVec3::Z)
                .unwrap()
                .is_none()
        );
        assert_eq!(serde_json::to_vec(&scene).unwrap(), saved);
        assert_eq!(scene.materials, original.materials);
        assert_eq!(
            scene.mesh_assets["mesh"].triangles,
            original.mesh_assets["mesh"].triangles
        );
    }
}

#[test]
fn hidden_components_remove_incident_surfaces_from_rendering_and_picking() {
    for kind in ["vertex", "edge", "face"] {
        let mut scene = scene();
        let mesh = scene.mesh_assets.get_mut("mesh").unwrap();
        let mut editing = Editing::default();
        match kind {
            "vertex" => {
                editing.hidden.vertices.insert("a".into());
            }
            "edge" => {
                editing
                    .hidden
                    .edges
                    .insert(topology(mesh).unwrap().edges.keys().next().unwrap().clone());
            }
            _ => {
                editing
                    .hidden
                    .faces
                    .insert(FaceRef::Triangle("face".into()));
            }
        }
        set_editing(mesh, Some(editing)).unwrap();
        assert!(math::vertices(&scene).unwrap().is_empty());
        assert!(hit(&scene).is_none());
    }
}

#[test]
fn hidden_crossing_polygon_does_not_prevent_other_surfaces_from_previewing() {
    let mut scene = scene();
    let mesh = scene.mesh_assets.get_mut("mesh").unwrap();
    mesh.vertices.insert("d".into(), [1., 1., 0.]);
    mesh.edges = topology(mesh).unwrap().edges;
    for (id, pair) in [("ad", ["a", "d"]), ("bd", ["b", "d"]), ("cd", ["c", "d"])] {
        mesh.edges.insert(id.into(), pair.map(String::from));
    }
    mesh.polygons.insert(
        "crossing".into(),
        formora::mesh::Polygon {
            corner_colors: None,
            vertices: ["a", "d", "b", "c"].map(String::from).to_vec(),
            uv_layers: Default::default(),
            corner_normals: None,
            normal: None,
            smooth: false,
            material_slot: None,
        },
    );
    mesh.validate().unwrap();
    assert!(mesh.tessellate().is_err());
    set_editing(
        mesh,
        Some(Editing {
            hidden: Elements {
                faces: BTreeSet::from([FaceRef::Polygon("crossing".into())]),
                ..Default::default()
            },
            ..Default::default()
        }),
    )
    .unwrap();
    assert!(mesh.tessellate().is_err());
    assert_eq!(math::vertices(&scene).unwrap().len(), 3);
    assert!(hit(&scene).is_some());
}
