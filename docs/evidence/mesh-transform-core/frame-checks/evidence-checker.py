from pathlib import Path
from collections import Counter
import copy,hashlib,json,re,shutil,subprocess
root=Path('/Users/chrischeng/faberlines/formora');folder=root/'docs/evidence/mesh-transform-core';candidate='4d7bc95bf988442cc95885ed4518d8ecd37e04fd';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
names=['full','focused','normal','primitives','scale','selection','creation','polygon']
for name in names:shutil.copytree('/private/tmp/formora-frame-'+name,folder/('frame-runtime' if name=='full' else 'frame-'+name))
report=json.load(open(folder/'frame-runtime/report.json'));focused=json.load(open(folder/'frame-focused/report.json'));binary_sha=sha(Path('/private/tmp/formora-target-actual185/debug/formora'))
assert report['checks']==2406 and report['scope']=='full_1203_cases_both_interfaces' and not report['passed'] and not report['required_full_gate_passed']
assert focused['checks']==30 and focused['scope']=='focused_diagnostic' and focused['passed'] and not focused['required_full_gate_passed']
assert report['input_hashes']==focused['input_hashes']=={name:sha(root/name) for name in report['input_hashes']}
subprocess.run(['git','diff','--quiet',candidate,'--','src','tests','tools','baseline','docs/contracts'],cwd=root,check=True)
subprocess.run(['git','diff','--quiet','e23bb03891435b37abd618c7ed22c698595ade7a','--','tools/compare_transform_reference.py','baseline/fixtures','baseline/reference'],cwd=root,check=True)
for name,data in [('frame-runtime',report),('frame-focused',focused)]:
 assert data['binary_sha256']==binary_sha and data['source_reference_checked']['passed']
 assert len(data['runs'])==len({(r['interface'],r['id']) for r in data['runs']})==data['checks']
 for row in data['runs']:
  p=folder/name/row['file'];assert sha(p)==row['sha256'];raw=json.load(open(p));assert raw['case']['id']==row['id'] and raw['status']==row['status']
  for phase in ['before','after']:
   q=raw['world_queries'][phase];assert q['entity']['transform']['precision']=='f32' and q['world_vertices']==raw[phase]['world_vertices'] and q['id']=='target'
old=json.load(open(folder/'uv-mirror-runtime/report.json'));before={(r['interface'],r['id']):r for r in old['runs']};now={(r['interface'],r['id']):r for r in report['runs']};assert set(before)==set(now)
passed=[r for r in report['runs'] if r['status']=='passed'];failures=[r for r in report['runs'] if r['status']=='failed'];improved=[key for key,row in now.items() if row['status']=='passed' and before[key]['status']!='passed'];regressed=[key for key,row in now.items() if row['status']!='passed' and before[key]['status']=='passed']
assert (len(passed),len(failures),len(improved),len(regressed))==(2392,14,30,0)
for key,row in now.items():
 previous=json.load(open(folder/'uv-mirror-runtime'/before[key]['file']));current=json.load(open(folder/'frame-runtime'/row['file']));expected=copy.deepcopy(previous['setup'])
 for command in expected['commands']:
  if command['operation']=='create_entity':command['entity']['transform']['precision']='f32'
 assert current['case']==previous['case'] and current['setup']==expected and current['request']==previous['request'] and row['reference_sha256']==before[key]['reference_sha256']
assert all(now[('cli',id)]['sha256']==now[('official_mcp_sdk',id)]['sha256'] for _,id in now)
undefined={'transform_'+id for id in ['0693','0701','0709','0717','0725','0733','0741']};assert {r['id'] for r in failures}==undefined and all('/geometry/' in r['error'] for r in failures)
analysis={'candidate':candidate,'checks':2406,'matched':2392,'matched_finished':sum(r.get('source_outcome')=='FINISHED' for r in passed),'matched_expected_cancellations':sum(r.get('source_outcome')=='CANCELLED' for r in passed),'failed':14,'improved':30,'regressions':0,'remaining_ids':sorted(undefined),'source_expected_results_unchanged':True,'source_requests_unchanged':True,'setup_changed_only_authored_f32_precision':True,'world_observer':'actual native entity query','both_interfaces_have_identical_raw_results':True,'required_transform_gate_passed':False}
assert analysis['matched_finished']==2380 and analysis['matched_expected_cancellations']==12;(folder/'frame-runtime/analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
regressions={}
for name,count in [('primitives',162),('scale',8),('selection',1060),('creation',262),('polygon',57)]:
 data=json.load(open(folder/('frame-'+name)/'report.json'));assert data['passed'] and data['binary_sha256']==binary_sha and len(data['runs'])==count
 assert all(row['status']=='passed' for row in data['runs'])
 for row in data['runs']:
  p=folder/('frame-'+name)/row.get('file',row['id']+'.json');assert sha(p)==row.get('sha256',row.get('candidate_sha256'))
 for names_field in ['source_files_sha256','adapter_files_sha256','capture_inputs_sha256']:
  for path,digest in data.get(names_field,{}).items():assert sha(root/path)==digest,path
 regressions[name]=count
normal=json.load(open(folder/'frame-normal/manifest.json'));assert normal['passed'] and normal['cases']==42 and normal['binary_sha256']==binary_sha
for row in normal['records']:assert sha(folder/'frame-normal'/row['file'])==row['sha256'] and row['maximum_absolute_error']==0
mcp=json.load(open('/private/tmp/formora-frame-mcp.stdout'));keys={'initialize','discovery','input_schemas','inspect','apply','stale_revision','undo','reload','mesh_create_edit_query','referenced_mesh_delete_rejected','mesh_undo_reload','polygon_tessellate_edit_undo_reload'};assert all(mcp[k]=='passed' for k in keys) and mcp['binary_sha256']==binary_sha and mcp['sdk_version']=='2.3.0' and mcp['protocol_version']=='2025-11-25' and not mcp['product_milestone_acceptance']
for name,file in [('frame-isolation','report.json'),('frame-gpu','manifest.json'),('frame-source-oracle-final','report.json')]:
 data=json.load(open(folder/name/file));assert data['passed'] and data['binary_sha256']==binary_sha and data['driver_sha256']==sha(folder/name/'capture-driver.py');assert data['source_files']=={name:sha(root/name) for name in data['source_files']}
 if name=='frame-gpu':assert data['fresh_reload_identical'] and data['changed_vertices']==15 and data['changed_pixels']==14302
 if name=='frame-source-oracle-final':assert len(data['cases'])==6 and all(r['matrix_exact'] and r['point_exact'] and r['queries_preserve_disk'] for r in data['cases']) and not data['measured_outputs_used_as_product_inputs'] and data['reference_binary_sha256']=='de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
perf=json.load(open(folder/'frame-performance/report.json'));pm=json.load(open(folder/'frame-performance/manifest.json'));assert not perf['passed'] and not pm['passed'] and len(perf['runs'])==9 and pm['core_runs_failed']==9 and pm['source_grid_position_comparison']=='unrun';assert pm['driver_sha256']==sha(folder/'frame-performance/capture-driver.rs')
assert pm['source_files']=={name:sha(root/name) for name in pm['source_files']}
for row in perf['runs']:
 assert row['core_end_ns']>row['core_start_ns'] and row['pipeline_end_ns']>row['pipeline_start_ns'];assert row['core_ms']==(row['core_end_ns']-row['core_start_ns'])/1e6;assert row['operation_save_reload_ms']==(row['pipeline_end_ns']-row['pipeline_start_ns'])/1e6
 assert row['maximum_core_ms']==250 and row['maximum_pipeline_ms']==2000 and row['core_ms']>250 and row['operation_save_reload_ms']<=2000 and not row['passed'] and row['reload_equal'] and row['topology_preserved'] and row['editing_preserved']
for name,digest in pm['artifacts'].items():assert sha(folder/'frame-performance'/name)==digest
checks=folder/'frame-checks';checks.mkdir()
for name in ['rust','python','clippy','format','build','mcp','normal','full','focused','primitives','scale','selection','creation','polygon']:
 for suffix in ['stdout','stderr']:shutil.copyfile('/private/tmp/formora-frame-'+name+'.'+suffix,checks/(name+'.'+suffix))
for name in ['baseline','strict']:
 p=Path('/private/tmp/formora-frame-'+name+'.json');data=json.load(open(p));assert data['structurally_valid'] and not data['baseline_ready'] and data['problems']==[] and (data['sources'],data['pending_sources'],data['pending_features'])==(9047,9003,31);shutil.copyfile(p,checks/(name+'.json'))
assert sum(map(int,re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',(checks/'rust.stdout').read_text())))==213;assert re.search(r'Ran 80 tests in ',(checks/'python.stderr').read_text()) and re.search(r'\nOK\s*$',(checks/'python.stderr').read_text())
for path in ['tests/preview.rs','tests/gimbal.rs','tests/mesh.rs']:
 old=subprocess.check_output(['git','show','e23bb03891435b37abd618c7ed22c698595ade7a:'+path],cwd=root,text=True);diff=subprocess.check_output(['git','diff','e23bb03891435b37abd618c7ed22c698595ade7a',candidate,'--',path],cwd=root,text=True);assert not any(line.startswith('-') and not line.startswith('---') for line in diff.splitlines()),path
lock=json.load(open(root/'baseline/lock.json'));old_lock=json.loads(subprocess.check_output(['git','show','e23bb03891435b37abd618c7ed22c698595ade7a:baseline/lock.json'],cwd=root));assert len(lock['artifacts'])==3785 and lock['artifacts'][:3780]==old_lock['artifacts']
for a in lock['artifacts']:assert sha(root/a['path'])==a['sha256'],a['path']
shutil.copyfile(__file__,checks/'evidence-checker.py')
artifact_dirs=['frame-runtime','frame-focused','frame-normal','frame-primitives','frame-scale','frame-selection','frame-creation','frame-polygon','frame-checks','frame-isolation','frame-gpu','frame-source-oracle-final','frame-performance']
manifest={'candidate':candidate,'binary_sha256':binary_sha,'rust_version':'1.85.0','rust_tests_passed':213,'python_tests_passed':80,'clippy':'passed','format':'passed','official_mcp_sdk_regression':'passed','normal_queries_passed':42,'complete_legacy_regressions':regressions,'source_checks':2406,'matched':2392,'failed':14,'improved':30,'regressions':0,'focused_checks':30,'focused_passed':True,'reference_world_matrix_orders_exact':6,'repository_denied_f32_world_mirror_uv_probe':'passed','real_metal_render_reload':'passed','baseline_structurally_valid':True,'baseline_ready':False,'baseline_pins':3785,'fixed_performance':'failed','performance_core_ms_range':[min(r['core_ms'] for r in perf['runs']),max(r['core_ms'] for r in perf['runs'])],'performance_pipeline_ms_range':[min(r['operation_save_reload_ms'] for r in perf['runs']),max(r['operation_save_reload_ms'] for r in perf['runs'])],'source_grid_position_comparison':'unrun','required_transform_gate_passed':False,'three_platform_ci':'unrun','dependency_integration':'unrun','independent_acceptance':'unrun','milestones_accepted':0,'source_inputs':report['input_hashes'],'artifacts':{str(p.relative_to(folder)):sha(p) for name in artifact_dirs for p in sorted((folder/name).rglob('*')) if p.is_file()},'evidence_integrity_passed':True}
(folder/'frame-implementation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({k:manifest[k] for k in ['candidate','binary_sha256','rust_tests_passed','python_tests_passed','matched','failed','improved','regressions','fixed_performance','evidence_integrity_passed','required_transform_gate_passed']},indent=2));print('Artifacts:',len(manifest['artifacts']))
