"""Audit local gates while leaving CI, integration and independent acceptance unrun."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from runtime_artifacts import read_json

IMPLEMENTATION='e16eab6471f32aa85c2bbba867e6fd4e09ead640'
BINARY='bd666398596d8a9ec61d8e12db62df53bd7c2aa53ba5492ceba65ab4ea655bef'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def passed(path,key='binary_sha256'):
    r=read_json(path);assert r['passed'] is True,path
    if key:assert r[key]==BINARY,path
    return r
def artifacts(folder,report):
    for name,digest in report.get('artifacts',{}).items():assert sha(folder/name)==digest,(folder,name)

assert sha(Path('/private/tmp/formora-target-actual185/debug/formora'))==BINARY
api=read_json(HERE/'complete-api-evidence.json')
assert api['complete_api_evidence_valid'] and api['complete_requests']==14326
assert api['implementation_commit']==IMPLEMENTATION and api['binary_sha256']==BINARY
diagnostics=HERE/'diagnostics'
rows=re.findall(r'test result: ok. (\d+) passed; (\d+) failed; (\d+) ignored;',
    (diagnostics/'rust-tests-full-01.stdout').read_text())
assert sum(int(r[0]) for r in rows)==271 and all(r[1:]==('0','0') for r in rows)
assert read_json(diagnostics/'rust-tests-full-01.json')['terminal_exit_code']==0
text=(diagnostics/'python-tests-full-01.stderr').read_text()
assert 'Ran 190 tests' in text and text.rstrip().endswith('OK')
for name in ['fmt-01','clippy-01','build-02']:
    assert read_json(diagnostics/(name+'.json'))['terminal_exit_code']==0
metadata=read_json(diagnostics/'metadata-commands.json')
assert metadata['binary_sha256']==BINARY
assert [r['terminal_exit_code'] for r in metadata['commands']]==[0,2]
assert metadata['commands'][0]['report']==metadata['commands'][1]['report']
assert metadata['commands'][0]['report']['structurally_valid']
assert not metadata['commands'][0]['report']['baseline_ready']
assert not metadata['commands'][0]['report']['problems']
assert not read_json(ROOT/'baseline/inventory.json')['complete_products']

retained=passed(HERE/'retained/report.json');assert retained['verification_inputs_unchanged']
assert {r['name']:r['actual_checks'] for r in retained['checks']}=={
    'primitive':162,'scale':8,'selection':1060,'creation':262,'payload':57,'normal':42,'rng':96,'mcp':None}
assert all(r['passed'] and r['exit_code']==0 for r in retained['checks'])
assert passed(HERE/'rng-one-shot/report.json')['checks']==48
assert len(passed(HERE/'source-oracle/report.json')['cases'])==6
for name in ['recipe','recipe-raw-legacy','recipe-mesh-legacy']:
    folder=HERE/name;r=passed(folder/'report.json');artifacts(folder,r)
    assert r['native_terminal_exit']==r['fresh_process_exit']==0
    for key in ['cursor_only_preserves_recipe','geometry_edit_marks_recipe',
        'failed_batch_preserves_recipe_and_disk','undo_replay_checked',
        'regeneration_restores_original_authored_geometry_and_attributes','fresh_reload_equal']:
        assert r[key]
for name in ['isolation','isolation-raw-legacy','isolation-scene','isolation-selection',
             'isolation-creation','isolation-rng','isolation-primitive']:
    folder=HERE/name;key='copied_binary_sha256' if name=='isolation-primitive' else 'binary_sha256'
    r=passed(folder/'report.json',key);artifacts(folder,r)
    assert r['denial_control_exit_code']!=0
    assert 'not permitted' in r['denial_control_stderr'] or 'Permission denied' in r['denial_control_stderr']
assert passed(HERE/'isolation/report.json')['native_calls']==29
for name,pixels in [('gpu',20083),('gpu-raw-legacy',20350),('gpu-rng-legacy',12532),('gpu-mirror-legacy',14302)]:
    folder=HERE/name;r=passed(folder/'manifest.json');artifacts(folder,r)
    assert '(Metal,' in r['gpu'] and r['changed_pixels']==pixels
    assert (folder/'after.png').read_bytes()==(folder/'reloaded.png').read_bytes()
assert passed(HERE/'gpu/manifest.json')['raw_nonunit_delta_and_inactive_values_preserved']
for name in ['failed-save-02','seven-actions','input-rejections']:
    folder=HERE/name;r=passed(folder/'report.json');artifacts(folder,r)
assert passed(HERE/'failed-save-02/report.json')['native_calls']==15
assert passed(HERE/'input-rejections/report.json')['required_rejections']==13
assert len(passed(HERE/'seven-actions/report.json')['actions'])==7

perf=HERE/'performance'
for name,count in [('raw-source-comparison-01.json',24),('retained-90-source-comparison-02.json',90),
        ('retained-rotation-source-comparison-01.json',24),('retained-30-source-comparison-02.json',30)]:
    r=passed(perf/name);assert r['samples']==count
    assert not r.get('diagnostic_failed_timings',False)
assert len(passed(perf/'retained-9-source-comparison-02.json',None)['records'])==9
archive_count=0;raw_scene_count=0
for name,accepted in [('raw-01',True),('retained-90-02',True),('retained-rotation-01',True),
        ('retained-39-02',True),('diagnostics/retained-90-01',False),('diagnostics/retained-39-01',False)]:
    folder=perf/name;index=read_json(folder/'scene-archive-index.json')
    assert index['all_raw_bytes_preserved'] and index['compression_after_timing']
    assert index['controller_passed'] is accepted
    for row in index['files']:
        path=folder/row['stored_path'];assert sha(path)==row['stored_sha256']
        data=gzip.decompress(path.read_bytes()) if row['encoding']=='gzip' else path.read_bytes()
        assert len(data)==row['raw_bytes'] and hashlib.sha256(data).hexdigest()==row['raw_sha256']
        archive_count+=1
    raw_scene_count+=index['raw_scene_count']
assert raw_scene_count==332
failed90=read_json(perf/'diagnostics/retained-90-01-source-comparison.json')
assert failed90['source_comparisons_passed'] and failed90['diagnostic_failed_timings']
assert not failed90['passed'] and not failed90['required_full_gate_passed']
failed90folder=perf/'diagnostics/retained-90-01/samples'
summary=read_json(failed90folder/'timing-summary.json')
failed90rows=[r for g in summary['groups'] for r in read_json(failed90folder/g['file'])['runs'] if not r['passed']]
assert len(failed90rows)==10 and {r['class'] for r in failed90rows}=={'A'}
failed39=read_json(perf/'diagnostics/retained-39-01/single/report.json')
assert sum(not r['passed'] for r in failed39['runs'])==1
timings=read_json(perf/'complete-timing-gates.json')
assert timings['timing_gates_passed'] and timings['final_complete_samples']==177
assert timings['preserved_unaccepted_trial_samples']==129 and timings['actual_over_limit_rows_in_unaccepted_trials']==11
result={'local_evidence_valid':True,'implementation_commit':IMPLEMENTATION,'binary_sha256':BINARY,
    'complete_api_requests':14326,'rust_tests':271,'python_tests':190,'accepted_release_samples':177,
    'preserved_unaccepted_trial_samples':129,'actual_over_limit_rows_in_unaccepted_trials':11,
    'archived_scene_files_rehashed':raw_scene_count,'archived_files_rehashed':archive_count,
    'baseline_ready':False,'three_platform_ci':'unrun','integration':'unrun',
    'independent_codex_acceptance':'unrun','product_acceptance':'unrun','milestones_accepted':0}
with (HERE/'local-evidence.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(result),flush=True)
