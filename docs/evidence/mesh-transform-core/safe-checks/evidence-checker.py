from pathlib import Path
from collections import Counter
import copy,hashlib,json,re,shutil,subprocess
root=Path('/Users/chrischeng/faberlines/formora');folder=root/'docs/evidence/mesh-transform-core';candidate='263fe1d7652e344e84ccb30a0d4e7c1ab5046def'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=json.load(open(folder/'safe-runtime/report.json'));focused=json.load(open(folder/'safe-focused/report.json'))
assert report['checks']==2406 and report['scope']=='full_1203_cases_both_interfaces' and not report['passed'] and not report['required_full_gate_passed']
assert focused['checks']==84 and focused['scope']=='focused_diagnostic' and focused['passed'] and not focused['required_full_gate_passed']
assert report['input_hashes']==focused['input_hashes']=={name:sha(root/name) for name in report['input_hashes']}
subprocess.run(['git','diff','--quiet',candidate,'--','src','tests','tools','baseline','docs/contracts'],cwd=root,check=True)
for name,data in [('safe-runtime',report),('safe-focused',focused)]:
 assert data['source_reference_checked']['passed']
 assert len(data['runs'])==len({(r['interface'],r['id']) for r in data['runs']})==data['checks']
 for row in data['runs']:
  p=folder/name/row['file'];assert sha(p)==row['sha256'];raw=json.load(open(p));assert raw['case']['id']==row['id'] and raw['status']==row['status']
old=json.load(open(folder/'gimbal-runtime/report.json'));before={(r['interface'],r['id']):r for r in old['runs']};now={(r['interface'],r['id']):r for r in report['runs']};assert set(before)==set(now)
matched=[r for r in report['runs'] if r['status']=='passed'];failures=[r for r in report['runs'] if r['status']=='failed'];improved=[key for key,row in now.items() if row['status']=='passed' and before[key]['status']!='passed'];regressed=[key for key,row in now.items() if row['status']!='passed' and before[key]['status']=='passed']
assert (len(matched),len(failures),len(improved),len(regressed))==(2314,92,36,0)
reasons=Counter()
for key,row in now.items():
 old_raw=json.load(open(folder/'gimbal-runtime'/before[key]['file']));raw=json.load(open(folder/'safe-runtime'/row['file']))
 assert raw['case']==old_raw['case'] and raw['setup']==old_raw['setup'] and row['reference_sha256']==before[key]['reference_sha256']
 expected=copy.deepcopy(old_raw['request'])
 if 'center_override' in raw['case']['parameters']:expected['commands'][0]['transform']['pivot']='bounds'
 assert raw['request']==expected
 if key in improved:
  if raw['case']['context']['profile']=='singular':reasons['singular_frames']+=1
  else:assert 'center_override' in raw['case']['parameters'];reasons['source_center_mapping']+=1
assert reasons=={'singular_frames':24,'source_center_mapping':12}
assert all(now[('cli',id)]['sha256']==now[('official_mcp_sdk',id)]['sha256'] for _,id in now)
all_axis=['transform_0693','transform_0701','transform_0709','transform_0717','transform_0725','transform_0733','transform_0741']
assert all(now[(interface,id)]['status']=='failed' for interface in ['cli','official_mcp_sdk'] for id in all_axis)
def category(row):
 e=row['error']
 if e.startswith('numeric mismatch: after/'):return 'numeric/'+e.split('after/')[1].split('/')[0]
 return e
per_interface={interface:dict(sorted(Counter(category(r) for r in failures if r['interface']==interface).items())) for interface in ['cli','official_mcp_sdk']}
analysis={'scope':'complete source run after certified singular transforms and explicit source centre mapping','matched':len(matched),'matched_finished':sum(r.get('source_outcome')=='FINISHED' for r in matched),'matched_expected_cancellations':sum(r.get('source_outcome')=='CANCELLED' for r in matched),'failed':len(failures),'newly_matched':len(improved),'improvements':dict(reasons),'regressions':0,'adapter_changed_only_source_override_pivot':True,'all_seven_undefined_axis_cases_retained':True,'per_interface_failures':per_interface,'both_interfaces_have_identical_raw_results':True,'required_transform_gate_passed':False,'source_report_sha256':sha(folder/'safe-runtime/report.json')}
assert (analysis['matched_finished'],analysis['matched_expected_cancellations'])==(2302,12)
(folder/'safe-runtime/analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
normal=json.load(open(folder/'safe-normal-regression/manifest.json'));assert normal['passed'] and normal['cases']==42
mcp=json.load(open('/private/tmp/formora-safe-mcp.stdout'));keys={'initialize','discovery','input_schemas','inspect','apply','stale_revision','undo','reload','mesh_create_edit_query','referenced_mesh_delete_rejected','mesh_undo_reload','polygon_tessellate_edit_undo_reload'};assert set(mcp)==keys|{'sdk_version','binary_sha256','protocol_version','product_milestone_acceptance'};assert all(mcp[k]=='passed' for k in keys) and mcp['sdk_version']=='2.3.0' and mcp['protocol_version']=='2025-11-25' and not mcp['product_milestone_acceptance']
checks=folder/'safe-checks';checks.mkdir(exist_ok=False)
for name in ['rust','python','clippy','format','mcp','normal','full']:
 for suffix in ['stdout','stderr']:shutil.copyfile('/private/tmp/formora-safe-'+name+'.'+suffix,checks/(name+'.'+suffix))
for name in ['baseline','strict']:
 p=Path('/private/tmp/formora-safe-'+name+'.json');data=json.load(open(p));assert data['structurally_valid'] and not data['baseline_ready'] and data['problems']==[];assert (data['sources'],data['pending_sources'],data['pending_features'])==(9047,9003,31);shutil.copyfile(p,checks/(name+'.json'))
assert sum(map(int,re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',(checks/'rust.stdout').read_text())))==185
assert re.search(r'Ran 77 tests in ',(checks/'python.stderr').read_text()) and re.search(r'\nOK\s*$',(checks/'python.stderr').read_text())
binary=Path('/private/tmp/formora-target-actual185/debug/formora');binary_sha=sha(binary);assert binary_sha==report['binary_sha256']==focused['binary_sha256']==normal['binary_sha256']==mcp['binary_sha256']
for path in ['safe-isolation/report.json','safe-gpu/manifest.json']:
 data=json.load(open(folder/path));assert data['passed'] and data['binary_sha256']==binary_sha;assert data['driver_sha256']==sha(folder/path.split('/')[0]/'capture-driver.py');assert data['source_files']=={name:sha(root/name) for name in data['source_files']}
 if path.endswith('manifest.json'):assert data['unrepresentable_y_unchanged'] and data['singular_object_scale']==[1,0,1]
audit_folder=folder/'safe-source-audit';audit=json.load(open(audit_folder/'report.json'));assert audit['passed'] and audit['candidate']==candidate and audit['extracted_functions_unchanged'] and audit['compile_exit']==audit['run_exit']==0
source=(root/audit['source_path']).read_text();assert sha(root/audit['source_path'])==audit['source_sha256'];svd=source[source.index('void svd_m4('):source.index('void pseudoinverse_m4_m4(')];pivot=source[source.index('bool invert_m4_m4_fallback('):source.index('bool invert_m4_m4(float')]
assert hashlib.sha256(svd.encode()).hexdigest()==audit['svd_function_sha256'] and hashlib.sha256(pivot.encode()).hexdigest()==audit['pivot_function_sha256'];oracle=(audit_folder/'source-oracle.cc').read_text();assert svd in oracle and pivot in oracle
for name,digest in audit['files'].items():assert sha(audit_folder/name)==digest
prior=json.loads(subprocess.check_output(['git','show','48f6d6ae2dba4906bb90a2245549cc1288964941:baseline/lock.json'],cwd=root,text=True));lock=json.load(open(root/'baseline/lock.json'));pins={r['path']:r for r in lock['artifacts']};assert len(pins)==3771 and len(prior['artifacts'])==3764 and all(pins[r['path']]==r for r in prior['artifacts'])
for row in lock['artifacts']:assert sha(root/row['path'])==row['sha256']
info=json.load(open('/private/tmp/formora-target-actual185/.rustc_info.json'));assert any(o.get('stdout','').startswith('rustc 1.85.0 ') for o in info['outputs'].values());(checks/'rustc-info.json').write_text(json.dumps(info,indent=2)+'\n');shutil.copyfile(__file__,checks/'evidence-checker.py')
folders=['safe-runtime','safe-focused','safe-normal-regression','safe-isolation','safe-gpu','safe-source-audit','safe-checks'];artifacts={str(p.relative_to(folder)):sha(p) for directory in folders for p in sorted((folder/directory).rglob('*')) if p.is_file() and not p.name.endswith('.formora.lock')}
manifest={'evidence_integrity_verified':True,'scope':'certified singular mesh frames and source centre mapping; complete issue #48 still fails','rust_candidate':candidate,'binary_sha256':binary_sha,'rust_tests':185,'python_tests':77,'format_clippy_passed':True,'focused_safe_comparisons':{'passed':True,'checks':84,'required_full_gate_passed':False},'full_source_gate':{'passed':False,'exit_code':1,'executed':2406,'matched':2314,'failed':92,'matched_finished':2302,'matched_expected_cancellations':12,'improved':36,'regressions':0},'source_spurious_dimensions_confirmed_by_unchanged_cpp':True,'exact_dyadic_rank_certificate':True,'absolute_singular_cutoff':1e-8,'svd_step_limit':200,'normal_regression_cases_passed':42,'mcp_regression_passed':True,'unseen_repository_read_denied_transforms_passed':True,'native_singular_metal_passed':True,'source_pins_preserved':3764,'source_pins_total':3771,'baseline_metadata_exit':0,'strict_baseline_exit':2,'remaining_failed':['92 full source comparisons including seven all-axis rotation cases per interface'],'required_unrun':['fixed release performance','final full regression set','three-platform CI','dependency integration','independent issue acceptance','full numeric and capacity domains','random sequence/distribution','custom normal authoring'],'milestone_acceptance':'unrun','artifacts':artifacts};(folder/'safe-implementation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'binary_sha256':binary_sha,'evidence_artifacts':len(artifacts),'matched':2314,'failed':92,'improved':36,'regressions':0,'per_interface_failures':per_interface}))
