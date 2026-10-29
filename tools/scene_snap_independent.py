#!/usr/bin/env python3
"""Check unseen scene snaps while native sandbox rules deny repository reads."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);calls=[]
    with tempfile.TemporaryDirectory(prefix='formora-scene-snap-independent-') as temporary, ExitStack() as cleanup:
        folder=Path(temporary);binary=folder/'formora';shutil.copyfile(args.binary.resolve(),binary);binary.chmod(0o755)
        policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(root))+'))';prefix=['/usr/bin/sandbox-exec','-p',policy]
        control=subprocess.run([*prefix,'/bin/cat',str(root/'baseline/fixtures/snap-menu.json')],cwd=folder,capture_output=True,text=True)
        assert control.returncode!=0 and not control.stdout and ('not permitted' in control.stderr or 'Permission denied' in control.stderr)
        path=folder/'scene.json';subprocess.run([*prefix,str(binary),'scene','init','--scene',str(path)],cwd=folder,capture_output=True,text=True,check=True)
        process=cleanup.enter_context(subprocess.Popen([*prefix,str(binary),'scene','serve','--scene',str(path)],cwd=folder,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True));sequence=0
        def call(name,args,error=False):
            nonlocal sequence
            sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':args})+'\n');process.stdin.flush()
            response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok'] is (not error),response
            calls.append({'name':name,'arguments':args,'response':response})
            with (out/'calls.jsonl').open('a') as stream:stream.write(json.dumps(calls[-1],allow_nan=False)+'\n')
            return response['error'] if error else response['result']
        def inspect():return call('scene_inspect',{})['scene']
        def snap(action,revision,**extra):return {'expected_revision':revision,'commands':[{'operation':'snap_scene','snap':{'action':action,**extra}}]}
        asset={'vertices':{'a':[-.5,-1.5,.5],'b':[1.375,-.625,.375],'c':[.25,1.75,.125],'hidden':[-.5,-1.5,.5]},
            'triangles':{'t':{'vertices':['a','b','c'],'uv_layers':{'UV':[[0,0],[1,0],[.5,1]]},'corner_normals':None,'material_slot':None}},
            'polygons':{},'material_slots':[],'vertex_groups':['Keep'],'vertex_weights':{'a':{'Keep':.75}}}
        def entity(location,parent=None,mesh=True):
            return {'name':'Unseen','parent':parent,'transform':{'translation':location,'rotation':{'kind':'euler','angles':[0,0,0],'order':'xyz'},'scale':[1,1,1],'precision':'f32'},
                'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None} if mesh else {'kind':'empty'}}
        context={'order':['target','shared','child'],'selected':['target'],'active':'target','edit_objects':[],
            'states':{'target':{'lock_location':[True,False,False],'lock_rotation':[False]*3}},'skip_children':True,'origins_only':True}
        setup={'expected_revision':0,'commands':[{'operation':'set_mesh_asset','id':'mesh','asset':asset},
            {'operation':'set_mesh_editing','id':'mesh','editing':{'mode':['vertex'],'selected':{'vertices':['a','b']},'hidden':{'vertices':['hidden']},'history':[{'domain':'vertex','id':'b'}],'active_face':None}},
            {'operation':'create_entity','id':'target','entity':entity([.375,-.625,.875])},
            {'operation':'create_entity','id':'shared','entity':entity([-2,0,1])},
            {'operation':'create_entity','id':'child','entity':entity([.25,.5,.75],'target',False)},
            {'operation':'set_authoring_context','context':{'cursor_location':[.37,-.62,.87],'cursor_rotation':[.17,.23,.41],'view_rotation':[.1,.2,.3]}},
            {'operation':'set_object_context','context':context}]}
        call('scene_apply',setup);before=inspect();request=snap({'kind':'selected_to_grid','spacing':1.},1)
        receipt=call('scene_apply',request);after=inspect();mesh=after['mesh_assets']['mesh'];old=before['mesh_assets']['mesh']
        expected={id:[p[0],p[1]+.375,p[2]-.125] for id,p in old['vertices'].items()}
        assert mesh['vertices']==expected and mesh['editing']==old['editing'] and mesh['triangles']['t']['uv_layers']==old['triangles']['t']['uv_layers']
        assert mesh['vertex_groups']==old['vertex_groups'] and mesh['vertex_weights']==old['vertex_weights']
        assert after['entities']['target']['transform']['translation']==[.375,-1.,1.] and after['entities']['child']==before['entities']['child']
        assert receipt['scene_snaps'][0]['meshes'][0]['shared_instances']==['shared','target']
        q={id:call('scene_inspect',{'entity':id,'world':True}) for id in ['target','shared','child']}
        assert [q['child']['world_matrix'][i][3] for i in range(3)]==[.625,-.125,1.625]
        assert q['target']['world_vertices']['a']==[-.125,-2.125,1.375]
        assert q['shared']['world_vertices']['a']==[-2.5,-1.125,1.375]
        assert after['authoring_context']==before['authoring_context'];saved=path.read_bytes()
        batch=snap({'kind':'cursor_to_center'},2);batch['commands'].append({'operation':'delete_entity','id':'missing'})
        for invalid in [batch,snap({'kind':'cursor_to_center'},0),snap({'kind':'cursor_to_center'},2,max_objects=1),snap({'kind':'cursor_to_center','answer':[1,2,3]},2)]:
            assert call('scene_apply',invalid,error=True);assert inspect()==after and path.read_bytes()==saved
        call('scene_undo',{'expected_revision':2});restored=inspect();assert {k:v for k,v in restored.items() if k!='revision'}=={k:v for k,v in before.items() if k!='revision'}
        call('scene_apply',{**request,'expected_revision':3});replay=inspect();assert {k:v for k,v in replay.items() if k!='revision'}=={k:v for k,v in after.items() if k!='revision'}
        context={**context,'selected':['target','shared'],'active':'shared','edit_objects':['shared'],'skip_children':False,'origins_only':False}
        call('scene_apply',{'expected_revision':4,'commands':[{'operation':'set_object_context','context':context}]})
        edited=call('scene_apply',snap({'kind':'selected_to_grid','spacing':1.},5));state=inspect();m=state['mesh_assets']['mesh']
        assert m['vertices']=={**expected,'a':[0.,-1.,0.],'b':[1.,0.,0.]}
        assert len(edited['scene_snaps'][0]['edit_meshes'])==1 and edited['scene_snaps'][0]['edit_meshes'][0]['entity']=='shared'
        normal=call('scene_inspect',{'mesh_asset':'mesh','normals':True})['normals']['faces'][0]['normal'];assert normal==[0.,0.,1.]
        active=call('scene_apply',snap({'kind':'cursor_to_active'},6));assert active['scene_snaps'][0]['target_world']==[-1.,0.,1.]
        assert active['scene_snaps'][0]['cursor_rotation_after']==[.17,.23,.41]
        final=inspect();process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();assert process.returncode==0,stderr
        fresh=subprocess.run([*prefix,str(binary),'scene','inspect','--scene',str(path)],cwd=folder,capture_output=True,text=True,check=True);assert json.loads(fresh.stdout)['scene']==final
        for name,value in [('before',before),('after-object',after),('after-edit',state),('final',final),('object-receipt',receipt),('edit-receipt',edited),('world-queries',q)]:
            (out/(name+'.json')).write_text(json.dumps(value,allow_nan=False)+'\n')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        report={'passed':True,'policy':policy,'denial_control_exit_code':control.returncode,'denial_control_stderr':control.stderr,
            'repository_reads':'denied by macOS sandbox','binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),
            'native_terminal_exit':process.returncode,'fresh_process_exit':fresh.returncode,'fresh_reload_equal':True,
            'unseen_geometry_and_normal_analytic_match':True,'shared_data_and_child_inverse_checked':True,'locks_checked':True,
            'stale_object_budget_unknown_field_and_batch_rejections_atomic':True,'undo_replay_checked':True,'cursor_rotation_exactly_preserved':True,
            'setup':setup,'native_calls':len(calls),'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'product_acceptance':'unrun'}
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'repository_reads':'denied','native_calls':len(calls)}))

if __name__=='__main__':main()
