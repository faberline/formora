#!/usr/bin/env python3
"""Execute authored selection requests in Rust. Never import reference selection flags."""
import argparse
import asyncio
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from runtime_binary import resolve_binary
import subprocess
import tempfile

from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from compare_selection_reference import compare_run, load

DOMAINS={'VERT':'vertex','EDGE':'edge','FACE':'face'}


@contextmanager
def native(binary,scene):
    process=subprocess.Popen([str(binary),'scene','serve','--scene',str(scene)],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    sequence=0
    def call(name,arguments):
        nonlocal sequence
        sequence+=1
        process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':arguments})+'\n')
        process.stdin.flush()
        line=process.stdout.readline()
        assert line, 'native server ended before its response'
        value=json.loads(line);assert value['id']==sequence
        return (value['result'],False) if value['ok'] else ({'error':value['error']},True)
    try:
        yield call
    finally:
        process.stdin.close()
        process.wait(timeout=10)
        error=process.stderr.read();process.stdout.close();process.stderr.close()
        assert process.returncode==0,error


def ids(indices,prefix):
    return [f'{prefix}{i:06}' for i in indices]


def face(id):
    return {'kind':'polygon','id':id}


def initial(mesh,run):
    vertices={id:point for id,point in zip(ids(range(len(mesh['vertices'])),'v'),mesh['vertices'])}
    edges={id:ids(pair,'v') for id,pair in zip(ids(range(len(mesh['edges'])),'e'),mesh['edges'])}
    polygons={f'f{i:06}':{'vertices':ids(vertices,'v'),
              'uv_layers':{layer['name']:layer['faces'][i] for layer in mesh['uv_layers']},
              'normal':None,'corner_normals':None,'smooth':mesh['face_smooth'][i],
              'material_slot':mesh['face_materials'][i]}
              for i,vertices in enumerate(mesh['faces'])}
    groups=mesh['group_scenarios'][run['groups']]
    asset={'vertices':vertices,'edges':edges,'polygons':polygons,'triangles':{},
           'material_slots':mesh['material_slots'],
           'uv_layout':{'layers':[layer['name'] for layer in mesh['uv_layers']],
                        'active':mesh['uv_layers'][mesh['active_uv_index']]['name']},
           'vertex_groups':groups['names'],
           'edge_seams':ids([i for i,on in enumerate(mesh['edge_seams']) if on],'e')}
    if groups['weights']:
        asset['vertex_weights']=groups['weights']
    selected={'vertices':[],'edges':[],'faces':[]}
    domain=run['seed']['domain']
    names=ids(run['seed']['indices'],{'VERT':'v','EDGE':'e','FACE':'f'}[domain])
    selected[{'VERT':'vertices','EDGE':'edges','FACE':'faces'}[domain]]=[face(n) for n in names] if domain=='FACE' else names
    history=[{'domain':DOMAINS[domain],**({'face':face(n)} if domain=='FACE' else {'id':n})} for n in names]
    editing={'mode':[DOMAINS[d] for d in run['initial_mode']], 'selected':selected,
             'hidden':{'vertices':ids(mesh['hidden']['vertices'],'v'),
                       'edges':ids(mesh['hidden']['edges'],'e'),
                       'faces':[face(n) for n in ids(mesh['hidden']['faces'],'f')]},
             'history':history,'active_face':face(names[-1]) if names and domain=='FACE' else None}
    commands=[{'operation':'set_material','id':name,'material':{'base_color':[0.4,0.6,0.8,1],
               'roughness':0.6,'metallic':0}} for name in mesh['material_slots']]
    commands.extend([{'operation':'set_mesh_asset','id':'selection','asset':asset},
                     {'operation':'set_mesh_editing','id':'selection','editing':editing}])
    return {'expected_revision':0,'commands':commands}


def selector(run):
    p=run['parameters'];op=run['operator']
    comparison={'LESS':'less','EQUAL':'equal','GREATER':'greater','NOTEQUAL':'not_equal'}
    if op=='select_mode':
        return {'kind':'mode','domain':DOMAINS[p['type']],'action':p.get('action','TOGGLE').lower(),
                'extend':p.get('use_extend',False),'expand':p.get('use_expand',False)}
    if op=='select_non_manifold':
        return {'kind':'non_manifold','extend':p['extend'],'wire':p['use_wire'],'boundary':p['use_boundary'],
                'multiple_faces':p['use_multi_face'],'non_contiguous':p['use_non_contiguous'],'vertices':p['use_verts']}
    if op=='select_loose': return {'kind':'loose',**p}
    if op=='select_interior_faces': return {'kind':'interior_faces'}
    if op=='select_face_by_sides': return {'kind':'faces_by_sides','count':p['number'],'comparison':comparison[p['type']],'extend':p['extend']}
    if op=='select_by_pole_count': return {'kind':'poles','count':p['pole_count'],'comparison':comparison[p['type']],'extend':p['extend'],'exclude_nonmanifold':p['exclude_nonmanifold']}
    if op=='select_ungrouped': return {'kind':'ungrouped',**p}
    raise ValueError('unknown authored selector')


def snapshot(query):
    asset=query['mesh_asset'];editing=asset['editing'];polygons=asset['polygons'];layout=asset['uv_layout']
    def faces(values):
        assert all(v['kind']=='polygon' for v in values)
        return sorted(v['id'] for v in values)
    def sets(value):
        return {'VERT':value['vertices'],'EDGE':value['edges'],'FACE':faces(value['faces'])}
    history=[{'domain':next(k for k,v in DOMAINS.items() if v==entry['domain']),
              'id':entry['face']['id'] if entry['domain']=='face' else entry['id']}
             for entry in editing['history']]
    return {'geometry':{'vertices':asset['vertices'],'edges':{id:sorted(pair) for id,pair in asset['edges'].items()},
             'faces':{id:p['vertices'] for id,p in polygons.items()},'face_smooth':{id:p['smooth'] for id,p in polygons.items()},
             'face_materials':{id:p['material_slot'] for id,p in polygons.items()},
             'edge_seams':{id:id in asset.get('edge_seams',[]) for id in asset['edges']},
             'material_slots':asset['material_slots'],
             'uv_layers':{name:{id:p['uv_layers'][name] for id,p in polygons.items()} for name in layout['layers']},
             'uv_layer_order':layout['layers'],'active_uv_index':layout['layers'].index(layout['active'])},
            'groups':{'names':asset.get('vertex_groups',[]),
                      'weights':{id:asset.get('vertex_weights',{}).get(id,{}) for id in asset['vertices']}},
            'mode':[key for key,value in DOMAINS.items() if value in editing['mode']],
            'selected':sets(editing['selected']),'hidden':sets(editing['hidden']),
            'history':history,'active_face':None if editing['active_face'] is None else editing['active_face']['id']}


def canonical_comparison(reference,candidate):
    # Native API error text differs from bpy. Compare its actual semantic code;
    # retain both raw messages in the saved data. Every state field remains exact.
    r,c=copy.deepcopy(reference),copy.deepcopy(candidate)
    for data in [r,c]:
        if data['result']['status']==['POLL_REJECTED']:
            data['result']['error']='semantic_error:'+data['result']['outcome']
    compare_run(r,c)


def outcome(value,error):
    if error:
        for code in ['invalid_selection_domain','missing_vertex_weights']:
            if value['error'].startswith(code+':'):
                return {'status':['POLL_REJECTED'],'error':value['error'],'outcome':code}
        raise ValueError('unexpected Rust failure: '+str(value))
    receipt=value['selection']
    assert len(receipt)==1 and receipt[0]['mesh_asset']=='selection' and receipt[0]['command_index']==0
    result=receipt[0]['outcome'];assert result in ['completed','unchanged']
    return {'status':['FINISHED' if result=='completed' else 'CANCELLED'],'error':None,'outcome':result}


async def run(binary,output,interfaces):
    root=Path(__file__).resolve().parents[1];suite=load(root/'baseline/fixtures/mesh-selection.json')
    reference=root/'baseline/reference/blender-5.2.3/mesh-selection'
    output.mkdir(parents=True,exist_ok=False);records=[]
    def cli(scene,action,*args,request=None):
        p=subprocess.run([str(binary),'scene',action,'--scene',str(scene),*map(str,args)],
                         input=None if request is None else json.dumps(request),capture_output=True,text=True)
        return json.loads(p.stdout),p.returncode!=0
    with tempfile.TemporaryDirectory(prefix='formora-selection-runtime-') as folder:
        for interface in interfaces:
            for index,case in enumerate(suite['runs']):
                scene=Path(folder)/(interface+'-'+case['id']+'.json')
                value,error=cli(scene,'init');assert not error
                setup=initial(suite['mesh'],case)
                request={'expected_revision':1,'commands':[{'operation':'select_mesh','id':'selection','selector':selector(case)}]}
                if interface=='cli':
                    value,error=cli(scene,'apply','--request','-',request=setup);assert not error,value
                    before_query,error=cli(scene,'inspect','--mesh-asset','selection');assert not error
                    before=snapshot(before_query);saved_before=scene.read_bytes()
                    with native(binary,scene) as call:
                        result,error=call('scene_apply',request)
                        after_query,query_error=call('scene_inspect',{'mesh_asset':'selection'});assert not query_error
                        observed=outcome(result,error);after=snapshot(after_query)
                        if error:
                            assert scene.read_bytes()==saved_before
                            undone,undo_error=call('scene_undo',{'expected_revision':1})
                            assert undo_error and undone['error']=='nothing to undo'
                            assert scene.read_bytes()==saved_before
                        else:
                            undone,undo_error=call('scene_undo',{'expected_revision':2});assert not undo_error
                            restored,query_error=call('scene_inspect',{'mesh_asset':'selection'});assert not query_error
                            assert restored['mesh_asset']==before_query['mesh_asset']
                            again={**request,'expected_revision':3}
                            reapplied,apply_error=call('scene_apply',again);assert not apply_error
                            assert outcome(reapplied,False)==observed
                    # Verify the one-shot CLI route as well as persistent CLI undo.
                    current,query_error=cli(scene,'inspect','--mesh-asset','selection');assert not query_error
                    reset={'expected_revision':current['revision'],'commands':[setup['commands'][-1]]}
                    reset_result,reset_error=cli(scene,'apply','--request','-',request=reset);assert not reset_error
                    restored,query_error=cli(scene,'inspect','--mesh-asset','selection');assert not query_error
                    assert restored['mesh_asset']==before_query['mesh_asset']
                    reset_bytes=scene.read_bytes()
                    echo={**request,'expected_revision':reset_result['revision']}
                    echoed,echo_error=cli(scene,'apply','--request','-',request=echo)
                    assert outcome(echoed,echo_error)==observed
                    if echo_error:assert scene.read_bytes()==reset_bytes
                else:
                    parameters=StdioServerParameters(command=str(binary),args=['mcp','--scene',str(scene)])
                    async with stdio_client(parameters) as (reader,writer):
                        async with ClientSession(reader,writer,read_timeout_seconds=10) as client:
                            await client.initialize();tools=await client.list_tools()
                            schema=next(tool.input_schema for tool in tools.tools if tool.name=='scene_apply')
                            Draft202012Validator(schema).validate(setup)
                            initialized=await client.call_tool('scene_apply',setup);assert not initialized.is_error
                            inspected=await client.call_tool('scene_inspect',{'mesh_asset':'selection'});assert not inspected.is_error
                            before_query=inspected.structured_content;before=snapshot(before_query)
                            saved_before=scene.read_bytes()
                            Draft202012Validator(schema).validate(request)
                            applied=await client.call_tool('scene_apply',request)
                            error=applied.is_error
                            result={'error':applied.content[0].text} if error else applied.structured_content
                            observed=outcome(result,error)
                            queried=await client.call_tool('scene_inspect',{'mesh_asset':'selection'});assert not queried.is_error
                            after_query=queried.structured_content;after=snapshot(after_query)
                            if error:
                                assert scene.read_bytes()==saved_before
                                undone=await client.call_tool('scene_undo',{'expected_revision':1})
                                assert not undone.is_error
                                empty=await client.call_tool('scene_inspect',{});assert not empty.is_error
                                assert not empty.structured_content['scene'].get('mesh_assets',{})
                                assert not empty.structured_content['scene']['materials']
                                restored_setup={**setup,'expected_revision':2}
                                restored=await client.call_tool('scene_apply',restored_setup);assert not restored.is_error
                            else:
                                undone=await client.call_tool('scene_undo',{'expected_revision':2});assert not undone.is_error
                                restored=await client.call_tool('scene_inspect',{'mesh_asset':'selection'});assert not restored.is_error
                                assert restored.structured_content['mesh_asset']==before_query['mesh_asset']
                                again={**request,'expected_revision':3}
                                reapplied=await client.call_tool('scene_apply',again);assert not reapplied.is_error
                                assert outcome(reapplied.structured_content,False)==observed
                reloaded,query_error=cli(scene,'inspect','--mesh-asset','selection');assert not query_error
                assert snapshot(reloaded)==after
                candidate={'run_id':case['id'],'operator':case['operator'],'parameters':case['parameters'],
                           'before':before,'after':after,'result':observed,'expected_negative':error}
                file=interface+'-'+case['id']+'.json';path=output/file
                path.write_text(json.dumps(candidate,sort_keys=True,allow_nan=False)+'\n')
                try:
                    canonical_comparison(load(reference/(case['id']+'.json')),candidate)
                    status='passed';message=None
                except Exception as e:
                    status='failed';message=str(e)
                records.append({'id':case['id'],'interface':interface,'status':status,'error':message,
                                'file':file,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                'reload_checked':True,'undo_checked':True,
                                'one_shot_cli_checked':interface=='cli','rejection_unchanged':error})
                if (index+1)%50==0:print(json.dumps({'interface':interface,'executed':index+1,'failed':sum(r['status']=='failed'for r in records)}),flush=True)
    passed=all(r['status']=='passed'for r in records)
    report={'passed':passed,'interfaces':interfaces,'runs':records,'checks':len(records),
            'required_full_interfaces':interfaces==['cli','official_mcp_sdk'],
            'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'source_files_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted([root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*')if p.is_file()]])},
            'adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'full_feature_acceptance':'unrun','product_milestone_acceptance':'unrun'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':passed,'checks':len(records),'failures':sum(r['status']=='failed'for r in records)}),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--interface',choices=['cli','both'],default='both')
    args=parser.parse_args()
    asyncio.run(run(resolve_binary(args.binary),args.output.resolve(),['cli'] if args.interface=='cli' else ['cli','official_mcp_sdk']))
