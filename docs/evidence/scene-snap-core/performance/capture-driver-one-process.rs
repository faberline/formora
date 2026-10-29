//! Same frozen inputs, sample counts, limits and timers in one native process.
use formora::scene::{Command, Editor, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::json;
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
    let mut inputs = Vec::new();
    for class in ["A", "B", "C"] {
        let path = authored.join(format!("input-{class}.json"));
        let input = Scene::load(&path).unwrap();
        assert_eq!(input.revision, 0);
        assert_eq!(input.mesh_assets.len(), if class == "C" { 2 } else { 1 });
        assert_eq!(input.entities.len(), 2);
        assert_eq!(
            input.authoring_context.as_ref().unwrap().cursor_location,
            [0.375, -0.625, 0.875]
        );
        for mesh in input.mesh_assets.values() {
            assert_eq!(
                (mesh.vertices.len(), mesh.edges.len(), mesh.polygons.len()),
                (10201, 20200, 10000)
            );
            assert_eq!(
                mesh.editing.as_ref().unwrap().selected.vertices.len(),
                10201
            );
        }
        let context = input.object_context.as_ref().unwrap();
        assert_eq!(context.active.as_deref(), Some("target"));
        assert_eq!(context.origins_only, class == "A");
        assert_eq!(context.skip_children, class == "A");
        // Preserve the exact pre-authored file bytes for independent binding.
        std::fs::copy(&path, output.join(path.file_name().unwrap())).unwrap();
        inputs.push((class, input));
    }
    let forms = [
        (
            "selected-grid",
            json!({"kind":"selected_to_grid","spacing":0.75}),
        ),
        ("selected-active", json!({"kind":"selected_to_active"})),
        (
            "cursor-grid",
            json!({"kind":"cursor_to_grid","spacing":0.75}),
        ),
        ("cursor-selected", json!({"kind":"cursor_to_selected"})),
        ("cursor-active", json!({"kind":"cursor_to_active"})),
        ("cursor-origin", json!({"kind":"cursor_to_center"})),
        (
            "selected-cursor-false-false",
            json!({"kind":"selected_to_cursor","use_offset":false,"use_rotation":false}),
        ),
        (
            "selected-cursor-false-true",
            json!({"kind":"selected_to_cursor","use_offset":false,"use_rotation":true}),
        ),
        (
            "selected-cursor-true-false",
            json!({"kind":"selected_to_cursor","use_offset":true,"use_rotation":false}),
        ),
        (
            "selected-cursor-true-true",
            json!({"kind":"selected_to_cursor","use_offset":true,"use_rotation":true}),
        ),
    ];
    let origin = Instant::now();
    let mut groups = Vec::new();
    for (class, input) in &inputs {
        let (maximum_core_ms, maximum_pipeline_ms) = if *class == "C" {
            (500., 4000.)
        } else {
            (250., 2000.)
        };
        for (name, action) in &forms {
            let command: Command = serde_json::from_value(
                json!({"operation":"snap_scene","snap":{"action":action,"pivot":"median"}}),
            )
            .unwrap();
            let mut runs = Vec::new();
            for sample in 1..=3 {
                let mut editor = Editor::new(input.clone()).unwrap();
                let cs = origin.elapsed().as_nanos();
                let core = editor
                    .apply_with_outcomes(&[command.clone()], Some(0))
                    .unwrap();
                let ce = origin.elapsed().as_nanos();
                assert_eq!(core.scene_snaps.len(), 1);
                assert_eq!(
                    serde_json::to_value(core.scene_snaps[0].status).unwrap(),
                    "finished"
                );
                let path = output.join(format!("{class}-{name}-{sample}.json"));
                assert!(!path.exists());
                let mut session = Session::create(&path, input.clone()).unwrap();
                let ps = origin.elapsed().as_nanos();
                let result = session
                    .apply_with_result(ApplyRequest {
                        expected_revision: 0,
                        commands: vec![command.clone()],
                    })
                    .unwrap();
                let fresh = Scene::load(&path).unwrap();
                let pe = origin.elapsed().as_nanos();
                assert_eq!(fresh, *editor.scene());
                assert_eq!(fresh, *session.scene());
                assert_eq!(
                    serde_json::to_value(&core.scene_snaps).unwrap(),
                    serde_json::to_value(&result.scene_snaps).unwrap()
                );
                drop(session);
                std::fs::write(
                    output.join(format!("{class}-{name}-{sample}-receipt.json")),
                    serde_json::to_vec(&result).unwrap(),
                )
                .unwrap();
                let core_ms = (ce - cs) as f64 / 1e6;
                let pipeline_ms = (pe - ps) as f64 / 1e6;
                let record = json!({"class":class,"form":name,"sample":sample,"action":action,"core_start_ns":cs,"core_end_ns":ce,"pipeline_start_ns":ps,"pipeline_end_ns":pe,"core_ms":core_ms,"operation_save_reload_ms":pipeline_ms,"maximum_core_ms":maximum_core_ms,"maximum_pipeline_ms":maximum_pipeline_ms,"passed":core_ms<=maximum_core_ms&&pipeline_ms<=maximum_pipeline_ms,"fresh_reload_equal":true,"receipt_equal":true});
                println!("{record}");
                runs.push(record);
            }
            let passed = runs.len() == 3 && runs.iter().all(|r| r["passed"] == true);
            let file = format!("report-{class}-{name}.json");
            let report = json!({"passed":passed,"profile":"release","grid":[100,100],"vertices_per_mesh":10201,"edges_per_mesh":20200,"faces_per_mesh":10000,"class":class,"form":name,"samples":3,"runs":runs,"issue_acceptance":"unrun","milestone_acceptance":"unrun"});
            std::fs::write(
                output.join(&file),
                serde_json::to_vec_pretty(&report).unwrap(),
            )
            .unwrap();
            groups.push(json!({"class":class,"form":name,"file":file,"passed":passed}));
        }
    }
    let passed = groups.len() == 30 && groups.iter().all(|g| g["passed"] == true);
    let summary = json!({"passed":passed,"profile":"release","process_id":std::process::id(),"groups":groups,"samples":90,"timing_method":"single native process; unchanged per-operation and operation/save/reload intervals","product_acceptance":"unrun","milestone_acceptance":"unrun"});
    std::fs::write(
        output.join("timing-summary.json"),
        serde_json::to_vec_pretty(&summary).unwrap(),
    )
    .unwrap();
    if !passed {
        std::process::exit(1);
    }
}
