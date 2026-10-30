#!/usr/bin/env python3
"""Author multi-data merge inputs without reading native or product answers."""
from itertools import product
from pathlib import Path
import argparse
import json


def author():
    contexts=[{'id':'active_a','active':'a','order':['parent','a','b','alias','untouched']},{'id':'active_alias','active':'alias','order':['parent','b','a','alias','untouched']},{'id':'active_b_a_first','active':'b','order':['parent','a','alias','b','untouched']},{'id':'active_b_alias_first','active':'b','order':['parent','alias','a','b','untouched']}]
    modes=[['VERT'],['EDGE'],['FACE'],['VERT','EDGE'],['VERT','FACE'],['EDGE','FACE'],['VERT','EDGE','FACE']]
    selections=['both','active_empty','other_empty','neither'];histories=['both_vertex','active_first_only','active_last_only','active_none','other_none','both_reverse'];methods=['CENTER','CURSOR','COLLAPSE','FIRST','LAST']
    runs=[]
    for context,selection,history,method,uvs,mode,frame in product(contexts,selections,histories,methods,[False,True],modes,['identity','noncommuting']):
     available=method not in ['FIRST','LAST'] or ('VERT' in mode and selection in ['both','other_empty'] and history!='active_none' and not (method=='FIRST' and history=='active_last_only') and not (method=='LAST' and history=='active_first_only'))
     runs.append({'id':f'multi_merge_{len(runs):05}','context':context['id'],'selection':selection,'history':history,'parameters':{'type':method,'uvs':uvs},'mode':mode,'frame':frame,'expected_enum_unavailable':not available})
    assert len(runs)==13440 and len({r['id'] for r in runs})==13440
    assert sum(r['expected_enum_unavailable'] for r in runs)==4352
    suite={'schema_version':1,'scope':'authored multi-independent-data merge contexts; native execution unrun','source_commit':'e13b728c6880d3084d9d57c30031ed5df8b39dee','contexts':contexts,'data_sharing':{'a':'mesh_a','alias':'mesh_a','b':'mesh_b','untouched':'mesh_outside'},'active_edit_data':['mesh_a','mesh_b'],'outside_edit_data':['mesh_outside'],'selection_rule':'select the whole data mesh or none; flush by the declared mask; empty selection has empty history','history_rule':'use selected vertex/edge/face endpoints; vertex endpoints permit FIRST/LAST only when VERT mode is enabled; opposite endpoint uses a selected edge for first-only/last-only; other_none affects only the other data mesh','comparison':{'positions_metres':1e-6,'normals':1e-6,'matrices':1e-6,'uv':1e-6,'weights':1e-6,'discrete':'exact'},'expected_cases':13440,'expected_enum_unavailable':4352,'expected_operator_finished':9088,'product_acceptance':'unrun','native_execution':'unrun','runs':runs}
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
    # Readiness belongs to capture evidence. Input bytes stay frozen across runs.
    for key in ['native_execution', 'native_adapter_ready', 'remaining_before_source_capture', 'product_acceptance', 'product_implementation_change']:
        suite.pop(key, None)
    suite['scope'] = 'authored_multi_independent_data_merge_inputs'
    suite['input_snapshot'] = 'before_native_execution_and_before_Rust_multi_data_extension'
    return suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = author()
    with args.output.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'authored_context_rows': len(value['runs']), 'native_execution': 'unrun', 'measured_outputs_read': False}))
