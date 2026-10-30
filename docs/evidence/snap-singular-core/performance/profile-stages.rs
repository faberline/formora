//! Diagnostic only. These measurements cannot pass any required timing gate.
use formora::scene::{Command, Editor, Scene};
use formora::session::InspectRequest;
use serde_json::{Value, json};
use std::{path::Path, time::Instant};

fn worlds(scene: &Scene) -> Vec<Value> {
    scene
        .entities
        .keys()
        .map(|id| {
            InspectRequest {
                entity: Some(id.clone()),
                world: true,
                ..InspectRequest::default()
            }
            .inspect(scene)
            .unwrap()
        })
        .collect()
}

fn main() {
    assert!(!cfg!(debug_assertions));
    let args = std::env::args().collect::<Vec<_>>();
    assert_eq!(args.len(), 2);
    let input = Scene::load(Path::new(&args[1])).unwrap();
    let command: Command = serde_json::from_value(json!({"operation":"snap_scene","snap":{
        "action":{"kind":"cursor_to_center"},"pivot":"median"}}))
    .unwrap();
    for diagnostic_sample in 1..=3 {
        let start = Instant::now();
        let mut editor = Editor::new(input.clone()).unwrap();
        let ready = start.elapsed().as_nanos();
        editor.scene().validate().unwrap();
        let validated_before = start.elapsed().as_nanos();
        let before = worlds(editor.scene());
        let queried_before = start.elapsed().as_nanos();
        let receipt = editor
            .apply_with_outcomes(&[command.clone()], Some(0))
            .unwrap();
        let applied = start.elapsed().as_nanos();
        editor.scene().validate().unwrap();
        let validated_after = start.elapsed().as_nanos();
        let after = worlds(editor.scene());
        let queried_after = start.elapsed().as_nanos();
        assert_eq!(before.len(), 4);
        assert_eq!(after.len(), 4);
        assert_eq!(receipt.scene_snaps.len(), 1);
        println!(
            "{}",
            json!({"scope":"DIAGNOSTIC_ONLY_NOT_ACCEPTANCE","diagnostic_sample":diagnostic_sample,
            "editor_initialization_ms":ready as f64/1e6,
            "before_validation_ms":(validated_before-ready) as f64/1e6,
            "before_world_queries_ms":(queried_before-validated_before) as f64/1e6,
            "apply_ms":(applied-queried_before) as f64/1e6,
            "after_validation_ms":(validated_after-applied) as f64/1e6,
            "after_world_queries_ms":(queried_after-validated_after) as f64/1e6,
            "concurrent_functional_gates_running":true})
        );
    }
}
