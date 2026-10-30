"""Exercise the frozen merge recipe and atomic-range rules on real CLI/MCP state."""
import asyncio
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')
OUT=Path('/private/tmp/formora-multi-merge-retained-recipe-01')
BINARY=Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
EXPECTED='64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019'

async def trial(interface,method,uvs):
    folder=OUT/f'{interface}-{method}-{uvs}';folder.mkdir()
    path=folder/'scene.json';calls=[];processes=[]
    def cli(action):
        command=[str(BINARY),'scene',action,'--scene',str(path)]
        p=subprocess.run(command,capture_output=True,text=True)
        processes.append({'command':command,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        assert p.returncode==0,p.stdout+p.stderr
        return json.loads(p.stdout)
    cli('init')
    async def exercise(call):
        def entity(id,parent,translation,rotation,scale,mesh=True):
            return {'operation':'create_entity','id':id,'entity':{'name':id,'parent':parent,'transform':{'translation':translation,'rotation':{'kind':'euler','angles':rotation,'order':'yxz'},'scale':scale,'precision':'f32'},'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None} if mesh else {'kind':'empty'}}}
        async def inspect():return (await call('scene_inspect',{}))['scene']
        async def apply(revision,commands,error=False):return await call('scene_apply',{'expected_revision':revision,'commands':commands},error)
        await apply(0,[{'operation':'create_mesh_primitive','id':'mesh','primitive':{'kind':'cube','size':1.7}},entity('parent',None,[1.125,-.75,.625],[.17,-.29,.41],[1.2,.7,1.6],False),entity('cube','parent',[.25,-.5,.75],[.13,.23,-.37],[-1.,2.,.8]),entity('other',None,[-3.,2.,1.],[.1,.2,.3],[.9,1.1,1.3]),{'operation':'set_authoring_context','context':{'cursor_location':[2.125,-1.3125,.75],'cursor_rotation':[.17,.23,.41]}}])
        initial=await inspect();original=copy.deepcopy(initial['mesh_assets']['mesh']);assert original['recipe']['edited'] is False
        assert len(original['vertices'])==8 and len(original['edges'])==12 and len(original['polygons'])==6
        await apply(initial['revision'],[{'operation':'set_mesh_editing','id':'mesh','editing':{'mode':['vertex'],'selected':{},'preview':False}},{'operation':'set_object_context','context':{'order':['parent','cube','other'],'selected':['cube'],'active':'cube','edit_objects':['cube']}}])
        empty=await inspect();noop=await apply(empty['revision'],[{'operation':'merge_mesh','merge':{'entity':'cube','method':'center','uvs':uvs}}]);empty_after=await inspect()
        assert noop['merges'][0]['reason']=='no_available_merge_target'
        assert empty_after['mesh_assets']==empty['mesh_assets'] and empty_after['mesh_assets']['mesh']['recipe']['edited'] is False
        ids=sorted(original['vertices'])
        editing={'mode':['vertex'],'selected':{'vertices':ids,'edges':sorted(original['edges']),'faces':[{'kind':'polygon','id':id} for id in sorted(original['polygons'])]},'history':[{'domain':'vertex','id':ids[0]},{'domain':'vertex','id':ids[-1]}],'preview':False}
        await apply(empty_after['revision'],[{'operation':'set_mesh_editing','id':'mesh','editing':editing}])
        before=await inspect();assert before['mesh_assets']['mesh']['recipe']['edited'] is False
        fresh=copy.deepcopy(original);old_editing=before['mesh_assets']['mesh']['editing']
        fresh['editing']={'mode':old_editing['mode'],'selected':{'vertices':[],'edges':[],'faces':[]},'hidden':{'vertices':[],'edges':[],'faces':[]},'history':[],'active_face':None}
        if old_editing.get('preview',True) is False:fresh['editing']['preview']=False
        request={'operation':'merge_mesh','merge':{'entity':'cube','method':method,'uvs':uvs}}
        integer=copy.deepcopy(before['mesh_assets']['mesh']);integer['integer_attributes']={'vertices':{'extreme':{id:2147483647 for id in ids}},'edges':{},'polygons':{},'triangles':{}}
        large=copy.deepcopy(before['mesh_assets']['mesh']);large['vertices']={id:[1e100,1e100,1e100] for id in ids}
        controls=[('stale',before['revision']-1,[request],None),('budget',before['revision'],[{'operation':'merge_mesh','merge':{**request['merge'],'max_components':1}}],None),('unknown',before['revision'],[{'operation':'merge_mesh','merge':{**request['merge'],'reference_path':'not-an-operation-input'}}],None),('late_batch',before['revision'],[request,{'operation':'delete_entity','id':'missing'}],None),('integer_overflow',before['revision'],[{'operation':'set_mesh_asset','id':'mesh','asset':integer},{'operation':'merge_mesh','merge':{'entity':'cube','method':'center','uvs':uvs}}],'integer vertex interpolation exceeds i32 range'),('coordinate_overflow',before['revision'],[{'operation':'set_mesh_asset','id':'mesh','asset':large},{'operation':'merge_mesh','merge':{'entity':'cube','method':'center','uvs':uvs}}],'mesh snap coordinates must fit finite f32 values')]
        rejected=[]
        for name,revision,commands,message in controls:
            saved=path.read_bytes();error=await apply(revision,commands,True)
            if message is not None:assert message in error,(name,error)
            assert await inspect()==before and path.read_bytes()==saved,name
            rejected.append({'name':name,'error':error,'disk_memory_revision_unchanged':True})
        receipt=await apply(before['revision'],[request]);after=await inspect();merged=after['mesh_assets']['mesh']
        assert merged['recipe']=={**before['mesh_assets']['mesh']['recipe'],'edited':True}
        assert len(merged['vertices'])==1 and not merged.get('edges') and not merged.get('polygons') and not merged['triangles']
        assert receipt['merges'][0]['shared_instances']==['cube','other'] and receipt['merges'][0]['before']=={'vertices':8,'edges':12,'faces':6,'corners':24} and receipt['merges'][0]['after']=={'vertices':1,'edges':0,'faces':0,'corners':0}
        assert after['entities']==before['entities'] and after['object_context']==before['object_context'] and after['authoring_context']==before['authoring_context']
        await call('scene_undo',{'expected_revision':after['revision']});restored=await inspect()
        assert {k:v for k,v in restored.items() if k!='revision'}=={k:v for k,v in before.items() if k!='revision'}
        replay=await apply(restored['revision'],[request]);replayed=await inspect()
        assert replay['merges']==receipt['merges'] and replayed['mesh_assets']==after['mesh_assets']
        regenerate={'operation':'regenerate_mesh_primitive','id':'mesh'}
        await apply(replayed['revision'],[regenerate]);regenerated=await inspect()
        assert regenerated['mesh_assets']['mesh']==fresh and regenerated['entities']==after['entities']
        await call('scene_undo',{'expected_revision':regenerated['revision']});undone_regeneration=await inspect()
        assert undone_regeneration['mesh_assets']==after['mesh_assets']
        await apply(undone_regeneration['revision'],[regenerate]);final=await inspect()
        assert final['mesh_assets']['mesh']==fresh and final['entities']==before['entities']
        assert cli('inspect')=={'revision':final['revision'],'scene':final}
        return {'before':before,'after':after,'regenerated':regenerated,'final':final,'initial_generated_asset':original,'receipt':receipt,'rejected':rejected,'noop_receipt':noop,'regeneration_undo_replay_checked':True,'fresh_reload_equal':True}
    terminal=None
    if interface=='native_cli_server':
        command=[str(BINARY),'scene','serve','--scene',str(path)]
        p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        async def call(name,arguments,error=False):
            request={'id':len(calls)+1,'name':name,'arguments':arguments};p.stdin.write(json.dumps(request)+'\n');p.stdin.flush();response=json.loads(p.stdout.readline())
            calls.append({'request':request,'response':response});assert response['id']==request['id'] and response['ok'] is (not error),response
            return response['error'] if error else response['result']
        try:result=await exercise(call)
        finally:
            p.stdin.close();code=p.wait(timeout=10);stderr=p.stderr.read();p.stdout.close();p.stderr.close();terminal={'command':command,'pid':p.pid,'exit':code,'stderr':stderr}
            (folder/'native-terminal.json').write_text(json.dumps(terminal,indent=2)+'\n')
            (folder/'native-calls.json').write_text(json.dumps(calls,indent=2)+'\n')
        assert code==0,stderr
    else:
        async with stdio_client(StdioServerParameters(command=str(BINARY),args=['mcp','--scene',str(path)])) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=10) as client:
                initialized=await client.initialize();schemas={tool.name:tool.input_schema for tool in (await client.list_tools()).tools}
                async def call(name,arguments,error=False):
                    if not error:Draft202012Validator(schemas[name]).validate(arguments)
                    response=await client.call_tool(name,arguments);raw=response.model_dump(mode='json');calls.append({'name':name,'arguments':arguments,'response':raw})
                    assert response.is_error is error,raw
                    return response.content[0].text if error else response.structured_content
                result=await exercise(call)
                result['mcp_initialization']=initialized.model_dump(mode='json');result['mcp_tools']=schemas
    result.update(interface=interface,method=method,uvs=uvs,calls=calls,cli_processes=processes,native_terminal=terminal,binary_sha256=sha(BINARY),saved_scene_sha256=sha(path),passed=True)
    target=folder/'record.json.gz';target.write_bytes(gzip.compress(json.dumps(result,allow_nan=False).encode(),mtime=0))
    return {'interface':interface,'method':method,'uvs':uvs,'calls':len(calls),'file':target.relative_to(OUT).as_posix(),'sha256':sha(target),'passed':True}

async def main():
    assert sha(BINARY)==EXPECTED;OUT.mkdir(exist_ok=False);rows=[]
    protected=[p for name in ['src','tests','tools','docs/contracts'] for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'];hashes={str(p.relative_to(ROOT)):sha(p) for p in protected}
    for interface in ['native_cli_server','official_mcp_sdk']:
        for method in ['center','cursor','collapse','first','last']:
            for uvs in [False,True]:
                row=await trial(interface,method,uvs);rows.append(row);print(json.dumps(row),flush=True)
    assert len(rows)==20 and sha(BINARY)==EXPECTED and hashes=={str(p.relative_to(ROOT)):sha(p) for p in protected}
    report={'passed':True,'cases':20,'primary_weld_requests':20,'successful_merge_requests_including_noops_and_replay':60,'negative_atomic_controls':120,'records':rows,'binary_sha256':EXPECTED,'implementation_commit':'bd13f3d424f2649b4b25c16305c4e5b0eb7f8542','input_hashes':hashes,'inputs_unchanged':True,'driver_sha256':sha(Path(__file__)),'contract':'existing frozen docs/contracts/mesh-merge-core.md; recipe, no-op, overflow, rollback, undo/replay and fresh reload requirements','source_answers_used_as_inputs':False,'one_shot_cli_mcp_2048_gate':'separate completed gate','native_cli_server_terminal_exits_checked':True,'official_mcp_sdk_transport_used':True,'product_acceptance':'unrun','independent_acceptance':'unrun'}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['passed','cases','negative_atomic_controls']}),flush=True)

if __name__=='__main__':asyncio.run(main())
