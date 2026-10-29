use formora::mesh::primitives::Primitive;
use formora::mesh::selection;
use formora::scene::*;
use formora::session::{ApplyRequest, Session, UndoRequest};
use serde_json::{Value, json};

fn command(value: Value) -> Command {
    serde_json::from_value(value).unwrap()
}
fn create(kind: &str) -> Command {
    command(json!({"operation":"create_mesh_object","creation":{
        "id":"object","asset":"mesh","name":"Editable object","primitive":{"kind":kind}}}))
}
fn append(prefix: &str, kind: &str) -> Command {
    command(json!({"operation":"append_mesh_primitive","creation":{
        "entity":"object","prefix":prefix,"primitive":{"kind":kind},"placement":{"location":[0,0,0]}}}))
}
fn context() -> Command {
    command(json!({"operation":"set_authoring_context","context":{
        "cursor_location":[4,-2,3],"cursor_rotation":[0.2,-0.4,0.6],"view_rotation":[0.35,-0.25,0.6]}}))
}

#[test]
fn legacy_json_remains_unchanged_and_context_is_queryable_and_undoable() {
    let empty = Scene::default();
    assert!(
        serde_json::to_value(&empty)
            .unwrap()
            .get("authoring_context")
            .is_none()
    );
    let mut editor = Editor::new(empty).unwrap();
    editor.apply(&[context()], Some(0)).unwrap();
    let snapshot = serde_json::to_vec(editor.scene()).unwrap();
    let restored: Scene = serde_json::from_slice(&snapshot).unwrap();
    assert_eq!(&restored, editor.scene());
    assert_eq!(
        restored.authoring_context.unwrap().cursor_location,
        [4., -2., 3.]
    );
    editor.undo(Some(1)).unwrap();
    assert!(editor.scene().authoring_context.is_none());
}

#[test]
fn receipts_are_ordered_real_components_and_created_objects_are_editable() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    let result = editor
        .apply_with_outcomes(
            &[context(), create("cube"), append("next", "plane")],
            Some(0),
        )
        .unwrap();
    assert_eq!(
        result
            .creation
            .iter()
            .map(|c| c.command_index)
            .collect::<Vec<_>>(),
        [1, 2]
    );
    let asset = editor.scene().mesh_assets["mesh"].clone();
    let topology = selection::topology(&asset).unwrap();
    let vertices: std::collections::BTreeSet<_> = result
        .creation
        .iter()
        .flat_map(|r| r.created.vertices.iter().cloned())
        .collect();
    assert_eq!(vertices, topology.vertices.into_iter().collect());
    for receipt in &result.creation {
        assert!(receipt.edit_ready);
        for edge in &receipt.created.edges {
            assert!(topology.edges.contains_key(edge));
        }
        for face in &receipt.created.faces {
            assert!(topology.faces.iter().any(|f| &f.face == face));
        }
    }
    assert_eq!(
        asset.editing.as_ref().unwrap().selected,
        result.creation[1].created
    );
    assert!(asset.recipe.as_ref().unwrap().edited);
    let vertex = result.creation[1].created.vertices.first().unwrap().clone();
    editor
        .apply(
            &[command(
                json!({"operation":"set_mesh_vertices","id":"mesh","positions":{vertex:[9,8,7]}}),
            )],
            Some(1),
        )
        .unwrap();
    editor.undo(Some(2)).unwrap();
    assert_eq!(editor.scene().mesh_assets["mesh"], asset);
}

#[test]
fn parent_world_frames_and_shared_assets_preserve_entity_ownership() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    editor.apply(&[create("cube")], Some(0)).unwrap();
    let mut scene = editor.scene().clone();
    let mut parent = scene.entities["object"].clone();
    parent.transform.translation = [10., -2., 4.];
    parent.transform.scale = [2., 3., 4.];
    scene.entities.insert("parent".into(), parent);
    let object = scene.entities.get_mut("object").unwrap();
    object.parent = Some("parent".into());
    object.transform.translation = [1., 2., 3.];
    let mut peer = object.clone();
    peer.parent = None;
    scene.entities.insert("peer".into(), peer);
    let entities = scene.entities.clone();
    let mut editor = Editor::new(scene).unwrap();
    editor.apply(&[append("added", "plane")], Some(1)).unwrap();
    assert_eq!(editor.scene().entities, entities);
    let mesh = &editor.scene().mesh_assets["mesh"];
    for (id, p) in mesh
        .vertices
        .iter()
        .filter(|(id, _)| id.starts_with("added_"))
    {
        let world = [2. * p[0] + 12., 3. * p[1] + 4., 4. * p[2] + 16.];
        assert!(world[2].abs() < 1e-6, "{id}: {world:?}");
        assert!(world[0].abs() <= 1.000001 && world[1].abs() <= 1.000001);
    }
    assert_eq!(mesh.vertices.len(), 12);
}

#[test]
fn existing_triangle_ids_uvs_materials_and_implicit_edges_survive_insertion() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    editor.apply(&[create("cube")], Some(0)).unwrap();
    let mut scene = editor.scene().clone();
    let legacy = serde_json::from_str(include_str!("fixtures/triangle-asset.json")).unwrap();
    scene.mesh_assets.insert("mesh".into(), legacy);
    // The fixture's material is authored through the public scene command.
    let mut scene_editor = Editor::new(Scene::default()).unwrap();
    scene_editor.apply(&[command(json!({"operation":"set_material","id":"paint","material":{"base_color":[0.4,0.6,0.8,1],"roughness":0.6,"metallic":0}}))],Some(0)).unwrap();
    scene.materials = scene_editor.scene().materials.clone();
    let mesh = scene.mesh_assets.get_mut("mesh").unwrap();
    for material in &mut mesh.material_slots {
        *material = Some("paint".into());
    }
    let before = mesh.clone();
    let edges = selection::topology(mesh).unwrap().edges;
    let mut editor = Editor::new(scene).unwrap();
    editor.apply(&[append("added", "torus")], Some(1)).unwrap();
    let after = &editor.scene().mesh_assets["mesh"];
    assert_eq!(after.triangles, before.triangles);
    assert_eq!(after.material_slots, before.material_slots);
    for (id, p) in before.vertices {
        assert_eq!(after.vertices[&id], p);
    }
    let topology = selection::topology(after).unwrap();
    for (id, pair) in edges {
        assert_eq!(topology.edges[&id], pair);
    }
}

#[test]
fn regenerate_keeps_the_creation_frame_after_context_changes_and_reload() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    let request = command(
        json!({"operation":"create_mesh_object","creation":{"id":"object","asset":"mesh","name":"Aligned","primitive":{"kind":"cylinder","vertices":7},"placement":{"align":"cursor"}}}),
    );
    editor.apply(&[context(), request], Some(0)).unwrap();
    let mut expected = editor.scene().mesh_assets["mesh"].clone();
    // Rebuild retains the frame and clears component state, as for legacy recipes.
    expected.editing = None;
    let scene: Scene =
        serde_json::from_slice(&serde_json::to_vec(editor.scene()).unwrap()).unwrap();
    let mut editor = Editor::new(scene).unwrap();
    editor
        .apply(
            &[
                command(json!({"operation":"set_authoring_context","context":null})),
                command(json!({"operation":"regenerate_mesh_primitive","id":"mesh"})),
            ],
            Some(1),
        )
        .unwrap();
    assert_eq!(editor.scene().mesh_assets["mesh"], expected);
    let primitive: Primitive =
        serde_json::from_value(json!({"kind":"cylinder","vertices":9})).unwrap();
    let frame = expected
        .recipe
        .as_ref()
        .unwrap()
        .creation_frame
        .as_ref()
        .unwrap();
    editor
        .apply(
            &[command(
                json!({"operation":"regenerate_mesh_primitive","id":"mesh","primitive":primitive}),
            )],
            Some(2),
        )
        .unwrap();
    assert_eq!(
        editor.scene().mesh_assets["mesh"],
        frame.generate(&primitive, 1_000_000).unwrap()
    );
}

#[test]
fn collisions_singular_targets_budgets_and_invalid_batches_leave_no_undo() {
    let mut editor = Editor::new(Scene::default()).unwrap();
    editor
        .apply(&[create("cube"), append("added", "plane")], Some(0))
        .unwrap();
    let baseline = editor.scene().clone();
    let failures = [
        vec![append("added", "plane")],
        vec![command(
            json!({"operation":"append_mesh_primitive","creation":{"entity":"object","prefix":"new","primitive":{"kind":"grid","x_subdivisions":100,"y_subdivisions":100},"max_components":100}}),
        )],
        vec![context(), create("cube")],
    ];
    for commands in failures {
        assert!(editor.apply_with_outcomes(&commands, Some(1)).is_err());
        assert_eq!(editor.scene(), &baseline);
    }
    let mut singular = baseline.clone();
    singular.entities.get_mut("object").unwrap().transform.scale[1] = 0.;
    let mut editor = Editor::new(singular.clone()).unwrap();
    assert!(
        editor
            .apply_with_outcomes(&[append("valid", "plane")], Some(1))
            .is_err()
    );
    assert_eq!(editor.scene(), &singular);
    assert!(editor.undo(Some(1)).is_err());
}

#[test]
fn creation_save_failure_has_no_receipt_memory_change_or_undo_entry() {
    let root = std::env::temp_dir().join(format!("formora-creation-save-{}", std::process::id()));
    std::fs::create_dir(&root).unwrap();
    let path = root.join("scene.json");
    let backup = root.join("backup.json");
    let mut session = Session::create(&path, Scene::default()).unwrap();
    let before = session.scene().clone();
    std::fs::rename(&path, &backup).unwrap();
    std::fs::create_dir(&path).unwrap();
    assert!(
        session
            .apply_with_result(ApplyRequest {
                expected_revision: 0,
                commands: vec![context(), create("cube")]
            })
            .is_err()
    );
    assert_eq!(session.scene(), &before);
    assert!(
        session
            .undo(UndoRequest {
                expected_revision: 0
            })
            .is_err()
    );
    std::fs::remove_dir(&path).unwrap();
    std::fs::rename(&backup, &path).unwrap();
    assert_eq!(Scene::load(&path).unwrap(), before);
    let result = session
        .apply_with_result(ApplyRequest {
            expected_revision: 0,
            commands: vec![create("cube")],
        })
        .unwrap();
    assert_eq!(result.creation.len(), 1);
    let expected = session.scene().clone();
    drop(session);
    let loaded = Session::open(&path).unwrap();
    assert_eq!(loaded.scene(), &expected);
    drop(loaded);
    std::fs::remove_dir_all(root).unwrap();
}

#[cfg(feature = "preview")]
#[test]
fn creation_markers_can_be_hidden_without_changing_selection_or_surface_picking() {
    use formora::preview::math;
    use glam::DVec3;
    let mut editor = Editor::new(Scene::default()).unwrap();
    editor
        .apply(&[create("cube"), append("offset", "plane")], Some(0))
        .unwrap();
    let mut scene = editor.scene().clone();
    let selected = scene.mesh_assets["mesh"]
        .editing
        .as_ref()
        .unwrap()
        .selected
        .clone();
    let hit = |scene: &Scene| {
        math::pick(scene, DVec3::new(0.2, 0.2, 5.), -DVec3::Z)
            .unwrap()
            .unwrap()
    };
    let before = hit(&scene);
    let visible = math::vertices(&scene).unwrap().len();
    scene
        .mesh_assets
        .get_mut("mesh")
        .unwrap()
        .editing
        .as_mut()
        .unwrap()
        .preview = false;
    assert!(math::vertices(&scene).unwrap().len() < visible);
    let after = hit(&scene);
    assert_eq!(before.entity, after.entity);
    assert_eq!(before.position, after.position);
    assert_eq!(before.distance, after.distance);
    assert_eq!(
        scene.mesh_assets["mesh"].editing.as_ref().unwrap().selected,
        selected
    );
    let stored = serde_json::to_vec(&scene).unwrap();
    let restored: Scene = serde_json::from_slice(&stored).unwrap();
    assert!(
        !restored.mesh_assets["mesh"]
            .editing
            .as_ref()
            .unwrap()
            .preview
    );
    assert_eq!(hit(&restored).position, after.position);
}
