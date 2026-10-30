"""Keep invalid delta inputs atomic while preserving finite inactive channels."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser();parser.add_argument('binary',type=Path);parser.add_argument('output',type=Path)
args=parser.parse_args();binary=args.binary.resolve();out=args.output.resolve();out.mkdir(exist_ok=False)
scene=out/'scene.json';calls=[];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(binary)
def call(action,request=None,error=False):
    command=[str(binary),'scene',action,'--scene',str(scene),*(['--request','-'] if request is not None else [])]
    raw=None if request is None else json.dumps(request,allow_nan=True)
    p=subprocess.run(command,input=raw,capture_output=True,text=True)
    calls.append({'command':command,'raw_request':raw,'stdout':p.stdout,'stderr':p.stderr,'exit_code':p.returncode})
    with (out/'calls.jsonl').open('a') as stream:stream.write(json.dumps(calls[-1],allow_nan=False)+'\n')
    value=json.loads(p.stdout);assert (p.returncode!=0)==error,(p.returncode,value,p.stderr)
    if error:assert isinstance(value['error'],str) and value['error']
    return value
transform={'translation':[.25,-.5,.75],'rotation':[0.,0.,0.,1.],'scale':[1.,1.,1.],'precision':'f32',
    'delta':{'translation':[.125,-.25,.375],'euler':[.12345678901234567,-.27,.43],
        'quaternion_wxyz':[-2.,0.,0.,-2.],'scale':[1.,1.,1.]}}
call('init');call('apply',{'expected_revision':0,'commands':[{'operation':'create_entity','id':'target',
    'entity':{'name':'Delta input control','parent':None,'transform':transform,'content':{'kind':'empty'}}}]})
before=call('inspect');saved=scene.read_bytes();rows=[]
def request(value,revision=1,id='target'):
    return {'expected_revision':revision,'commands':[{'operation':'set_transform','id':id,'transform':value}]}
cases=[]
def add(name,edit):
    value=copy.deepcopy(transform);edit(value);cases.append((name,request(value)))
add('unknown_delta_field',lambda v:v['delta'].update(answer=[1,2,3]))
add('conflicting_delta_mode',lambda v:v['delta'].update(mode='xyz'))
add('wrong_euler_dimension',lambda v:v['delta'].update(euler=[0.,0.]))
add('wrong_quaternion_dimension',lambda v:v['delta'].update(quaternion_wxyz=[1.,0.,0.]))
add('nonfinite_active_translation',lambda v:v['delta']['translation'].__setitem__(0,float('inf')))
add('nonfinite_inactive_euler',lambda v:v['delta']['euler'].__setitem__(0,float('nan')))
add('finite_f64_translation_outside_f32',lambda v:v['delta']['translation'].__setitem__(0,1e308))
add('finite_f64_scale_outside_f32',lambda v:v['delta']['scale'].__setitem__(0,1e308))
add('finite_quaternion_normalization_overflow',lambda v:v['delta'].update(quaternion_wxyz=[1e20]*4))
add('legacy_unit_quaternion_stays_strict',lambda v:v.update(rotation=[0.,0.,0.,2.]))
cases.extend([('stale_revision',request(copy.deepcopy(transform),0)),('unknown_entity',request(copy.deepcopy(transform),id='missing'))])
late=request(copy.deepcopy(transform));late['commands'][0]['transform']['translation'][0]=7.
invalid=copy.deepcopy(transform);invalid['delta']['translation'][0]=1e308
late['commands'].append({'operation':'set_transform','id':'target','transform':invalid});cases.append(('late_finite_range_failure',late))
for name,operation in cases:
    response=call('apply',operation,error=True)
    assert scene.read_bytes()==saved and call('inspect')==before
    rows.append({'name':name,'passed':True,'error':response['error'],'disk_and_revision_unchanged':True})
valid=copy.deepcopy(transform);valid['delta']['euler']=[1e308,-0.,.12345678901234567]
call('apply',request(valid));after=call('inspect')
assert after['scene']['entities']['target']['transform']['delta']==valid['delta'] and after['revision']==2
world=call('inspect')
assert world==after and binary_sha==sha(binary)
(out/'after.json').write_text(json.dumps(after,indent=2,allow_nan=False)+'\n')
report={'passed':True,'binary_sha256':binary_sha,'driver_sha256':sha(Path(__file__)),
    'rejected_cases':rows,'required_rejections':len(cases),'finite_inactive_f64_preserved':True,
    'successful_fresh_reload_equal':True,'legacy_unit_quaternion_validation_unchanged':True,
    'native_calls':len(calls),'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file() and not p.name.endswith('.formora.lock')},
    'product_acceptance':'unrun'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'atomic_invalid_inputs':len(cases),'finite_inactive_f64_preserved':True}))
