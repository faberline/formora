from pathlib import Path
from collections import Counter
import hashlib,json,re,shutil,subprocess
root=Path('/Users/chrischeng/faberlines/formora');folder=root/'docs/evidence/mesh-transform-core';candidate='32bd336d8dd708b5dc59c7fdb82c414a08d0adaf'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['full','focused']:
 shutil.copytree('/private/tmp/formora-uv-mirror-'+name,folder/('uv-mirror-runtime' if name=='full' else 'uv-mirror-focused'))
shutil.copytree('/private/tmp/formora-uv-mirror-normal',folder/'uv-mirror-normal-regression')
report=json.load(open(folder/'uv-mirror-runtime/report.json'));focused=json.load(open(folder/'uv-mirror-focused/report.json'))
assert report['checks']==2406 and report['scope']=='full_1203_cases_both_interfaces' and not report['passed'] and not report['required_full_gate_passed']
assert focused['checks']==60 and focused['scope']=='focused_diagnostic' and focused['passed'] and not focused['required_full_gate_passed']
assert report['input_hashes']==focused['input_hashes']=={name:sha(root/name) for name in report['input_hashes']}
subprocess.run(['git','diff','--quiet',candidate,'--','src','tests','tools','baseline','docs/contracts'],cwd=root,check=True)
subprocess.run(['git','diff','--quiet','3c5736a268269f80650d09cdbdfd16a25b79b7bb','--','tools/compare_transform_reference.py','baseline/fixtures','baseline/reference'],cwd=root,check=True)
for name,data in [('uv-mirror-runtime',report),('uv-mirror-focused',focused)]:
 assert data['source_reference_checked']['passed']
 assert len(data['runs'])==len({(r['interface'],r['id']) for r in data['runs']})==data['checks']
 for row in data['runs']:
  p=folder/name/row['file'];assert sha(p)==row['sha256'];raw=json.load(open(p));assert raw['case']['id']==row['id'] and raw['status']==row['status']
old=json.load(open(folder/'safe-runtime/report.json'));before={(r['interface'],r['id']):r for r in old['runs']};now={(r['interface'],r['id']):r for r in report['runs']};assert set(before)==set(now)
matched=[r for r in report['runs'] if r['status']=='passed'];failures=[r for r in report['runs'] if r['status']=='failed'];improved=[key for key,row in now.items() if row['status']=='passed' and before[key]['status']!='passed'];regressed=[key for key,row in now.items() if row['status']!='passed' and before[key]['status']=='passed']
assert (len(matched),len(failures),len(improved),len(regressed))==(2362,44,48,0)
reasons=Counter()
for key,row in now.items():
 old_raw=json.load(open(folder/'safe-runtime'/before[key]['file']));raw=json.load(open(folder/'uv-mirror-runtime'/row['file']))
 assert raw['case']==old_raw['case'] and raw['setup']==old_raw['setup'] and raw['request']==old_raw['request'] and row['reference_sha256']==before[key]['reference_sha256']
 if key in improved:
  if raw['case']['context']['correct_face_attributes']:reasons['face_attribute_correction']+=1
  else:assert raw['case']['context']['mirror_x'] and raw['case']['parameters']['mirror'];reasons['mirror']+=1
assert reasons=={'face_attribute_correction':36,'mirror':12}
assert all(now[('cli',id)]['sha256']==now[('official_mcp_sdk',id)]['sha256'] for _,id in now)
all_axis=['transform_0693','transform_0701','transform_0709','transform_0717','transform_0725','transform_0733','transform_0741']
assert all(now[(interface,id)]['status']=='failed' for interface in ['cli','official_mcp_sdk'] for id in all_axis)
def category(row):
 error=row['error']
 if '/geometry/' in error:return 'geometry_numeric'
 if '/normals/' in error:return 'normal_numeric'
 if '/world_vertices/' in error:return 'world_position_numeric'
 raise AssertionError(error)
per_interface={name:dict(Counter(category(r) for r in failures if r['interface']==name)) for name in ['cli','official_mcp_sdk']}
assert per_interface['cli']==per_interface['official_mcp_sdk']=={'geometry_numeric':10,'normal_numeric':6,'world_position_numeric':6}
analysis={'candidate':candidate,'checks':2406,'matched':2362,'matched_finished':sum(r.get('source_outcome')=='FINISHED' for r in matched),'matched_expected_cancellations':sum(r.get('source_outcome')=='CANCELLED' for r in matched),'failed':44,'improved':48,'improvements':dict(reasons),'regressions':0,'adapter_requests_and_setups_unchanged':True,'all_seven_undefined_axis_cases_retained':True,'per_interface_failures':per_interface,'both_interfaces_have_identical_raw_results':True,'required_transform_gate_passed':False,'source_report_sha256':sha(folder/'uv-mirror-runtime/report.json')}
assert (analysis['matched_finished'],analysis['matched_expected_cancellations'])==(2350,12)
(folder/'uv-mirror-runtime/analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
normal=json.load(open(folder/'uv-mirror-normal-regression/manifest.json'));assert normal['passed'] and normal['cases']==42
mcp=json.load(open('/private/tmp/formora-uv-mirror-mcp.stdout'));keys={'initialize','discovery','input_schemas','inspect','apply','stale_revision','undo','reload','mesh_create_edit_query','referenced_mesh_delete_rejected','mesh_undo_reload','polygon_tessellate_edit_undo_reload'};assert set(mcp)==keys|{'sdk_version','binary_sha256','protocol_version','product_milestone_acceptance'};assert all(mcp[k]=='passed' for k in keys) and mcp['sdk_version']=='2.3.0' and mcp['protocol_version']=='2025-11-25' and not mcp['product_milestone_acceptance']
checks=folder/'uv-mirror-checks';checks.mkdir()
for name in ['rust','python','clippy','format','build','mcp','normal','full','focused']:
 for suffix in ['stdout','stderr']:shutil.copyfile('/private/tmp/formora-uv-mirror-'+name+'.'+suffix,checks/(name+'.'+suffix))
shutil.copyfile('/private/tmp/formora-uv-mirror-rustc-info.txt',checks/'rustc-info.txt')
for name in ['baseline','strict']:
 p=Path('/private/tmp/formora-uv-mirror-'+name+'.json');data=json.load(open(p));assert data['structurally_valid'] and not data['baseline_ready'] and data['problems']==[];assert (data['sources'],data['pending_sources'],data['pending_features'])==(9047,9003,31);shutil.copyfile(p,checks/(name+'.json'))
assert sum(map(int,re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',(checks/'rust.stdout').read_text())))==205
assert re.search(r'Ran 79 tests in ',(checks/'python.stderr').read_text()) and re.search(r'\nOK\s*$',(checks/'python.stderr').read_text())
binary=Path('/private/tmp/formora-target-actual185/debug/formora');binary_sha=sha(binary);assert binary_sha==report['binary_sha256']==focused['binary_sha256']==normal['binary_sha256']==mcp['binary_sha256']
for path in ['uv-mirror-isolation/report.json','uv-mirror-gpu/manifest.json']:
 data=json.load(open(folder/path));assert data['passed'] and data['binary_sha256']==binary_sha;assert data['driver_sha256']==sha(folder/path.split('/')[0]/'capture-driver.py');assert data['source_files']=={name:sha(root/name) for name in data['source_files']}
 if path.endswith('manifest.json'):assert data['uv_correction'] and data['mirror_destination']=='v0011' and data['changed_pixels']==14302 and data['changed_vertices']==15 and data['fresh_reload_identical']
audit_folder=folder/'uv-mirror-source-audit';audit=json.load(open(audit_folder/'report.json'));assert audit['passed'] and audit['candidate']==candidate and audit['returncode']==0 and audit['cross_platform']=='unrun'
source=root/'baseline/sources/mesh-uv-mirror-transform/mesh_mirror.cc';assert sha(source)==audit['primary_source_sha256'];s=source.read_text();body=s[s.index('static int mirrtopo_hash_sort('):s.index('\nstatic int mirrtopo_vert_sort(')];assert hashlib.sha256(body.encode()).hexdigest()==audit['literal_function_sha256'];assert body in (audit_folder/'probe.cc').read_text();assert (audit_folder/'probe.stdout').read_bytes()==b'9 1 9 2 2 1 \n'
for name,digest in audit['artifacts'].items():assert sha(audit_folder/name)==digest
milestones=[m for page in json.load(open('/private/tmp/formora-uv-mirror-milestones.json')) for m in page];assert len(milestones)==11 and all(m['state']=='open' and m['due_on'] is None for m in milestones)
shutil.copyfile('/private/tmp/formora-uv-mirror-milestones.json',checks/'milestones.json')
shutil.copyfile(__file__,checks/'evidence-checker.py')
lock=json.load(open(root/'baseline/lock.json'));assert len(lock['artifacts'])==3780 and len({a['path'] for a in lock['artifacts']})==3780
for a in lock['artifacts']:assert sha(root/a['path'])==a['sha256'],a['path']
manifest={'candidate':candidate,'binary_sha256':binary_sha,'rust_version':'1.85.0','rust_tests_passed':205,'python_tests_passed':79,'clippy':'passed','format':'passed','official_mcp_sdk_regression':'passed','normal_queries_passed':42,'source_checks':2406,'matched':2362,'failed':44,'improved':48,'regressions':0,'focused_checks':60,'focused_passed':True,'source_cpp_hash_comparator_probe':'passed_on_current_macos','repository_denied_unseen_mirror_uv_probe':'passed','real_metal_render_reload':'passed','first_gpu_driver_failure_preserved':True,'baseline_structurally_valid':True,'baseline_ready':False,'baseline_pins':3780,'issues_accepted':False,'milestones_accepted':0,'milestones_open':11,'required_transform_gate_passed':False,'fixed_performance':'unrun','complete_legacy_regressions_on_final_candidate':'unrun','three_platform_ci':'unrun','dependency_integration':'unrun','independent_acceptance':'unrun','source_inputs':report['input_hashes'],'artifacts':{str(p.relative_to(folder)):sha(p) for name in ['uv-mirror-runtime','uv-mirror-focused','uv-mirror-normal-regression','uv-mirror-checks','uv-mirror-isolation','uv-mirror-gpu','uv-mirror-gpu-attempt-1','uv-mirror-source-audit'] for p in sorted((folder/name).rglob('*')) if p.is_file()},'evidence_integrity_passed':True}
(folder/'uv-mirror-implementation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:manifest[k] for k in ['candidate','rust_tests_passed','python_tests_passed','matched','failed','improved','regressions','evidence_integrity_passed','required_transform_gate_passed']},indent=2));print('Artifacts:',len(manifest['artifacts']))
