import copy,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
root=Path('/Users/chrischeng/faberlines/formora');sys.path.insert(0,str(root/'tools'))
import random_falloff_runtime as rng
binary=Path('/private/tmp/formora-target-actual185/debug/formora');out=root/'docs/evidence/snap-rotation-core/rng-one-shot';out.mkdir(exist_ok=False)
source=root/'baseline/reference/blender-5.2.3/random-falloff/first-sequence.bin';reference=source.read_bytes();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();binary_sha=sha(binary)
base=root/'docs/evidence/snap-rotation-core/retained/rng';records=json.loads((base/'report.json').read_text());assert records['passed'] and records['checks']==96
cases=[r for r in records['records'] if r['interface']=='cli'];assert len(cases)==48;results=[]
with tempfile.TemporaryDirectory(prefix='formora-rng-one-shot-') as temporary:
 for index,entry in enumerate(cases):
  path=Path(temporary)/f'{index}.json';case=entry['case'];old=json.loads((base/entry['file']).read_text())
  def call(action,request=None,error=False):
   command=[str(binary),'scene',action,'--scene',str(path),*(['--request','-'] if request is not None else [])]
   p=subprocess.run(command,input=None if request is None else json.dumps(request),capture_output=True,text=True);value=json.loads(p.stdout)
   assert (p.returncode!=0)==error,(p.returncode,value,p.stderr)
   return value
  call('init');call('apply',rng.setup());before=call('inspect');request={'expected_revision':1,'commands':[rng.operation(*case)]}
  result=call('apply',request);after=call('inspect');assert result['transforms']==old['result']['transforms'];assert after['scene']['mesh_assets']==old['after']['scene']['mesh_assets']
  assert result['transforms'][0]['influence']==rng.expected_weights(case,reference);saved=path.read_bytes()
  bad_rotation={'operation':'transform_mesh','transform':{'entity':'target','change':{'kind':'rotate','radians':.61,'axis':'z'},'constraint_axis':[True,True,True]}}
  bad_seed=rng.operation(4294967296,'blender_5_2');rejected=[]
  for commands in [[bad_seed],[bad_rotation],[rng.operation(*case),bad_rotation]]:
   response=call('apply',{'expected_revision':2,'commands':commands},error=True);assert path.read_bytes()==saved and call('inspect')==after
   if commands[-1]==bad_rotation:assert response['error']==rng.UNDEFINED_ROTATION_ERROR
   rejected.append({'commands':commands,'response':response})
  file=f'cli-{index:03}.json';target=out/file;target.write_text(json.dumps({'case':case,'setup':rng.setup(),'request':request,'before':before,'result':result,'after':after,'rejected_requests':rejected,'passed':True},allow_nan=False)+'\n')
  results.append({'case':case,'file':file,'sha256':sha(target),'passed':True})
assert sha(binary)==binary_sha
report={'passed':True,'checks':48,'interface':'one-shot CLI with fresh processes','binary_sha256':binary_sha,'reference_sha256':sha(source),'driver_sha256':sha(Path(__file__)),'records':results,'approved_all_axis_rotation_rejection_and_late_batch_rollback':True,'full_product_acceptance':'unrun'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'passed':True,'one_shot_cli_checks':48}))
