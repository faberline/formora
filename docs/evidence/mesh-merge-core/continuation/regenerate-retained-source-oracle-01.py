from pathlib import Path
import json,subprocess,hashlib,tempfile
root=Path('/private/tmp/formora-mesh-merge-sparse');binary=Path('/private/tmp/formora-merge-regen-target-actual185/debug/formora');output=Path('/private/tmp/formora-merge-regen-source-oracle-01');output.mkdir(exist_ok=False);source=json.load(open('/private/tmp/formora-mesh-merge-sparse/docs/evidence/mesh-transform-core/frame-source-oracle-final/reference-report.json'));records=[];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='formora-frame-oracle-') as temporary:
 for case in source['cases']:
  path=Path(temporary)/(case['id']+'.json');calls=[]
  def call(*args,request=None):
   result=subprocess.run([str(binary),*map(str,args)],input=None if request is None else json.dumps(request),capture_output=True,text=True);calls.append({'arguments':list(map(str,args)),'request':request,'stdout':result.stdout,'stderr':result.stderr,'exit_code':result.returncode});assert result.returncode==0,result.stdout+result.stderr;return json.loads(result.stdout)
  call('scene','init','--scene',path);commands=[]
  for id,location,angles,scale,parent in [('parent',[1.25,-0.75,2],[0.37,-0.23,0.51],[1.2,0.7,1.6],None),('child',[-0.7,0.35,0.6],[0.13,0.29,-0.41],[0.9,1.4,0.8],'parent')]:
   commands.append({'operation':'create_entity','id':id,'entity':{'name':id,'parent':parent,'transform':{'translation':location,'rotation':{'kind':'euler','angles':angles,'order':case['id'].lower()},'scale':scale,'precision':'f32'},'content':{'kind':'empty'} if id=='parent' else {'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}}})
  asset={'operation':'set_mesh_asset','id':'mesh','asset':{'vertices':{'probe':[3.25,-1.7,0.9]},'edges':{},'triangles':{},'material_slots':[]}}
  call('scene','apply','--scene',path,'--request','-',request={'expected_revision':0,'commands':[asset,*commands]});saved=path.read_bytes();parent=call('scene','inspect','--scene',path,'--entity','parent','--world');child=call('scene','inspect','--scene',path,'--entity','child','--world');assert path.read_bytes()==saved
  assert parent['world_matrix']==case['parent']['world_matrix'],case['id']
  assert child['world_matrix']==case['child']['world_matrix'],case['id']
  assert child['world_vertices']['probe']==case['world_point'],(case['id'],child['world_vertices']['probe'],case['world_point'])
  records.append({'id':case['id'],'matrix_exact':True,'point_exact':True,'queries_preserve_disk':True,'commands':calls})
for name in ['report.json']:(output/('reference-'+name)).write_bytes((root/'docs/evidence/mesh-transform-core/reuse-source-oracle'/('reference-'+name)).read_bytes())
report={'passed':True,'binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),'reference_binary_sha256':sha(Path('/Applications/Blender.app/Contents/MacOS/Blender')),'cases':records,'inputs_authored_in_driver':True,'measured_outputs_used_as_product_inputs':False,'source_files':{str(p.relative_to(root)):sha(p) for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]])},'issue_acceptance':'unrun','milestone_acceptance':'unrun'};(output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'exact_euler_orders':len(records),'native_world_matrices_and_points':'exact','query_disk_bytes':'unchanged'}))
