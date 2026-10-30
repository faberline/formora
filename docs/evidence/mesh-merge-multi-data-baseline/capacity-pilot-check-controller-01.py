from pathlib import Path
import gzip,json,math,time,traceback
from compare_multi_mesh_merge_capacity_reference import load_capture,digest
from compare_multi_mesh_merge_reference import validate_run
from generate_multi_mesh_merge_capacity_cases import author
root=Path.cwd();suite_path=root/'baseline/fixtures/mesh-merge-multi-data-capacity.json';suite=json.loads(suite_path.read_text());assert suite==author();folder=root/'docs/evidence/mesh-merge-multi-data-baseline/capacity-pilot-01';runs=suite['runs'][::3];rows=[]
try:load_capture(folder,suite_path,runs,True);header={'passed':True}
except Exception as e:header={'passed':False,'error':str(e),'traceback':traceback.format_exc()}
for run in runs:
 print(json.dumps({'checking':run['id']}),flush=True);started=time.monotonic()
 try:
  m=json.loads((folder/'manifest.json').read_text());meta=next(r for r in m['runs'] if r['id']==run['id']);path=folder/meta['file'];assert digest(path)==meta['sha256'];raw=gzip.decompress(path.read_bytes());import hashlib;assert hashlib.sha256(raw).hexdigest()==meta['raw_sha256'] and len(raw)==meta['raw_bytes'];record=json.loads(raw);clock=record['native_operator_clock'];assert clock['is_Rust_product_timing'] is False and clock['after_ns']>clock['before_ns']>0 and math.isfinite(clock['elapsed_ms']) and clock['elapsed_ms']==(clock['after_ns']-clock['before_ns'])/1e6
  outcome=validate_run(suite,run,record['data']);rows.append({'id':run['id'],'passed':True,'outcome':outcome,'checker_seconds':time.monotonic()-started})
 except Exception as e:rows.append({'id':run['id'],'passed':False,'error':str(e),'traceback':traceback.format_exc()})
result={'scope':'focused_capacity_diagnostic_only','complete_capacity_source_gate':False,'header':header,'total':len(rows),'passed':sum(r['passed'] for r in rows),'rows':rows,'Rust_product_timing':'unrun','product_acceptance':'unrun'}
with (folder.parent/'capacity-pilot-01-check.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'total':len(rows),'passed':result['passed'],'header':header,'first_failure':next((r for r in rows if not r['passed']),None)}),flush=True)
raise SystemExit(0 if header['passed'] and result['passed']==len(rows) else 1)
