//! Before-code merge workload and validation clocks. No discarded samples.
use formora::scene::{Command, Editor, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::{Value, json};
use std::{path::Path, time::Instant};

fn main() {
    assert!(!cfg!(debug_assertions));
    assert_eq!(std::env::consts::ARCH, "aarch64");
    assert_eq!(std::env::consts::OS, "macos");
    let args = std::env::args().collect::<Vec<_>>();
    assert_eq!(args.len(), 3);
    let authored = Path::new(&args[1]);
    let output = Path::new(&args[2]);
    std::fs::create_dir(output).unwrap();
    let input_path = authored.join("authored-grid.json");
    let input = Scene::load(&input_path).unwrap();
    let forms: Value =
        serde_json::from_slice(&std::fs::read(authored.join("authored-forms.json")).unwrap())
            .unwrap();
    assert_eq!(forms["total_samples"], 30);
    assert_eq!(forms["samples_per_form"], 3);
    assert_eq!(forms["maximum_core_ms"], 250);
    assert_eq!(forms["maximum_pipeline_ms"], 2000);
    assert_eq!(forms["forms"].as_array().unwrap().len(), 10);
    assert_eq!(input.revision, 0);
    assert_eq!(input.mesh_assets.len(), 1);
    assert_eq!(input.entities.len(), 3);
    let mesh = &input.mesh_assets["grid"];
    assert_eq!(
        (mesh.vertices.len(), mesh.edges.len(), mesh.polygons.len()),
        (10201, 20200, 10000)
    );
    assert_eq!(
        mesh.editing.as_ref().unwrap().selected.vertices.len(),
        10201
    );
    let raw = serde_json::to_value(mesh).unwrap();
    assert_eq!(raw["uv_layout"]["layers"], json!(["Detail", "Layout"]));
    assert_eq!(
        raw["integer_attributes"]["vertices"]["signed_label"]["v000000"],
        -24
    );
    assert_eq!(raw["vertex_weights"]["v000000"]["pin"], 0.);
    assert_eq!(raw["vertex_weights"]["v000001"]["pin"], 1.);
    assert_eq!(input.entities["target"].transform.translation, [0.; 3]);
    std::fs::copy(&input_path, output.join("authored-grid.json")).unwrap();
    std::fs::copy(
        authored.join("authored-forms.json"),
        output.join("authored-forms.json"),
    )
    .unwrap();
    let origin = Instant::now();
    let mut groups = Vec::new();
    let mut all_runs = Vec::new();
    for form in forms["forms"].as_array().unwrap() {
        let name = form["id"].as_str().unwrap();
        let method = form["method"].as_str().unwrap().to_lowercase();
        let command: Command = serde_json::from_value(json!({
            "operation":"merge_mesh", "merge":{
                "entity":"target", "method":method,
                "uvs":form["uvs"], "max_components":forms["max_components"]
            }
        }))
        .unwrap();
        let mut runs = Vec::new();
        for sample in 1..=3 {
            // Independent prepared editors. Full input validation remains
            // inside each clock in addition to constructor validation.
            let mut editor = Editor::new(input.clone()).unwrap();
            let cs = origin.elapsed().as_nanos();
            editor.scene().validate().unwrap();
            let core = editor
                .apply_with_outcomes(&[command.clone()], Some(0))
                .unwrap();
            editor.scene().validate().unwrap();
            let ce = origin.elapsed().as_nanos();
            let core_json = serde_json::to_value(&core).unwrap();
            assert_eq!(core_json["merges"].as_array().unwrap().len(), 1);
            assert_eq!(core_json["merges"][0]["status"], "finished");
            let path = output.join(format!("{name}-{sample}.json"));
            assert!(!path.exists());
            let mut session = Session::create(&path, input.clone()).unwrap();
            let ps = origin.elapsed().as_nanos();
            session.scene().validate().unwrap();
            let result = session
                .apply_with_result(ApplyRequest {
                    expected_revision: 0,
                    commands: vec![command.clone()],
                })
                .unwrap();
            let fresh = Scene::load(&path).unwrap();
            fresh.validate().unwrap();
            let pe = origin.elapsed().as_nanos();
            assert_eq!(fresh, *editor.scene());
            assert_eq!(fresh, *session.scene());
            assert_eq!(fresh.mesh_assets["grid"].vertices.len(), 1);
            assert!(fresh.mesh_assets["grid"].edges.is_empty());
            assert!(fresh.mesh_assets["grid"].polygons.is_empty());
            let actual = serde_json::to_value(&result).unwrap();
            assert_eq!(core_json["merges"], actual["merges"]);
            drop(session);
            std::fs::write(
                output.join(format!("{name}-{sample}-receipt.json")),
                serde_json::to_vec(&result).unwrap(),
            )
            .unwrap();
            let core_ms = (ce - cs) as f64 / 1e6;
            let pipeline_ms = (pe - ps) as f64 / 1e6;
            let record = json!({
                "form":name,"sample":sample,"method":method,"uvs":form["uvs"],
                "core_start_ns":cs,"core_end_ns":ce,
                "pipeline_start_ns":ps,"pipeline_end_ns":pe,
                "core_ms":core_ms,"operation_save_reload_ms":pipeline_ms,
                "maximum_core_ms":250.,"maximum_pipeline_ms":2000.,
                "passed":core_ms<=250. && pipeline_ms<=2000.,
                "fresh_reload_equal":true,"receipt_equal":true,
                "full_input_and_result_validation_inside_clocks":true
            });
            println!("{record}");
            all_runs.push(record.clone());
            runs.push(record);
        }
        let passed = runs.len() == 3 && runs.iter().all(|r| r["passed"] == true);
        let file = format!("report-{name}.json");
        let report = json!({"passed":passed,"form":name,"samples":3,"runs":runs,
                            "product_acceptance":"unrun","milestone_acceptance":"unrun"});
        std::fs::write(
            output.join(&file),
            serde_json::to_vec_pretty(&report).unwrap(),
        )
        .unwrap();
        groups.push(json!({"form":name,"file":file,"passed":passed}));
    }
    let passed =
        all_runs.len() == 30 && groups.len() == 10 && groups.iter().all(|g| g["passed"] == true);
    let summary = json!({"passed":passed,"profile":"release","process_id":std::process::id(),
        "groups":groups,"runs":all_runs,"samples":30,
        "timing_method":"one process, all frozen forms; full input/result validation in both clocks",
        "product_acceptance":"unrun","milestone_acceptance":"unrun"});
    std::fs::write(
        output.join("timing-summary.json"),
        serde_json::to_vec_pretty(&summary).unwrap(),
    )
    .unwrap();
    if !passed {
        std::process::exit(1);
    }
}
