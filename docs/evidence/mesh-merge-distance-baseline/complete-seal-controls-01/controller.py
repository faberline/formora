"""Reject altered before-execution seals without running a native operation."""
from pathlib import Path
import copy
import hashlib
import json
import sys

ROOT=Path('/private/tmp/formora-merge-distance-baseline');sys.path.insert(0,str(ROOT/'tools'))
from merge_distance_source_seal import verify

SUITE=ROOT/'baseline/fixtures/mesh-merge-distance-complete-02.json'
SEAL=ROOT/'baseline/fixtures/mesh-merge-distance-source-seal-01.json'
OUT=ROOT/'docs/evidence/mesh-merge-distance-baseline/complete-seal-controls-01';OUT.mkdir(exist_ok=False)
original=verify(SUITE,SEAL);rows=[]
def reject(name,mutation,reason):
    value=copy.deepcopy(original);mutation(value);path=OUT/(name+'.json')
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    try:verify(SUITE,path)
    except AssertionError as error:
        assert reason in str(error),(name,'wrong rejection',str(error))
        rows.append({'name':name,'rejected':True,'error':str(error),'file':path.name})
    else:raise AssertionError('forged seal passed: '+name)
reject('wrong_limit',lambda x:x['acceptance_limits'].update(per_data_core_ms=251),'source seal limits')
reject('wrong_source',lambda x:x.update(source_commit='0'*40),'source seal identity')
reject('wrong_binary',lambda x:x.update(binary_sha256='0'*64),'source seal identity')
reject('wrong_case_count',lambda x:x.update(cases=x['cases']-1),'source seal suite binding')
reject('wrong_suite_hash',lambda x:x.update(suite_sha256='0'*64),'source seal suite binding')
reject('missing_code_input',lambda x:x['input_hashes'].pop(next(iter(x['input_hashes']))),'source seal code/source binding')
reject('changed_code_input',lambda x:x['input_hashes'].__setitem__(next(iter(x['input_hashes'])),'0'*64),'source seal code/source binding')
reject('post_execution_seal',lambda x:x.update(complete_source_execution_at_seal='passed'),'before-execution source seal')
report={'genuine_seal_verified':True,'source_seal_sha256':hashlib.sha256(SEAL.read_bytes()).hexdigest(),
        'code_commit':original['code_commit'],'cases':original['cases'],'sealed_inputs':len(original['input_hashes']),
        'controls':rows,'forged_native_operations_executed':False,'complete_source_execution':'unrun','product_acceptance':'unrun'}
with (OUT/'report.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
with (OUT/'controller.py').open('xb') as stream:stream.write(Path(__file__).read_bytes())
print(json.dumps({'seal_verified':True,'forged_seals_rejected':len(rows),'native_execution':'unrun'}))
