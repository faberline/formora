//! Before-code aggregate merge clocks. Retain all thirty samples.
use formora::scene::{Command, Editor, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::{Value, json};
use std::{path::Path, time::Instant};

fn main() {
    assert!(!cfg!(debug_assertions));
    assert_eq!(std::env::consts::ARCH, "aarch64");
    assert_eq!(std::env::consts::OS, "macos");
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 3);
    let authored = Path::new(&args[1]);
    let output = Path::new(&args[2]);
    std::fs::create_dir(output).unwrap();
    let input = Scene::load(&authored.join("authored-grid.json")).unwrap();
    let forms: Value =
        serde_json::from_slice(&std::fs::read(authored.join("authored-forms.json")).unwrap())
            .unwrap();
    assert_eq!(forms["total_samples"], 30);
    assert_eq!(forms["samples_per_form"], 3);
    assert_eq!(forms["maximum_core_ms"], 500);
    assert_eq!(forms["maximum_pipeline_ms"], 4000);
    assert_eq!(forms["forms"].as_array().unwrap().len(), 10);
    assert_eq!(input.revision, 0);
    assert_eq!(input.mesh_assets.len(), 3);
    assert_eq!(input.entities.len(), 5);
    for name in ["mesh_a", "mesh_b"] {
        let mesh = &input.mesh_assets[name];
        assert_eq!(
            (mesh.vertices.len(), mesh.edges.len(), mesh.polygons.len()),
            (10201, 20200, 10000)
        );
        assert_eq!(
            mesh.editing.as_ref().unwrap().selected.vertices.len(),
            10201
        );
        let data = serde_json::to_value(mesh).unwrap();
        assert_eq!(data["uv_layout"]["layers"], json!(["Detail", "Layout"]));
        assert_eq!(
            data["integer_attributes"]["vertices"]["vertices_signed"]["v000000"],
            -128
        );
        assert_eq!(data["vertex_weights"]["v000000"]["pin"], 0.);
        assert_eq!(data["vertex_weights"]["v000001"]["pin"], 1.);
    }
    assert_eq!(
        input.object_context.as_ref().unwrap().active.as_deref(),
        Some("a")
    );
    assert_eq!(input.object_context.as_ref().unwrap().edit_objects.len(), 2);
    for name in ["authored-grid.json", "authored-forms.json"] {
        std::fs::copy(authored.join(name), output.join(name)).unwrap();
    }
    let origin = Instant::now();
    let mut records = Vec::new();
    for form in forms["forms"].as_array().unwrap() {
        let name = form["id"].as_str().unwrap();
        let method = form["method"].as_str().unwrap().to_lowercase();
        let command: Command = serde_json::from_value(json!({
            "operation":"merge_edit_meshes", "merge":{
                "method":method,"uvs":form["uvs"],"max_components":forms["max_components"]
            }
        }))
        .unwrap();
        for sample in 1..=3 {
            let mut editor = Editor::new(input.clone()).unwrap();
            let cs = origin.elapsed().as_nanos();
            editor.scene().validate().unwrap();
            let core = editor
                .apply_with_outcomes(&[command.clone()], Some(0))
                .unwrap();
            editor.scene().validate().unwrap();
            let ce = origin.elapsed().as_nanos();
            let core_json = json!({"edit_merges":&core.edit_merges,"merges":&core.merges});
            assert_eq!(core_json["edit_merges"].as_array().unwrap().len(), 1);
            assert_eq!(core_json["edit_merges"][0]["status"], "finished");
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
            assert_eq!(fresh.mesh_assets["mesh_a"].vertices.len(), 1);
            let first_last = method == "first" || method == "last";
            assert_eq!(
                fresh.mesh_assets["mesh_b"].vertices.len(),
                if first_last { 10201 } else { 1 }
            );
            if first_last {
                assert_eq!(fresh.mesh_assets["mesh_b"], input.mesh_assets["mesh_b"]);
            }
            assert_eq!(
                fresh.mesh_assets["mesh_outside"],
                input.mesh_assets["mesh_outside"]
            );
            assert_eq!(fresh.entities, input.entities);
            assert_eq!(fresh.object_context, input.object_context);
            assert_eq!(fresh.authoring_context, input.authoring_context);
            assert_eq!(fresh.materials, input.materials);
            let actual = serde_json::to_value(&result).unwrap();
            assert_eq!(core_json["edit_merges"], actual["edit_merges"]);
            assert_eq!(
                core_json["merges"],
                actual.get("merges").cloned().unwrap_or_else(|| json!([]))
            );
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
                "core_start_ns":cs,"core_end_ns":ce,"pipeline_start_ns":ps,"pipeline_end_ns":pe,
                "core_ms":core_ms,"operation_save_reload_ms":pipeline_ms,
                "maximum_core_ms":500.,"maximum_pipeline_ms":4000.,
                "passed":core_ms<=500. && pipeline_ms<=4000.,
                "fresh_reload_equal":true,"receipt_equal":true,
                "full_input_and_result_validation_inside_clocks":true
            });
            println!("{record}");
            records.push(record);
        }
    }
    let passed = records.len() == 30 && records.iter().all(|r| r["passed"] == true);
    let report = json!({"passed":passed,"profile":"release","process_id":std::process::id(),
        "samples":30,"groups":10,"runs":records,"product_acceptance":"unrun"});
    std::fs::write(
        output.join("timing-summary.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .unwrap();
    if !passed {
        std::process::exit(1);
    }
}
