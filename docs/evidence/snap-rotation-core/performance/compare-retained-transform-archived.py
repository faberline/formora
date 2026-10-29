from pathlib import Path
import json,hashlib,math
root=Path(__file__).resolve().parents[4];perf=Path(__file__).resolve().parent/'retained-39-01/transform';first=root/'docs/evidence/mesh-transform-core/reuse-grid-source-first';repeat=root/'docs/evidence/mesh-transform-core/reuse-grid-source-repeat';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.load(open(first/'report.json'));b=json.load(open(repeat/'report.json'));assert a['passed'] and b['passed'] and a['process_id']!=b['process_id'];assert a['build_hash']==b['build_hash']=='e13b728c6880';assert a['version']==b['version']==[5,2,3];assert a['driver_sha256']==b['driver_sha256']==sha(first/'capture-driver.py')
assert a['input_sha256']==b['input_sha256']==sha(perf/'input.json');assert a['reference_adapter_hashes']==b['reference_adapter_hashes']
for name,digest in a['reference_adapter_hashes'].items():assert sha(root/'tools'/name)==digest
input_scene=json.load(open(perf/'input.json'));input_asset=input_scene['mesh_assets']['grid'];records=[]
for row,again in zip(a['records'],b['records']):
 assert row['operator']==again['operator'];assert sha(first/row['file'])==row['sha256'] and sha(repeat/again['file'])==again['sha256'];one=json.load(open(first/row['file']));two=json.load(open(repeat/again['file']));kind=row['operator'];assert one['status']==two['status']==['FINISHED']
 for phase in ['before','after']:
  for key in ['geometry','normals','world_vertices','selected','hidden','mode','history','active_face']:assert one[phase][key]==two[phase][key],(kind,phase,key)
 assert one['before']['geometry']['vertices']==input_asset['vertices'];assert one['before']['geometry']['edges']=={id:sorted(pair) for id,pair in input_asset['edges'].items()};assert one['before']['geometry']['faces']=={id:p['vertices'] for id,p in input_asset['polygons'].items()};assert len(one['before']['selected']['VERT'])==10201 and not one['before']['history'];assert one['after']['objects']['target']['matrix_world']==[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
 for run in range(1,4):
  path=perf/f'{kind}-{run}.json';scene=json.load(open(path));asset=scene['mesh_assets']['grid'];source=one['after'];assert asset['edges']==input_asset['edges'];assert {id:p['vertices'] for id,p in asset['polygons'].items()}==source['geometry']['faces'];assert asset['editing']==input_asset['editing'];assert scene['entities']==input_scene['entities']
  maxima={'position':0.,'face_normal':0.,'corner_normal':0.};components=0
  def compare(actual,expected,kind):
   global components
   assert len(actual)==len(expected)
   for x,y in zip(actual,expected):
    assert math.isfinite(x) and math.isfinite(y);error=abs(x-y);maxima[kind]=max(maxima[kind],error);components+=1;assert error<=1e-6,(row['operator'],run,kind,error,actual,expected)
  assert set(asset['vertices'])==set(source['geometry']['vertices'])
  for id,p in asset['vertices'].items():compare(p,source['geometry']['vertices'][id],'position')
  for id,p in asset['polygons'].items():
   compare(p['normal'],source['normals']['faces'][id],'face_normal');assert len(p['corner_normals'])==len(source['normals']['corners'][id])
   for actual,expected in zip(p['corner_normals'],source['normals']['corners'][id]):compare(actual,expected,'corner_normal')
  records.append({'operation':kind,'run':run,'scene_sha256':sha(path),'reference_sha256':row['sha256'],'repeat_reference_sha256':again['sha256'],'vertices':10201,'faces':10000,'components':components,'maximum_absolute_errors':maxima,'tolerance':1e-6,'passed':True})
r={'passed':True,'records':records,'reference_processes':[a['process_id'],b['process_id']],'reference_binary_sha256':sha(Path('/Applications/Blender.app/Contents/MacOS/Blender')),'authored_input_sha256':sha(perf/'input.json'),'reference_driver_sha256':a['driver_sha256'],'comparison_driver_sha256':sha(Path(__file__)),'fixed_tolerance':1e-6,'source_repeat_geometry_and_normals_exact':True,'scope':'independent source comparison for all nine frozen performance-grid outputs; not issue or milestone acceptance'};(perf/'source-comparison-report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'passed':True,'grid_outputs':len(records),'source_processes':r['reference_processes'],'maximum_errors':{kind:max(x['maximum_absolute_errors'][kind] for x in records) for kind in maxima},'fixed_tolerance':1e-6}))
