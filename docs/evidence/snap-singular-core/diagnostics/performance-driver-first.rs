//! Sixty fixed samples. Full validation and real queries remain inside clocks.
use formora::scene::{Command, Editor, Scene};
use formora::session::{ApplyRequest, InspectRequest, Session};
use serde_json::{Value, json};
use std::{path::Path, time::Instant};

fn inspect(scene: &Scene) -> Value {
    scene.validate().unwrap();
    let mut worlds = serde_json::Map::new();
    for id in scene.entities.keys() {
        let value = InspectRequest {
            entity: Some(id.clone()),
            world: true,
            ..InspectRequest::default()
        }
        .inspect(scene)
        .unwrap();
        assert!(value["world_matrix"].is_array());
        assert!(value["object_frames"]["matrix_basis"].is_array());
        if value["object_frames"]["matrix_local"].is_null() {
            assert_eq!(
                value["object_frames"]["matrix_local_error"],
                "cannot_invert"
            );
        } else {
            assert!(value["object_frames"]["matrix_local"].is_array());
            assert!(value["object_frames"].get("matrix_local_error").is_none());
        }
        worlds.insert(id.clone(), value);
    }
    Value::Object(worlds)
}

fn main() {
    assert!(!cfg!(debug_assertions));
    assert_eq!(std::env::consts::ARCH, "aarch64");
    assert_eq!(std::env::consts::OS, "macos");
    let args = std::env::args().collect::<Vec<_>>();
    assert_eq!(args.len(), 3);
    let authored = Path::new(&args[1]);
    let output = Path::new(&args[2]);
    std::fs::create_dir(output).unwrap();
    let config: Value =
        serde_json::from_slice(&std::fs::read(authored.join("authored-forms.json")).unwrap())
            .unwrap();
    assert_eq!(config["samples"], 60);
    assert_eq!(config["samples_per_form"], 3);
    assert_eq!(config["maximum_core_ms"], 250);
    assert_eq!(config["maximum_pipeline_ms"], 2000);
    assert_eq!(config["frames"].as_array().unwrap().len(), 2);
    assert_eq!(config["forms"].as_array().unwrap().len(), 10);
    let origin = Instant::now();
    let mut runs = Vec::new();
    for frame in config["frames"].as_array().unwrap() {
        let frame_name = frame["id"].as_str().unwrap();
        let input = Scene::load(&authored.join(frame["scene"].as_str().unwrap())).unwrap();
        let mesh = &input.mesh_assets["grid"];
        assert_eq!(
            (mesh.vertices.len(), mesh.edges.len(), mesh.polygons.len()),
            (10201, 20200, 10000)
        );
        for form in config["forms"].as_array().unwrap() {
            let name = form["id"].as_str().unwrap();
            let command: Command = serde_json::from_value(form["command"].clone()).unwrap();
            for sample in 1..=3 {
                let mut editor = Editor::new(input.clone()).unwrap();
                let cs = origin.elapsed().as_nanos();
                let before_core = inspect(editor.scene());
                let core = editor
                    .apply_with_outcomes(&[command.clone()], Some(0))
                    .unwrap();
                let after_core = inspect(editor.scene());
                let ce = origin.elapsed().as_nanos();
                let stem = format!("{frame_name}-{name}-{sample}");
                let path = output.join(format!("{stem}.json"));
                let mut session = Session::create(&path, input.clone()).unwrap();
                let ps = origin.elapsed().as_nanos();
                let before_pipeline = inspect(session.scene());
                let result = session
                    .apply_with_result(ApplyRequest {
                        expected_revision: 0,
                        commands: vec![command.clone()],
                    })
                    .unwrap();
                let fresh = Scene::load(&path).unwrap();
                let after_pipeline = inspect(&fresh);
                let pe = origin.elapsed().as_nanos();
                assert_eq!(fresh, *editor.scene());
                assert_eq!(fresh, *session.scene());
                assert_eq!(before_core, before_pipeline);
                assert_eq!(after_core, after_pipeline);
                assert_eq!(
                    serde_json::to_value(core.scene_snaps).unwrap(),
                    serde_json::to_value(&result.scene_snaps).unwrap()
                );
                assert_eq!(result.scene_snaps.len(), 1);
                assert_eq!(
                    serde_json::to_value(result.scene_snaps[0].status).unwrap(),
                    "finished"
                );
                assert_eq!(fresh.revision, 1);
                drop(session);
                std::fs::write(
                    output.join(format!("{stem}-queries-receipt.json")),
                    serde_json::to_vec(
                        &json!({"before":before_pipeline,"after":after_pipeline,"receipt":result}),
                    )
                    .unwrap(),
                )
                .unwrap();
                let core_ms = (ce - cs) as f64 / 1e6;
                let pipeline_ms = (pe - ps) as f64 / 1e6;
                let row = json!({"frame":frame_name,"form":name,"sample":sample,
                    "file":path.file_name().unwrap().to_str().unwrap(),
                    "core_start_ns":cs,"core_end_ns":ce,"pipeline_start_ns":ps,"pipeline_end_ns":pe,
                    "core_ms":core_ms,"operation_save_reload_ms":pipeline_ms,
                    "maximum_core_ms":250.,"maximum_pipeline_ms":2000.,
                    "passed":core_ms<=250. && pipeline_ms<=2000.});
                println!("{row}");
                runs.push(row);
            }
        }
    }
    let passed = runs.len() == 60 && runs.iter().all(|r| r["passed"] == true);
    std::fs::write(
        output.join("timing-summary.json"),
        serde_json::to_vec_pretty(&json!({"passed":passed,"samples":60,"runs":runs,
            "source_comparisons":"unrun","product_acceptance":"unrun"}))
        .unwrap(),
    )
    .unwrap();
    if !passed {
        std::process::exit(1);
    }
}
