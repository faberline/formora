#!/usr/bin/env python3
"""Check authored transform inputs, independent geometry rules and process repeats."""
import argparse
import copy
import json
import math
from pathlib import Path
from compare_selection_reference import load, digest, require, validate_state, bind_initial_state

STATE_KEYS=['geometry','groups','selected','hidden','mode','history','active_face']
def selection(state):return {key:state[key] for key in STATE_KEYS}
def near(a,b,tolerance=1e-6,message='numeric value differs'):
    require(len(a)==len(b) and all(abs(x-y)<=tolerance for x,y in zip(a,b)),message)
def finite(value):
    if isinstance(value,dict):
        for v in value.values():finite(v)
    elif isinstance(value,list):
        for v in value:finite(v)
    elif type(value) in [int,float]:require(math.isfinite(value),'non-finite reference value')


def tree(a,b,tolerance=1e-6,path=''):
    if isinstance(a,dict):
        require(isinstance(b,dict) and set(a)==set(b),'fields differ: '+path)
        for key in a:tree(a[key],b[key],tolerance,path+'/'+key)
    elif isinstance(a,list):
        require(isinstance(b,list) and len(a)==len(b),'array length differs: '+path)
        for i,(x,y) in enumerate(zip(a,b)):tree(x,y,tolerance,path+'/'+str(i))
    elif type(a) in [int,float] and type(b) in [int,float]:require(abs(a-b)<=tolerance,'numeric mismatch: '+path)
    else:require(type(a) is type(b) and a==b,'value differs: '+path)


def rotation(q):
    w,x,y,z=q
    return [[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
            [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
            [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]


def validate(run,data,suite):
    require(data['run_id']==run['id'] and data['operator']==run['operator'],'run identity differs')
    require(data['parameters']==run['parameters'] and data['context']==run['context'],'operation inputs differ')
    require(data['repeat_policy']==run['repeat_policy'],'repeat policy differs')
    finite(data);mesh=copy.deepcopy(suite['mesh'])
    if run['context'].get('hide_all'):mesh['hidden']={key:list(range(len(mesh[key]))) for key in ['vertices','edges','faces']}
    before,after=data['before'],data['after']
    for state in [before,after]:
        validate_state(selection(state))
        g=state['geometry'];require(set(state['world_vertices'])==set(g['vertices']),'world vertex IDs differ')
        require(set(state['normals'])=={'faces','corners'},'normal fields differ')
        for key in ['faces','corners']:require(set(state['normals'][key])==set(g['faces']),'normal face IDs differ')
        for id,face in g['faces'].items():
            require(len(state['normals']['faces'][id])==3,'normal size differs')
            require(len(state['normals']['corners'][id])==len(face),'corner normal count differs')
            require(all(len(n)==3 for n in state['normals']['corners'][id]),'corner normal size differs')
        view=state['environment'];r=rotation(view['view_rotation'])
        for i in range(3):near(view['view_matrix'][i][:3],[r[j][i] for j in range(3)],message='stale viewport matrix')
    bind_initial_state(mesh,run,selection(before))
    # A complete independent selection closure, not merely inclusion of the seed.
    g=before['geometry'];domain=run['seed']['domain'];prefix={'VERT':'v','EDGE':'e','FACE':'f'}[domain]
    seeds={prefix+f'{i:06}' for i in run['seed']['indices']};v=set();e=set();f=set()
    if domain=='VERT':
        v=seeds;e={id for id,pair in g['edges'].items() if set(pair)<=v};f={id for id,face in g['faces'].items() if set(face)<=v}
    elif domain=='EDGE':
        e=seeds;v={id for edge in e for id in g['edges'][edge]};pairs={tuple(g['edges'][id]) for id in e}
        f={id for id,face in g['faces'].items() if all(tuple(sorted(pair)) in pairs for pair in zip(face,face[1:]+face[:1]))}
    else:
        f=seeds;v={id for face in f for id in g['faces'][face]};pairs={tuple(sorted(pair)) for id in f for face in [g['faces'][id]] for pair in zip(face,face[1:]+face[:1])};e={id for id,pair in g['edges'].items() if tuple(pair) in pairs}
    require(before['selected']=={'VERT':sorted(v),'EDGE':sorted(e),'FACE':sorted(f)},'authored selection closure differs')
    profile=suite['profiles'][run['context']['profile']]
    for field in ['location','rotation','scale']:near(before['objects']['target'][field],profile[field],message='authored object frame differs')
    for field in ['cursor_location','cursor_rotation','view_location']:near(before['environment'][field],suite['environment'][field],message='authored environment differs')
    require(before['environment']['pivot']==run['context']['pivot'],'authored pivot differs')
    for key in ['edges','faces','face_smooth','face_materials','edge_seams','material_slots','uv_layer_order','active_uv_index']:
        require(g[key]==after['geometry'][key],'transform changed preserved topology/attribute: '+key)
    for key in ['groups','selected','hidden','mode','history','active_face','objects','environment']:
        require(before[key]==after[key],'transform changed unrelated state: '+key)
    if not run['context']['correct_face_attributes']:require(g['uv_layers']==after['geometry']['uv_layers'],'UVs changed with correction disabled')
    for id in before['hidden']['VERT']:require(g['vertices'][id]==after['geometry']['vertices'][id],'hidden vertex moved')
    status=data['result']['status'];require(status in [['FINISHED'],['CANCELLED'],['ERROR']],'unknown source result')
    if status!=['FINISHED']:require(before==after,'cancelled/rejected operation changed state')
    if status==['ERROR']:require(run['label']=='singular target' and bool(data['result']['error']),'unexpected source error')
    return analytic(run,data)


def analytic(run,data):
    p=run['parameters'];c=run['context'];before=data['before'];after=data['after'];g=before['geometry']
    if data['result']['status']!=['FINISHED']:return 0
    if c['profile']!='identity' or p.get('orient_type','GLOBAL')!='GLOBAL' or 'orient_matrix' in p or c['mirror_x'] or c['correct_face_attributes']:return 0
    if p.get('use_proportional_edit'):
        if run['operator']!='translate' or p.get('use_proportional_connected') or p.get('proportional_edit_falloff')=='RANDOM':return 0
        selected=before['selected']['VERT'];require(len(selected)==1,'proportional oracle needs one authored seed');center=g['vertices'][selected[0]]
        r=rotation(before['environment']['view_rotation']);normal=[r[i][2] for i in range(3)];radius=p['proportional_size']
        for id,point in g['vertices'].items():
            delta=[point[i]-center[i] for i in range(3)]
            if p.get('use_proportional_projected'):
                depth=sum(x*y for x,y in zip(delta,normal));delta=[delta[i]-depth*normal[i] for i in range(3)]
            distance=math.sqrt(sum(v*v for v in delta));d=max(0.,1-distance/radius);falloff=p.get('proportional_edit_falloff','SMOOTH')
            factor={'SMOOTH':min(1.,3*d*d-2*d*d*d),'SPHERE':math.sqrt(2*d-d*d),'ROOT':math.sqrt(d),'INVERSE_SQUARE':d*(2-d),'SHARP':d*d,'LINEAR':d,'CONSTANT':1. if distance<=radius else 0.}[falloff]
            if id in selected:factor=1.
            if id in before['hidden']['VERT']:factor=0.
            near(after['geometry']['vertices'][id],[point[i]+p['value'][i]*factor for i in range(3)],message='independent proportional translation differs')
        return 1
    selected=before['selected']['VERT'];mask=p.get('constraint_axis',[False]*3)
    if run['operator']!='translate' and (c['pivot']!='MEDIAN_POINT' or 'center_override' in p or any(mask)):return 0
    center=[sum(g['vertices'][id][j] for id in selected)/len(selected) for j in range(3)]
    for id,point in g['vertices'].items():
        expected=list(point)
        if id in selected:
            # EXEC numeric values are final. The source applies the orientation
            # matrix without clipping this vector to the interactive axis mask.
            if run['operator']=='translate':expected=[point[j]+p['value'][j] for j in range(3)]
            elif run['operator']=='resize':expected=[center[j]+(point[j]-center[j])*p['value'][j] for j in range(3)]
            else:
                angle=p['value'];x,y=point[0]-center[0],point[1]-center[1]
                expected=[center[0]+math.cos(angle)*x-math.sin(angle)*y,center[1]+math.sin(angle)*x+math.cos(angle)*y,point[2]]
        near(after['geometry']['vertices'][id],expected,message='independent basic transform differs')
    return 1


def stochastic(run,data):
    before=data['before'];after=data['after'];points=before['world_vertices'];selected=before['selected']['VERT'];center=[sum(points[id][j] for id in selected)/len(selected) for j in range(3)];p=run['parameters'];checks=0
    for id,point in points.items():
        actual=after['world_vertices'][id]
        if run['operator']=='rotate':
            x,y=point[0]-center[0],point[1]-center[1];u,v=actual[0]-center[0],actual[1]-center[1]
            # Bound support componentwise through an inferred rotation angle.
            angle=math.atan2(x*v-y*u,x*u+y*v) if x*x+y*y>1e-14 else 0.
            require(-1e-6<=angle<=p['value']+1e-6,'random angle outside support')
            expected=[center[0]+math.cos(angle)*x-math.sin(angle)*y,center[1]+math.sin(angle)*x+math.cos(angle)*y,point[2]]
        else:
            delta=p['value'] if run['operator']=='translate' else [(point[j]-center[j])*(p['value'][j]-1) for j in range(3)]
            axis=max(range(3),key=lambda j:abs(delta[j]));factor=(actual[axis]-point[axis])/delta[axis] if abs(delta[axis])>1e-12 else 0.
            require(-1e-6<=factor<=1+1e-6,'random influence outside support')
            expected=[point[j]+delta[j]*factor for j in range(3)]
        near(actual,expected,message='random result leaves requested transform path');checks+=1
    return checks


def compare(suite,reference,repeat,suite_sha):
    a=load(reference/'manifest.json');b=load(repeat/'manifest.json')
    require(a['process_id']!=b['process_id'],'reference processes are not independent')
    expected_version=suite['reference']['version'];expected_build=suite['reference']['build_hash']
    runs=suite['runs'];records=[];analytic_checks=stochastic_checks=0
    root=Path(__file__).resolve().parents[1];build_pin=load(root/'baseline/reference/builds/blender-5.2.3/report.json')
    executable_sha=build_pin['files'][build_pin['entry_executable']]['sha256']
    for folder,m in [(reference,a),(repeat,b)]:
        require(m['scope']=='complete_1191_authored_transform_cases','focused capture cannot accept the suite')
        require(m['version']==expected_version and m['build_hash']==expected_build,'reference build differs')
        require(m['binary_sha256']==executable_sha,'reference executable pin differs')
        require(m['suite_sha256']==suite_sha,'suite pin differs')
        require(m['adapter_sha256']==digest(Path(__file__).with_name('blender_transform_reference.py')),'adapter pin differs')
        require(m['base_adapter_sha256']==digest(Path(__file__).with_name('blender_selection_reference.py')),'base adapter pin differs')
        require(m['operator_properties_sha256']==digest(folder/'operator-properties.json'),'parameter metadata hash differs')
        require([r['id'] for r in m['runs']]==[r['id'] for r in runs],'captured run IDs differ')
    require(a['binary_sha256']==b['binary_sha256'],'reference executable differs')
    tree(load(reference/'operator-properties.json'),load(repeat/'operator-properties.json'),0.)
    for run,ra,rb in zip(runs,a['runs'],b['runs']):
        captures=[]
        for folder,record in [(reference,ra),(repeat,rb)]:
            require(record['file']==run['id']+'.json','capture path differs')
            path=folder/record['file'];require(digest(path)==record['sha256'],'capture hash differs')
            data=load(path);require(record['status']==data['result']['status'] and record['repeat_policy']==data['repeat_policy'],'manifest outcome differs')
            analytic_checks+=validate(run,data,suite);captures.append(data)
        first,second=captures;tree(first['before'],second['before'])
        require(first['result']==second['result'],'reference outcomes differ')
        if run['repeat_policy']=='deterministic':tree(first['after'],second['after'])
        else:
            for capture in captures:stochastic_checks+=stochastic(run,capture)
        records.append({'id':run['id'],'status':'checked','repeat_policy':run['repeat_policy'],'source_result':first['result']['status']})
    return {'passed':True,'scope':'source reference and finite analytic checks only','runs':records,'cases':len(records),'analytic_checks':analytic_checks,
            'stochastic_vertex_path_checks':stochastic_checks,'reference_process_ids':[a['process_id'],b['process_id']],
            'random_sequence_or_distribution_acceptance':'unrun','product_acceptance':'unrun','full_feature_acceptance':'unrun'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('suite',type=Path);p.add_argument('reference',type=Path);p.add_argument('repeat',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    suite=load(args.suite)
    result=compare(suite,args.reference,args.repeat,digest(args.suite));args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='runs'}))
