#!/usr/bin/env python3
"""Compare the 550 object/multi-edit cases through actual CLI and official MCP."""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from runtime_artifacts import write_json

from compare_snap_menu_reference import compare as verify_source, digest, load, tree
from snap_runtime_smoke import setup as single_setup, request_for as single_request, factor
from transform_runtime_smoke import pose, PIVOTS
from selection_runtime_smoke import snapshot as selection_snapshot

ROOT=Path(__file__).resolve().parents[1]
KEYS={'geometry','groups','selected','hidden','mode','history','active_face','normals','world_vertices','active_material_index','data_edit_mode'}


def covered(run):return run['mode']=='OBJECT' or run['context']['multi_object']


def setup(suite,run):
    """Accept only authored inputs. This function never reads source results."""
    assert covered(run) and factor(run)==1.
    proxy=copy.deepcopy(run);proxy['mode']='EDIT_MESH';proxy['context']['multi_object']=False
    result=single_setup(suite,proxy);commands=result['commands'];c=run['context']
    asset=copy.deepcopy(next(x['asset'] for x in commands if x['operation']=='set_mesh_asset'))
    editing=copy.deepcopy(next(x['editing'] for x in commands if x['operation']=='set_mesh_editing'))
    secondary_asset='mesh' if c['linked_data'] else 'secondary_mesh'
    if not c['linked_data']:
        commands.extend([{'operation':'set_mesh_asset','id':secondary_asset,'asset':asset},
                         {'operation':'set_mesh_editing','id':secondary_asset,'editing':editing}])
    commands.extend([
        {'operation':'create_entity','id':'secondary','entity':{'name':'Secondary','parent':c['secondary_parent'],
            'transform':pose(suite['object_inputs']['secondary']),'content':{'kind':'mesh','geometry':{'kind':'asset','id':secondary_asset},'material':None}}},
        {'operation':'create_entity','id':'child','entity':{'name':'Child','parent':'target',
            'transform':pose(suite['object_inputs']['child']),'content':{'kind':'empty'}}}])
    order=['target']+(['parent'] if suite['profiles'][c['profile']]['parent'] is not None else [])+['secondary','child']
    selected=c['object_selection'];edit=[]
    if run['mode']=='EDIT_MESH':
        # Entering native edit mode admits the active object's data first.
        # A selected linked user stays in OBJECT mode while its data is live.
        assets={'target':'mesh','secondary':secondary_asset};seen=set()
        for id in [c['active_object'],*order]:
            if id in selected and id in assets and assets[id] not in seen:
                edit.append(id);seen.add(assets[id])
    commands.append({'operation':'set_object_context','context':{'order':order,'selected':selected,'active':c['active_object'],
        'edit_objects':edit,'states':{'target':{'lock_location':c['lock_location'],'lock_rotation':c['lock_rotation']}},
        'skip_children':c['skip_children'],'origins_only':c['origins_only']}})
    return result


def request_for(run,revision=1):
    snap=single_request(run,revision)['commands'][0]['snap'];snap.pop('entity')
    return {'expected_revision':revision,'commands':[{'operation':'snap_scene','snap':snap}]}


def mesh_snapshot(query,scene,world,id):
    asset=query['mesh_asset'];result=selection_snapshot(query)
    result['normals']={'faces':{},'corners':{}}
    for face in query['normals']['faces']:
        assert face['face']['kind']=='polygon';name=face['face']['id']
        result['normals']['faces'][name]=face['normal'];result['normals']['corners'][name]=face['corner_normals']
    assert world['id']==id and world['entity']==scene['entities'][id]
    result['world_vertices']=world['world_vertices'];result['active_material_index']=asset.get('active_material_index',0)
    context=scene['object_context'];asset_id=scene['entities'][id]['content']['geometry']['id']
    result['data_edit_mode']=any(scene['entities'][other]['content']['geometry']['id']==asset_id for other in context['edit_objects'])
    if not result['data_edit_mode']:result['mode']=[];result['history']=[];result['active_face']=None
    return result


def frame_snapshot(query,scene,id):
    entity=scene['entities'][id];t=entity['transform'];frames=query['object_frames']
    assert t['rotation']['kind']=='euler' and t['rotation']['order']=='xyz'
    return {'parent':entity['parent'],'location':t['translation'],'rotation':t['rotation']['angles'],'scale':t['scale'],
        'matrix_world':query['world_matrix'],'matrix_basis':frames['matrix_basis'],'matrix_local':frames['matrix_local'],
        'matrix_parent_inverse':frames['matrix_parent_inverse'],'selected':frames['selected'],
        'mode':'EDIT' if frames['edit_mode'] else 'OBJECT','lock_location':frames['lock_location'],'lock_rotation':frames['lock_rotation']}


def snapshot(scene,queries,worlds):
    meshes={id:mesh_snapshot(queries[entity['content']['geometry']['id']],scene,worlds[id],id)
        for id,entity in scene['entities'].items() if entity['content']['kind']=='mesh'}
    sharing={}
    for id,entity in scene['entities'].items():
        if entity['content']['kind']=='mesh':sharing.setdefault(entity['content']['geometry']['id'],[]).append(id)
    context=scene['object_context']
    return {'objects':{id:frame_snapshot(worlds[id],scene,id) for id in scene['entities']},'meshes':meshes,
        'sharing':sorted(sorted(group) for group in sharing.values()),'active_object':context['active'],
        'mode':'EDIT_MESH' if context['edit_objects'] else 'OBJECT','cursor':scene['authoring_context']}


def compare_state(reference,actual):
    for key in ['sharing','active_object','mode']:tree(reference[key],actual[key],key)
    assert set(reference['objects'])==set(actual['objects']) and set(reference['meshes'])==set(actual['meshes'])
    for id,frame in actual['objects'].items():tree({key:reference['objects'][id][key] for key in frame},frame,'objects/'+id)
    for id,mesh in actual['meshes'].items():
        expected=copy.deepcopy(reference['meshes'][id]);expected['geometry']['vertices']=expected['vertices_metres'];expected['world_vertices']=expected['world_vertices_metres']
        tree({key:expected[key] for key in KEYS},mesh,'meshes/'+id)
    tree(reference['cursor_metres'],actual['cursor']['cursor_location'],'cursor/location')
    tree(reference['cursor']['rotation'],actual['cursor']['cursor_rotation'],'cursor/rotation')


def check_result(reference,request,before,after,result,error,scene_before,scene_after):
    outcome=reference['result']['status'][0]
    if outcome=='ERROR':
        assert request['commands'][0]['snap']['action']['kind']=='selected_to_active'
        assert error=='scene snap: no active element found' and result is None,error
        assert before==after and scene_before==scene_after
        return 'explicit_atomic_rejection'
    assert error is None,error
    assert len(result['scene_snaps'])==1 and not result.get('snaps') and not result.get('transforms')
    receipt=result['scene_snaps'][0];assert receipt['command_index']==0 and receipt['action']==request['commands'][0]['snap']['action']
    assert receipt['status']==('cancelled' if outcome=='CANCELLED' else 'finished')
    assert bool(receipt['reason'])==(outcome=='CANCELLED')
    for key in ['cursor_location','cursor_rotation']:
        stem='cursor' if key=='cursor_location' else 'cursor_rotation'
        assert receipt[stem+'_before']==before['cursor'][key] and receipt[stem+'_after']==after['cursor'][key]
    assert receipt['cursor_changed']==any(before['cursor'][k]!=after['cursor'][k] for k in ['cursor_location','cursor_rotation'])
    changed_objects={id for id in before['objects'] if any(before['objects'][id][key]!=after['objects'][id][key] for key in ['location','rotation','scale','matrix_parent_inverse'])}
    assert {x['entity'] for x in receipt['objects']}==changed_objects,'false object change receipt'
    assert len(receipt['objects'])==len(changed_objects)
    for item in receipt['objects']:
        id=item['entity']
        assert item['transform_before']==scene_before['entities'][id]['transform']
        assert item['transform_after']==scene_after['entities'][id]['transform']
        assert item['parent_inverse_before']==before['objects'][id]['matrix_parent_inverse']
        assert item['parent_inverse_after']==after['objects'][id]['matrix_parent_inverse']
    changes=receipt['meshes']+receipt['edit_meshes'];seen=set()
    for item in changes:
        asset=item['mesh_asset'];assert asset not in seen,'double shared mesh edit';seen.add(asset)
        users=sorted(id for id,e in scene_after['entities'].items() if e['content']['kind']=='mesh' and e['content']['geometry']['id']==asset)
        assert item['shared_instances']==users
        first=users[0];old=before['meshes'][first]['geometry'];new=after['meshes'][first]['geometry']
        changed={id for id in old['vertices'] if old['vertices'][id]!=new['vertices'][id]}
        assert set(item['changed']['vertices'])==changed,'false vertex change receipt'
        assert set(item['changed']['edges'])=={id for id,edge in old['edges'].items() if changed&set(edge)}
        assert item['changed']['faces']==[{'kind':'polygon','id':id} for id,face in old['faces'].items() if changed&set(face)]
    actual_mesh_changes={scene_after['entities'][id]['content']['geometry']['id'] for id in before['meshes']
        if before['meshes'][id]['geometry']['vertices']!=after['meshes'][id]['geometry']['vertices']}
    assert actual_mesh_changes<=seen,'missing mesh change receipt'
    if outcome=='CANCELLED':assert before==after and not changes and not receipt['objects'] and not receipt['cursor_changed']
    assert scene_before['materials']==scene_after['materials']
    return 'explicit_cancellation' if outcome=='CANCELLED' else 'defined_numeric_source_comparison'


async def run(binary,output,case_ids=(),interfaces=('cli','official_mcp_sdk'),gzip_output=False):
    from jsonschema import Draft202012Validator
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    suite_path=ROOT/'baseline/fixtures/snap-menu.json';suite=load(suite_path)
    first=ROOT/'baseline/reference/blender-5.2.3/snap-menu';second=ROOT/'baseline/reference/blender-5.2.3/snap-menu-repeat'
    source=verify_source(suite_path,first,second);assert source['passed']
    cases=[r for r in suite['runs'] if covered(r)];assert len(cases)==550
    if case_ids:assert set(case_ids)<={r['id'] for r in cases};cases=[r for r in cases if r['id'] in case_ids]
    def inputs():
        return sorted([ROOT/'Cargo.toml',ROOT/'Cargo.lock',ROOT/'.github/workflows/contracts.yml',*[p for name in ['src','tests','tools','baseline','docs/contracts'] for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']])
    hashes={p.relative_to(ROOT).as_posix():digest(p) for p in inputs()};binary_sha=digest(binary)
    output.mkdir(parents=True,exist_ok=False);records=[]
    def cli(scene,action,*args,request=None):
        p=subprocess.run([str(binary),'scene',action,'--scene',str(scene),*args],input=None if request is None else json.dumps(request),capture_output=True,text=True)
        value=json.loads(p.stdout)
        if p.returncode==0:return value,None
        assert isinstance(value.get('error'),str) and value['error'],(p.returncode,p.stdout,p.stderr)
        return None,value['error']
    with tempfile.TemporaryDirectory(prefix='formora-scene-snap-') as temporary:
        for interface in interfaces:
            for index,case in enumerate(cases):
                case_workspace=tempfile.TemporaryDirectory(prefix=interface+'-'+case['id']+'-',dir=temporary)
                scene=Path(case_workspace.name)/(interface+'-'+case['id']+'.json');_,error=cli(scene,'init');assert error is None
                create=setup(suite,case);request=request_for(case)
                async def exercise(call):
                    _,error=await call('scene_apply',create);assert error is None,(case['id'],error)
                    async def inspect():
                        s,error=await call('scene_inspect',{});assert error is None;s=s['scene'];queries={};worlds={}
                        for id in s['mesh_assets']:
                            q,error=await call('scene_inspect',{'mesh_asset':id,'normals':True});assert error is None;queries[id]=q
                        for id in s['entities']:
                            q,error=await call('scene_inspect',{'entity':id,'world':True});assert error is None;worlds[id]=q
                        return snapshot(s,queries,worlds),s,queries,worlds
                    before,scene_before,queries_before,worlds_before=await inspect();saved=scene.read_bytes()
                    result,error=await call('scene_apply',request)
                    after,scene_after,queries_after,worlds_after=await inspect()
                    if error is not None:assert saved==scene.read_bytes() and scene_before==scene_after,'failed snap changed disk or revision'
                    else:assert scene_after['revision']==2 and result['revision']==2
                    fresh,fresh_error=cli(scene,'inspect');assert fresh_error is None and fresh['scene']==scene_after
                    return before,after,result,error,scene_before,scene_after,queries_before,queries_after,worlds_before,worlds_after,hashlib.sha256(saved).hexdigest(),digest(scene)
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
                before,after,result,error,scene_before,scene_after,qb,qa,wb,wa,saved_before,saved_after=values
                failure=None;kind=None
                try:
                    for folder in [first,second]:
                        reference=load(folder/(case['id']+'.json'));compare_state(reference['before'],before);compare_state(reference['after'],after)
                        kind=check_result(reference,request,before,after,result,error,scene_before,scene_after)
                except (AssertionError,ValueError,KeyError) as issue:failure=str(issue) or type(issue).__name__
                file=interface+'-'+case['id']+'.json';path=output/file
                path=write_json(path,{'case':case,'setup':create,'request':request,'before':before,'after':after,'result':result,'error':error,
                    'before_scene':scene_before,'after_scene':scene_after,'queries':{'before':qb,'after':qa},'world_queries':{'before':wb,'after':wa},
                    'saved_before_sha256':saved_before,'saved_after_sha256':saved_after,'fresh_reload_matches':True,
                    'status':'passed' if failure is None else 'failed','comparison_error':failure},gzip_output)
                file=path.name
                records.append({'id':case['id'],'interface':interface,'file':file,'sha256':digest(path),'status':'passed' if failure is None else 'failed','error':failure,'comparison_kind':kind})
                case_workspace.cleanup()
                if (index+1)%50==0:print(json.dumps({'interface':interface,'executed':index+1,'failed':sum(r['status']=='failed' for r in records)}),flush=True)
    unchanged=hashes=={p.relative_to(ROOT).as_posix():digest(p) for p in inputs()} and binary_sha==digest(binary)
    passed=unchanged and all(r['status']=='passed' for r in records);full=not case_ids and set(interfaces)=={'cli','official_mcp_sdk'}
    report={'passed':passed,'checks':len(records),'scope':'full_550_object_multi_edit_cases_both_interfaces' if full else 'focused_diagnostic',
        'required_full_gate_passed':full and passed and len(records)==1100,'binary_sha256':binary_sha,'input_hashes':hashes,
        'verification_inputs_unchanged':unchanged,'source_checked':source,'runs':records,'single_edit_cases_separate_gate':1122,
        'snap_product_acceptance':'unrun','three_platform_ci':'unrun','integrated_acceptance':'unrun'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({key:report[key] for key in ['passed','checks','scope','required_full_gate_passed']}))
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--case',action='append',default=[],dest='case_ids');parser.add_argument('--interface',action='append',choices=['cli','official_mcp_sdk'])
    parser.add_argument('--gzip-output',action='store_true',help='retain exact raw JSON bytes in lossless gzip files')
    args=parser.parse_args();asyncio.run(run(args.binary.resolve(),args.output.resolve(),args.case_ids,args.interface or ('cli','official_mcp_sdk'),args.gzip_output))
