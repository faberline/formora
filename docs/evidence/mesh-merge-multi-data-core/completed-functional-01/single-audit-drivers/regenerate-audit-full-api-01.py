"""Audit every raw saved CLI/MCP exchange and reject incomplete full-gate evidence."""
from pathlib import Path
import copy,hashlib,importlib.util,json,sys
ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core');HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('merge_api_audit',Path('/private/tmp/formora-mesh-merge-multi-data-core/docs/evidence/mesh-merge-core/continuation/runtime-cli-mcp.py'));api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
DATA=Path('/private/tmp/formora-multi-merge-single-retained-api-01');OUT=Path('/private/tmp/formora-multi-merge-single-retained-audit-01');OUT.mkdir(exist_ok=False)
BINARY=Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora');binary_hash=api.sha(BINARY)
report=api.pilot.load(DATA/'report.json');suite=api.pilot.load(ROOT/'baseline/fixtures/mesh-merge.json')
folders,source=api.source_preflight(suite)
expected={(interface,case['id']) for interface in ['cli','official_mcp_sdk'] for case in suite['runs']};cases={case['id']:case for case in suite['runs']}
def full_header(value):
 assert value['passed'] is True and value['required_full_gate_passed'] is True and value['checks']==2048
 assert value['inputs_unchanged'] is True and value['binary_sha256']==binary_hash=='64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019'
 rows=value['runs'];assert len(rows)==2048 and len({(r['interface'],r['id']) for r in rows})==2048
 assert {(r['interface'],r['id']) for r in rows}==expected
 assert all(r['status']=='passed' and r['error'] is None for r in rows)
full_header(report)
for relative,digest in report['input_hashes'].items():assert api.sha(ROOT/relative)==digest
def check_authored(case,references,raw):
 assert raw['case']==case
 assert raw['setup']==api.pilot.setup(suite,case)
 assert raw['request']=={'expected_revision':1,'commands':[{'operation':'merge_mesh','merge':{'entity':'target','method':case['parameters']['type'].lower(),'uvs':case['parameters']['uvs']}}]}
 api.check_record(case,references,raw)
rows=[]
for index,row in enumerate(report['runs']):
 path=DATA/row['file'];assert path.parent==DATA and api.sha(path)==row['sha256']
 raw=api.pilot.load(path);case=cases[row['id']]
 assert raw['case']==case and raw['interface']==row['interface'] and raw['status']=='passed' and raw['comparison_error'] is None
 for process in raw['cli_processes']:assert process['command'][0]==str(BINARY)
 if row['interface']=='official_mcp_sdk':assert raw['mcp_initialization']['protocol_version']=='2025-11-25'
 references=[api.pilot.load(folder/(case['id']+'.json.gz')) for folder in folders]
 check_authored(case,references,raw)
 rows.append({'id':row['id'],'interface':row['interface'],'raw_sha256':row['sha256'],'source_sha256':[api.sha(folder/(case['id']+'.json.gz')) for folder in folders],'passed':True})
 if (index+1)%100==0:print(json.dumps({'audited':index+1}),flush=True)
controls=[]
for name,mutate in [('missing_case',lambda r:r['runs'].pop()),('duplicate_case',lambda r:r['runs'].__setitem__(1,copy.deepcopy(r['runs'][0]))),('missing_interface',lambda r:r['runs'].__setitem__(slice(1024,None),[])),('failed_case',lambda r:r['runs'][0].__setitem__('status','failed')),('unrun_gate',lambda r:r.__setitem__('required_full_gate_passed',False)),('input_drift',lambda r:r.__setitem__('inputs_unchanged',False)),('wrong_binary',lambda r:r.__setitem__('binary_sha256','0'*64))]:
 bad=copy.deepcopy(report);mutate(bad)
 try:full_header(bad)
 except (AssertionError,KeyError,ValueError) as error:controls.append({'control':name,'rejected':True,'error':str(error) or type(error).__name__})
 else:raise AssertionError('accepted false full evidence '+name)

base=api.pilot.load(DATA/'official_mcp_sdk-merge_0000.json.gz');case=cases['merge_0000'];references=[api.pilot.load(folder/(case['id']+'.json.gz')) for folder in folders]
check_authored(case,references,base)
def leaked_setup(record):
 command=next(c for c in record['setup']['commands'] if c['operation']=='set_mesh_asset')
 command['asset']=copy.deepcopy(record['after']['query']['mesh_asset'])
 record['mcp_responses'][0]['arguments']=copy.deepcopy(record['setup'])
def unknown_reference(record):
 record['request']['commands'][0]['merge']['reference_path']='measured-source-answer.json'
 response=next(r for r in record['mcp_responses'] if r['tool']=='scene_apply' and r['arguments']['expected_revision']==1)
 response['arguments']=copy.deepcopy(record['request'])
def missing_terminal(record):record['cli_processes'][-1].pop('exit')
def wrong_case(record):record['case']=copy.deepcopy(cases['merge_0001'])
for name,mutate in [('source_result_in_setup_with_forged_raw_arguments',leaked_setup),('source_reference_parameter_with_forged_raw_arguments',unknown_reference),('missing_fresh_native_terminal',missing_terminal),('wrong_authored_case',wrong_case)]:
 bad=copy.deepcopy(base);mutate(bad)
 try:check_authored(case,references,bad)
 except (AssertionError,KeyError,ValueError) as error:controls.append({'control':name,'rejected':True,'error':str(error) or type(error).__name__})
 else:raise AssertionError('false authored evidence accepted '+name)
assert base==api.pilot.load(DATA/'official_mcp_sdk-merge_0000.json.gz')

assert api.sha(BINARY)==binary_hash
result={'passed':True,'checks':len(rows),'all_raw_cli_mcp_source_checks_passed':True,'report_sha256':api.sha(DATA/'report.json'),'binary_sha256':binary_hash,'source_checked':source,'runs':rows,'negative_controls':controls,'audit_driver_sha256':api.sha(Path(__file__)),'runtime_checker_sha256':api.sha(Path('/private/tmp/formora-mesh-merge-multi-data-core/docs/evidence/mesh-merge-core/continuation/runtime-cli-mcp.py')),'product_acceptance':'unrun','independent_acceptance':'unrun'}
(OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'checks':len(rows),'negative_controls':len(controls)}),flush=True)
