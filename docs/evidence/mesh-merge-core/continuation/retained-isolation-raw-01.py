"""Use unseen raw rotations with repository reads denied to native processes."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[4]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def near(a,b):
    if isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):near(x,y)
    else:assert math.isfinite(a) and math.isfinite(b) and abs(a-b)<=1e-6,(a,b)
def channels(mode='quaternion',euler=None,q=None,axis=None):
    return {'mode':mode,'euler':euler or [.12345678901234567,-.27,.43],
            'quaternion_wxyz':q or [.5,-.5,.5,.5],'axis_angle':axis or [.71,-3.,2.,4.]}
def transform(raw,location=None):
    return {'translation':location or [0.,0.,0.],'rotation':{'kind':'channels','channels':raw},'scale':[1.,1.,1.],'precision':'f32'}
def entity(raw,location=None,parent=None,mesh=True):
    return {'name':'Unseen raw rotation','parent':parent,'transform':transform(raw,location),
            'content':{'kind':'mesh','geometry':{'kind':'asset','id':'mesh'},'material':None} if mesh else {'kind':'empty'}}
def authoring(raw,location):return {'cursor_location':location,'cursor_rotation':raw['euler'],'cursor_orientation':raw}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);calls=[]
    with tempfile.TemporaryDirectory(prefix='formora-raw-rotation-denied-') as temporary,ExitStack() as cleanup:
        folder=Path(temporary);binary=folder/'formora';shutil.copyfile(args.binary.resolve(),binary);binary.chmod(0o755)
        policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(ROOT))+')(subpath '+json.dumps('/Users/chrischeng/faberlines/formora')+'))'
        prefix=['/usr/bin/sandbox-exec','-p',policy]
        control=subprocess.run([*prefix,'/bin/cat',str(ROOT/'Cargo.toml')],cwd=folder,capture_output=True,text=True)
        assert control.returncode!=0 and not control.stdout and ('not permitted' in control.stderr or 'Permission denied' in control.stderr)
        path=folder/'scene.json';subprocess.run([*prefix,str(binary),'scene','init','--scene',str(path)],cwd=folder,capture_output=True,text=True,check=True)
        process=cleanup.enter_context(subprocess.Popen([*prefix,str(binary),'scene','serve','--scene',str(path)],cwd=folder,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True));sequence=0
        def call(name,arguments,error=False):
            nonlocal sequence
            sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':arguments})+'\n');process.stdin.flush()
            result=json.loads(process.stdout.readline());assert result['id']==sequence and result['ok'] is (not error),result
            calls.append({'name':name,'arguments':arguments,'response':result})
            with (out/'calls.jsonl').open('a') as stream:stream.write(json.dumps(calls[-1],allow_nan=False)+'\n')
            return result['error'] if error else result['result']
        def inspect():return call('scene_inspect',{})
        def request(action,revision,**fields):return {'expected_revision':revision,'commands':[{'operation':'snap_scene','snap':{'action':action,**fields}}]}
        selected={'kind':'selected_to_cursor','use_offset':False,'use_rotation':True}
        raw=channels();cursor=channels(q=[.8,0.,0.,.6]);zero=channels('xyz',euler=[0.,0.,0.])
        asset={'vertices':{'a':[1.,0.,0.],'b':[0.,1.,0.],'c':[0.,0.,1.]},
            'triangles':{'tri':{'vertices':['a','b','c'],'uv_layers':{'UV':[[0,0],[1,0],[0,1]]},'corner_normals':None,'material_slot':None}},
            'material_slots':[],'editing':{'selected':{'vertices':['a']},'history':[{'domain':'vertex','id':'a'}]}}
        context={'order':['target','linked','follower','parent','parented'],'selected':['target'],'active':'target',
            'states':{'target':{'lock_rotation':[True,False,False],'lock_rotation_w':False,'lock_rotations_4d':True}},'skip_children':True}
        setup={'expected_revision':0,'commands':[{'operation':'set_mesh_asset','id':'mesh','asset':asset},
            {'operation':'create_entity','id':'target','entity':entity(raw,[.25,-.5,.75])},
            {'operation':'create_entity','id':'linked','entity':entity(raw,[-2.,1.,0.])},
            {'operation':'create_entity','id':'follower','entity':entity(zero,[.25,-.5,.75],'target',False)},
            {'operation':'create_entity','id':'parent','entity':entity(channels('xyz',euler=[0.,0.,math.pi/2]),[1.,2.,3.],mesh=False)},
            {'operation':'create_entity','id':'parented','entity':entity(channels('xzy',euler=[0.,0.,0.]),[.25,.75,-.5],'parent')},
            {'operation':'set_authoring_context','context':authoring(cursor,[1.25,-.75,.5])},
            {'operation':'set_object_context','context':context}]}
        call('scene_apply',setup);before=inspect()['scene'];child_before=call('scene_inspect',{'entity':'follower','world':True})
        first_request=request(selected,1);first=call('scene_apply',first_request);after=inspect()['scene']
        value=after['entities']['target']['transform']['rotation']['channels'];q=value['quaternion_wxyz']
        assert q==[f32(.8),-.5,0.,f32(.6)] and sum(x*x for x in q)>1.2
        assert value['euler']==raw['euler'] and value['axis_angle']==raw['axis_angle']
        assert after['mesh_assets']==before['mesh_assets'] and after['entities']['linked']==before['entities']['linked']
        world=call('scene_inspect',{'entity':'target','world':True});near(world['world_vertices']['a'],[1.674,.018,.02])
        child_after=call('scene_inspect',{'entity':'follower','world':True});near(child_before['world_matrix'],child_after['world_matrix'])
        assert after['object_context']['states']['follower']['parent_inverse']!=before['object_context']['states'].get('follower',{}).get('parent_inverse')
        assert {v['entity'] for v in first['scene_snaps'][0]['objects']}=={'target','follower'}
        saved=path.read_bytes();late=request({'kind':'cursor_to_center'},2);late['commands'].append({'operation':'delete_entity','id':'missing'})
        for invalid in [late,request(selected,0),request(selected,2,max_objects=0),request({'kind':'cursor_to_center','answer':[1,2,3]},2)]:
            assert call('scene_apply',invalid,error=True);assert inspect()['scene']==after and path.read_bytes()==saved
        call('scene_undo',{'expected_revision':2});restored=inspect()['scene']
        assert {k:v for k,v in restored.items() if k!='revision'}=={k:v for k,v in before.items() if k!='revision'}
        call('scene_apply',{**first_request,'expected_revision':3});replay=inspect()['scene']
        assert {k:v for k,v in replay.items() if k!='revision'}=={k:v for k,v in after.items() if k!='revision'}
        parent_cursor=channels('axis_angle',axis=[math.pi,0.,0.,2.])
        call('scene_apply',{'expected_revision':4,'commands':[
            {'operation':'set_object_context','context':{'order':context['order'],'selected':['parented'],'active':'parented'}},
            {'operation':'set_authoring_context','context':authoring(parent_cursor,[3.,4.,5.])}]})
        parented_before=inspect()['scene'];parent_result=call('scene_apply',request(selected,5));parent_query=call('scene_inspect',{'entity':'parented','world':True})
        near(parent_query['world_vertices']['a'],[2.,4.,5.]);parented_after=inspect()['scene']
        assert parented_after['entities']['parented']['transform']['rotation']['channels']['mode']=='xzy'
        for field in ['quaternion_wxyz','axis_angle']:
            assert parented_after['entities']['parented']['transform']['rotation']['channels'][field]==parented_before['entities']['parented']['transform']['rotation']['channels'][field]
        clear=channels('axis_angle',axis=[1.13,2.,-1.,3.])
        call('scene_apply',{'expected_revision':6,'commands':[{'operation':'set_authoring_context','context':authoring(clear,[.25,-.75,1.25])}]})
        cleared=call('scene_apply',{'expected_revision':7,'commands':[{'operation':'snap_mesh','snap':{'entity':'target','action':{'kind':'cursor_to_center'}}}]})
        final_inspection=inspect();final=final_inspection['scene'];final_cursor=final['authoring_context']['cursor_orientation']
        assert final_cursor=={**clear,'axis_angle':[0.,0.,1.,0.]} and final['authoring_context']['cursor_rotation']==clear['euler']
        near(final_inspection['cursor_matrix'],[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]])
        assert cleared['snaps'][0]['cursor_changed'] and cleared['snaps'][0]['cursor_orientation_after']==final_cursor
        process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();assert process.returncode==0,stderr
        fresh=subprocess.run([*prefix,str(binary),'scene','inspect','--scene',str(path)],cwd=folder,capture_output=True,text=True,check=True)
        assert json.loads(fresh.stdout)==final_inspection
        for name,value in [('before',before),('after-locked',after),('parented-before',parented_before),('parented-after',parented_after),
            ('final',final_inspection),('locked-receipt',first),('parent-receipt',parent_result),('clear-receipt',cleared),
            ('world-query',world),('parent-query',parent_query),('follower-before',child_before),('follower-after',child_after)]:
            with (out/(name+'.json')).open('x') as stream:json.dump(value,stream,allow_nan=False);stream.write('\n')
        report={'passed':True,'binary_sha256':sha(binary),'driver_sha256':sha(Path(__file__)),'policy':policy,
            'denial_control_exit_code':control.returncode,'denial_control_stderr':control.stderr,'repository_reads':'denied by macOS sandbox',
            'native_terminal_exit':process.returncode,'fresh_process_exit':fresh.returncode,'native_calls':len(calls),
            'raw_nonunit_and_inactive_channels_preserved':True,'physical_rotation_analytic_match':True,'parent_conversion_analytic_match':True,
            'child_world_and_real_parent_inverse_checked':True,'locks_checked':True,'undo_replay_checked':True,'fresh_reload_equal':True,
            'atomic_rejections_checked':True,'cursor_active_only_clear_checked':True,'setup':setup,
            'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'product_acceptance':'unrun'}
        with (out/'report.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
        print(json.dumps({'passed':True,'repository_reads':'denied','native_calls':len(calls)}))


if __name__=='__main__':main()
