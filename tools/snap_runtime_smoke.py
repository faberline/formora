#!/usr/bin/env python3
"""Execute every required single edit-mesh snap through real CLI and MCP."""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from runtime_artifacts import write_json

from compare_snap_menu_reference import compare as verify_source, digest, load, tree, grid_step, f32
from transform_runtime_smoke import setup as transform_setup, snapshot, PIVOTS, RUNTIME_KEYS

ROOT=Path(__file__).resolve().parents[1]


def covered(run):
    return run['mode']=='EDIT_MESH' and not run['context']['multi_object']


def factor(run):
    c=run['context'];return 1. if c['unit_system']=='NONE' else c['unit_scale_length']


def setup(suite,run):
    """Only authored data enters this function; no measured state is accepted."""
    assert covered(run)
    authored=copy.deepcopy(suite);scale=factor(run)
    authored['mesh']['vertices']=[[f32(f32(v)*scale) for v in p] for p in suite['mesh']['vertices']]
    for profile in authored['profiles'].values():
        profile['location']=[f32(f32(v)*scale) for v in profile['location']]
        if profile['parent'] is not None:profile['parent']['location']=[f32(f32(v)*scale) for v in profile['parent']['location']]
    request=transform_setup(authored,run)
    for command in request['commands']:
        if command['operation']=='set_authoring_context':
            command['context']={'cursor_location':[f32(f32(v)*scale) for v in run['context']['cursor_location']],
                'cursor_rotation':[f32(v) for v in run['context']['cursor_rotation']],
                'view_rotation':[f32(v) for v in suite['environment']['view_rotation']]}
        if command['operation']=='set_mesh_editing':
            editing=command['editing']
            # Blender's selection flush clears the authored hidden-only seed.
            # Apply the same input rule before asking Rust to validate editing.
            if run['context'].get('hide_all'):
                editing['selected']={'vertices':[],'edges':[],'faces':[]}
                editing['history']=[];editing['active_face']=None
            if run['context']['history']=='clear':editing['history']=[]
            value=run['context']['active_face_override']
            if value!='preserve':editing['active_face']=None if value is None else {'kind':'polygon','id':f'f{value:06}'}
    return request


def request_for(run,revision=1):
    action={'kind':run['operator'].removeprefix('snap_')}
    if run['operator'].endswith('_to_grid'):action['spacing']=f32(grid_step(run['context'])*factor(run))
    if run['operator']=='snap_selected_to_cursor':
        action.update(use_offset=run['parameters'].get('use_offset',True),use_rotation=run['parameters'].get('use_rotation',False))
    return {'expected_revision':revision,'commands':[{'operation':'snap_mesh','snap':{
        'entity':'target','action':action,'pivot':PIVOTS[run['context']['pivot']]}}]}


def expected_mesh(source):
    mesh=copy.deepcopy(source['meshes']['target'])
    mesh['geometry']['vertices']=mesh['vertices_metres'];mesh['world_vertices']=mesh['world_vertices_metres']
    return {key:mesh[key] for key in RUNTIME_KEYS}


def compare_output(run,reference,before,after,result,error,request,scene_before,scene_after):
    for phase,state,scene in [('before',before,scene_before),('after',after,scene_after)]:
        tree(expected_mesh(reference[phase]),state,phase+'/mesh')
        context=scene['authoring_context'];expected=reference[phase]
        tree(expected['cursor_metres'],context['cursor_location'],phase+'/cursor position')
        tree(expected['cursor']['rotation'],context['cursor_rotation'],phase+'/cursor rotation')
    assert scene_before['entities']==scene_after['entities'],'unrelated entity frames changed'
    assert scene_before['materials']==scene_after['materials'],'materials changed'
    outcome=reference['result']['status'][0]
    if outcome=='ERROR':
        assert run['operator']=='snap_selected_to_active' and error is not None and error.strip()=='mesh snap: no active element found',error
        assert result is None and before==after and scene_before==scene_after
        return {'source_outcome':'ERROR','comparison_kind':'explicit_atomic_rejection'}
    assert error is None,error
    assert len(result['snaps'])==1 and not result.get('transforms')
    receipt=result['snaps'][0]
    assert receipt['command_index']==0 and receipt['entity']=='target' and receipt['mesh_asset']=='mesh'
    assert receipt['shared_instances']==['target'] and receipt['action']==request['commands'][0]['snap']['action']
    assert receipt['status']==('cancelled' if outcome=='CANCELLED' else 'finished')
    assert bool(receipt['reason'])==(outcome=='CANCELLED')
    assert receipt['rotation_applied'] is False
    changed={id for id,p in before['geometry']['vertices'].items() if p!=after['geometry']['vertices'][id]}
    assert set(receipt['changed']['vertices'])==changed,'false changed vertex receipt'
    assert set(receipt['changed']['edges'])=={id for id,pair in before['geometry']['edges'].items() if changed&set(pair)}
    assert receipt['changed']['faces']==[{'kind':'polygon','id':id} for id,face in before['geometry']['faces'].items() if changed&set(face)]
    cursor_before=scene_before['authoring_context'];cursor_after=scene_after['authoring_context']
    assert receipt['cursor_before']==cursor_before['cursor_location'] and receipt['cursor_after']==cursor_after['cursor_location']
    assert receipt['cursor_rotation_before']==cursor_before['cursor_rotation'] and receipt['cursor_rotation_after']==cursor_after['cursor_rotation']
    assert receipt['cursor_changed']==any(cursor_before[key]!=cursor_after[key] for key in ['cursor_location','cursor_rotation'])
    if outcome=='CANCELLED':assert before==after and not changed and not receipt['cursor_changed']
    return {'source_outcome':outcome,'comparison_kind':'explicit_cancellation' if outcome=='CANCELLED' else 'defined_numeric_source_comparison'}


async def run(binary,output,case_ids=(),interfaces=('cli','official_mcp_sdk'),gzip_output=False):
    from jsonschema import Draft202012Validator
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    suite_path=ROOT/'baseline/fixtures/snap-menu.json';suite=load(suite_path)
    first=ROOT/'baseline/reference/blender-5.2.3/snap-menu';second=ROOT/'baseline/reference/blender-5.2.3/snap-menu-repeat'
    source=verify_source(suite_path,first,second);assert source['passed']
    cases=[r for r in suite['runs'] if covered(r)];assert len(cases)==1122
    if case_ids:assert set(case_ids)<={r['id'] for r in cases};cases=[r for r in cases if r['id'] in case_ids]
    def inputs():
        return sorted([ROOT/'Cargo.toml',ROOT/'Cargo.lock',ROOT/'.github/workflows/contracts.yml',*[p for name in ['src','tests','tools','baseline','docs/contracts'] for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']])
    paths=inputs()
    hashes={p.relative_to(ROOT).as_posix():digest(p) for p in paths};binary_sha=digest(binary)
    output.mkdir(parents=True,exist_ok=False);records=[]
    def cli(scene,action,*args,request=None):
        p=subprocess.run([str(binary),'scene',action,'--scene',str(scene),*args],input=None if request is None else json.dumps(request),capture_output=True,text=True)
        value=json.loads(p.stdout)
        if p.returncode==0:return value,None
        assert isinstance(value.get('error'),str) and value['error'],(p.returncode,p.stdout,p.stderr)
        return None,value['error']
    with tempfile.TemporaryDirectory(prefix='formora-snap-runtime-') as temporary:
        for interface in interfaces:
            for index,case in enumerate(cases):
                case_workspace=tempfile.TemporaryDirectory(prefix=interface+'-'+case['id']+'-',dir=temporary)
                scene=Path(case_workspace.name)/(interface+'-'+case['id']+'.json');_,error=cli(scene,'init');assert error is None
                create=setup(suite,case);request=request_for(case)
                async def exercise(call):
                    _,error=await call('scene_apply',create);assert error is None,(case['id'],error)
                    async def inspect():
                        q,error=await call('scene_inspect',{'mesh_asset':'mesh','normals':True});assert error is None
                        s,error=await call('scene_inspect',{});assert error is None
                        w,error=await call('scene_inspect',{'entity':'target','world':True});assert error is None
                        return snapshot(q,s['scene'],w),s['scene'],w
                    before,scene_before,world_before=await inspect();saved=scene.read_bytes()
                    result,error=await call('scene_apply',request)
                    after,scene_after,world_after=await inspect()
                    if error is not None:assert saved==scene.read_bytes() and scene_before==scene_after,'failed snap changed disk or revision'
                    else:assert scene_after['revision']==2 and result['revision']==2
                    # A separate process reopens the actual saved scene.
                    fresh,fresh_error=cli(scene,'inspect');assert fresh_error is None and fresh['scene']==scene_after
                    return before,after,result,error,scene_before,scene_after,world_before,world_after,hashlib.sha256(saved).hexdigest(),digest(scene)
                if interface=='cli':
                    async def call(name,args):
                        if name=='scene_apply':return cli(scene,'apply','--request','-',request=args)
                        if 'entity' in args:return cli(scene,'inspect','--entity',args['entity'],'--world')
                        return cli(scene,'inspect',*(['--mesh-asset','mesh','--normals'] if args else []))
                    values=await exercise(call)
                else:
                    async with stdio_client(StdioServerParameters(command=str(binary),args=['mcp','--scene',str(scene)])) as (reader,writer):
                        async with ClientSession(reader,writer,read_timeout_seconds=10) as client:
                            await client.initialize();schemas={t.name:t.input_schema for t in (await client.list_tools()).tools}
                            async def call(name,args):
                                Draft202012Validator(schemas[name]).validate(args);response=await client.call_tool(name,args)
                                return (None,response.content[0].text) if response.is_error else (response.structured_content,None)
                            values=await exercise(call)
                before,after,result,error,scene_before,scene_after,world_before,world_after,saved_before,saved_after=values
                failure=None;comparison={}
                try:
                    for folder in [first,second]:
                        reference=load(folder/(case['id']+'.json'))
                        comparison=compare_output(case,reference,before,after,result,error,request,scene_before,scene_after)
                        for phase,query in [('before',world_before),('after',world_after)]:
                            expected=copy.deepcopy(reference[phase]['objects']['target']['matrix_world'])
                            for i in range(3):expected[i][3]*=factor(case)
                            tree(expected,query['world_matrix'],phase+'/world frame')
                except (AssertionError,ValueError,KeyError) as issue:failure=str(issue)
                file=interface+'-'+case['id']+'.json';path=output/file
                path=write_json(path,{'case':case,'setup':create,'request':request,'before':before,'after':after,'result':result,'error':error,
                    'before_scene':scene_before,'after_scene':scene_after,'world_queries':{'before':world_before,'after':world_after},
                    'saved_before_sha256':saved_before,'saved_after_sha256':saved_after,'fresh_reload_matches':True,
                    'status':'passed' if failure is None else 'failed','comparison_error':failure},gzip_output)
                file=path.name
                records.append({'id':case['id'],'interface':interface,'file':file,'sha256':digest(path),'status':'passed' if failure is None else 'failed','error':failure,**comparison})
                case_workspace.cleanup()
                if (index+1)%50==0:print(json.dumps({'interface':interface,'executed':index+1,'failed':sum(r['status']=='failed' for r in records)}),flush=True)
    unchanged=hashes=={p.relative_to(ROOT).as_posix():digest(p) for p in inputs()} and binary_sha==digest(binary)
    passed=unchanged and all(r['status']=='passed' for r in records);full=not case_ids and set(interfaces)=={'cli','official_mcp_sdk'}
    report={'passed':passed,'checks':len(records),'scope':'full_1122_single_edit_cases_both_interfaces' if full else 'focused_diagnostic',
        'required_full_gate_passed':full and passed and len(records)==2244,'binary_sha256':binary_sha,'input_hashes':hashes,
        'verification_inputs_unchanged':unchanged,'source_checked':source,'runs':records,'remaining_object_multi_edit_cases':550,
        'snap_product_acceptance':'unrun','three_platform_ci':'unrun','integrated_acceptance':'unrun'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ['passed','checks','scope','required_full_gate_passed']}))
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--case',action='append',default=[],dest='case_ids');parser.add_argument('--interface',action='append',choices=['cli','official_mcp_sdk'])
    parser.add_argument('--gzip-output',action='store_true',help='retain exact raw JSON bytes in lossless gzip files')
    args=parser.parse_args();asyncio.run(run(args.binary.resolve(),args.output.resolve(),args.case_ids,args.interface or ('cli','official_mcp_sdk'),args.gzip_output))
