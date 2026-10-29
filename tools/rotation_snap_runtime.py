#!/usr/bin/env python3
"""Run all authored raw-rotation snaps through actual CLI and official MCP."""
import argparse
import asyncio
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from compare_snap_menu_reference import tree, floats
from compare_snap_rotation_reference import compare as verify_source
from runtime_artifacts import write_json
from scene_snap_runtime_smoke import setup as object_setup, request_for, mesh_snapshot, KEYS

ROOT=Path(__file__).resolve().parents[1]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())
def channel_input(value):
    value=floats(value);value['mode']=value['mode'].lower();return value


def setup(suite,case):
    """Read only authored data. Measured source state is never an input."""
    result=object_setup(suite,case)
    for command in result['commands']:
        if command['operation']=='create_entity':
            name=command['id'];t=command['entity']['transform']
            if name in ['target','secondary']:channels=channel_input(case['rotations']['objects'])
            else:channels={'mode':'xyz','euler':t['rotation']['angles'],
                           'quaternion_wxyz':[1.,0.,0.,0.],'axis_angle':[0.,0.,1.,0.]}
            t['rotation']={'kind':'channels','channels':channels}
        if command['operation']=='set_authoring_context':
            channels=channel_input(case['rotations']['cursor'])
            command['context'].update(cursor_rotation=channels['euler'],cursor_orientation=channels)
        if command['operation']=='set_object_context':
            context=command['context']
            for name in ['target','secondary']:
                context['states'].setdefault(name,{})
                context['states'][name].update(lock_rotation=case['context']['lock_rotation'],
                    lock_rotation_w=case['rotations']['lock_rotation_w'],
                    lock_rotations_4d=case['rotations']['lock_rotations_4d'])
    return result


def snapshot(inspection,queries,worlds):
    scene=inspection['scene'];context=scene['object_context']
    meshes={id:mesh_snapshot(queries[e['content']['geometry']['id']],scene,worlds[id],id)
            for id,e in scene['entities'].items() if e['content']['kind']=='mesh'}
    frames={};rotations={};sharing={}
    for id,e in scene['entities'].items():
        transform=e['transform'];rotation=transform['rotation'];assert rotation['kind']=='channels'
        channels=copy.deepcopy(rotation['channels']);channels['mode']=channels['mode'].upper()
        query=worlds[id];f=query['object_frames']
        frames[id]={'parent':e['parent'],'location':transform['translation'],'rotation':channels['euler'],
            'rotation_mode':channels['mode'],'scale':transform['scale'],'matrix_world':query['world_matrix'],
            'matrix_basis':f['matrix_basis'],'matrix_local':f['matrix_local'],'matrix_parent_inverse':f['matrix_parent_inverse'],
            'selected':f['selected'],'mode':'EDIT' if f['edit_mode'] else 'OBJECT',
            'lock_location':f['lock_location'],'lock_rotation':f['lock_rotation']}
        channels.update(lock_rotation=f['lock_rotation'],lock_rotation_w=f.get('lock_rotation_w',False),
                        lock_rotations_4d=f.get('lock_rotations_4d',False));rotations[id]=channels
        if e['content']['kind']=='mesh':sharing.setdefault(e['content']['geometry']['id'],[]).append(id)
    cursor=copy.deepcopy(scene['authoring_context']['cursor_orientation']);cursor['mode']=cursor['mode'].upper()
    return {'objects':frames,'meshes':meshes,'sharing':sorted(sorted(v) for v in sharing.values()),
        'active_object':context['active'],'mode':'EDIT_MESH' if context['edit_objects'] else 'OBJECT',
        'cursor':scene['authoring_context'],'cursor_matrix':inspection['cursor_matrix'],
        'rotation_channels':rotations,'cursor_channels':cursor}


def compare_state(reference,actual):
    for key in ['sharing','active_object','mode']:tree(reference[key],actual[key],key)
    assert set(reference['objects'])==set(actual['objects']) and set(reference['meshes'])==set(actual['meshes'])
    for id,frame in actual['objects'].items():tree({k:reference['objects'][id][k] for k in frame},frame,'objects/'+id)
    for id,mesh in actual['meshes'].items():
        expected=copy.deepcopy(reference['meshes'][id]);expected['geometry']['vertices']=expected['vertices_metres'];expected['world_vertices']=expected['world_vertices_metres']
        tree({k:expected[k] for k in KEYS},mesh,'meshes/'+id)
    for id,channels in actual['rotation_channels'].items():
        tree({k:reference['rotation_channels'][id][k] for k in channels},channels,'raw object channels/'+id)
    tree(reference['cursor_channels'],actual['cursor_channels'],'raw cursor channels')
    tree(reference['cursor']['matrix'],actual['cursor_matrix'],'actual Rust cursor matrix')
    tree(reference['cursor_metres'],actual['cursor']['cursor_location'],'cursor location')
    tree(reference['cursor']['rotation'],actual['cursor']['cursor_rotation'],'cursor stored Euler')


def check_result(request,before,after,result,error,old,new):
    assert error is None,error
    assert len(result['scene_snaps'])==1 and not result.get('snaps') and not result.get('transforms')
    receipt=result['scene_snaps'][0]
    assert receipt['command_index']==0 and receipt['action']==request['commands'][0]['snap']['action']
    assert receipt['status']=='finished' and receipt['reason'] is None
    for key,field in [('cursor_location','cursor'),('cursor_rotation','cursor_rotation'),('cursor_orientation','cursor_orientation')]:
        assert receipt[field+'_before']==old['authoring_context'][key]
        assert receipt[field+'_after']==new['authoring_context'][key]
    changed_cursor=any(old['authoring_context'][k]!=new['authoring_context'][k]
                       for k in ['cursor_location','cursor_rotation','cursor_orientation'])
    assert receipt['cursor_changed']==changed_cursor,'false raw cursor receipt'
    changed={id for id in old['entities'] if old['entities'][id]['transform']!=new['entities'][id]['transform']
             or before['objects'][id]['matrix_parent_inverse']!=after['objects'][id]['matrix_parent_inverse']}
    assert len(receipt['objects'])==len(changed) and {v['entity'] for v in receipt['objects']}==changed,'false raw object receipt'
    for item in receipt['objects']:
        id=item['entity']
        assert item['transform_before']==old['entities'][id]['transform'] and item['transform_after']==new['entities'][id]['transform']
        assert item['parent_inverse_before']==before['objects'][id]['matrix_parent_inverse']
        assert item['parent_inverse_after']==after['objects'][id]['matrix_parent_inverse']
    seen=set()
    for item in receipt['meshes']+receipt['edit_meshes']:
        asset=item['mesh_asset'];assert asset not in seen,'double shared edit';seen.add(asset)
        users=sorted(id for id,e in new['entities'].items() if e['content']['kind']=='mesh' and e['content']['geometry']['id']==asset)
        assert item['shared_instances']==users
        a=before['meshes'][users[0]]['geometry'];b=after['meshes'][users[0]]['geometry']
        changes={id for id,p in a['vertices'].items() if p!=b['vertices'][id]}
        assert set(item['changed']['vertices'])==changes
        assert set(item['changed']['edges'])=={id for id,pair in a['edges'].items() if changes&set(pair)}
        assert item['changed']['faces']==[{'kind':'polygon','id':id} for id,face in a['faces'].items() if changes&set(face)]
    actual_changes={new['entities'][id]['content']['geometry']['id'] for id,m in before['meshes'].items()
                    if m['geometry']['vertices']!=after['meshes'][id]['geometry']['vertices']}
    assert actual_changes<=seen,'missing actual shared edit receipt'
    assert old['materials']==new['materials']


async def run(binary,output,case_ids=(),interfaces=('cli','official_mcp_sdk'),gzip_output=False,
              suite_path=None,folders=None,source_verifier=verify_source,expected_cases=2496,
              setup_case=setup,take_snapshot=snapshot,compare_snapshot=compare_state):
    from jsonschema import Draft202012Validator
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    suite_path=suite_path or ROOT/'baseline/fixtures/snap-rotation.json';suite=load(suite_path)
    folders=folders or [ROOT/'baseline/reference/blender-5.2.3'/name for name in ['snap-rotation','snap-rotation-repeat']]
    source=source_verifier(suite_path,*folders);assert source['passed']
    cases=suite['runs'];assert len(cases)==expected_cases
    if case_ids:assert set(case_ids)<={c['id'] for c in cases};cases=[c for c in cases if c['id'] in case_ids]
    def inputs():return sorted([ROOT/'Cargo.toml',ROOT/'Cargo.lock',ROOT/'.github/workflows/contracts.yml',
        *[p for folder in ['src','tests','tools','baseline','docs/contracts'] for p in (ROOT/folder).rglob('*')
          if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']])
    hashes={p.relative_to(ROOT).as_posix():digest(p) for p in inputs()};binary_sha=digest(binary)
    output.mkdir(parents=True,exist_ok=False);records=[]
    def cli(scene,action,*args,request=None):
        p=subprocess.run([str(binary),'scene',action,'--scene',str(scene),*args],input=None if request is None else json.dumps(request),capture_output=True,text=True)
        value=json.loads(p.stdout)
        if p.returncode==0:return value,None
        assert isinstance(value.get('error'),str) and value['error'],(p.returncode,p.stdout,p.stderr)
        return None,value['error']
    with tempfile.TemporaryDirectory(prefix='formora-raw-rotation-') as temporary:
        for interface in interfaces:
            for index,case in enumerate(cases):
                with tempfile.TemporaryDirectory(prefix=case['id']+'-',dir=temporary) as workspace:
                    scene=Path(workspace)/'scene.json';_,error=cli(scene,'init');assert error is None
                    create=setup_case(suite,case);request=request_for(case)
                    async def exercise(call):
                        _,error=await call('scene_apply',create);assert error is None,(case['id'],error)
                        async def inspect():
                            inspection,error=await call('scene_inspect',{});assert error is None
                            s=inspection['scene'];queries={};worlds={}
                            for id in s['mesh_assets']:
                                q,error=await call('scene_inspect',{'mesh_asset':id,'normals':True});assert error is None;queries[id]=q
                            for id in s['entities']:
                                q,error=await call('scene_inspect',{'entity':id,'world':True});assert error is None;worlds[id]=q
                            return take_snapshot(inspection,queries,worlds),s,queries,worlds,inspection
                        before,old,qb,wb,ib=await inspect();saved=scene.read_bytes()
                        result,error=await call('scene_apply',request)
                        after,new,qa,wa,ia=await inspect()
                        if error is None:assert new['revision']==result['revision']==2
                        else:assert saved==scene.read_bytes() and old==new
                        fresh,fresh_error=cli(scene,'inspect');assert fresh_error is None and fresh==ia
                        return before,after,result,error,old,new,qb,qa,wb,wa,ib,ia,hashlib.sha256(saved).hexdigest(),digest(scene)
                    if interface=='cli':
                        async def call(name,args):
                            if name=='scene_apply':return cli(scene,'apply','--request','-',request=args)
                            if 'entity' in args:return cli(scene,'inspect','--entity',args['entity'],'--world')
                            return cli(scene,'inspect',*(['--mesh-asset',args['mesh_asset'],'--normals'] if args else []))
                        values=await exercise(call)
                    else:
                        async with stdio_client(StdioServerParameters(command=str(binary),args=['mcp','--scene',str(scene)])) as (reader,writer):
                            async with ClientSession(reader,writer,read_timeout_seconds=10) as client:
                                await client.initialize();schemas={t.name:t.input_schema for t in (await client.list_tools()).tools}
                                async def call(name,args):
                                    Draft202012Validator(schemas[name]).validate(args);response=await client.call_tool(name,args)
                                    return (None,response.content[0].text) if response.is_error else (response.structured_content,None)
                                values=await exercise(call)
                    before,after,result,error,old,new,qb,qa,wb,wa,ib,ia,saved_before,saved_after=values
                    failure=None
                    try:
                        for folder in folders:
                            ref=load(folder/(case['id']+'.json.gz'));compare_snapshot(ref['before'],before);compare_snapshot(ref['after'],after)
                        check_result(request,before,after,result,error,old,new)
                    except (AssertionError,ValueError,KeyError) as issue:failure=str(issue) or type(issue).__name__
                    path=write_json(output/(interface+'-'+case['id']+'.json'),{'case':case,'setup':create,'request':request,
                        'before':before,'after':after,'result':result,'error':error,'before_scene':old,'after_scene':new,
                        'queries':{'before':qb,'after':qa},'world_queries':{'before':wb,'after':wa},
                        'scene_inspections':{'before':ib,'after':ia},'saved_before_sha256':saved_before,'saved_after_sha256':saved_after,
                        'fresh_reload_matches':True,'status':'passed' if failure is None else 'failed','comparison_error':failure},gzip_output)
                    records.append({'id':case['id'],'interface':interface,'file':path.name,'sha256':digest(path),
                                    'status':'passed' if failure is None else 'failed','error':failure})
                if (index+1)%50==0:print(json.dumps({'interface':interface,'executed':index+1,'failed':sum(r['status']=='failed' for r in records)}),flush=True)
    unchanged=hashes=={p.relative_to(ROOT).as_posix():digest(p) for p in inputs()} and binary_sha==digest(binary)
    passed=unchanged and all(r['status']=='passed' for r in records);full=not case_ids and set(interfaces)=={'cli','official_mcp_sdk'}
    report={'passed':passed,'checks':len(records),'scope':f'full_{expected_cases}_cases_both_interfaces' if full else 'focused_diagnostic',
        'required_full_gate_passed':passed and full and len(records)==2*expected_cases,'verification_inputs_unchanged':unchanged,
        'binary_sha256':binary_sha,'input_hashes':hashes,'source_checked':source,'runs':records,
        'product_acceptance':'unrun','three_platform_ci':'unrun','integrated_acceptance':'unrun'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','checks','required_full_gate_passed']}),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--case',action='append',default=[],dest='case_ids');parser.add_argument('--interface',action='append',choices=['cli','official_mcp_sdk'])
    parser.add_argument('--gzip-output',action='store_true')
    args=parser.parse_args();asyncio.run(run(args.binary.resolve(),args.output.resolve(),args.case_ids,args.interface or ('cli','official_mcp_sdk'),args.gzip_output))
