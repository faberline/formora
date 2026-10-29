use formora::scene::{Scene,Editor};
use serde_json::json;
use std::time::Instant;
fn main(){
 assert!(!cfg!(debug_assertions));let bytes=std::fs::read("/private/tmp/formora-frame-performance/input.json").unwrap();let scene:Scene=serde_json::from_slice(&bytes).unwrap();let asset=&scene.mesh_assets["grid"];
 for run in 0..3 {
  let start=Instant::now();std::hint::black_box(asset.clone());println!("{}",json!({"part":"asset_clone","run":run,"ms":start.elapsed().as_secs_f64()*1000.}));
  let start=Instant::now();asset.validate().unwrap();println!("{}",json!({"part":"asset_validate","run":run,"ms":start.elapsed().as_secs_f64()*1000.}));
  let start=Instant::now();scene.validate().unwrap();println!("{}",json!({"part":"scene_validate","run":run,"ms":start.elapsed().as_secs_f64()*1000.}));
  let start=Instant::now();std::hint::black_box(formora::mesh::normals::automatic(asset).unwrap());println!("{}",json!({"part":"automatic_normals","run":run,"ms":start.elapsed().as_secs_f64()*1000.}));
  let start=Instant::now();std::hint::black_box(formora::mesh::selection::topology(asset).unwrap());println!("{}",json!({"part":"topology_description","run":run,"ms":start.elapsed().as_secs_f64()*1000.}));
  let start=Instant::now();std::hint::black_box(Editor::new(scene.clone()).unwrap());println!("{}",json!({"part":"editor_prepare","run":run,"ms":start.elapsed().as_secs_f64()*1000.}));
 }
}
