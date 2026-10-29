use formora::mesh::{MeshAsset,Polygon,selection::{self,Editing}};
use formora::scene::{Scene,Entity,EntityKind,Geometry,Transform,Command,Editor};
use formora::session::{Session,ApplyRequest};
use formora::transforms::Precision;
use serde_json::json;
use std::{path::Path,time::Instant};
fn id(x:usize,y:usize)->String {format!("v{:06}",y*101+x)}
fn fixture()->Scene {
 let mut asset=MeshAsset::default();
 for y in 0..=100 {for x in 0..=100 {asset.vertices.insert(id(x,y),[x as f64,y as f64,0.]);}}
 for y in 0..=100 {for x in 0..=100 {for (nx,ny) in [(x+1,y),(x,y+1)] {if nx<=100 && ny<=100 {asset.edges.insert(format!("e{:06}",asset.edges.len()),[id(x,y),id(nx,ny)]);}}}}
 for y in 0..100 {for x in 0..100 {asset.polygons.insert(format!("f{:06}",y*100+x),Polygon{vertices:vec![id(x,y),id(x+1,y),id(x+1,y+1),id(x,y+1)],uv_layers:Default::default(),corner_normals:None,normal:None,smooth:false,material_slot:None});}}
 let mut editing=Editing::default();editing.selected.vertices=asset.vertices.keys().cloned().collect();selection::set_editing(&mut asset,Some(editing)).unwrap();
 assert_eq!((asset.vertices.len(),asset.edges.len(),asset.polygons.len()),(10201,20200,10000));
 let mut scene=Scene::default();scene.mesh_assets.insert("grid".into(),asset);scene.entities.insert("target".into(),Entity{name:"Grid".into(),parent:None,transform:Transform{precision:Precision::F32,..Default::default()},content:EntityKind::Mesh{geometry:Geometry::Asset{id:"grid".into()},material:None}});scene.validate().unwrap();scene
}
fn main() {
 assert!(!cfg!(debug_assertions));assert_eq!(std::env::consts::ARCH,"aarch64");assert_eq!(std::env::consts::OS,"macos");
 let folder=std::env::args().nth(1).expect("output directory");let output=Path::new(&folder);std::fs::create_dir(output).unwrap();
 let input=fixture();std::fs::write(output.join("input.json"),serde_json::to_vec(&input).unwrap()).unwrap();let origin=Instant::now();let mut records=Vec::new();
 for (kind,change) in [("translate",json!({"kind":"translate","value":[0.375,-0.625,0.25]})),("rotate",json!({"kind":"rotate","radians":-0.61,"axis":"z"})),("resize",json!({"kind":"resize","value":[1.25,0.65,1.1]}))] {
  let command:Command=serde_json::from_value(json!({"operation":"transform_mesh","transform":{"entity":"target","change":change,"orientation":{"kind":"global"},"pivot":"median"}})).unwrap();
  for run in 1..=3 {
   let mut editor=Editor::new(input.clone()).unwrap();let start=origin.elapsed().as_nanos();let core=editor.apply_with_outcomes(&[command.clone()],Some(0)).unwrap();let end=origin.elapsed().as_nanos();
   assert_eq!(core.transforms.len(),1);assert_eq!(core.transforms[0].influence.len(),10201);assert_eq!(core.transforms[0].changed.vertices.len(),if kind=="translate" {10201}else{10200});
   let asset=&editor.scene().mesh_assets["grid"];assert_eq!((asset.vertices.len(),asset.edges.len(),asset.polygons.len()),(10201,20200,10000));assert_eq!(asset.editing,input.mesh_assets["grid"].editing);assert_eq!(asset.edges,input.mesh_assets["grid"].edges);assert_eq!(editor.scene().entities,input.entities);

   let path=output.join(format!("{kind}-{run}.json"));let mut session=Session::create(&path,input.clone()).unwrap();let ps=origin.elapsed().as_nanos();let receipt=session.apply_with_result(ApplyRequest{expected_revision:0,commands:vec![command.clone()]}).unwrap();let restored=Scene::load(&path).unwrap();assert_eq!(restored,*session.scene());assert_eq!(restored,*editor.scene());let pe=origin.elapsed().as_nanos();assert_eq!(serde_json::to_value(&receipt.transforms).unwrap(),serde_json::to_value(&core.transforms).unwrap());
   let core_ms=(end-start) as f64/1e6;let pipeline_ms=(pe-ps) as f64/1e6;let record=json!({"operation":kind,"run":run,"core_start_ns":start,"core_end_ns":end,"pipeline_start_ns":ps,"pipeline_end_ns":pe,"core_ms":core_ms,"operation_save_reload_ms":pipeline_ms,"maximum_core_ms":250,"maximum_pipeline_ms":2000,"passed":core_ms<=250. && pipeline_ms<=2000.,"topology_preserved":true,"editing_preserved":true,"reload_equal":true,"receipt_equal":true});println!("{record}");records.push(record);std::fs::write(output.join(format!("{kind}-{run}-receipt.json")),serde_json::to_vec(&receipt).unwrap()).unwrap();drop(session);
  }
 }
 let passed=records.iter().all(|r|r["passed"]==true);let report=json!({"passed":passed,"profile":"release","feature_flags":[],"grid":[100,100],"vertices":10201,"edges":20200,"faces":10000,"runs":records,"source_position_comparison":"required separately at unchanged 1e-6 limit","issue_acceptance":"unrun","milestone_acceptance":"unrun"});std::fs::write(output.join("report.json"),serde_json::to_vec_pretty(&report).unwrap()).unwrap();if !passed {std::process::exit(1);}
}
