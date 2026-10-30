"""Actual saved merge results through the CLI and official MCP SDK."""
import argparse
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('merge_pilot',HERE/'pilot-native.py')
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)
from compare_mesh_merge_reference import compare_case
from generate_mesh_merge_cases import author
from runtime_artifacts import write_json
from scene_snap_runtime_smoke import frame_snapshot
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=pilot.ROOT
sha=pilot.sha

def component_sets(asset):
    return {'vertices':set(asset['vertices']),'edges':set(asset.get('edges',{})),
        'faces':{('polygon',id) for id in asset.get('polygons',{})}|{('triangle',id) for id in asset['triangles']}}

def receipt_sets(elements):
    result={'vertices':set(elements['vertices']),'edges':set(elements['edges']),
        'faces':{(face['kind'],face['id']) for face in elements['faces']}}
    assert all(len(result[domain])==len(elements[domain]) for domain in result),'duplicate receipt component'
    return result

def flags(asset,domain,id):
    editing=asset.get('editing') or {}
    item={'kind':id[0],'id':id[1]} if domain=='faces' else id
    return tuple(item in editing.get(field,{}).get(domain,[]) for field in ['selected','hidden'])

def integers(asset,domain,id):
    if domain=='faces':domain,id=('polygons' if id[0]=='polygon' else 'triangles'),id[1]
    return {name:layer.get(id) for name,layer in (asset.get('integer_attributes') or {}).get(domain,{}).items()}

def validate_receipt(before,after,result,request):
    old=before['query']['mesh_asset'];new=after['query']['mesh_asset'];bs=component_sets(old);ns=component_sets(new)
    assert len(result['merges'])==1 and not any(result.get(field) for field in ['snaps','transforms','scene_snaps','creation','selection'])
    receipt=result['merges'][0];parameters=request['commands'][0]['merge']
    assert receipt['command_index']==0 and receipt['entity']=='target' and receipt['mesh_asset']=='mesh'
    assert receipt['method']==parameters['method'] and receipt['uvs']==parameters['uvs'] and receipt['status']=='finished'
    users=sorted(id for id,entity in after['scene']['entities'].items() if entity['content'].get('geometry')=={'kind':'asset','id':'mesh'})
    assert receipt['shared_instances']==users==['secondary','target']
    for name,asset,sets in [('before',old,bs),('after',new,ns)]:
        corners=sum(len(face['vertices']) for field in ['polygons','triangles'] for face in asset.get(field,{}).values())
        assert receipt[name]=={domain:len(ids) for domain,ids in sets.items()}|{'corners':corners},'false component counts'
    assert receipt_sets(receipt['removed'])=={domain:bs[domain]-ns[domain] for domain in bs},'false removed components'
    assert receipt_sets(receipt['created'])=={domain:ns[domain]-bs[domain] for domain in bs},'false created components'
    moved={id for id in bs['vertices']&ns['vertices'] if old['vertices'][id]!=new['vertices'][id]}
    changed={domain:set() for domain in bs}
    for domain in bs:
        for id in bs[domain]&ns[domain]:
            different=flags(old,domain,id)!=flags(new,domain,id) or integers(old,domain,id)!=integers(new,domain,id)
            if domain=='vertices':
                different|=id in moved or old.get('vertex_weights',{}).get(id)!=new.get('vertex_weights',{}).get(id)
            elif domain=='edges':
                different|=old['edges'][id]!=new['edges'][id] or bool(moved&set(new['edges'][id])) or ((id in old.get('edge_seams',[]))!=(id in new.get('edge_seams',[])))
            else:
                field='polygons' if id[0]=='polygon' else 'triangles';key=id[1]
                different|=old[field][key]!=new[field][key] or bool(moved&set(new[field][key]['vertices'])) or ((key in old.get('smooth_triangles',[]))!=(key in new.get('smooth_triangles',[])))
            if different:changed[domain].add(id)
    assert receipt_sets(receipt['changed'])==changed,'false changed survivors'
    lineage=receipt['source_to_survivor'];vmap=lineage['vertices']
    assert set(vmap)==bs['vertices'] and set(vmap.values())==ns['vertices']
    assert all(vmap[id]==id for id in ns['vertices']),'surviving vertex remapped to another ID'
    selected=set(old.get('editing',{}).get('selected',{}).get('vertices',[]))
    if selected and parameters['method']!='collapse':
        history=old['editing']['history'];target=min(selected)
        if parameters['method'] in ['first','last']:target=history[0 if parameters['method']=='first' else -1]['id']
        assert vmap=={id:target if id in selected else id for id in bs['vertices']},'false pointmerge lineage'
    if parameters['method']=='collapse':
        adjacent={}
        for edge in old['editing']['selected']['edges']:
            a,b=old['edges'][edge];adjacent.setdefault(a,set()).add(b);adjacent.setdefault(b,set()).add(a)
        remaining=set(adjacent)
        while remaining:
            reached=set();pending=[min(remaining)]
            while pending:
                id=pending.pop()
                if id not in reached:reached.add(id);pending.extend(adjacent[id]-reached)
            survivors=reached&ns['vertices'];assert len(survivors)==1
            assert {vmap[id] for id in reached}==survivors,'false collapse component lineage'
            remaining-=reached
        assert all(vmap[id]==id for id in bs['vertices']-set(adjacent))
    pairs={tuple(sorted(pair)):id for id,pair in new.get('edges',{}).items()}
    expected_edges={id:pairs[tuple(sorted([vmap[a],vmap[b]]))] for id,(a,b) in old.get('edges',{}).items() if vmap[a]!=vmap[b]}
    assert lineage['edges']==expected_edges,'false edge lineage'
    face_lineage={}
    for row in lineage['faces']:
        source=(row['source']['kind'],row['source']['id']);assert source not in face_lineage
        values={(item['kind'],item['id']) for item in row['survivors']};assert len(values)==len(row['survivors']) and values<=ns['faces']
        face_lineage[source]=values
        field='polygons' if source[0]=='polygon' else 'triangles'
        original={vmap[v] for v in old[field][source[1]]['vertices']}
        for kind,id in values:
            face=new['polygons' if kind=='polygon' else 'triangles'][id]
            assert set(face['vertices'])<=original,'face lineage leaves its mapped source corners'
    assert set(face_lineage)==bs['faces']
    assert set().union(*face_lineage.values())==ns['faces'],'missing face lineage'

def compare_phase(source,state):
    assert set(state['scene']['entities'])==set(source['objects'])
    for id,world in state['worlds'].items():
        actual=frame_snapshot(world,state['scene'],id)
        pilot.tree({key:source['objects'][id][key] for key in actual},actual,'object/'+id)
    for id in ['target','secondary']:
        pilot.compare(source['meshes'][id],state['query'],state['worlds'][id])
    pilot.tree(source['cursor']['location'],state['scene']['authoring_context']['cursor_location'],'cursor/location')
    pilot.tree(source['cursor']['rotation'],state['scene']['authoring_context']['cursor_rotation'],'cursor/rotation')

def validate_transport(record):
    expected=[('scene_apply',record['setup'],{'revision':1},None)]
    for phase in ['before','after']:
        state=record[phase]
        expected.append(('scene_inspect',{}, {'revision':state['scene']['revision'],'scene':state['scene']},None))
        expected.append(('scene_inspect',{'mesh_asset':'mesh','normals':True},state['query'],None))
        for id,world in state['worlds'].items():expected.append(('scene_inspect',{'entity':id,'world':True},world,None))
        if phase=='before':expected.append(('scene_apply',record['request'],record['result'],record['error']))
    processes=record['cli_processes'];assert processes and processes[0]['command'][2]=='init' and processes[0]['exit']==0
    fresh=processes[-1];assert fresh['command'][2]=='inspect' and fresh['exit']==0
    assert json.loads(fresh['stdout'])=={'revision':record['after']['scene']['revision'],'scene':record['saved_scene']},'fresh process binding differs'
    if record['interface']=='official_mcp_sdk':
        rows=record['mcp_responses'];assert len(rows)==len(expected),'missing or duplicate MCP response'
        for row,(name,arguments,result,error) in zip(rows,expected):
            assert row['tool']==name and row['arguments']==arguments,'MCP request binding differs'
            response=row['response']
            assert response['is_error']==(error is not None)
            if error is None:assert response['structured_content']==result,'MCP raw result binding differs'
            else:assert response['structured_content'] is None and response['content'][0]['text']==error
        assert len(processes)==2,'unexpected native path substituted for MCP'
    else:
        rows=processes[1:-1];assert len(rows)==len(expected),'missing or duplicate CLI process'
        for row,(name,arguments,result,error) in zip(rows,expected):
            command=row['command'];action=command[2]
            assert action==('apply' if name=='scene_apply' else 'inspect')
            if action=='apply':assert row['request']==arguments,'CLI stdin request differs'
            else:
                actual={}
                if '--entity' in command:actual={'entity':command[command.index('--entity')+1],'world':'--world' in command}
                elif '--mesh-asset' in command:actual={'mesh_asset':command[command.index('--mesh-asset')+1],'normals':'--normals' in command}
                assert actual==arguments,'CLI query binding differs'
            assert (row['exit']==0)==(error is None),'CLI terminal result differs'
            value=json.loads(row['stdout'])
            assert value==(result if error is None else {'error':error}),'CLI raw result binding differs'


def check_record(case,references,record):
    validate_transport(record)
    before,after=record['before'],record['after']
    assert record['saved_scene']==after['scene'] and record['fresh_reload_matches']
    for field in ['entities','materials','object_context','authoring_context']:
        assert before['scene'][field]==after['scene'][field],'unrelated scene field changed/'+field
    for reference in references:
        compare_phase(reference['before'],before);compare_phase(reference['after'],after)
        if reference['result']['status']==['ENUM_REJECTED']:
            assert case['expected_empty_enum_boundary'] and record['error'] and record['result'] is None
            assert 'merge method unavailable' in record['error'] and before==after and record['saved_before_sha256']==record['saved_after_sha256']
        else:
            assert record['error'] is None and after['scene']['revision']==record['result']['revision']==2
            validate_receipt(before,after,record['result'],record['request'])

def source_preflight(suite):
    assert suite==author()
    folders=[ROOT/'docs/evidence/mesh-merge-baseline'/name for name in ['native-01','native-02']]
    manifests=[pilot.load(folder/'manifest.json') for folder in folders];pids=[]
    for folder,manifest in zip(folders,manifests):
        terminal=pilot.load(folder.parent/(folder.name+'-process')/'terminal.json')
        assert terminal['terminal_exit_code']==0 and terminal['process_id']==manifest['process_id']
        assert terminal['manifest_sha256']==sha(folder/'manifest.json') and terminal['capture_lock_sha256']==sha(folder/'capture-lock.json')==manifest['capture_lock_sha256']
        assert [row['id'] for row in manifest['runs']]==[case['id'] for case in suite['runs']]
        assert manifest['scope']=='complete_1024_authored_mesh_merge_cases' and manifest['binary_sha256']=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
        for row in manifest['runs']:assert sha(folder/row['file'])==row['sha256']
        # Verify original capture inputs in the admitted Git snapshot. Absent
        # sparse paths are read as Git objects; they are never fed to Rust.
        for absolute,digest in manifest['input_hashes'].items():
            relative=absolute.split('/formora/',1)[1]
            raw=(folder/'capture-lock.json').read_bytes() if relative=='baseline/lock.json' else subprocess.check_output(['git','show','74a4fc5b852be620e3a1fd9329aa6e73a01e52e1:'+relative],cwd=ROOT)
            import hashlib
            assert hashlib.sha256(raw).hexdigest()==digest,relative
            path=ROOT/relative
            if relative!='baseline/lock.json' and path.exists():assert sha(path)==digest,relative
        pids.append(manifest['process_id'])
    assert len(set(pids))==2 and manifests[0]['input_hashes']==manifests[1]['input_hashes']
    counts={'changed_geometry':0,'unchanged_geometry':0,'enum_rejected':0}
    for case in suite['runs']:
        refs=[pilot.load(folder/(case['id']+'.json.gz')) for folder in folders]
        result=compare_case(suite,case,*refs)
        counts['enum_rejected' if result['enum_rejected'] else 'changed_geometry' if result['geometry_changed'] else 'unchanged_geometry']+=1
    assert counts=={'changed_geometry':920,'unchanged_geometry':88,'enum_rejected':16}
    return folders,{'passed':True,'cases':1024,'native_processes':pids,'outcomes':counts,'captured_inputs_verified':True}

async def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False);binary=args.binary.resolve();binary_hash=sha(binary)
    suite=pilot.load(ROOT/'baseline/fixtures/mesh-merge.json');folders,source=source_preflight(suite)
    cases=[case for case in suite['runs'] if not args.case or case['id'] in args.case]
    interfaces=args.interface or ['cli','official_mcp_sdk']
    def inputs():return sorted([p for name in ['src','tests','tools','docs/contracts'] for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']+[Path(__file__).resolve(),HERE/'pilot-native.py',ROOT/'baseline/fixtures/mesh-merge.json',ROOT/'baseline/fixtures/mesh-selection.json'])
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in inputs()};records=[]
    for interface in interfaces:
        for index,case in enumerate(cases):
            record={'case':case,'interface':interface,'setup':pilot.setup(suite,case),'request':{'expected_revision':1,'commands':[{'operation':'merge_mesh','merge':{'entity':'target','method':case['parameters']['type'].lower(),'uvs':case['parameters']['uvs']}}]},'error':None,'comparison_error':None}
            with tempfile.TemporaryDirectory(prefix='formora-merge-'+interface+'-') as temporary:
                scene=Path(temporary)/'scene.json';cli_calls=[]
                def cli(action,*flags,request=None):
                    command=[str(binary),'scene',action,'--scene',str(scene),*flags]
                    process=subprocess.run(command,input=None if request is None else json.dumps(request),capture_output=True,text=True)
                    cli_calls.append({'command':command,'request':request,'exit':process.returncode,'stdout':process.stdout,'stderr':process.stderr})
                    response=json.loads(process.stdout)
                    return (response,None) if process.returncode==0 else (None,response['error'])
                _,error=cli('init');assert error is None
                async def exercise(call):
                    _,error=await call('scene_apply',record['setup']);assert error is None,error
                    async def inspect():
                        value,error=await call('scene_inspect',{});assert error is None
                        query,error=await call('scene_inspect',{'mesh_asset':'mesh','normals':True});assert error is None
                        worlds={}
                        for id in value['scene']['entities']:
                            world,error=await call('scene_inspect',{'entity':id,'world':True});assert error is None;worlds[id]=world
                        return {'scene':value['scene'],'query':query,'worlds':worlds}
                    record['before']=await inspect();record['saved_before_sha256']=sha(scene)
                    record['result'],record['error']=await call('scene_apply',record['request'])
                    record['after']=await inspect();record['saved_after_sha256']=sha(scene);record['saved_scene']=pilot.load(scene)
                    fresh,error=cli('inspect');assert error is None and fresh['scene']==record['after']['scene']
                    record['fresh_reload_matches']=True
                if interface=='cli':
                    async def call(name,arguments):
                        if name=='scene_apply':return cli('apply','--request','-',request=arguments)
                        if 'entity' in arguments:return cli('inspect','--entity',arguments['entity'],'--world')
                        return cli('inspect',*(['--mesh-asset','mesh','--normals'] if arguments else []))
                    await exercise(call)
                else:
                    async with stdio_client(StdioServerParameters(command=str(binary),args=['mcp','--scene',str(scene)])) as (reader,writer):
                        async with ClientSession(reader,writer,read_timeout_seconds=10) as client:
                            initialized=await client.initialize();schemas={tool.name:tool.input_schema for tool in (await client.list_tools()).tools};record['mcp_initialization']=initialized.model_dump(mode='json');record['mcp_responses']=[]
                            async def call(name,arguments):
                                Draft202012Validator(schemas[name]).validate(arguments);response=await client.call_tool(name,arguments)
                                record['mcp_responses'].append({'tool':name,'arguments':arguments,'response':response.model_dump(mode='json')})
                                return (None,response.content[0].text) if response.is_error else (response.structured_content,None)
                            await exercise(call)
                record['cli_processes']=cli_calls
                try:
                    references=[pilot.load(folder/(case['id']+'.json.gz')) for folder in folders]
                    check_record(case,references,record)
                except (AssertionError,KeyError,ValueError) as failure:record['comparison_error']=str(failure) or type(failure).__name__
            record['status']='passed' if record['comparison_error'] is None else 'failed'
            path=write_json(output/(interface+'-'+case['id']+'.json'),record,True)
            records.append({'id':case['id'],'interface':interface,'file':path.name,'sha256':sha(path),'status':record['status'],'error':record['comparison_error']})
            if (index+1)%50==0:print(json.dumps({'interface':interface,'executed':index+1,'failed':sum(row['status']=='failed' for row in records)}),flush=True)
    unchanged=hashes=={p.relative_to(ROOT).as_posix():sha(p) for p in inputs()} and sha(binary)==binary_hash
    passed=unchanged and all(row['status']=='passed' for row in records);full=not args.case and set(interfaces)=={'cli','official_mcp_sdk'} and len(interfaces)==2
    report={'passed':passed,'checks':len(records),'required_full_gate_passed':passed and full and len(records)==2048,'source_checked':source,'binary_sha256':binary_hash,'input_hashes':hashes,'inputs_unchanged':unchanged,'runs':records,'product_acceptance':'unrun','three_platform_ci':'unrun','integration':'unrun','independent_acceptance':'unrun'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({key:report[key] for key in ['passed','checks','required_full_gate_passed']}),flush=True)
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--case',action='append',default=[]);parser.add_argument('--interface',action='append',choices=['cli','official_mcp_sdk']);asyncio.run(run(parser.parse_args()))
