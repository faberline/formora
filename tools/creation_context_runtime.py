#!/usr/bin/env python3
"""Execute all authored creation contexts in Rust, using receipts for actual origin IDs."""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from compare_mesh_reference import compare
from polygon_reference_smoke import from_query, transform_from_matrix
from selection_runtime_smoke import native


def seed_commands(seed,layers):
    geometry=seed['geometry'];profile=seed['uv_profiles'][str(layers)]
    vertices={f'seed_v{i:06}':point for i,point in enumerate(geometry['vertices'])}
    edges={f'seed_e{i:06}':[f'seed_v{v:06}' for v in pair] for i,pair in enumerate(geometry['edges'])}
    polygons={};offset=0
    for i,face in enumerate(geometry['faces']):
        polygons[f'seed_p{i:06}']={'vertices':[f'seed_v{v:06}' for v in face],
             'normal':geometry['face_normals'][i],'corner_normals':geometry['corner_normals'][offset:offset+len(face)],
             'smooth':geometry['smooth_faces'][i],'material_slot':geometry['face_materials'][i],
             'uv_layers':{layer['name']:layer['faces'][i] for layer in profile['uv_layers']}}
        offset+=len(face)
    names=[l['name'] for l in profile['uv_layers']]
    selected={'vertices':list(vertices),'edges':list(edges),'faces':[{'kind':'polygon','id':id} for id in polygons]}
    asset={'vertices':vertices,'edges':edges,'polygons':polygons,'triangles':{},'material_slots':seed['material_slots'],
           'active_material_index':seed['active_material_index'],
           'uv_layout':{'layers':names,'active':names[profile['active_uv_index']] if names else None},
           'editing':{'selected':selected,'preview':False}}
    materials=[{'operation':'set_material','id':name,'material':{'base_color':[0.4,0.6,0.8,1],'roughness':0.6,'metallic':0}} for name in seed['material_slots']]
    return [*materials,{'operation':'set_mesh_asset','id':'seed','asset':asset},
       {'operation':'create_entity','id':'target','entity':{'name':'Seed','parent':None,
        'transform':transform_from_matrix(seed['matrix_world']),
        'content':{'kind':'mesh','geometry':{'kind':'asset','id':'seed'},'material':None}}}]


def request_for(case):
    p=case['parameters'];kind=case['operator'];skip={'align','location','rotation','enter_editmode'}
    if kind not in {'cube','uv_sphere','ico_sphere','cylinder','cone'}:skip.add('scale')
    primitive={'kind':kind,**{k:v for k,v in p.items() if k not in skip}}
    for key in ['fill_type','end_fill_type','mode']:
        if key in primitive:primitive[key]=primitive[key].lower()
    placement={'align':p.get('align','WORLD').lower(),'location':p.get('location'),'rotation':p.get('rotation')}
    if case['state']['creation_kind']=='new_object':
        command={'operation':'create_mesh_object','creation':{'id':'target','asset':'created','name':case['id'],
                 'primitive':primitive,'placement':placement,'preview_selection':p.get('enter_editmode',False)}}
    else:
        command={'operation':'append_mesh_primitive','creation':{'entity':'target','prefix':'added','primitive':primitive,'placement':placement}}
    return {'expected_revision':1,'commands':[command]}


def without_revision(scene):
    scene=copy.deepcopy(scene);scene.pop('revision');return scene


def snapshot(scene,receipt,run_id,before):
    asset_id=receipt['mesh_asset'];asset=scene['mesh_assets'][asset_id];entity=scene['entities'][receipt['entity']]
    # The inspector's strict tessellation is queried separately; comparison uses
    # authored polygon/corner data. Degenerate polygons retain their topology.
    candidate=from_query({'mesh_asset':asset,'tessellation':{'triangles':[]}},entity['transform'],run_id)
    created=receipt['created'];previous=before.get('mesh_assets',{}).get(asset_id,{})
    actual={'vertices':set(asset['vertices']),'edges':set(asset.get('edges',{})),'faces':set(asset.get('polygons',{}))}
    prior={'vertices':set(previous.get('vertices',{})),'edges':set(previous.get('edges',{})),'faces':set(previous.get('polygons',{}))}
    observed={'vertices':set(created['vertices']),'edges':set(created['edges']),
              'faces':{face['id'] for face in created['faces']}}
    assert all(face['kind']=='polygon' for face in created['faces'])
    for key in actual:assert observed[key]==actual[key]-prior[key] and not (observed[key]&prior[key]),key
    editing=asset['editing'];selection=editing['selected'];polygons=asset.get('polygons',{})
    layers=asset['uv_layout']['layers'];active=asset['uv_layout']['active']
    candidate.update({'creation_kind':receipt['kind'],'object_count':len(scene['entities']),
         'active_uv_index':layers.index(active) if active is not None else -1,
         'material_slot_count':len(asset['material_slots']),'material_slots':asset['material_slots'],
         'active_material_index':asset.get('active_material_index',0),
         'vertex_origin':['created' if id in observed['vertices'] else 'existing' for id in asset['vertices']],
         'edge_origin':['created' if id in observed['edges'] else 'existing' for id in asset.get('edges',{})],
         'face_origin':['created' if id in observed['faces'] else 'existing' for id in polygons],
         'vertex_selected':[id in selection['vertices'] for id in asset['vertices']],
         'edge_selected':[id in selection['edges'] for id in asset.get('edges',{})],
         'face_selected':[{'kind':'polygon','id':id} in selection['faces'] for id in polygons],
         'face_materials':[p['material_slot'] if p['material_slot'] is not None else 0 for p in polygons.values()],
         'diagnostics':asset.get('diagnostics',[]),'observed_receipt':receipt})
    for id,point in previous.get('vertices',{}).items():assert asset['vertices'][id]==point
    for id,pair in previous.get('edges',{}).items():assert asset['edges'][id]==pair
    for id,face in previous.get('polygons',{}).items():
        for key in ['vertices','normal','corner_normals','smooth','material_slot']:assert asset['polygons'][id][key]==face[key],(id,key)
        for layer,uvs in face['uv_layers'].items():assert asset['polygons'][id]['uv_layers'][layer]==uvs
    if previous:
        assert asset['material_slots']==previous['material_slots']
        assert scene['entities']==before['entities']
    return candidate


async def run(binary,output,case_ids=()):
    root=Path(__file__).resolve().parents[1];suite=json.loads((root/'baseline/fixtures/mesh-creation-contexts.json').read_text())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    source_files=[root/'Cargo.toml',root/'Cargo.lock',*[p for p in (root/'src').rglob('*') if p.is_file()]]
    source_snapshot={str(p.relative_to(root)):sha(p) for p in sorted(source_files)}
    input_files=[root/name for name in ['tools/creation_context_runtime.py','tools/compare_mesh_reference.py','tools/polygon_reference_smoke.py','tools/selection_runtime_smoke.py','baseline/fixtures/mesh-creation-contexts.json','baseline/fixtures/mesh-creation-seed.json']]
    input_files += sorted((root/'baseline/reference/blender-5.2.3/mesh-contexts').glob('*.json'))
    input_snapshot={str(p.relative_to(root)):sha(p) for p in input_files}
    binary_sha=sha(binary)
    seed=json.loads((root/'baseline/fixtures/mesh-creation-seed.json').read_text());assert len(suite['runs'])==131
    if case_ids:
        assert set(case_ids) <= {case['id'] for case in suite['runs']}, 'unknown case ID'
        suite['runs']=[case for case in suite['runs'] if case['id'] in case_ids]
    output.mkdir(parents=True,exist_ok=False);records=[]
    def cli(scene,action,request=None):
        args=[str(binary),'scene',action,'--scene',str(scene)]
        if request is not None:args+=['--request','-']
        result=subprocess.run(args,input=None if request is None else json.dumps(request),capture_output=True,text=True,check=True)
        return json.loads(result.stdout)
    with tempfile.TemporaryDirectory(prefix='formora-creation-context-') as folder:
        for interface in ['cli','official_mcp_sdk']:
            for index,case in enumerate(suite['runs']):
                scene=Path(folder)/(interface+'-'+case['id']+'.json');cli(scene,'init')
                state=case['state'];context={key:state[key] for key in ['cursor_location','cursor_rotation','view_rotation']}
                setup={'expected_revision':0,'commands':[{'operation':'set_authoring_context','context':context}]}
                if state['creation_kind']=='append_mesh':setup['commands']+=seed_commands(seed,state['seed_uv_layers'])
                request=request_for(case)
                async def exercise(call):
                    initialized=await call('scene_apply',setup)
                    before=(await call('scene_inspect',{}))['scene']
                    result=await call('scene_apply',request);assert len(result['creation'])==1
                    receipt=result['creation'][0];assert receipt['command_index']==0 and receipt['edit_ready']
                    after=(await call('scene_inspect',{}))['scene']
                    candidate=snapshot(after,receipt,case['id'],before)
                    created=receipt['created']['vertices'];assert created
                    id=created[0];point=after['mesh_assets'][receipt['mesh_asset']]['vertices'][id]
                    await call('scene_apply',{'expected_revision':2,'commands':[{'operation':'set_mesh_vertices','id':receipt['mesh_asset'],'positions':{id:[point[0]+0.125,*point[1:]]}}]})
                    edited=(await call('scene_inspect',{}))['scene'];assert edited['mesh_assets'][receipt['mesh_asset']]['vertices'][id][0]==point[0]+0.125
                    await call('scene_undo',{'expected_revision':3});restored=(await call('scene_inspect',{}))['scene']
                    assert without_revision(restored)==without_revision(after)
                    await call('scene_undo',{'expected_revision':4});restored=(await call('scene_inspect',{}))['scene']
                    assert without_revision(restored)==without_revision(before)
                    replay=await call('scene_apply',{**request,'expected_revision':5});assert replay['creation']==result['creation']
                    again=(await call('scene_inspect',{}))['scene'];assert without_revision(again)==without_revision(after)
                    return candidate,before,after,result
                if interface=='cli':
                    with native(binary,scene) as sync:
                        async def call(name,arguments):
                            value,error=sync(name,arguments);assert not error,value;return value
                        candidate,before,after,result=await exercise(call)
                    # Independently execute the one-shot CLI route from the same authored inputs.
                    other=Path(folder)/('one-shot-'+case['id']+'.json');cli(other,'init');cli(other,'apply',setup)
                    echoed=cli(other,'apply',request);observed=cli(other,'inspect')['scene']
                    assert echoed['creation']==result['creation'] and without_revision(observed)==without_revision(after)
                else:
                    parameters=StdioServerParameters(command=str(binary),args=['mcp','--scene',str(scene)])
                    async with stdio_client(parameters) as (reader,writer):
                        async with ClientSession(reader,writer,read_timeout_seconds=10) as client:
                            await client.initialize();listed=await client.list_tools()
                            schemas={t.name:t.input_schema for t in listed.tools}
                            async def call(name,arguments):
                                Draft202012Validator(schemas[name]).validate(arguments)
                                value=await client.call_tool(name,arguments);assert not value.is_error,value
                                return value.structured_content
                            candidate,before,after,result=await exercise(call)
                reloaded=cli(scene,'inspect')['scene'];assert without_revision(reloaded)==without_revision(after)
                candidate.update({'observed_request':request,'editability_checked':True,'undo_checked':True,'reload_checked':True})
                file=interface+'-'+case['id']+'.json';(output/file).write_text(json.dumps(candidate,allow_nan=False)+'\n')
                reference_path=root/'baseline/reference/blender-5.2.3/mesh-contexts'/(case['id']+'.json')
                reference=json.loads(reference_path.read_text())
                try:comparison=compare(reference,candidate,suite['comparison']);status='passed';error=None
                except Exception as e:comparison={};status='failed';error=str(e)
                records.append({'id':case['id'],'interface':interface,'status':status,'error':error,'file':file,
                    'sha256':hashlib.sha256((output/file).read_bytes()).hexdigest(),'reference_sha256':hashlib.sha256(reference_path.read_bytes()).hexdigest(),**comparison})
                if (index+1)%20==0:print(json.dumps({'interface':interface,'executed':index+1,'failed':sum(r['status']=='failed' for r in records)}),flush=True)
    passed=all(r['status']=='passed' for r in records)
    assert source_snapshot=={str(p.relative_to(root)):sha(p) for p in sorted(source_files)},'source changed during capture'
    assert input_snapshot=={str(p.relative_to(root)):sha(p) for p in input_files},'inputs changed during capture'
    assert binary_sha==sha(binary),'binary changed during capture'
    report={'passed':passed,'checks':len(records),'scope':'focused' if case_ids else 'full_131_contexts_both_interfaces','runs':records,'binary_sha256':binary_sha,
       'source_files_sha256':source_snapshot,'capture_inputs_sha256':input_snapshot,
       'adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'full_numeric_domains':'unrun','milestone_acceptance':'unrun'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':passed,'checks':len(records),'failures':[(r['id'],r['interface'],r['error']) for r in records if r['status']=='failed']}))
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--case',action='append',default=[],dest='case_ids')
    args=parser.parse_args();asyncio.run(run(args.binary.resolve(),args.output.resolve(),args.case_ids))
