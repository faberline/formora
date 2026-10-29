#![cfg(feature = "preview")]
use formora::preview::{Playback, math};
use formora::scene::*;
use glam::{DQuat, DVec3};

fn mesh(name: &str, translation: [f64; 3]) -> Entity {
    Entity {
        name: name.into(),
        parent: None,
        transform: Transform {
            translation,
            ..Transform::default()
        },
        content: EntityKind::Mesh {
            geometry: Geometry::Cube { size: [1.0; 3] },
            material: None,
        },
    }
}

#[test]
fn world_transform_and_picking_include_parent_rotation_and_scale() {
    let mut scene = Scene::default();
    scene.entities.insert(
        "parent".into(),
        Entity {
            name: "Parent".into(),
            parent: None,
            transform: Transform {
                translation: [10.0, 0.0, 0.0],
                rotation: DQuat::from_rotation_z(std::f64::consts::FRAC_PI_2)
                    .to_array()
                    .into(),
                scale: [2.0, 1.0, 1.0],
                ..Default::default()
            },
            content: EntityKind::Empty,
        },
    );
    let mut child = mesh("Child", [1.0, 0.0, 0.0]);
    child.parent = Some("parent".into());
    scene.entities.insert("child".into(), child);
    let matrices = math::world_transforms(&scene).unwrap();
    assert!(
        matrices["child"]
            .transform_point3(DVec3::ZERO)
            .abs_diff_eq(DVec3::new(10.0, 2.0, 0.0), 1e-10)
    );
    let hit = math::pick(&scene, DVec3::new(10.0, -5.0, 0.0), DVec3::Y)
        .unwrap()
        .unwrap();
    assert_eq!(hit.entity, "child");
    assert!((hit.distance - 6.0).abs() < 1e-10);
    assert!(hit.position.abs_diff_eq(DVec3::new(10.0, 1.0, 0.0), 1e-10));
}

#[test]
fn picking_selects_the_nearest_visible_mesh() {
    let mut scene = Scene::default();
    scene
        .entities
        .insert("far".into(), mesh("Far", [0.0, 0.0, 0.0]));
    scene
        .entities
        .insert("near".into(), mesh("Near", [0.0, 0.0, 2.0]));
    let hit = math::pick(&scene, DVec3::new(0.0, 0.0, 5.0), -DVec3::Z)
        .unwrap()
        .unwrap();
    assert_eq!(hit.entity, "near");
    assert_eq!(hit.distance, 2.5);
    assert!(
        math::pick(&scene, DVec3::new(5.0, 5.0, 5.0), -DVec3::Z)
            .unwrap()
            .is_none()
    );
}

#[test]
fn camera_center_ray_matches_authored_orientation_and_door_is_clickable() {
    let scene = room_demo().unwrap();
    let (origin, direction) = math::ray(&scene, 1280, 800, 640.0, 400.0).unwrap();
    assert!(origin.abs_diff_eq(DVec3::new(0.0, -8.0, 4.0), 1e-10));
    assert!(direction.abs_diff_eq(DVec3::new(0.0, 8.0, -2.5).normalize(), 1e-10));
    let camera = math::camera(&scene, 1280, 800).unwrap();
    let projected = camera
        .view_projection
        .project_point3(DVec3::new(0.0, -3.0, 1.2));
    let (origin, direction) = math::ray(
        &scene,
        1280,
        800,
        (projected.x + 1.0) * 640.0,
        (1.0 - projected.y) * 400.0,
    )
    .unwrap();
    let hit = math::pick(&scene, origin, direction).unwrap().unwrap();
    assert_eq!(hit.entity, "door_panel");
    assert_eq!(
        math::door_for_entity(&scene, &hit.entity).as_deref(),
        Some("front_door")
    );
}

#[test]
fn preview_rejects_geometry_that_cannot_be_represented_on_the_gpu() {
    let mut scene = Scene::default();
    scene
        .entities
        .insert("huge".into(), mesh("Huge", [f64::MAX, 0.0, 0.0]));
    assert!(math::vertices(&scene).is_err());
    assert!(math::ray(&scene, 0, 800, 0.0, 0.0).is_err());
}

#[test]
fn playback_does_not_change_authored_state_or_revision() {
    let authored = room_demo().unwrap();
    let mut playback = Playback::new(&authored);
    playback.toggle_door("front_door").unwrap();
    playback.advance(0.5).unwrap();
    assert_eq!(playback.scene.doors["front_door"].progress, 0.5);
    assert_eq!(playback.scene.revision, authored.revision);
    assert_eq!(authored.doors["front_door"].progress, 0.0);
    assert_eq!(authored.time_seconds, 0.0);
}

#[test]
fn agent_duration_edit_preserves_playback_pose_and_changes_remaining_speed() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    let mut playback = Playback::new(editor.scene());
    playback.toggle_door("front_door").unwrap();
    playback.advance(0.5).unwrap();
    let rotation = playback.scene.entities["door_hinge"].transform.rotation;
    editor
        .apply(
            &[Command::SetDoorDuration {
                id: "front_door".into(),
                duration_seconds: 2.0,
            }],
            None,
        )
        .unwrap();
    playback.sync(editor.scene()).unwrap();
    assert_eq!(playback.scene.doors["front_door"].progress, 0.5);
    assert_eq!(
        playback.scene.entities["door_hinge"].transform.rotation,
        rotation
    );
    playback.advance(0.5).unwrap();
    assert_eq!(playback.scene.doors["front_door"].progress, 0.75);
    assert_eq!(editor.scene().doors["front_door"].progress, 0.0);
}

#[test]
fn explicit_agent_playback_commands_override_preview_state() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    let mut playback = Playback::new(editor.scene());
    playback.toggle_door("front_door").unwrap();
    playback.advance(0.8).unwrap();
    editor
        .apply(
            &[
                Command::TriggerDoor {
                    id: "front_door".into(),
                    open: true,
                },
                Command::Advance { seconds: 0.25 },
            ],
            None,
        )
        .unwrap();
    playback.sync(editor.scene()).unwrap();
    assert_eq!(playback.scene.doors["front_door"].progress, 0.25);
}

#[test]
fn explicit_same_value_agent_trigger_closes_from_current_live_position() {
    let mut editor = Editor::new(room_demo().unwrap()).unwrap();
    let mut playback = Playback::new(editor.scene());
    playback.toggle_door("front_door").unwrap();
    playback.advance(1.0).unwrap();
    editor
        .apply(
            &[Command::TriggerDoor {
                id: "front_door".into(),
                open: false,
            }],
            None,
        )
        .unwrap();
    playback.sync(editor.scene()).unwrap();
    assert!(!playback.scene.doors["front_door"].target_open);
    assert_eq!(playback.scene.doors["front_door"].progress, 1.0);
    playback.advance(0.5).unwrap();
    assert_eq!(playback.scene.doors["front_door"].progress, 0.5);
}

#[test]
fn paused_playback_is_stable_and_room_generates_real_triangles() {
    let scene = room_demo().unwrap();
    let mut playback = Playback::new(&scene);
    playback.advance(10.0).unwrap();
    assert_eq!(playback.scene, scene);
    let vertices = math::vertices(&scene).unwrap();
    assert!(!vertices.is_empty());
    assert!(vertices.iter().all(|v| {
        v.position
            .iter()
            .chain(v.normal.iter())
            .all(|n| n.is_finite())
    }));
}

#[test]
fn shared_triangle_assets_render_pick_edit_materials_and_skip_zero_area() {
    let asset: formora::mesh::MeshAsset =
        serde_json::from_str(include_str!("fixtures/triangle-asset.json")).unwrap();
    let mut scene = Scene::default();
    scene.materials.insert(
        "red".into(),
        Material {
            base_color: [1., 0., 0., 1.],
            roughness: 0.5,
            metallic: 0.,
        },
    );
    scene.mesh_assets.insert("surface".into(), asset);
    let mut a = mesh("A", [0., 0., 1.]);
    a.content = EntityKind::Mesh {
        geometry: Geometry::Asset {
            id: "surface".into(),
        },
        material: None,
    };
    scene.entities.insert("a".into(), a.clone());
    a.transform.translation = [4., 0., 2.];
    a.transform.scale = [-2., 1., 1.];
    scene.entities.insert("b".into(), a);
    let vertices = math::vertices(&scene).unwrap();
    assert_eq!(vertices.len(), 12); // Two real triangles per instance. Coincident IDs stay stored.
    assert_eq!(vertices[0].color, [1., 0., 0., 1.]);
    assert_eq!(vertices[3].color, [0.65, 0.68, 0.72, 1.]);
    assert!(vertices.iter().all(|v| {
        v.position
            .iter()
            .chain(v.normal.iter())
            .all(|n| n.is_finite())
    }));
    let hit = math::pick(&scene, DVec3::new(1.5, 0.5, 10.), -DVec3::Z)
        .unwrap()
        .unwrap();
    assert_eq!(hit.entity, "b");
    assert!((hit.distance - 8.).abs() < 1e-6);
    assert!(
        math::pick(&scene, DVec3::new(10., 10., 10.), -DVec3::Z)
            .unwrap()
            .is_none()
    );
    let moved = scene
        .simulated(&[Command::SetMeshVertices {
            id: "surface".into(),
            positions: std::collections::BTreeMap::from([("b".into(), [2., 0., 0.5])]),
        }])
        .unwrap();
    let vertices = math::vertices(&moved).unwrap();
    assert!(vertices.iter().any(|v| v.position == [2., 0., 1.5]));
    assert!(vertices.iter().any(|v| v.position == [0., 0., 2.5]));
    assert_eq!(moved.mesh_assets["surface"].vertices.len(), 5);
    let mut collapsed = scene.clone();
    collapsed
        .entities
        .values_mut()
        .for_each(|e| e.transform.scale = [0.; 3]);
    assert!(math::vertices(&collapsed).unwrap().is_empty());
    assert!(
        math::pick(&collapsed, DVec3::new(0., 0., 10.), -DVec3::Z)
            .unwrap()
            .is_none()
    );
}
