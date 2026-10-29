//! Fixed issue #44 samples. Run in release with the actual Rust 1.85 toolchain.
use formora::scene::{Command, Editor, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::json;
use std::time::Instant;
fn command(value: serde_json::Value) -> Command {
    serde_json::from_value(value).unwrap()
}
fn main() {
    assert!(
        !cfg!(debug_assertions),
        "performance acceptance requires release"
    );
    let root = std::env::temp_dir().join(format!(
        "formora-creation-context-bench-{}",
        std::process::id()
    ));
    std::fs::create_dir(&root).unwrap();
    let origin = Instant::now();
    let mut runs = vec![];
    for append in [false, true] {
        let sample = if append {
            "append_grid_100x100_to_cube"
        } else {
            "create_grid_100x100"
        };
        let mut initial = Editor::new(Scene::default()).unwrap();
        let mut setup = vec![command(
            json!({"operation":"set_authoring_context","context":{"cursor_location":[2,-1,3],"cursor_rotation":[0.2,-0.4,0.6],"view_rotation":[0.35,-0.25,0.6]}}),
        )];
        if append {
            setup.push(command(json!({"operation":"create_mesh_object","creation":{"id":"seed","asset":"seed-mesh","name":"Seed","primitive":{"kind":"cube"}}})));
        }
        initial.apply(&setup, Some(0)).unwrap();
        let operation = if append {
            json!({"operation":"append_mesh_primitive","creation":{"entity":"seed","prefix":"grid","primitive":{"kind":"grid","x_subdivisions":100,"y_subdivisions":100},"placement":{"align":"view"}}})
        } else {
            json!({"operation":"create_mesh_object","creation":{"id":"grid","asset":"grid-mesh","name":"Grid","primitive":{"kind":"grid","x_subdivisions":100,"y_subdivisions":100},"placement":{"align":"view"}}})
        };
        let operation = command(operation);
        for run in 1..=3 {
            let mut editor = Editor::new(initial.scene().clone()).unwrap();
            let core_start = origin.elapsed().as_nanos();
            let outcome = editor
                .apply_with_outcomes(std::slice::from_ref(&operation), Some(1))
                .unwrap();
            let core_end = origin.elapsed().as_nanos();
            let receipt = &outcome.creation[0];
            assert_eq!(receipt.created.vertices.len(), 10201);
            assert_eq!(receipt.created.faces.len(), 10000);
            let path = root.join(format!("{sample}-{run}.json"));
            let pipeline_start = origin.elapsed().as_nanos();
            let mut session = Session::create(&path, initial.scene().clone()).unwrap();
            let saved = session
                .apply_with_result(ApplyRequest {
                    expected_revision: 1,
                    commands: vec![operation.clone()],
                })
                .unwrap();
            let loaded = Scene::load(&path).unwrap();
            let pipeline_end = origin.elapsed().as_nanos();
            assert_eq!(&loaded, editor.scene());
            assert_eq!(&loaded, session.scene());
            assert_eq!(saved.creation[0].created, receipt.created);
            let core_ms = (core_end - core_start) as f64 / 1e6;
            let operation_save_reload_ms = (pipeline_end - pipeline_start) as f64 / 1e6;
            runs.push(json!({"sample":sample,"run":run,"core_start_ns":core_start,"core_end_ns":core_end,"pipeline_start_ns":pipeline_start,"pipeline_end_ns":pipeline_end,
                "core_ms":core_ms,"operation_save_reload_ms":operation_save_reload_ms,"created_vertices":receipt.created.vertices.len(),"created_edges":receipt.created.edges.len(),"created_faces":receipt.created.faces.len(),"reload_equal":true,"passed":core_ms<=500. && operation_save_reload_ms<=2000.}));
        }
    }
    std::fs::remove_dir_all(root).unwrap();
    let passed = runs.iter().all(|r| r["passed"] == true);
    println!(
        "{}",
        json!({"passed":passed,"limits_ms":{"core":500,"operation_save_reload":2000},"runs":runs,"full_feature_acceptance":"unrun"})
    );
    assert!(passed, "fixed creation context performance contract failed");
}
