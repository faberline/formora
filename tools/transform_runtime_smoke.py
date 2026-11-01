#!/usr/bin/env python3
"""Run the complete authored transform suite in Rust. Partial captures never accept it."""
import argparse
import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
from runtime_binary import resolve_binary
import struct
import subprocess
import tempfile
from runtime_artifacts import write_json

from compare_transform_reference import compare as verify_source, digest, load, tree, stochastic
from normal_runtime_smoke import asset_from_case
from transform_source_policy import POLICY, undefined_rotation, require_rejection

DOMAINS={'VERT':'vertex','EDGE':'edge','FACE':'face'}
PIVOTS={'MEDIAN_POINT':'median','BOUNDING_BOX_CENTER':'bounds','CURSOR':'cursor','ACTIVE_ELEMENT':'active','INDIVIDUAL_ORIGINS':'individual'}
RUNTIME_KEYS={'geometry','groups','selected','hidden','mode','history','active_face','normals','world_vertices','active_material_index'}


def f32(v):return struct.unpack('<f',struct.pack('<f',v))[0]


def pose(profile):
    return {'translation':[f32(v) for v in profile['location']],
            'rotation':{'kind':'euler','angles':[f32(v) for v in profile['rotation']],'order':'xyz'},
            'scale':[f32(v) for v in profile['scale']],'precision':'f32'}


def quaternion(rotation):
    if isinstance(rotation,list):return rotation
    if rotation['kind']=='axis_angle':
        axis=rotation['axis'];scale=max(abs(v) for v in axis);axis=[v/scale for v in axis];length=math.sqrt(sum(v*v for v in axis))
        s,c=math.sin(rotation['radians']/2),math.cos(rotation['radians']/2)
        return [v/length*s for v in axis]+[c]
    assert rotation['kind']=='euler'
    (i,j,k),parity={'xyz':((0,1,2),False),'xzy':((0,2,1),True),'yxz':((1,0,2),True),
                     'yzx':((1,2,0),False),'zxy':((2,0,1),False),'zyx':((2,1,0),True)}[rotation.get('order','xyz')]
    e=rotation['angles'];si,ci=math.sin(e[i]/2),math.cos(e[i]/2);sj,cj=math.sin(e[j]*(-0.5 if parity else 0.5)),math.cos(e[j]*(-0.5 if parity else 0.5));sh,ch=math.sin(e[k]/2),math.cos(e[k]/2)
    cc,cs,sc,ss=ci*ch,ci*sh,si*ch,si*sh;q=[0.0]*4
    q[i]=cj*sc-sj*cs;q[j]=cj*ss+sj*cc;q[k]=cj*cs-sj*sc;q[3]=cj*cc+sj*ss
    if parity:q[j]=-q[j]
    return q


def setup(suite,run):
    mesh=copy.deepcopy(suite['mesh'])
    if run['context'].get('hide_all'):mesh['hidden']={key:list(range(len(mesh[key]))) for key in ['vertices','edges','faces']}
    asset=asset_from_case({'vertices':mesh['vertices'],'edges':mesh['edges'],'faces':mesh['faces'],
                          'smooth':mesh['face_smooth'],'kinds':['polygon']*len(mesh['faces']),
                          'seams':[i for i,on in enumerate(mesh['edge_seams']) if on]})
    asset['material_slots']=mesh['material_slots'];asset['active_material_index']=mesh['active_material_index']
    asset['uv_layout']={'layers':[l['name'] for l in mesh['uv_layers']],'active':mesh['uv_layers'][mesh['active_uv_index']]['name']}
    for i,polygon in enumerate(asset['polygons'].values()):
        polygon['material_slot']=mesh['face_materials'][i]
        polygon['uv_layers']={l['name']:l['faces'][i] for l in mesh['uv_layers']}
    groups=mesh['group_scenarios'][run['groups']];asset['vertex_groups']=groups['names']
    if groups['weights']:asset['vertex_weights']=groups['weights']
    domain=run['seed']['domain'];ids=[{'VERT':'v','EDGE':'e','FACE':'f'}[domain]+f'{i:06}' for i in run['seed']['indices']]
    face=lambda id:{'kind':'polygon','id':id}
    selected={'vertices':[],'edges':[],'faces':[]};selected[{'VERT':'vertices','EDGE':'edges','FACE':'faces'}[domain]]=[face(id) for id in ids] if domain=='FACE' else ids
    editing={'mode':[DOMAINS[d] for d in run['initial_mode']],'selected':selected,
             'hidden':{'vertices':[f'v{i:06}' for i in mesh['hidden']['vertices']],
                       'edges':[f'e{i:06}' for i in mesh['hidden']['edges']],
                       'faces':[face(f'f{i:06}') for i in mesh['hidden']['faces']]},
             'history':[{'domain':DOMAINS[domain],**({'face':face(id)} if domain=='FACE' else {'id':id})} for id in ids],
             'active_face':face(ids[-1]) if ids and domain=='FACE' else None}
    commands=[{'operation':'set_material','id':name,'material':{'base_color':[0.4,0.6,0.8,1],'roughness':0.6,'metallic':0}} for name in mesh['material_slots']]
    environment=suite['environment'];commands.append({'operation':'set_authoring_context','context':{key:environment[key] for key in ['cursor_location','cursor_rotation','view_rotation']}})
    profile=suite['profiles'][run['context']['profile']]
    if profile['parent'] is not None:
        commands.append({'operation':'create_entity','id':'parent','entity':{'name':'Parent','parent':None,'transform':pose(profile['parent']),'content':{'kind':'empty'}}})
    commands.extend([{'operation':'set_mesh_asset','id':'mesh','asset':asset},
                     {'operation':'set_mesh_editing','id':'mesh','editing':editing},
                     {'operation':'create_entity','id':'target','entity':{'name':'Target','parent':'parent' if profile['parent'] is not None else None,
                         'transform':pose(profile),'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}}}])
    return {'expected_revision':0,'commands':commands}


def request_for(run):
    p=run['parameters'];kind=run['operator'];mask=p.get('constraint_axis',[False]*3)
    assert set(p)<={'value','orient_type','orient_axis','mirror','use_proportional_edit','snap','constraint_axis','orient_matrix','orient_matrix_type','center_override','proportional_size','proportional_edit_falloff','use_proportional_connected','use_proportional_projected','use_accurate'}
    # use_accurate initializes mouse input only when the source has an input event.
    # This fixed suite uses numeric EXEC requests without an input event.
    assert not p.get('snap',False), 'snapping requires a separate implementation'
    orientation={'kind':p.get('orient_type','GLOBAL').lower()}
    # RNA reads a flat float array into Blender's column-major custom_matrix.
    if 'orient_matrix' in p:orientation={'kind':'custom','matrix':[list(column) for column in zip(*p['orient_matrix'])]}
    if kind=='rotate':
        # Numeric viewport rotation flips an unconstrained axis in the fixed source.
        change={'kind':'rotate','radians':p['value'] if any(mask) else -p['value'],'axis':p.get('orient_axis','Z').lower()}
    else:change={'kind':kind,'value':p['value']}
    transform={'entity':'target','change':change,'orientation':orientation,'pivot':PIVOTS[run['context']['pivot']],
               'constraint_axis':[False]*3 if kind in ['translate','resize'] else mask,
               'correct_face_attributes':run['context']['correct_face_attributes'],'keep_connected':run['context']['keep_connected']}
    if 'center_override' in p:
        # Source t_around_get disables individual/active setup for an explicit point.
        transform['center_override']=p['center_override'];transform['pivot']='bounds'
    if p.get('use_proportional_edit'):
        falloff=p.get('proportional_edit_falloff','SMOOTH').lower()
        transform['proportional']={'radius':p['proportional_size'],'falloff':falloff,
              'connected':p.get('use_proportional_connected',False),'projected':p.get('use_proportional_projected',False)}
        if falloff=='random':transform['proportional']['seed']=0x464f524d4f5241
    if run['context']['mirror_x'] and p.get('mirror',False):transform['mirror']={'axis':'x','topology':run['context']['mirror_topology']}
    return {'expected_revision':1,'commands':[{'operation':'transform_mesh','transform':transform}]}


def world(scene,id):
    entity=scene['entities'][id];t=entity['transform'];q=quaternion(t['rotation']);norm=math.sqrt(sum(v*v for v in q));x,y,z,w=[v/norm for v in q]
    r=[[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
       [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
       [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
    m=[[r[i][j]*t['scale'][j] for j in range(3)]+[t['translation'][i]] for i in range(3)]+[[0,0,0,1]]
    if entity['parent'] is not None:
        a=world(scene,entity['parent']);m=[[sum(a[i][k]*m[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    return m


def snapshot(query,scene,world_query):
    from selection_runtime_smoke import snapshot as selected_snapshot
    result=selected_snapshot(query)
    assert world_query['id']=='target' and world_query['entity']==scene['entities']['target']
    assert set(world_query['world_vertices'])==set(query['mesh_asset']['vertices'])
    result['normals']={'faces':{},'corners':{}}
    for f in query['normals']['faces']:
        assert f['face']['kind']=='polygon';id=f['face']['id'];result['normals']['faces'][id]=f['normal'];result['normals']['corners'][id]=f['corner_normals']
    result['world_vertices']=world_query['world_vertices']
    result['active_material_index']=query['mesh_asset'].get('active_material_index',0)
    return result


def check_receipt(result,request,before,after):
    assert len(result['transforms'])==1;receipt=result['transforms'][0]
    assert receipt['command_index']==0 and receipt['entity']=='target' and receipt['mesh_asset']=='mesh' and receipt['shared_instances']==['target']
    vertices=before['geometry']['vertices'];changed={id for id,p in vertices.items() if p!=after['geometry']['vertices'][id]}
    assert set(receipt['changed']['vertices'])==changed
    assert set(receipt['changed']['edges'])=={id for id,pair in before['geometry']['edges'].items() if changed & set(pair)}
    attribute_faces={id for id in before['geometry']['faces'] if any(before['geometry']['uv_layers'][layer][id]!=after['geometry']['uv_layers'][layer][id] for layer in before['geometry']['uv_layers'])}
    assert receipt.get('attribute_faces',[])==[{'kind':'polygon','id':id} for id in sorted(attribute_faces)]
    assert receipt['changed']['faces']==[{'kind':'polygon','id':id} for id,face in before['geometry']['faces'].items() if changed & set(face) or id in attribute_faces]
    assert set(receipt['centres_local'])==set(receipt['influence'])
    plane=set(receipt.get('mirror_plane_vertices',[]));sources=receipt.get('mirror_sources',{})
    assert changed<=set(receipt['influence'])|plane|set(sources)
    assert not (set(before['hidden']['VERT'])&(set(receipt['influence'])|plane|set(sources)|set(sources.values())))
    assert all(math.isfinite(w) and 0<w<=1 for w in receipt['influence'].values())
    assert all(receipt['influence'][id]==1 for id in before['selected']['VERT'])
    assert receipt['random_seed']==request['commands'][0]['transform'].get('proportional',{}).get('seed')
    for vector in [receipt['pivot_world'],*receipt['basis_world'],*receipt['centres_local'].values()]:assert len(vector)==3 and all(math.isfinite(v) for v in vector)
    transform=request['commands'][0]['transform']
    if 'mirror' in transform:
        axis='xyz'.index(transform['mirror']['axis'])
        assert all(abs(vertices[id][axis])<f32(0.00002) and after['geometry']['vertices'][id][axis]==0 for id in plane)
        for destination,source in sources.items():
            assert destination!=source and source not in sources
            expected=list(after['geometry']['vertices'][source]);expected[axis]*=-1
            assert after['geometry']['vertices'][destination]==expected
            if source in receipt['influence']:assert receipt['influence'][destination]==receipt['influence'][source]
    else:assert not plane and not sources
    if transform['orientation']['kind']=='normal' and transform['pivot']=='individual':
        assert set(receipt['component_basis_local'])==set(receipt['influence'])
        for matrix in receipt['component_basis_local'].values():
            assert len(matrix)==3 and all(len(row)==3 and all(math.isfinite(v) for v in row) for row in matrix)
    else:assert 'component_basis_local' not in receipt


def compare_output(run,reference,before,after,result,error,request):
    assert set(before)==set(after)==RUNTIME_KEYS, 'runtime snapshot fields are incomplete'
    keys=sorted(RUNTIME_KEYS)
    tree({k:reference['before'][k] for k in keys},before,path='before')
    if undefined_rotation(run):
        assert request==request_for(run), 'policy rejection request differs from the authored mapping'
        return require_rejection(run,request,before,after,result,error)
    if error is not None:
        assert error.strip()=='mesh transform has no visible selected vertices' and reference['result']['status']==['CANCELLED'],error
        assert before==after
        return {'source_outcome':'CANCELLED'}
    assert reference['result']['status']==['FINISHED']
    check_receipt(result,request,before,after)
    if run['repeat_policy']=='deterministic':tree({k:reference['after'][k] for k in keys},after,path='after')
    else:
        # Preserve actual attributes. Random vertex/normal values use the frozen path policy.
        for key in keys:
            if key not in ['geometry','normals','world_vertices']:tree(reference['after'][key],after[key],path=key)
        for key in after['geometry']:
            if key!='vertices':tree(reference['after']['geometry'][key],after['geometry'][key],path=key)
        stochastic(run,{'before':before,'after':after})
    return {'source_outcome':'FINISHED'}


async def run(binary,output,case_ids=(),interfaces=('cli','official_mcp_sdk'),gzip_output=False):
    from jsonschema import Draft202012Validator
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    root=Path(__file__).resolve().parents[1];suite_path=root/'baseline/fixtures/mesh-transform.json';suite=load(suite_path)
    reference=root/'baseline/reference/blender-5.2.3/mesh-transform';repeat=root/'baseline/reference/blender-5.2.3/mesh-transform-repeat'
    source_checked=verify_source(suite,reference,repeat,digest(suite_path));assert source_checked['passed']
    cases=suite['runs']
    if case_ids:assert set(case_ids)<={r['id'] for r in cases};cases=[r for r in cases if r['id'] in case_ids]
    paths=[root/'Cargo.toml',root/'Cargo.lock',*[p for name in ['src','tests','tools','baseline','docs/contracts'] for p in (root/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']]
    hashes={str(p.relative_to(root)):digest(p) for p in sorted(paths)};binary_sha=digest(binary)
    output.mkdir(parents=True,exist_ok=False);records=[]
    def cli(scene,action,*args,request=None):
        result=subprocess.run([str(binary),'scene',action,'--scene',str(scene),*args],input=None if request is None else json.dumps(request),capture_output=True,text=True)
        value=json.loads(result.stdout)
        if result.returncode==0:return value,None
        assert isinstance(value.get('error'),str) and value['error'],(result.stdout,result.stderr)
        return None,value['error']
    with tempfile.TemporaryDirectory(prefix='formora-transform-runtime-') as temporary:
        for interface in interfaces:
            for index,case in enumerate(cases):
                case_workspace=tempfile.TemporaryDirectory(prefix=interface+'-'+case['id']+'-',dir=temporary)
                scene=Path(case_workspace.name)/(interface+'-'+case['id']+'.json');initialized,error=cli(scene,'init');assert error is None
                create=setup(suite,case);request=request_for(case);policy_evidence={}
                async def exercise(call):
                    result,error=await call('scene_apply',create);assert error is None,(case['id'],error)
                    before_query,error=await call('scene_inspect',{'mesh_asset':'mesh','normals':True});assert error is None
                    before_scene,error=await call('scene_inspect',{});assert error is None
                    before_world,error=await call('scene_inspect',{'entity':'target','world':True});assert error is None
                    saved=scene.read_bytes();before=snapshot(before_query,before_scene['scene'],before_world)
                    result,error=await call('scene_apply',request)
                    after_query,inspect_error=await call('scene_inspect',{'mesh_asset':'mesh','normals':True});assert inspect_error is None
                    after_scene,inspect_error=await call('scene_inspect',{});assert inspect_error is None
                    after_world,inspect_error=await call('scene_inspect',{'entity':'target','world':True});assert inspect_error is None
                    assert before_scene['scene']['entities']==after_scene['scene']['entities']
                    if error is not None:
                        assert saved==scene.read_bytes() and before_scene==after_scene
                        if undefined_rotation(case):
                            policy_evidence.update({'before_scene':before_scene,'after_scene':after_scene,
                                'saved_scene_before_sha256':hashlib.sha256(saved).hexdigest(),
                                'saved_scene_after_sha256':digest(scene)})
                    else:assert after_query['revision']==2
                    return before,snapshot(after_query,after_scene['scene'],after_world),result,error,before_world,after_world
                if interface=='cli':
                    async def call(name,arguments):
                        if name=='scene_apply':return cli(scene,'apply','--request','-',request=arguments)
                        if 'entity' in arguments:return cli(scene,'inspect','--entity',arguments['entity'],'--world')
                        return cli(scene,'inspect',*(['--mesh-asset',arguments['mesh_asset'],'--normals'] if arguments else []))
                    before,after,result,error,before_world,after_world=await exercise(call)
                else:
                    parameters=StdioServerParameters(command=str(binary),args=['mcp','--scene',str(scene)])
                    async with stdio_client(parameters) as (reader,writer):
                        async with ClientSession(reader,writer,read_timeout_seconds=10) as client:
                            await client.initialize();schemas={t.name:t.input_schema for t in (await client.list_tools()).tools}
                            async def call(name,arguments):
                                Draft202012Validator(schemas[name]).validate(arguments)
                                response=await client.call_tool(name,arguments)
                                return (None,response.content[0].text) if response.is_error else (response.structured_content,None)
                            before,after,result,error,before_world,after_world=await exercise(call)
                try:comparison=compare_output(case,load(reference/(case['id']+'.json')),before,after,result,error,request);status='passed';failure=None
                except (AssertionError,ValueError,KeyError) as e:comparison={};status='failed';failure=str(e)
                path=output/(interface+'-'+case['id']+'.json');data={'case':case,'setup':create,'request':request,'before':before,'after':after,'world_queries':{'before':before_world,'after':after_world},'result':result,'error':error,'status':status,'comparison_error':failure}
                if undefined_rotation(case):data.update({'comparison_policy':comparison,'policy_evidence':policy_evidence})
                path=write_json(path,data,gzip_output)
                records.append({'id':case['id'],'interface':interface,'status':status,'error':failure,'file':path.name,'sha256':digest(path),'reference_sha256':digest(reference/(case['id']+'.json')),**comparison})
                case_workspace.cleanup()
                if (index+1)%50==0:print(json.dumps({'interface':interface,'executed':index+1,'failed':sum(r['status']=='failed' for r in records)}),flush=True)
    assert hashes=={str(p.relative_to(root)):digest(p) for p in sorted(paths)} and binary_sha==digest(binary),'capture inputs changed'
    full=not case_ids and set(interfaces)=={'cli','official_mcp_sdk'};passed=all(r['status']=='passed' for r in records)
    authored={case['id']:case for case in cases};defined=[r for r in records if r.get('comparison_kind')!=POLICY]
    report={'passed':passed,'checks':len(records),'scope':'full_1203_cases_both_interfaces' if full else 'focused_diagnostic',
            'required_full_gate_passed':full and passed and len(records)==2406,'binary_sha256':binary_sha,'input_hashes':hashes,'runs':records,
            'defined_deterministic_source_checks':sum(authored[r['id']]['repeat_policy']=='deterministic' for r in defined),
            'stochastic_support_checks':sum(authored[r['id']]['repeat_policy']!='deterministic' for r in defined),
            'approved_source_rejection_checks':len(records)-len(defined),
            'source_rejection_policy':'human-approved exact rejection, not a numeric source match',
            'source_reference_checked':source_checked,'product_acceptance':'unrun','three_platform_ci':'unrun','integrated_acceptance':'unrun'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['passed','checks','scope','required_full_gate_passed']}))
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--case',action='append',default=[],dest='case_ids');parser.add_argument('--interface',action='append',choices=['cli','official_mcp_sdk'])
    parser.add_argument('--gzip-output',action='store_true',help='retain exact raw JSON bytes in lossless gzip files')
    args=parser.parse_args();asyncio.run(run(resolve_binary(args.binary),args.output.resolve(),args.case_ids,args.interface or ('cli','official_mcp_sdk'),args.gzip_output))
