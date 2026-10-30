"""Add independently authored mesh and frame inputs; native execution remains unrun."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
suite=json.loads((HERE/'authored-context-cases.json').read_bytes())
def asset(points,faces):
 pairs=sorted({tuple(sorted((face[i-1],face[i]))) for face in faces for i in range(len(face))})
 vertices={f'v{i:06}':p for i,p in enumerate(points)};edges={f'e{i:06}':[f'v{a:06}',f'v{b:06}'] for i,(a,b) in enumerate(pairs)};polygons={}
 for i,face in enumerate(faces):
  polygons[f'f{i:06}']={'vertices':[f'v{v:06}' for v in face],'uv_layers':{'Detail':[[points[v][0]*.37+.13,points[v][1]*.29-.17] for v in face],'Layout':[[points[v][0]*.23-points[v][1]*.07+.2,points[v][1]*.31+points[v][0]*.11-.4] for v in face]},'smooth':i%2==0,'material_slot':i%2,'normal':None,'corner_normals':None}
 integers={domain:{name:{id:(i if name.startswith('formora_') else (i%3-1 if name=='duplicate' else i*3-7)) for i,id in enumerate(items)} for name in [tag,'signed','duplicate']} for domain,items,tag in [('vertices',vertices,'formora_v_id'),('edges',edges,'formora_e_id'),('polygons',polygons,'formora_f_id')]};integers['triangles']={}
 return {'vertices':vertices,'edges':edges,'polygons':polygons,'triangles':{},'material_slots':['mat0','mat1'],'uv_layout':{'layers':['Detail','Layout'],'active':'Layout'},'edge_seams':[next(iter(edges))],'vertex_groups':['pin','soft'],'vertex_weights':{id:{'pin':0. if i%2==0 else 1.,'soft':(i%4)/4.} for i,id in enumerate(vertices)},'integer_attributes':integers}
suite['mesh_assets']={'mesh_a':asset([[0.,0.,0.],[2.25,0.,0.],[2.5,1.5,.125],[.25,1.75,0.],[4.5,.25,-.25],[4.75,1.5,0.]],[[0,1,2,3],[1,4,5,2]]),'mesh_b':asset([[-1.25,-.5,.25],[.5,-.75,.5],[1.75,.25,0.],[1.5,1.5,.25],[0.,2.,.375],[-1.5,1.,.125]],[[0,1,2,3,4,5]]),'mesh_outside':asset([[9.,0.,0.],[10.,0.,0.],[9.,1.,0.]],[[0,1,2]])}
def frame(t,r,s):return {'translation':t,'rotation':{'kind':'euler','angles':r,'order':'yzx'},'scale':s,'precision':'f32'}
identity=frame([0.,0.,0.],[0.,0.,0.],[1.,1.,1.])
suite['entity_frames']={'identity':{id:{'parent':None,'transform':identity} for id in ['parent','a','b','alias','untouched']},'noncommuting':{'parent':{'parent':None,'transform':frame([1.125,-.75,.625],[.31,-.47,.19],[1.2,.7,1.6])},'a':{'parent':'parent','transform':frame([.25,-.5,.75],[.13,.23,-.37],[-.8,1.3,.9])},'b':{'parent':None,'transform':frame([-2.25,.75,1.125],[-.29,.41,.17],[.7,1.2,1.6])},'alias':{'parent':None,'transform':frame([3.25,-1.5,.375],[.37,-.19,.23],[1.1,-.9,.8])},'untouched':{'parent':None,'transform':frame([7.,2.,-.5],[.11,.07,-.13],[.9,.8,1.1])}}}
suite['authoring_context']={'cursor_location':[-2.125,1.375,.625],'cursor_rotation':[.17,-.23,.31]};suite['units']={'unit_system':'NONE','unit_scale_length':1.0}
suite['materials']={'mat0':{'base_color':[.8,.3,.2,1.],'roughness':.5,'metallic':0.},'mat1':{'base_color':[.2,.4,.9,1.],'roughness':.7,'metallic':0.}}
suite['product_implementation_change']=False
suite['native_adapter_ready']=False
suite['remaining_before_source_capture']=['native creation adapter with independently derived alias/edit-object setup rules','full initial-state binding and typed history selection adapter','source repeat checker and corruption controls','before-code capture contract and immutable input seal']
suite['future_product_performance_proposal']={'two_class_A_grids_vertices_each':10201,'edges_each':20200,'quads_each':10000,'forms':10,'samples_each':3,'maximum_core_ms':500,'maximum_operation_save_reload_ms':4000,'basis':'two existing class-A budgets of 250/2000 ms; freeze full attributed inputs and source results before a Rust multi-data extension; no timing result is claimed'}
for name,mesh in suite['mesh_assets'].items():
 assert all(len(v)==3 for v in mesh['vertices'].values())
 for values in mesh['integer_attributes'].values():
  for layer in values.values():assert all(-(2**31)<=v<2**31 for v in layer.values())
raw=(json.dumps(suite,indent=2)+'\n').encode();target=HERE/'authored-inputs-v2.json';assert not target.exists();target.write_bytes(raw)
print(json.dumps({'authored_context_rows':len(suite['runs']),'independent_mesh_inputs':3,'native_adapter_ready':False,'native_execution':'unrun','suite_sha256':hashlib.sha256(raw).hexdigest()}))
