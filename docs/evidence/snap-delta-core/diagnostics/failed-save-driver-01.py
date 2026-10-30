"""Prove delta rollback when actual native CLI persistence fails."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
args=parser.parse_args();binary=args.binary.resolve();out=args.output.resolve();out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(binary)
scene=out/'scene.json';backup=out/'before-failed-save.json';calls=[]
subprocess.run([str(binary),'scene','init','--scene',str(scene)],capture_output=True,check=True)
raw={'mode':'quaternion','euler':[.21345678901234567,-.27,.43],
     'quaternion_wxyz':[.5,-.5,.5,.5],'axis_angle':[.71,-3.,2.,4.]}
delta={'translation':[.125,-.25,.375],'euler':[.11345678901234567,-.31789,.4789],
       'quaternion_wxyz':[-2.,0.,0.,-2.],'scale':[1.,1.,1.]}
cursor={**raw,'quaternion_wxyz':[.8,0.,0.,.6]}
setup=[{'operation':'create_entity','id':'target','entity':{'name':'Delta save rollback','parent':None,
    'transform':{'translation':[.25,-.5,.75],'rotation':{'kind':'channels','channels':raw},
        'scale':[1.,1.,1.],'precision':'f32','delta':delta},'content':{'kind':'empty'}}},
    {'operation':'set_authoring_context','context':{'cursor_location':[1.25,-.75,.5],
        'cursor_rotation':cursor['euler'],'cursor_orientation':cursor}},
    {'operation':'set_object_context','context':{'selected':['target'],'active':'target',
        'states':{'target':{'lock_rotation':[True,False,False]}}}}]
snap={'operation':'snap_scene','snap':{'action':{'kind':'selected_to_cursor','use_offset':False,'use_rotation':True}}}
with subprocess.Popen([str(binary),'scene','serve','--scene',str(scene)],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as process:
    sequence=0
    def call(name,arguments,error=False):
        global sequence
        sequence+=1;process.stdin.write(json.dumps({'id':sequence,'name':name,'arguments':arguments})+'\n');process.stdin.flush()
        response=json.loads(process.stdout.readline());assert response['id']==sequence and response['ok'] is (not error),response
        calls.append({'name':name,'arguments':arguments,'response':response})
        with (out/'calls.jsonl').open('a') as stream:stream.write(json.dumps(calls[-1],allow_nan=False)+'\n')
        return response.get('error') if error else response['result']
    def inspect():return call('scene_inspect',{})['scene']
    call('scene_apply',{'expected_revision':0,'commands':setup});before=inspect();saved=scene.read_bytes()
    scene.rename(backup);scene.mkdir()
    failure=call('scene_apply',{'expected_revision':1,'commands':[snap]},error=True)
    assert 'directory' in failure.lower(),failure
    assert inspect()==before and backup.read_bytes()==saved and not list(scene.iterdir())
    scene.rmdir();shutil.copyfile(backup,scene)
    call('scene_undo',{'expected_revision':1});undone=inspect()
    assert not undone['entities'] and not undone['mesh_assets'] and undone['revision']==2
    call('scene_apply',{'expected_revision':2,'commands':setup});recreated=inspect()
    result=call('scene_apply',{'expected_revision':3,'commands':[snap]});after=inspect()
    assert after['entities']['target']['transform']['delta']==delta
    assert result['scene_snaps'][0]['objects'][0]['transform_after']==after['entities']['target']['transform']
    world=call('scene_inspect',{'entity':'target','world':True})['world_matrix']
    for i,expected in enumerate([.482,-.326,.02]):
        assert math.isfinite(world[i][0]+world[i][3]) and abs(world[i][0]+world[i][3]-expected)<=1e-6
    call('scene_undo',{'expected_revision':4});restored=inspect()
    assert {k:v for k,v in restored.items() if k!='revision'}=={k:v for k,v in recreated.items() if k!='revision'}
    replay=call('scene_apply',{'expected_revision':5,'commands':[snap]});final=inspect()
    assert replay['scene_snaps']==result['scene_snaps']
    assert {k:v for k,v in final.items() if k!='revision'}=={k:v for k,v in after.items() if k!='revision'}
    process.stdin.close();process.wait(timeout=10);stderr=process.stderr.read();assert process.returncode==0,stderr
fresh=subprocess.run([str(binary),'scene','inspect','--scene',str(scene)],capture_output=True,text=True,check=True)
assert json.loads(fresh.stdout)['scene']==final and binary_sha==sha(binary)
for name,value in [('before',before),('after',after),('undo-after-save-failure',undone),('receipt',result),('final',final)]:
    (out/(name+'.json')).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
report={'passed':True,'binary_sha256':binary_sha,'driver_sha256':sha(Path(__file__)),
    'actual_persistence_failure':failure,'failed_save_preserves_memory_revision_original_disk':True,
    'failed_save_adds_no_undo_entry':True,'delta_and_inactive_channels_preserved':True,
    'physical_delta_point_matches_analytic':True,'real_receipt_matches_saved_transform':True,
    'undo_replay_and_fresh_reload_equal':True,'native_terminal_exit':process.returncode,
    'fresh_process_exit':fresh.returncode,'native_calls':len(calls),
    'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file() and not p.name.endswith('.formora.lock')},
    'product_acceptance':'unrun'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'actual_failed_save_rollback':True,'native_calls':len(calls)}))
