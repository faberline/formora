from pathlib import Path
import hashlib,json,platform,subprocess,sys
root=Path('/Users/chrischeng/faberlines/formora');sys.path.insert(0,str(root/'tools'));from png_pixels import read_rgba8
output=root/'docs/evidence/mesh-transform-core/gpu';output.mkdir(parents=True,exist_ok=False);binary=Path('/private/tmp/formora-target-actual185/debug/formora');target=binary.parent;compiler=Path('/private/tmp/formora-rustup-cache/toolchains/1.85.0-aarch64-apple-darwin/bin/rustc');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(binary);source={str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])};calls=[];runs=[]
probe=Path('/private/tmp/formora-transform-picking-proof.rs');probe.write_text('''use formora::{preview::math,scene::Scene};
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
''')
glams=list((target/'deps').glob('libglam-*.rlib'));assert len(glams)==1,glams
version=subprocess.check_output([str(compiler),'--version'],text=True).strip();assert version.startswith('rustc 1.85.0 ')
probe_binary=Path('/private/tmp/formora-transform-picking-proof');compile_command=[str(compiler),'--edition=2024','--crate-name','formora_transform_picking_proof',str(probe),'--extern','formora='+str(target/'libformora.rlib'),'--extern','glam='+str(glams[0]),'-L','dependency='+str(target/'deps'),'-o',str(probe_binary)]
compiled=subprocess.run(compile_command,capture_output=True,text=True);assert compiled.returncode==0,compiled.stderr
identity={'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1]}
def entity(id,content,transform):return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':None,'transform':transform,'content':content}}
def call(*args,request=None):
 r=subprocess.run([str(binary),*map(str,args)],input=None if request is None else json.dumps(request),capture_output=True,text=True);calls.append({'arguments':list(map(str,args)),'request':request,'stdout':r.stdout,'stderr':r.stderr,'exit_code':r.returncode});assert r.returncode==0,r.stdout+r.stderr;return json.loads(r.stdout)
def difference(a,b):
 w,h,first=read_rgba8(a);wb,hb,second=read_rgba8(b);assert (w,h)==(wb,hb)==(640,480);return sum(first(x,y)!=second(x,y) for y in range(h) for x in range(w))
for change in [{'kind':'translate','value':[0.6,0.3,0]},{'kind':'rotate','radians':0.61,'axis':'y'},{'kind':'resize','value':[0.7,1.3,0.8]}]:
 kind=change['kind'];folder=output/kind;folder.mkdir();scene=folder/'scene.json';call('scene','init','--scene',scene)
 call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':0,'commands':[
  {'operation':'create_mesh_object','creation':{'id':'target','asset':'mesh','name':kind,'primitive':{'kind':'cube','size':1.5},'preview_selection':False}},
  entity('camera',{'kind':'camera','vertical_fov_degrees':45,'near':0.1,'far':100},{**identity,'translation':[0,0,5]}),{'operation':'set_active_camera','id':'camera'},entity('light',{'kind':'light','color':[1,1,1],'intensity':2},{**identity,'translation':[2,3,5]})]})
 before=call('scene','inspect','--scene',scene);gpu=call('render','--scene',scene,'--output',folder/'before.png','--width',640,'--height',480)['gpu'];assert '(Metal,' in gpu,gpu
 receipt=call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':1,'commands':[{'operation':'transform_mesh','transform':{'entity':'target','change':change}}]});assert len(receipt['transforms'])==1 and len(receipt['transforms'][0]['changed']['vertices'])==8
 after=call('scene','inspect','--scene',scene);assert before['scene']['entities']==after['scene']['entities'];assert after['scene']['mesh_assets']['mesh']['recipe']['edited']
 (folder/'after-scene.json').write_bytes(scene.read_bytes())
 for name in ['after','reloaded']:call('render','--scene',scene,'--output',folder/(name+'.png'),'--width',640,'--height',480)
 assert (folder/'after.png').read_bytes()==(folder/'reloaded.png').read_bytes();changed=difference(folder/'before.png',folder/'after.png');assert changed>500,changed
 editing=after['scene']['mesh_assets']['mesh']['editing'];editing['preview']=True
 call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':2,'commands':[{'operation':'set_mesh_editing','id':'mesh','editing':editing}]})
 call('render','--scene',scene,'--output',folder/'markers.png','--width',640,'--height',480);markers=difference(folder/'after.png',folder/'markers.png');assert markers>20,markers
 picked=subprocess.run([str(probe_binary),str(folder/'after-scene.json'),str(scene)],capture_output=True,text=True);assert picked.returncode==0,picked.stderr;values=picked.stdout.strip().split(',');assert len(values)==6
 (folder/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');runs.append({'kind':kind,'gpu':gpu,'different_pixels':changed,'marker_pixels':markers,'fresh_reload_identical':True,'picking_identical_with_markers':True,'pick_point':[float(x) for x in values[2:5]],'pick_distance':float(values[5]),'render_vertices_before_markers':int(values[0]),'render_vertices_after_markers':int(values[1])})
assert binary_sha==sha(binary) and source=={name:sha(root/name) for name in source}
manifest={'passed':True,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'binary_sha256':binary_sha,'source_files':source,'platform':platform.platform(),'runs':runs,'commands':calls,'driver_sha256':sha(Path(__file__)),'probe_source_sha256':sha(probe),'probe_binary_sha256':sha(probe_binary),'formora_library_sha256':sha(target/'libformora.rlib'),'glam_library_sha256':sha(glams[0]),'probe_compile_command':compile_command,'rustc':version,'artifacts':{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file() and not p.name.endswith('.formora.lock')},'scope':'basic native mesh transforms only; source gate, other options, platforms and milestone acceptance remain incomplete'}
(output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'passed':True,'runs':runs}))
