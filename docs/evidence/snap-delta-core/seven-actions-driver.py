"""Analytic native checks for all seven delta-composed direct actions."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser();parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
args=parser.parse_args();binary=args.binary.resolve();out=args.output.resolve();out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(binary);records=[]
raw={'mode':'xyz','euler':[0.,0.,0.],'quaternion_wxyz':[.5,-.5,.5,.5],'axis_angle':[.71,-3.,2.,4.]}
delta={'translation':[.125,-.25,.375],'euler':[0.,0.,math.pi/2],
       'quaternion_wxyz':[-2.,0.,0.,-2.],'scale':[1.,1.,1.]}
other_delta={**delta,'translation':[.25,.125,.375]}
cursor_location=[1.25,-.75,.5]
def entity(location,channels):
    return {'name':'Analytic delta','parent':None,'transform':{'translation':location,
        'rotation':{'kind':'channels','channels':raw},'scale':[1.,1.,1.],'precision':'f32','delta':channels},
        'content':{'kind':'empty'}}
def near(a,b):
    assert len(a)==len(b)
    for x,y in zip(a,b):assert math.isfinite(x) and math.isfinite(y) and abs(x-y)<=1e-6,(a,b)
for kind,parameters in [('selected_to_grid',{'spacing':.5}),
    ('selected_to_cursor',{'use_offset':False,'use_rotation':True}),('selected_to_active',{}),
    ('cursor_to_grid',{'spacing':.5}),('cursor_to_selected',{}),('cursor_to_active',{}),('cursor_to_center',{})]:
    folder=out/kind;folder.mkdir();scene=folder/'scene.json';calls=[]
    def call(*arguments,request=None):
        p=subprocess.run([str(binary),*map(str,arguments)],input=None if request is None else json.dumps(request),capture_output=True,text=True)
        calls.append({'arguments':list(map(str,arguments)),'request':request,'stdout':p.stdout,'stderr':p.stderr,'exit_code':p.returncode})
        with (folder/'calls.jsonl').open('a') as stream:stream.write(json.dumps(calls[-1],allow_nan=False)+'\n')
        assert p.returncode==0,p.stdout+p.stderr
        return json.loads(p.stdout)
    call('scene','init','--scene',scene)
    both=kind in ['selected_to_active','cursor_to_selected','cursor_to_active']
    setup={'expected_revision':0,'commands':[
        {'operation':'create_entity','id':'target','entity':entity([.25,-.5,.75],delta)},
        {'operation':'create_entity','id':'anchor','entity':entity([-.5,.25,-.125],other_delta)},
        {'operation':'set_authoring_context','context':{'cursor_location':cursor_location,'cursor_rotation':raw['euler'],'cursor_orientation':raw}},
        {'operation':'set_object_context','context':{'order':['target','anchor'],
            'selected':['target','anchor'] if both else ['target'],'active':'anchor' if both else 'target'}}]}
    call('scene','apply','--scene',scene,'--request','-',request=setup)
    before=call('scene','inspect','--scene',scene)['scene']
    result=call('scene','apply','--scene',scene,'--request','-',request={'expected_revision':1,
        'commands':[{'operation':'snap_scene','snap':{'action':{'kind':kind,**parameters}}}]})
    after=call('scene','inspect','--scene',scene)['scene']
    assert result['revision']==after['revision']==2
    for name in ['target','anchor']:
        assert after['entities'][name]['transform']['delta']==before['entities'][name]['transform']['delta']
    if kind.startswith('selected'):
        expected={'selected_to_grid':[.5,-.5,1.],'selected_to_cursor':cursor_location,
                  'selected_to_active':[-.25,.375,.25]}[kind]
        world=call('scene','inspect','--scene',scene,'--entity','target','--world')['world_matrix']
        near([row[3] for row in world[:3]],expected)
        near([world[i][0]+world[i][3] for i in range(3)],[expected[0],expected[1]+1.,expected[2]])
        assert after['authoring_context']==before['authoring_context']
    else:
        expected={'cursor_to_grid':[1.5,-.5,.5],'cursor_to_selected':[.0625,-.1875,.6875],
                  'cursor_to_active':[-.25,.375,.25],'cursor_to_center':[0.,0.,0.]}[kind]
        near(after['authoring_context']['cursor_location'],expected)
        assert before['entities']==after['entities']
        assert after['authoring_context']['cursor_orientation']==raw
    receipt=result['scene_snaps'][0]
    assert receipt['status']=='finished' and receipt['reason'] is None
    changed={name for name in before['entities'] if before['entities'][name]!=after['entities'][name]}
    assert {v['entity'] for v in receipt['objects']}==changed
    for item in receipt['objects']:
        assert item['transform_before']==before['entities'][item['entity']]['transform']
        assert item['transform_after']==after['entities'][item['entity']]['transform']
    assert not receipt['meshes'] and not receipt['edit_meshes']
    assert call('scene','inspect','--scene',scene)['scene']==after
    records.append({'action':kind,'passed':True,'delta_channels_unchanged':True,
        'analytic_world_or_cursor_match':True,'real_receipts_and_fresh_reload_checked':True,'native_calls':len(calls)})
assert len(records)==7 and binary_sha==sha(binary)
report={'passed':True,'binary_sha256':binary_sha,'driver_sha256':sha(Path(__file__)),
    'actions':records,'position_limit':1e-6,'inputs_authored_in_driver':True,
    'source_outputs_used_as_inputs':False,'product_acceptance':'unrun'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'analytic_direct_actions':7}))
