//! Frozen native controls. Compile against the unrepaired release library first.
use formora::mesh::primitives::{DEFAULT_MAX_COMPONENTS, Primitive};
use formora::mesh::selection::{self, Domain, Editing};
use formora::scene::{Command, Editor, Entity, EntityKind, Geometry, Scene, Transform};
use serde_json::{Value, json};
use std::collections::BTreeSet;
fn command(v: Value) -> Command {
    serde_json::from_value(v).unwrap()
}
fn setup(kind: &str, mode: Domain, preview: bool, owner: Option<&str>) -> Editor {
    let primitive: Primitive = serde_json::from_value(json!({"kind":kind})).unwrap();
    let mut asset = primitive.generate(DEFAULT_MAX_COMPONENTS).unwrap();
    if owner.is_some() {
        let mut editing = Editing {
            mode: BTreeSet::from([mode]),
            preview,
            ..Editing::default()
        };
        editing.selected.vertices = asset.vertices.keys().cloned().collect();
        editing.selected.edges = asset.edges.keys().cloned().collect();
        editing.selected.faces = asset
            .polygons
            .keys()
            .map(|id| selection::FaceRef::Polygon(id.clone()))
            .collect();
        if let Some(id) = asset.vertices.keys().next() {
            editing
                .history
                .push(selection::Component::Vertex { id: id.clone() });
        }
        editing.active_face = asset
            .polygons
            .keys()
            .next()
            .map(|id| selection::FaceRef::Polygon(id.clone()));
        selection::set_editing(&mut asset, Some(editing)).unwrap();
    }
    let mut scene = Scene::default();
    scene.mesh_assets.insert("mesh".into(), asset);
    for id in ["a", "b"] {
        scene.entities.insert(
            id.into(),
            Entity {
                name: id.into(),
                parent: None,
                transform: Transform::default(),
                content: EntityKind::Mesh {
                    geometry: Geometry::Asset { id: "mesh".into() },
                    material: None,
                },
            },
        );
    }
    scene.object_context=Some(serde_json::from_value(json!({"order":["a","b"],"selected":[owner.unwrap_or("a")],"active":owner.unwrap_or("a"),"edit_objects":owner.into_iter().collect::<Vec<_>>()})).unwrap());
    Editor::new(scene).unwrap()
}
fn apply(editor: &mut Editor, commands: &[Command]) {
    let revision = editor.scene().revision;
    editor.apply(commands, Some(revision)).unwrap();
}
fn regenerate() -> Command {
    command(json!({"operation":"regenerate_mesh_primitive","id":"mesh"}))
}
fn expected(editor: &Editor, primitive: Primitive) -> formora::mesh::MeshAsset {
    let mut mesh = primitive.generate(DEFAULT_MAX_COMPONENTS).unwrap();
    if let Some(old) = editor.scene().mesh_assets["mesh"].editing.as_ref() {
        mesh.editing = Some(Editing {
            mode: old.mode.clone(),
            preview: old.preview,
            ..Editing::default()
        });
    }
    mesh
}
#[test]
fn same_recipe_after_merge_keeps_shared_edit_context_and_restores_fresh_data() {
    let mut editor = setup("cube", Domain::Vertex, false, Some("a"));
    let primitive = editor.scene().mesh_assets["mesh"]
        .recipe
        .as_ref()
        .unwrap()
        .primitive
        .clone();
    let fresh = expected(&editor, primitive);
    apply(
        &mut editor,
        &[command(
            json!({"operation":"merge_mesh","merge":{"entity":"a","method":"center","uvs":true}}),
        )],
    );
    assert_eq!(editor.scene().mesh_assets["mesh"].vertices.len(), 1);
    assert!(
        editor.scene().mesh_assets["mesh"]
            .recipe
            .as_ref()
            .unwrap()
            .edited
    );
    let merged = editor.scene().clone();
    apply(&mut editor, &[regenerate()]);
    assert_eq!(editor.scene().mesh_assets["mesh"], fresh);
    assert_eq!(editor.scene().entities, merged.entities);
    assert_eq!(editor.scene().object_context, merged.object_context);
    let revision = editor.scene().revision;
    editor.undo(Some(revision)).unwrap();
    assert_eq!(editor.scene().mesh_assets, merged.mesh_assets);
    apply(&mut editor, &[regenerate()]);
    assert_eq!(editor.scene().mesh_assets["mesh"], fresh);
    Editor::new(serde_json::from_slice(&serde_json::to_vec(editor.scene()).unwrap()).unwrap())
        .unwrap();
}
#[test]
fn changed_primitive_clears_old_component_state_and_keeps_face_mode_and_preview() {
    let mut editor = setup("cube", Domain::Face, false, Some("a"));
    let primitive: Primitive =
        serde_json::from_value(json!({"kind":"plane","size":3.125})).unwrap();
    let fresh = expected(&editor, primitive.clone());
    let old = editor.scene().clone();
    apply(
        &mut editor,
        &[command(
            json!({"operation":"regenerate_mesh_primitive","id":"mesh","primitive":primitive}),
        )],
    );
    assert_eq!(editor.scene().mesh_assets["mesh"], fresh);
    assert_eq!(editor.scene().entities, old.entities);
    assert_eq!(editor.scene().object_context, old.object_context);
}
#[test]
fn the_shared_secondary_user_can_be_the_only_edit_object() {
    let mut editor = setup("grid", Domain::Edge, true, Some("b"));
    let primitive = editor.scene().mesh_assets["mesh"]
        .recipe
        .as_ref()
        .unwrap()
        .primitive
        .clone();
    let fresh = expected(&editor, primitive);
    let context = editor.scene().object_context.clone();
    apply(&mut editor, &[regenerate()]);
    assert_eq!(editor.scene().mesh_assets["mesh"], fresh);
    assert_eq!(editor.scene().object_context, context);
}
#[test]
fn all_existing_generators_keep_the_three_modes_and_both_preview_settings() {
    for kind in [
        "plane",
        "cube",
        "grid",
        "circle",
        "uv_sphere",
        "ico_sphere",
        "cylinder",
        "cone",
        "torus",
        "monkey",
    ] {
        for mode in [Domain::Vertex, Domain::Edge, Domain::Face] {
            for preview in [false, true] {
                let mut editor = setup(kind, mode, preview, Some("a"));
                let primitive = editor.scene().mesh_assets["mesh"]
                    .recipe
                    .as_ref()
                    .unwrap()
                    .primitive
                    .clone();
                let fresh = expected(&editor, primitive);
                apply(&mut editor, &[regenerate()]);
                assert_eq!(
                    editor.scene().mesh_assets["mesh"],
                    fresh,
                    "{kind}/{mode:?}/{preview}"
                );
            }
        }
    }
}
#[test]
fn object_mode_keeps_the_exact_legacy_fresh_asset_without_editing() {
    let mut editor = setup("cube", Domain::Vertex, true, None);
    let old = editor.scene().clone();
    apply(&mut editor, &[regenerate()]);
    assert_eq!(editor.scene().mesh_assets, old.mesh_assets);
    assert!(editor.scene().mesh_assets["mesh"].editing.is_none());
}
#[test]
fn bad_budget_and_late_batch_preserve_scene_and_previous_undo() {
    let mut editor = setup("cube", Domain::Vertex, false, Some("a"));
    let initial = editor.scene().clone();
    apply(
        &mut editor,
        &[command(
            json!({"operation":"merge_mesh","merge":{"entity":"a","method":"center"}}),
        )],
    );
    let merged = editor.scene().clone();
    for commands in [
        vec![command(
            json!({"operation":"regenerate_mesh_primitive","id":"mesh","max_components":0}),
        )],
        vec![
            regenerate(),
            command(json!({"operation":"delete_entity","id":"missing"})),
        ],
    ] {
        let revision = editor.scene().revision;
        let error = editor.apply(&commands, Some(revision)).unwrap_err();
        if commands.len() == 2 {
            assert!(
                error.to_string().contains("unknown entity: missing"),
                "late command was not reached: {error}"
            );
        }
        assert_eq!(editor.scene(), &merged);
    }
    let revision = editor.scene().revision;
    editor.undo(Some(revision)).unwrap();
    assert_eq!(editor.scene().mesh_assets, initial.mesh_assets);
    assert_eq!(editor.scene().object_context, initial.object_context);
}
