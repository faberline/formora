from datetime import datetime, timezone
import hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tools'))
from multi_mesh_merge_capacity_inputs import input_paths
root=Path.cwd(); proof=root/'docs/evidence/mesh-merge-multi-data-baseline';suite=root/'baseline/fixtures/mesh-merge-multi-data-capacity.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs={str(p.relative_to(root)):sha(p) for p in input_paths(suite)}
result={'scope':'complete_30_two_class_A_merge_cases','started_utc':datetime.now(timezone.utc).isoformat(),'input_hashes':inputs,'commands':[],'product_acceptance':'unrun','complete_capacity_source_gate':False}
try:
 for name in ['capacity-native-01','capacity-native-02']:
  command=[sys.executable,str(root/'tools/launch_multi_mesh_merge_capacity_reference.py'),'--suite',str(suite),'--output',str(proof/name),'--timeout','2700']
  print(json.dumps({'starting':name,'full_cases':30}),flush=True)
  code=subprocess.call(command);result['commands'].append({'name':name,'command':command,'exit_code':code})
  assert code==0,(name,code)
 command=[sys.executable,str(root/'tools/compare_multi_mesh_merge_capacity_reference.py'),'--suite',str(suite),'--first',str(proof/'capacity-native-01'),'--second',str(proof/'capacity-native-02'),'--output',str(proof/'capacity-source-comparison-01.json')]
 print(json.dumps({'starting':'complete_source_comparison'}),flush=True)
 with (proof/'capacity-source-comparison-01.stdout').open('x') as out,(proof/'capacity-source-comparison-01.stderr').open('x') as err:
  code=subprocess.call(command,stdout=out,stderr=err)
 result['commands'].append({'name':'source_comparison','command':command,'exit_code':code})
 assert code==0,('source_comparison',code)
 assert inputs=={str(p.relative_to(root)):sha(p) for p in input_paths(suite)},'input drift'
 comparison=json.loads((proof/'capacity-source-comparison-01.json').read_text());assert comparison['complete_capacity_source_gate'] and comparison['cases']==30 and comparison['source_comparison_passed']
 result['complete_capacity_source_gate']=True
except BaseException as e:
 result['error']=str(e);result['traceback']=traceback.format_exc()
finally:
 result['ended_utc']=datetime.now(timezone.utc).isoformat()
 with (proof/'capacity-full-source-parent-01.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'complete_capacity_source_gate':result['complete_capacity_source_gate'],'error':result.get('error'),'product_acceptance':'unrun'}),flush=True)
raise SystemExit(0 if result['complete_capacity_source_gate'] else 1)
