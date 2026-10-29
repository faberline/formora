from pathlib import Path
from collections import Counter
import hashlib,json,re,shutil,subprocess
root=Path('/Users/chrischeng/faberlines/formora');folder=root/'docs/evidence/mesh-transform-core'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();candidate='3befda13bc356444056f5c6ffeabd1b800cc3ac5'
report=json.load(open(folder/'orientation-runtime/report.json'));focused=json.load(open(folder/'orientation-focused/report.json'))
assert report['checks']==2406 and report['scope']=='full_1203_cases_both_interfaces' and not report['passed'] and not report['required_full_gate_passed']
assert focused['checks']==234 and focused['scope']=='focused_diagnostic' and not focused['passed'] and not focused['required_full_gate_passed']
assert report['input_hashes']==focused['input_hashes']=={name:sha(root/name) for name in report['input_hashes']}
subprocess.run(['git','diff','--quiet',candidate,'--','src','tests','tools','baseline','docs/contracts'],cwd=root,check=True)
for name,data in [('orientation-runtime',report),('orientation-focused',focused)]:
 assert data['source_reference_checked']['passed']
 assert len(data['runs'])==len({(r['interface'],r['id']) for r in data['runs']})==data['checks']
 for row in data['runs']:
  p=folder/name/row['file'];assert sha(p)==row['sha256'];raw=json.load(open(p));assert raw['case']['id']==row['id'] and raw['status']==row['status']
old=json.load(open(folder/'connected-runtime/report.json'));old_rows={(r['interface'],r['id']):r for r in old['runs']};now={(r['interface'],r['id']):r for r in report['runs']};assert set(old_rows)==set(now)
matched=[r for r in report['runs'] if r['status']=='passed'];failures=[r for r in report['runs'] if r['status']=='failed'];improved=[key for key,r in now.items() if r['status']=='passed' and old_rows[key]['status']!='passed'];regressed=[key for key,r in now.items() if r['status']!='passed' and old_rows[key]['status']=='passed']
assert (len(matched),len(failures),len(improved),len(regressed))==(2052,354,222,0)
assert sum(r['status']=='passed' for r in focused['runs'])==222
assert all(old_rows[key]['error']=='mesh transform normal orientation is not implemented yet' for key in improved)
for key in improved:
 raw=json.load(open(folder/'orientation-runtime'/now[key]['file']));assert raw['case']['parameters']['orient_type']=='NORMAL'
assert all(now[('cli',id)]['sha256']==now[('official_mcp_sdk',id)]['sha256'] for _,id in now)
def category(r):
 e=r['error']
 if e.startswith('numeric mismatch: after/'):
  return 'numeric/'+e.split('after/')[1].split('/')[0]
 return e
per_interface={interface:dict(sorted(Counter(category(r) for r in failures if r['interface']==interface).items())) for interface in ['cli','official_mcp_sdk']}
analysis={'scope':'complete source run after geometric normal and individual island orientation','matched':len(matched),'matched_finished':sum(r.get('source_outcome')=='FINISHED' for r in matched),'matched_expected_cancellations':sum(r.get('source_outcome')=='CANCELLED' for r in matched),'failed':len(failures),'newly_matched':len(improved),'regressions':0,'new_matches_all_normal_orientation':True,'per_interface_failures':per_interface,'both_interfaces_have_identical_raw_results':True,'required_transform_gate_passed':False,'source_report_sha256':sha(folder/'orientation-runtime/report.json')}
assert (analysis['matched_finished'],analysis['matched_expected_cancellations'])==(2040,12)
(folder/'orientation-runtime/analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
normal=json.load(open(folder/'orientation-normal-regression/manifest.json'));assert normal['passed'] and normal['cases']==42
mcp=json.load(open('/private/tmp/formora-orientation-mcp.stdout'));mcp_checks={'initialize','discovery','input_schemas','inspect','apply','stale_revision','undo','reload','mesh_create_edit_query','referenced_mesh_delete_rejected','mesh_undo_reload','polygon_tessellate_edit_undo_reload'};assert set(mcp)==mcp_checks|{'sdk_version','binary_sha256','protocol_version','product_milestone_acceptance'};assert all(mcp[k]=='passed' for k in mcp_checks) and mcp['sdk_version']=='2.3.0' and mcp['protocol_version']=='2025-11-25' and not mcp['product_milestone_acceptance']
checks=folder/'orientation-checks';checks.mkdir(exist_ok=False)
for name in ['rust','python','clippy','format','mcp','normal','full']:
 for suffix in ['stdout','stderr']:shutil.copyfile('/private/tmp/formora-orientation-'+name+'.'+suffix,checks/(name+'.'+suffix))
for name in ['baseline','strict']:
 p=Path('/private/tmp/formora-orientation-'+name+'.json');data=json.load(open(p));assert data['structurally_valid'] and not data['baseline_ready'] and data['problems']==[];assert (data['sources'],data['pending_sources'],data['pending_features'])==(9047,9003,31);shutil.copyfile(p,checks/(name+'.json'))
rust=(checks/'rust.stdout').read_text();assert sum(map(int,re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',rust)))==158;python=(checks/'python.stderr').read_text();assert re.search(r'Ran 74 tests in ',python) and re.search(r'\nOK\s*$',python)
binary=Path('/private/tmp/formora-target-actual185/debug/formora');binary_sha=sha(binary);assert binary_sha==report['binary_sha256']==focused['binary_sha256']==normal['binary_sha256']==mcp['binary_sha256']
for path in ['orientation-isolation/report.json','orientation-gpu/manifest.json']:
 data=json.load(open(folder/path));assert data['passed'] and data['binary_sha256']==binary_sha;assert data['driver_sha256']==sha(folder/path.split('/')[0]/'capture-driver.py');assert data['source_files']=={name:sha(root/name) for name in data['source_files']}
prior=json.loads(subprocess.check_output(['git','show','1260a7935fc5b3aa247398fb19e5689b3f9d910f:baseline/lock.json'],cwd=root,text=True));lock=json.load(open(root/'baseline/lock.json'));pins={r['path']:r for r in lock['artifacts']};assert len(pins)==3762 and len(prior['artifacts'])==3755 and all(pins[r['path']]==r for r in prior['artifacts'])
for r in lock['artifacts']:assert sha(root/r['path'])==r['sha256']
info=json.load(open('/private/tmp/formora-target-actual185/.rustc_info.json'));assert any(o.get('stdout','').startswith('rustc 1.85.0 ') for o in info['outputs'].values());(checks/'rustc-info.json').write_text(json.dumps(info,indent=2)+'\n')
shutil.copyfile(__file__,checks/'evidence-checker.py')
folders=['orientation-runtime','orientation-focused','orientation-normal-regression','orientation-isolation','orientation-gpu','orientation-checks'];artifacts={str(p.relative_to(folder)):sha(p) for directory in folders for p in sorted((folder/directory).rglob('*')) if p.is_file() and not p.name.endswith('.formora.lock')}
manifest={'evidence_integrity_verified':True,'scope':'geometric normal and individual island mesh transform frames; complete issue #48 still fails','rust_candidate':candidate,'binary_sha256':binary_sha,'rust_tests':158,'python_tests':74,'format_clippy_passed':True,'focused_normal_comparisons':{'passed':False,'exit_code':1,'checks':234,'matched':222,'failed':12},'full_source_gate':{'passed':False,'exit_code':1,'executed':2406,'matched':2052,'failed':354,'matched_finished':2040,'matched_expected_cancellations':12,'improved':222,'regressions':0},'normal_regression_cases_passed':42,'mcp_regression_passed':True,'unseen_repository_read_denied_transforms_passed':True,'native_normal_metal_passed':True,'source_pins_preserved':3755,'source_pins_total':3762,'baseline_metadata_exit':0,'strict_baseline_exit':2,'required_unrun':['remaining source failures','fixed release performance','final full regression set','three-platform CI','dependency integration','independent issue acceptance','full numeric and capacity domains','random sequence/distribution','custom normal authoring'],'milestone_acceptance':'unrun','artifacts':artifacts};(folder/'orientation-implementation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'binary_sha256':binary_sha,'evidence_artifacts':len(artifacts),'matched':2052,'failed':354,'failures_per_interface':per_interface}))
