//! Fixed 10 forms x 3 samples. No source result enters the authored input.
use formora::mesh::{creation::AuthoringContext, selection::Component};
use formora::scene::{Command,Editor,Scene};
use formora::session::{ApplyRequest,Session};
use serde_json::json;
use std::{path::Path,time::Instant};

fn main() {
    assert!(!cfg!(debug_assertions));assert_eq!(std::env::consts::ARCH,"aarch64");assert_eq!(std::env::consts::OS,"macos");
    let args=std::env::args().collect::<Vec<_>>();assert_eq!(args.len(),3);
    let mut input=Scene::load(Path::new(&args[1])).unwrap();let output=Path::new(&args[2]);std::fs::create_dir(output).unwrap();
    assert_eq!(input.revision,0);assert_eq!(input.entities.len(),1);assert_eq!(input.mesh_assets.len(),1);
    let mesh=input.mesh_assets.get_mut("grid").unwrap();assert_eq!((mesh.vertices.len(),mesh.edges.len(),mesh.polygons.len()),(10201,20200,10000));
    let editing=mesh.editing.as_mut().unwrap();assert_eq!(editing.selected.vertices.len(),10201);
    editing.history=vec![Component::Vertex {id:mesh.vertices.keys().next_back().unwrap().clone()}];
    input.authoring_context=Some(AuthoringContext {cursor_location:[0.375,-0.625,0.875],..Default::default()});input.validate().unwrap();
    input.save(&output.join("input.json")).unwrap();
    let mut forms=vec![("selected-grid".to_string(),json!({"kind":"selected_to_grid","spacing":0.75})),
        ("selected-active".into(),json!({"kind":"selected_to_active"})),
        ("cursor-grid".into(),json!({"kind":"cursor_to_grid","spacing":0.75})),
        ("cursor-selected".into(),json!({"kind":"cursor_to_selected"})),
        ("cursor-active".into(),json!({"kind":"cursor_to_active"})),
        ("cursor-origin".into(),json!({"kind":"cursor_to_center"}))];
    for offset in [false,true] {for rotation in [false,true] {
        forms.push((format!("selected-cursor-{offset}-{rotation}"),json!({"kind":"selected_to_cursor","use_offset":offset,"use_rotation":rotation})));
    }}
    assert_eq!(forms.len(),10);let origin=Instant::now();let mut runs=Vec::new();
    for (name,action) in forms {
        let command:Command=serde_json::from_value(json!({"operation":"snap_mesh","snap":{"entity":"target","action":action,"pivot":"median"}})).unwrap();
        for sample in 1..=3 {
            let mut editor=Editor::new(input.clone()).unwrap();let cs=origin.elapsed().as_nanos();
            let core=editor.apply_with_outcomes(&[command.clone()],Some(0)).unwrap();let ce=origin.elapsed().as_nanos();
            assert_eq!(core.snaps.len(),1);assert_eq!(serde_json::to_value(core.snaps[0].status).unwrap(),"finished");
            let actual=&editor.scene().mesh_assets["grid"];let original=&input.mesh_assets["grid"];
            assert_eq!((actual.vertices.len(),actual.edges.len(),actual.polygons.len()),(10201,20200,10000));
            assert_eq!(actual.edges,original.edges);assert_eq!(actual.editing,original.editing);assert_eq!(editor.scene().entities,input.entities);
            assert_eq!(actual.polygons.keys().collect::<Vec<_>>(),original.polygons.keys().collect::<Vec<_>>());
            let path=output.join(format!("{name}-{sample}.json"));let mut session=Session::create(&path,input.clone()).unwrap();
            let ps=origin.elapsed().as_nanos();let result=session.apply_with_result(ApplyRequest {expected_revision:0,commands:vec![command.clone()]}).unwrap();
            let fresh=Scene::load(&path).unwrap();let pe=origin.elapsed().as_nanos();
            assert_eq!(fresh,*editor.scene());assert_eq!(fresh,*session.scene());
            assert_eq!(serde_json::to_value(&core.snaps).unwrap(),serde_json::to_value(&result.snaps).unwrap());
            std::fs::write(output.join(format!("{name}-{sample}-receipt.json")),serde_json::to_vec(&result).unwrap()).unwrap();
            let core_ms=(ce-cs) as f64/1e6;let pipeline_ms=(pe-ps) as f64/1e6;
            let record=json!({"form":name,"sample":sample,"action":action,"core_start_ns":cs,"core_end_ns":ce,
                "pipeline_start_ns":ps,"pipeline_end_ns":pe,"core_ms":core_ms,"operation_save_reload_ms":pipeline_ms,
                "maximum_core_ms":250,"maximum_pipeline_ms":2000,"passed":core_ms<=250.&&pipeline_ms<=2000.,
                "topology_and_editing_preserved":true,"fresh_reload_equal":true,"receipt_equal":true});
            println!("{record}");runs.push(record);drop(session);
        }
    }
    let passed=runs.len()==30&&runs.iter().all(|r|r["passed"]==true);
    let report=json!({"passed":passed,"profile":"release","grid":[100,100],"vertices":10201,"edges":20200,"faces":10000,
        "forms":10,"samples_per_form":3,"runs":runs,"source_comparison":"required separately at fixed 1e-6 limits",
        "issue_acceptance":"unrun","milestone_acceptance":"unrun"});
    std::fs::write(output.join("report.json"),serde_json::to_vec_pretty(&report).unwrap()).unwrap();if !passed {std::process::exit(1);}
}
