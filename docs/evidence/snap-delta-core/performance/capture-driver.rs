//! Fixed additional 24 samples, original timers, one native process.
use formora::objects::State;
use formora::transforms::Delta;
use formora::rotation::{Channels, Mode, RotationAngles, TransformRotation};
use formora::scene::{Command, Editor, Scene};
use formora::session::{ApplyRequest, Session};
use serde_json::{Value, json};
use std::{path::Path, time::Instant};

fn channels(value: &Value) -> Channels {
    let mut value=value.clone();value["mode"]=json!(value["mode"].as_str().unwrap().to_lowercase());
    let mut result:Channels=serde_json::from_value(value).unwrap();
    result.euler=result.euler.map(|v| f64::from(v as f32));
    result.quaternion_wxyz=result.quaternion_wxyz.map(|v| f64::from(v as f32));
    result.axis_angle=result.axis_angle.map(|v| f64::from(v as f32));
    result
}
fn delta(value: &Value) -> Delta {
    let mut value=value.clone();let translation=value.as_object_mut().unwrap().remove("location").unwrap();
    value["translation"]=translation;
    let mut result:Delta=serde_json::from_value(value).unwrap();
    result.translation=result.translation.map(|v|f64::from(v as f32));
    result.euler=result.euler.map(|v|f64::from(v as f32));
    result.quaternion_wxyz=result.quaternion_wxyz.map(|v|f64::from(v as f32));
    result.scale=result.scale.map(|v|f64::from(v as f32));result
}
fn main() {
    assert!(!cfg!(debug_assertions));assert_eq!(std::env::consts::ARCH,"aarch64");assert_eq!(std::env::consts::OS,"macos");
    let args=std::env::args().collect::<Vec<_>>();assert_eq!(args.len(),3);
    let authored=Path::new(&args[1]);let output=Path::new(&args[2]);std::fs::create_dir(output).unwrap();
    let base=Scene::load(&authored.join("authored-grid.json")).unwrap();
    let modes:Value=serde_json::from_slice(&std::fs::read(authored.join("authored-modes.json")).unwrap()).unwrap();
    assert_eq!(modes["samples_per_mode"],3);assert_eq!(modes["maximum_core_ms"],250);assert_eq!(modes["maximum_pipeline_ms"],2000);
    let command:Command=serde_json::from_value(json!({"operation":"snap_scene","snap":{"action":{
        "kind":"selected_to_cursor","use_offset":false,"use_rotation":true},"pivot":"median"}})).unwrap();
    let mut inputs=Vec::new();
    for mode in modes["modes"].as_array().unwrap() {
        let name=mode["object"]["mode"].as_str().unwrap();let mut scene=base.clone();
        let object=channels(&mode["object"]);let cursor=channels(&mode["cursor"]);
        assert_eq!(object.mode,cursor.mode);assert_eq!(scene.entities.len(),2);assert_eq!(scene.mesh_assets.len(),1);
        let mesh=&scene.mesh_assets["grid"];assert_eq!((mesh.vertices.len(),mesh.edges.len(),mesh.polygons.len()),(10201,20200,10000));
        assert_eq!(mesh.editing.as_ref().unwrap().selected.vertices.len(),10201);
        scene.entities.get_mut("target").unwrap().transform.rotation=TransformRotation::Authored(RotationAngles::Channels { channels:object });
        scene.entities.get_mut("child").unwrap().transform.rotation=TransformRotation::Authored(RotationAngles::Channels {
            channels:Channels {mode:Mode::Xyz,euler:[0.;3],quaternion_wxyz:[1.,0.,0.,0.],axis_angle:[0.,0.,1.,0.]} });
        scene.entities.get_mut("target").unwrap().transform.delta=delta(&modes["target_delta"]);
        scene.entities.get_mut("child").unwrap().transform.delta=delta(&modes["child_delta"]);
        let context=scene.object_context.as_mut().unwrap();assert!(context.origins_only && context.skip_children);
        context.states.insert("target".into(),State {lock_rotation:[true,false,false],lock_rotation_w:false,lock_rotations_4d:true,..State::default()});
        context.states.insert("child".into(),State {lock_rotations_4d:false,..State::default()});
        let context=scene.authoring_context.as_mut().unwrap();assert_eq!(context.cursor_location,[0.375,-0.625,0.875]);
        context.cursor_rotation=cursor.euler;context.cursor_orientation=Some(cursor);
        scene.validate().unwrap();scene.save(&output.join(format!("input-{name}.json"))).unwrap();
        inputs.push((name.to_owned(),scene));
    }
    assert_eq!(inputs.len(),8);
    let origin=Instant::now();let mut runs=Vec::new();
    for (name,input) in &inputs {
        for sample in 1..=3 {
            let mut editor=Editor::new(input.clone()).unwrap();
            let cs=origin.elapsed().as_nanos();
            let core=editor.apply_with_outcomes(&[command.clone()],Some(0)).unwrap();
            let ce=origin.elapsed().as_nanos();
            assert_eq!(core.scene_snaps.len(),1);
            let path=output.join(format!("{name}-{sample}.json"));assert!(!path.exists());
            let mut session=Session::create(&path,input.clone()).unwrap();
            let ps=origin.elapsed().as_nanos();
            let result=session.apply_with_result(ApplyRequest {expected_revision:0,commands:vec![command.clone()]}).unwrap();
            let fresh=Scene::load(&path).unwrap();let pe=origin.elapsed().as_nanos();
            assert_eq!(fresh,*editor.scene());assert_eq!(fresh,*session.scene());
            assert_eq!(serde_json::to_value(&core.scene_snaps).unwrap(),serde_json::to_value(&result.scene_snaps).unwrap());
            assert_eq!(serde_json::to_value(core.scene_snaps[0].status).unwrap(),"finished");
            drop(session);
            std::fs::write(output.join(format!("{name}-{sample}-receipt.json")),serde_json::to_vec(&result).unwrap()).unwrap();
            let core_ms=(ce-cs) as f64/1e6;let pipeline_ms=(pe-ps) as f64/1e6;
            let row=json!({"mode":name,"sample":sample,"file":path.file_name().unwrap().to_str().unwrap(),
                "core_start_ns":cs,"core_end_ns":ce,"pipeline_start_ns":ps,"pipeline_end_ns":pe,
                "core_ms":core_ms,"operation_save_reload_ms":pipeline_ms,"maximum_core_ms":250.,"maximum_pipeline_ms":2000.,
                "passed":core_ms<=250. && pipeline_ms<=2000.});
            println!("{row}");runs.push(row);
        }
    }
    let passed=runs.len()==24 && runs.iter().all(|r| r["passed"]==true);
    std::fs::write(output.join("timing-summary.json"),serde_json::to_vec_pretty(&json!({"passed":passed,"samples":24,"runs":runs,
        "source_comparisons":"unrun","product_acceptance":"unrun"})).unwrap()).unwrap();
    if !passed {std::process::exit(1);}
}
