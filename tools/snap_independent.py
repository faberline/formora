#!/usr/bin/env python3
"""Exercise unseen native snap requests with repository reads denied."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);calls=[]
    with tempfile.TemporaryDirectory(prefix='formora-snap-independent-') as temporary, ExitStack() as cleanup:
        folder=Path(temporary);binary=folder/'formora';shutil.copyfile(args.binary.resolve(),binary);binary.chmod(0o755)
        policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))'
        prefix=['/usr/bin/sandbox-exec','-p',policy]
        control=subprocess.run([*prefix,'/bin/cat',str(root/'baseline/fixtures/snap-menu.json')],cwd=folder,capture_output=True,text=True)
        assert control.returncode!=0 and not control.stdout and ('not permitted' in control.stderr or 'Permission denied' in control.stderr)
        path=folder/'scene.json'
        init=subprocess.run([*prefix,str(binary),'scene','init','--scene',str(path)],cwd=folder,capture_output=True,text=True,check=True)
        process=cleanup.enter_context(subprocess.Popen([*prefix,str(binary),'scene','serve','--scene',str(path)],cwd=folder,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
        sequence=0
        def call(name,args,error=False):
            nonlocal sequence
            sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':args})+'\n');process.stdin.flush()
            response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok'] is (not error),response
            calls.append({'name':name,'arguments':args,'response':response})
            with (out/'calls.jsonl').open('a') as stream:stream.write(json.dumps(calls[-1],allow_nan=False)+'\n')
            return response['error'] if error else response['result']
        def inspect():return call('scene_inspect',{})['scene']
        def snap(action,revision,**extra):return {'expected_revision':revision,'commands':[{'operation':'snap_mesh','snap':{'entity':'target','action':action,**extra}}]}
        asset={'vertices':{'a':[-.5,-1.5,.5],'b':[1.375,-.625,.375],'c':[.25,1.75,.125],'hidden':[-.5,-1.5,.5]},
            'triangles':{'t':{'vertices':['a','b','c'],'uv_layers':{'UV':[[0,0],[1,0],[.5,1]]},'corner_normals':None,'material_slot':None}},
            'polygons':{},'material_slots':[],'vertex_groups':['Keep'],'vertex_weights':{'a':{'Keep':.75}}}
        entity={'name':'Unseen','parent':None,'transform':{'translation':[0,0,0],'rotation':[0,0,0,1],'scale':[1,1,1],'precision':'f32'},
            'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None}}
        setup={'expected_revision':0,'commands':[{'operation':'set_mesh_asset','id':'mesh','asset':asset},
            {'operation':'set_mesh_editing','id':'mesh','editing':{'mode':['vertex'],'selected':{'vertices':['a','b']},'hidden':{'vertices':['hidden']},
                'history':[{'domain':'vertex','id':'b'}],'active_face':None}},
            {'operation':'create_entity','id':'target','entity':entity},{'operation':'create_entity','id':'shared','entity':{**entity,'name':'Shared'}},
            {'operation':'set_authoring_context','context':{'cursor_location':[.37,-.62,.87],'cursor_rotation':[.17,.23,.41],'view_rotation':[.1,.2,.3]}}]}
        call('scene_apply',setup);before=inspect();request=snap({'kind':'selected_to_grid','spacing':1.},1)
        receipt=call('scene_apply',request);after=inspect();m=after['mesh_assets']['mesh'];old=before['mesh_assets']['mesh']
        assert m['vertices']=={**old['vertices'],'a':[0.,-1.,1.],'b':[1.,-1.,0.]}
        assert m['editing']==old['editing'] and m['vertex_groups']==old['vertex_groups'] and m['vertex_weights']==old['vertex_weights']
        assert m['triangles']['t']['uv_layers']==old['triangles']['t']['uv_layers'] and after['entities']==before['entities']
        assert receipt['snaps'][0]['changed']['vertices']==['a','b'] and receipt['snaps'][0]['shared_instances']==['shared','target']
        q=call('scene_inspect',{'mesh_asset':'mesh','normals':True});normal=q['normals']['faces'][0]['normal']
        a,b,c=[m['vertices'][id] for id in ['a','b','c']];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        n=[u[(i+1)%3]*v[(i+2)%3]-u[(i+2)%3]*v[(i+1)%3] for i in range(3)];length=math.sqrt(sum(x*x for x in n))
        assert all(abs(normal[i]-n[i]/length)<=1e-6 for i in range(3))
        saved=path.read_bytes()
        batch=snap({'kind':'selected_to_grid','spacing':.5},2);batch['commands'].append({'operation':'delete_entity','id':'missing'})
        assert call('scene_apply',batch,error=True);assert inspect()==after and path.read_bytes()==saved
        for invalid in [snap({'kind':'cursor_to_center'},0),snap({'kind':'cursor_to_center'},2,max_components=1),
                        snap({'kind':'cursor_to_center','answer':[0,0,0]},2)]:
            assert call('scene_apply',invalid,error=True);assert inspect()==after and path.read_bytes()==saved
        call('scene_undo',{'expected_revision':2});restored=inspect();assert {k:v for k,v in restored.items() if k!='revision'}=={k:v for k,v in before.items() if k!='revision'}
        call('scene_apply',{**request,'expected_revision':3});replay=inspect();assert {k:v for k,v in replay.items() if k!='revision'}=={k:v for k,v in after.items() if k!='revision'}
        origin=call('scene_apply',snap({'kind':'cursor_to_center'},4));assert origin['snaps'][0]['cursor_rotation_after']==[0.,0.,0.]
        assert inspect()['authoring_context']['cursor_location']==[0.,0.,0.]
        call('scene_undo',{'expected_revision':5});active=call('scene_apply',snap({'kind':'cursor_to_active'},6))
        assert active['snaps'][0]['target_world']==[1.,-1.,0.] and active['snaps'][0]['cursor_rotation_after']==before['authoring_context']['cursor_rotation'],(active['snaps'][0],before['authoring_context'])
        call('scene_undo',{'expected_revision':7});final=inspect();assert {k:v for k,v in final.items() if k!='revision'}=={k:v for k,v in after.items() if k!='revision'}
        process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();assert process.returncode==0,stderr
        fresh=subprocess.run([*prefix,str(binary),'scene','inspect','--scene',str(path)],cwd=folder,capture_output=True,text=True,check=True)
        assert json.loads(fresh.stdout)['scene']==final
        for name,value in [('before',before),('after',after),('final',final),('receipt',receipt),('normal-query',q)]:
            (out/(name+'.json')).write_text(json.dumps(value,allow_nan=False)+'\n')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        report={'passed':True,'policy':policy,'denial_control_exit_code':control.returncode,'denial_control_stderr':control.stderr,
            'source_repository_reads':'denied by macOS sandbox','binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),
            'native_terminal_exit':process.returncode,'fresh_process_exit':fresh.returncode,'fresh_reload_equal':True,
            'unseen_geometry_analytic_match':True,'normal_analytic_match':True,'shared_asset_preserved':True,
            'stale_budget_unknown_field_and_batch_rejections_atomic':True,'undo_replay_checked':True,'cursor_origin_active_checked':True,
            'setup':setup,'calls':calls,'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'product_acceptance':'unrun'}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'repository_reads':'denied','native_calls':len(calls)}))


if __name__=='__main__':main()
