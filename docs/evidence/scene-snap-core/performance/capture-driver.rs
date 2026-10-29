//! Frozen inputs. Ten forms x three samples in each class. Retain all raw files.
use formora::mesh::{creation::AuthoringContext, selection::Component};
use formora::objects::Context;
use formora::rotation::{EulerOrder, RotationAngles, TransformRotation};
use formora::scene::{Command, Editor, Entity, EntityKind, Scene, Transform};
use formora::session::{ApplyRequest, Session};
use serde_json::json;
use std::{collections::BTreeSet, path::Path, time::Instant};

fn main() {
    assert!(!cfg!(debug_assertions));
    assert_eq!(std::env::consts::ARCH, "aarch64");
    assert_eq!(std::env::consts::OS, "macos");
    let args = std::env::args().collect::<Vec<_>>();
    assert!(args.len() == 4 || args.len() == 6);
    let original = Scene::load(Path::new(&args[1])).unwrap();
    let output = Path::new(&args[2]);
    let prepare = args[3] == "prepare";
    assert_eq!(original.revision, 0);
    assert_eq!((original.entities.len(), original.mesh_assets.len()), (1, 1));
    if prepare { std::fs::create_dir(output).unwrap(); }
    else { assert!(output.is_dir()); assert_eq!(args[3], "run"); }
    let mut inputs = Vec::new();
    for class in ["A", "B", "C"] {
        let mut input = original.clone();
        let asset = input.mesh_assets.get_mut("grid").unwrap();
        assert_eq!((asset.vertices.len(), asset.edges.len(), asset.polygons.len()), (10201, 20200, 10000));
        let editing = asset.editing.as_mut().unwrap();
        assert_eq!(editing.selected.vertices.len(), 10201);
        editing.history = vec![Component::Vertex { id: asset.vertices.keys().next_back().unwrap().clone() }];
        let target = input.entities.get_mut("target").unwrap();
        target.transform.translation = if class == "A" { [0.25, -0.5, 0.75] } else { [0.; 3] };
        target.transform.rotation = TransformRotation::Authored(RotationAngles::Euler { angles: [0.; 3], order: EulerOrder::Xyz });
        target.transform.precision = formora::transforms::Precision::F32;
        let mut context = Context { order: vec!["target".into()], selected: BTreeSet::from(["target".into()]), active: Some("target".into()), ..Context::default() };
        if class == "A" {
            input.entities.insert("child".into(), Entity { name: "Child".into(), parent: Some("target".into()), transform: Transform { translation: [1., 2., 3.], rotation: TransformRotation::Authored(RotationAngles::Euler { angles: [0.; 3], order: EulerOrder::Xyz }), precision: formora::transforms::Precision::F32, ..Transform::default() }, content: EntityKind::Empty });
            context.order.push("child".into()); context.skip_children = true; context.origins_only = true;
        } else {
            let mut second = input.entities["target"].clone(); second.name = "Secondary".into(); second.transform.translation = [2., 0., 0.];
            if class == "C" {
                input.mesh_assets.insert("secondary_grid".into(), input.mesh_assets["grid"].clone());
                if let EntityKind::Mesh { geometry: formora::scene::Geometry::Asset { id }, .. } = &mut second.content { *id = "secondary_grid".into(); } else { panic!("requires grid asset"); }
            }
            input.entities.insert("secondary".into(), second); context.order.push("secondary".into()); context.selected.insert("secondary".into()); context.edit_objects.insert("target".into());
            if class == "C" { context.edit_objects.insert("secondary".into()); }
        }
        input.object_context = Some(context);
        input.authoring_context = Some(AuthoringContext { cursor_location: [0.375, -0.625, 0.875], ..Default::default() }); input.validate().unwrap();
        let path = output.join(format!("input-{class}.json"));
        if prepare { input.save(&path).unwrap(); } else { assert_eq!(Scene::load(&path).unwrap(), input); }
        inputs.push((class, input));
    }
    if prepare { return; }
    let forms = [
        ("selected-grid", json!({"kind":"selected_to_grid","spacing":0.75})),
        ("selected-active", json!({"kind":"selected_to_active"})),
        ("cursor-grid", json!({"kind":"cursor_to_grid","spacing":0.75})),
        ("cursor-selected", json!({"kind":"cursor_to_selected"})),
        ("cursor-active", json!({"kind":"cursor_to_active"})),
        ("cursor-origin", json!({"kind":"cursor_to_center"})),
        ("selected-cursor-false-false", json!({"kind":"selected_to_cursor","use_offset":false,"use_rotation":false})),
        ("selected-cursor-false-true", json!({"kind":"selected_to_cursor","use_offset":false,"use_rotation":true})),
        ("selected-cursor-true-false", json!({"kind":"selected_to_cursor","use_offset":true,"use_rotation":false})),
        ("selected-cursor-true-true", json!({"kind":"selected_to_cursor","use_offset":true,"use_rotation":true})),
    ];
    let (class, input) = inputs.iter().find(|(class, _)| *class == args[4]).expect("unknown class");
    let (name, action) = forms.iter().find(|(name, _)| *name == args[5]).expect("unknown form");
    let report_path = output.join(format!("report-{class}-{name}.json")); assert!(!report_path.exists());
    let (maximum_core_ms, maximum_pipeline_ms) = if *class == "C" { (500., 4000.) } else { (250., 2000.) };
    let command: Command = serde_json::from_value(json!({"operation":"snap_scene","snap":{"action":action,"pivot":"median"}})).unwrap();
    let origin = Instant::now(); let mut runs = Vec::new();
    for sample in 1..=3 {
        let mut editor = Editor::new(input.clone()).unwrap(); let cs = origin.elapsed().as_nanos();
        let core = editor.apply_with_outcomes(&[command.clone()], Some(0)).unwrap(); let ce = origin.elapsed().as_nanos();
        assert_eq!(core.scene_snaps.len(), 1); assert_eq!(serde_json::to_value(core.scene_snaps[0].status).unwrap(), "finished");
        let path = output.join(format!("{class}-{name}-{sample}.json")); assert!(!path.exists());
        let mut session = Session::create(&path, input.clone()).unwrap(); let ps = origin.elapsed().as_nanos();
        let result = session.apply_with_result(ApplyRequest { expected_revision: 0, commands: vec![command.clone()] }).unwrap();
        let fresh = Scene::load(&path).unwrap(); let pe = origin.elapsed().as_nanos();
        assert_eq!(fresh, *editor.scene()); assert_eq!(fresh, *session.scene());
        assert_eq!(serde_json::to_value(&core.scene_snaps).unwrap(), serde_json::to_value(&result.scene_snaps).unwrap()); drop(session);
        std::fs::write(output.join(format!("{class}-{name}-{sample}-receipt.json")), serde_json::to_vec(&result).unwrap()).unwrap();
        let core_ms = (ce-cs) as f64/1e6; let pipeline_ms = (pe-ps) as f64/1e6;
        let record = json!({"class":class,"form":name,"sample":sample,"action":action,"core_start_ns":cs,"core_end_ns":ce,"pipeline_start_ns":ps,"pipeline_end_ns":pe,"core_ms":core_ms,"operation_save_reload_ms":pipeline_ms,"maximum_core_ms":maximum_core_ms,"maximum_pipeline_ms":maximum_pipeline_ms,"passed":core_ms<=maximum_core_ms&&pipeline_ms<=maximum_pipeline_ms,"fresh_reload_equal":true,"receipt_equal":true});
        println!("{record}"); runs.push(record);
    }
    let passed = runs.len()==3 && runs.iter().all(|r| r["passed"]==true);
    let report = json!({"passed":passed,"profile":"release","grid":[100,100],"vertices_per_mesh":10201,"edges_per_mesh":20200,"faces_per_mesh":10000,"class":class,"form":name,"samples":3,"runs":runs,"complete_gate":"requires all 30 class/form reports and all 90 source comparisons","issue_acceptance":"unrun","milestone_acceptance":"unrun"});
    std::fs::write(report_path, serde_json::to_vec_pretty(&report).unwrap()).unwrap(); if !passed { std::process::exit(1); }
}
