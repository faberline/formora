import copy,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,'/private/tmp/formora-merge-distance-baseline/tools')
from merge_distance_capacity_seal import verify,digest
root=Path('/private/tmp/formora-merge-distance-baseline')
suite=root/'baseline/fixtures/mesh-merge-distance-capacity-01.json'
seal=root/'baseline/fixtures/mesh-merge-distance-capacity-seal-01.json'
original=verify(suite,seal)
mutations=[('scope',lambda v:v.update(scope='diagnostic')),('case_count',lambda v:v.update(cases=191)),('suite_digest',lambda v:v.update(suite_sha256='0'*64)),('binary_identity',lambda v:v.update(binary_sha256='0'*64)),('product_budget',lambda v:v['product_limits'].update(per_data_core_ms=251)),('source_dependency',lambda v:v.update(functional_seal_sha256='0'*64)),('execution_before_seal',lambda v:v.update(complete_capacity_execution_at_seal='done')),('hardware',lambda v:v['hardware'].update(cpu='unknown')),('input_digest',lambda v:v['input_hashes'].update({'tools/merge_distance_capacity_seal.py':'0'*64}))]
rows=[]
with tempfile.TemporaryDirectory(prefix='formora-distance-capacity-seal-controls-') as directory:
 for name,mutate in mutations:
  value=copy.deepcopy(original);mutate(value);path=Path(directory)/(name+'.json');path.write_text(json.dumps(value))
  try:verify(suite,path)
  except AssertionError as error:rows.append({'control':name,'rejected':True,'reason':str(error)})
  else:raise AssertionError('accepted corrupt seal '+name)
report={'seal_verified':True,'seal_sha256':digest(seal),'sealed_files':len(original['input_hashes']),'code_commit':original['code_commit'],'cases':original['cases'],'controls':rows,'control_count':len(rows),'native_execution':'unrun','rust_product_timing':'unrun'}
output=Path('/private/tmp/formora-distance-capacity-seal-controls-01.json')
with output.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(report))
