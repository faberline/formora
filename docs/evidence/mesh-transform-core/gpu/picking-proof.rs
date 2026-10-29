use formora::{preview::math,scene::Scene};
use glam::DVec3;
fn main() {
 let args:Vec<_>=std::env::args().collect();
 let a=Scene::load(std::path::Path::new(&args[1])).unwrap();
 let b=Scene::load(std::path::Path::new(&args[2])).unwrap();
 let origin=DVec3::new(0.,0.,5.);let direction=-DVec3::Z;
 let first=math::pick(&a,origin,direction).unwrap().unwrap();
 let second=math::pick(&b,origin,direction).unwrap().unwrap();
 assert_eq!(first.entity,second.entity);assert_eq!(first.position,second.position);assert_eq!(first.distance,second.distance);
 let av=math::vertices(&a).unwrap().len();let bv=math::vertices(&b).unwrap().len();assert_eq!(av,36);assert_eq!(bv,av+48);
 println!("{},{},{},{},{},{}",av,bv,first.position.x,first.position.y,first.position.z,first.distance);
}
