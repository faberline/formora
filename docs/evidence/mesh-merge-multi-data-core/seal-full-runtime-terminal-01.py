"""Preserve actual full-run completion; do not accept the still-live raw audit."""
from pathlib import Path
from collections import Counter
import gzip
import hashlib
import json
import subprocess

ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')
RAW=Path('/private/tmp/formora-multi-merge-api-full-01')
PARENT=Path('/private/tmp/formora-multi-merge-full-process-01')
OUT=ROOT/'docs/evidence/mesh-merge-multi-data-core/full-runtime-terminal-01'
OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
report=load(RAW/'report.json');started=load(PARENT/'started.json');terminal=load(PARENT/'terminal.json')
assert started['process_id']==terminal['process_id']==5100 and terminal['terminal_exit_code']==0
assert started['head']==report['head']=='bd13f3d424f2649b4b25c16305c4e5b0eb7f8542'
assert report['complete'] and report['executed_records']==report['required_records']==26880 and report['failed_records']==0
assert report['required_interfaces']==['cli','official_mcp_sdk']
assert report['outcomes']=={'finished_source_comparison':18176,'explicit_enum_rejection':8704}
assert len(report['records'])==26880 and len({(r['interface'],r['id']) for r in report['records']})==26880
counts=Counter((r['interface'],r['kind']) for r in report['records'])
for interface in report['required_interfaces']:
    assert counts[(interface,'finished_source_comparison')]==9088
    assert counts[(interface,'explicit_enum_rejection')]==4352
assert all(r['status']=='passed' and r['error'] is None for r in report['records'])
assert sha(report['binary'])==report['binary_sha256']=='64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019'
assert all(sha(ROOT/name)==digest for name,digest in report['input_hashes'].items())
for name in ['stdout','stderr']:
    assert sha(PARENT/name)==terminal[name+'_sha256']
rows=[]
def copy(source,relative,compress=False):
    raw=source.read_bytes();stored=gzip.compress(raw,mtime=0) if compress else raw
    path=OUT/relative
    with path.open('xb') as f:f.write(stored)
    assert (gzip.decompress(path.read_bytes()) if compress else path.read_bytes())==raw
    assert source.read_bytes()==raw
    rows.append({'original':str(source),'stored':relative,'raw_sha256':hashlib.sha256(raw).hexdigest(),
                 'stored_sha256':sha(path),'raw_bytes':len(raw),'compressed':compress})
copy(RAW/'report.json','runtime-report.json.gz',True)
copy(RAW/'started.json','runtime-started.json')
for name in ['started.json','terminal.json','stdout','stderr']:
    copy(PARENT/name,'parent-'+name+('.gz' if name in ['stdout','stderr'] else ''),name in ['stdout','stderr'])
proof={'runtime_parent_wait_verified':True,'process_id':5100,'terminal_exit_code':0,
       'runtime_report_complete':True,'interface_records':26880,
       'outcomes':report['outcomes'],'required_interfaces':report['required_interfaces'],
       'per_interface':{i:{k:counts[(i,k)] for k in report['outcomes']} for i in report['required_interfaces']},
       'frozen_input_files_verified':len(report['input_hashes']),'input_hashes_unchanged':True,
       'frozen_head':report['head'],'evidence_head_before_this_doc':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
       'binary_sha256':report['binary_sha256'],'copies':rows,'originals_preserved':True,
       'all_raw_records_audit':'running; not accepted','full_corruption_controls':'unrun',
       'retained_207_timing_source_samples':'unrun','required_ci':'unpassed',
       'full_interface_gate_accepted':False,'product_acceptance':'unrun','independent_acceptance':'unrun'}
with (OUT/'report.json').open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({k:proof[k] for k in ['runtime_parent_wait_verified','interface_records','frozen_input_files_verified','full_interface_gate_accepted']}))
