import bpy,bmesh,sys,json,copy,os,hashlib,traceback
from pathlib import Path
root=Path('/Users/chrischeng/faberlines/formora');sys.path.insert(0,str(root/'tools'));import blender_transform_reference as reference
output=Path(sys.argv[sys.argv.index('--')+1]);assert not output.exists();output.mkdir()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def capture():
 try:
  assert not bpy.app.background and bpy.app.build_hash.decode()=='e13b728c6880'
  source=Path('/private/tmp/formora-frame-performance/input.json');scene=json.loads(source.read_text());asset=scene['mesh_assets']['grid'];ids=list(asset['vertices']);index={id:i for i,id in enumerate(ids)}
  mesh={'vertices':list(asset['vertices'].values()),'edges':[[index[v] for v in pair] for pair in asset['edges'].values()],'faces':[[index[v] for v in f['vertices']] for f in asset['polygons'].values()],
        'face_smooth':[f['smooth'] for f in asset['polygons'].values()],'face_materials':[0]*10000,'edge_seams':[False]*20200,'material_slots':[],
        'uv_layers':[],'active_uv_index':0,'active_material_index':0,'hidden':{'vertices':[],'edges':[],'faces':[]},'group_scenarios':{'none':{'names':[],'weights':{}}}}
  assert (len(mesh['vertices']),len(mesh['edges']),len(mesh['faces']))==(10201,20200,10000)
  base=json.load(open(root/'baseline/fixtures/mesh-transform.json'));suite={'mesh':mesh,'environment':base['environment'],'profiles':{'identity':base['profiles']['identity']}}
  records=[]
  for operator,value in [('translate',[0.375,-0.625,0.25]),('rotate',0.61),('resize',[1.25,0.65,1.1])]:
   run={'context':{'profile':'identity','pivot':'MEDIAN_POINT','correct_face_attributes':False,'keep_connected':True,'mirror_x':False,'mirror_topology':False},'initial_mode':['VERT'],'seed':{'domain':'VERT','indices':list(range(10201))},'groups':'none'}
   obj,area,region=reference.create(suite,run);bm=bmesh.from_edit_mesh(obj.data);bm.select_history.clear();bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)
   before=reference.snapshot(obj,area);parameters={'value':value,'orient_type':'GLOBAL','mirror':False,'use_proportional_edit':False,'snap':False}
   with bpy.context.temp_override(window=bpy.context.window,area=area,region=region):status=sorted(getattr(bpy.ops.transform,operator)(**parameters))
   assert status==['FINISHED'];after=reference.snapshot(obj,area);assert len(after['geometry']['vertices'])==10201
   raw={'operator':operator,'parameters':parameters,'context':run,'before':before,'after':after,'status':status};path=output/(operator+'.json');path.write_text(json.dumps(raw,allow_nan=False)+'\n');records.append({'operator':operator,'file':path.name,'sha256':digest(path)})
  (output/'report.json').write_text(json.dumps({'passed':True,'process_id':os.getpid(),'build_hash':bpy.app.build_hash.decode(),'version':list(bpy.app.version),'input_sha256':digest(source),'driver_sha256':digest(Path(__file__)),'reference_adapter_hashes':{name:digest(root/'tools'/name) for name in ['blender_transform_reference.py','blender_selection_reference.py']},'records':records,'scope':'additional fixed performance-grid source geometry; no product acceptance'},indent=2)+'\n')
  print(json.dumps({'passed':True,'process_id':os.getpid(),'operations':3,'vertices':10201}),flush=True)
 except Exception:
  (output/'failure.txt').write_text(traceback.format_exc());traceback.print_exc()
 finally:bpy.ops.wm.quit_blender()
 return None
bpy.app.timers.register(capture,first_interval=1.0)
