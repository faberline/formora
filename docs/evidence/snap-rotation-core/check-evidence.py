"""Recheck complete local evidence without granting integration or acceptance."""
import collections
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
import rotation_snap_runtime as rotation
import scene_snap_runtime_smoke as scene
import snap_runtime_smoke as single
import transform_runtime_smoke as transform
from runtime_artifacts import read_json
from compare_snap_menu_reference import tree

IMPLEMENTATION='c67d2370c00d2031adb7d896c978b25ffdd3d885'
BINARY='093b46f00749eddde3930d4aa5377315a553bafb878807f8ecb8f42db37e54fa'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def passed(path,binary=True):
    value=read_json(path);assert value['passed'] is True,path
    if binary:assert value['binary_sha256']==BINARY,path
    return value


def audit(kind,count):
    folder=HERE/('runtime-'+kind);report=passed(folder/'report.json')
    assert report['checks']==count and report['required_full_gate_passed'] and len(report['runs'])==count
    for name,digest in report['input_hashes'].items():assert sha(ROOT/name)==digest,name
    family={'full':'snap-rotation','scene':'snap-menu','single':'snap-menu','transform':'mesh-transform'}[kind]
    suite=read_json(ROOT/'baseline/fixtures'/(family+'.json'));cases={r['id']:r for r in suite['runs']}
    compact={key:value for key,value in suite.items() if key!='runs'}
    module={'full':rotation,'scene':scene,'single':single,'transform':transform}[kind]
    covered={id for id,r in cases.items() if kind in ['full','transform'] or (scene.covered(r) if kind=='scene' else single.covered(r))}
    refs=[ROOT/'baseline/reference/blender-5.2.3'/name for name in [family,family+'-repeat']]
    seen=set();counts=collections.Counter();setup_cache={}
    for index,row in enumerate(report['runs']):
        pair=(row['interface'],row['id']);assert pair not in seen and row['id'] in covered;seen.add(pair)
        assert row['status']=='passed';path=folder/row['file'];assert sha(path)==row['sha256']
        raw=read_json(path);case=cases[row['id']]
        assert raw['case']==case and raw['status']=='passed' and raw['comparison_error'] is None
        if kind!='transform':assert raw['fresh_reload_matches']
        if row['id'] not in setup_cache:setup_cache[row['id']]=module.setup(compact,case)
        assert raw['setup']==setup_cache[row['id']] and raw['request']==module.request_for(case)
        for ref in refs:
            source=read_json(ref/(row['id']+('.json.gz' if kind=='full' else '.json')))
            if kind=='full':
                for phase in ['before','after']:
                    assert raw[phase+'_scene']==raw['scene_inspections'][phase]['scene']
                    actual=rotation.snapshot(raw['scene_inspections'][phase],raw['queries'][phase],raw['world_queries'][phase])
                    assert actual==raw[phase];rotation.compare_state(source[phase],actual)
                rotation.check_result(raw['request'],raw['before'],raw['after'],raw['result'],raw['error'],raw['before_scene'],raw['after_scene'])
                result='defined_numeric_source_comparison'
            elif kind=='scene':
                scene.compare_state(source['before'],raw['before']);scene.compare_state(source['after'],raw['after'])
                result=scene.check_result(source,raw['request'],raw['before'],raw['after'],raw['result'],raw['error'],raw['before_scene'],raw['after_scene'])
            elif kind=='single':
                result=single.compare_output(case,source,raw['before'],raw['after'],raw['result'],raw['error'],raw['request'],raw['before_scene'],raw['after_scene'])['comparison_kind']
            else:result=transform.compare_output(case,source,raw['before'],raw['after'],raw['result'],raw['error'],raw['request'])
            if kind in ['single','transform']:
                for phase in ['before','after']:
                    matrix=copy.deepcopy(source[phase]['objects']['target']['matrix_world'])
                    if kind=='single':
                        for i in range(3):matrix[i][3]*=single.factor(case)
                    tree(matrix,raw['world_queries'][phase]['world_matrix'],'retained actual world query')
        counts[str(result)]+=1
        if (index+1)%500==0:print(json.dumps({'runtime':kind,'audited':index+1}),flush=True)
    assert seen=={(interface,id) for interface in ['cli','official_mcp_sdk'] for id in covered}
    if kind=='transform':
        assert report['defined_deterministic_source_checks']==2344 and report['stochastic_support_checks']==48 and report['approved_source_rejection_checks']==14
    return {'requests':count,'outcomes':dict(counts),'raw_source_comparisons_rechecked':True}


def main():
    for name in ['src','tests','tools','docs/contracts']:
        for p in sorted((ROOT/name).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
            assert subprocess.check_output(['git','show',IMPLEMENTATION+':'+p.relative_to(ROOT).as_posix()],cwd=ROOT)==p.read_bytes(),p
    local=read_json(HERE/'local/commands.json');assert local['implementation_commit']==IMPLEMENTATION and local['binary_sha256']==BINARY
    for name,digest in local['artifacts'].items():assert sha(HERE/'local'/name)==digest
    rows=re.findall(r'test result: ok. (\d+) passed; (\d+) failed; (\d+) ignored;',(HERE/'local/rust.stdout').read_text())
    assert sum(int(r[0]) for r in rows)==263 and all(r[1:]==('0','0') for r in rows)
    text=(HERE/'local/python.stderr').read_text();assert 'Ran 152 tests' in text and text.rstrip().endswith('OK')
    assert local['commands']['strict-metadata']['terminal_exit_code']==2
    metadata=read_json(HERE/'local/metadata.json');assert metadata==read_json(HERE/'local/strict-metadata.json')
    assert metadata['structurally_valid'] and not metadata['baseline_ready'] and not metadata['problems']
    assert not read_json(ROOT/'baseline/inventory.json')['complete_products']
    runtime={kind:audit(kind,n) for kind,n in [('full',4992),('scene',1100),('single',2244),('transform',2406)]}
    assert runtime['full']['outcomes']=={'defined_numeric_source_comparison':4992}
    assert runtime['scene']['outcomes']=={'defined_numeric_source_comparison':1094,'explicit_cancellation':4,'explicit_atomic_rejection':2}
    assert runtime['single']['outcomes']=={'defined_numeric_source_comparison':2072,'explicit_cancellation':136,'explicit_atomic_rejection':36}
    retained=passed(HERE/'retained/report.json');assert retained['verification_inputs_unchanged']
    assert {r['name']:r['actual_checks'] for r in retained['checks']}=={'primitive':162,'scale':8,'selection':1060,'creation':262,'payload':57,'normal':42,'rng':96,'mcp':None}
    assert all(r['passed'] and r['exit_code']==0 for r in retained['checks'])
    assert passed(HERE/'rng-one-shot/report.json')['checks']==48 and len(passed(HERE/'source-oracle/report.json')['cases'])==6
    for folder in ['recipe','recipe-legacy']:
        value=passed(HERE/folder/'report.json');assert value['native_terminal_exit']==value['fresh_process_exit']==0
        for key in ['cursor_only_preserves_recipe','geometry_edit_marks_recipe','failed_batch_preserves_recipe_and_disk','undo_replay_checked','regeneration_restores_original_authored_geometry_and_attributes','fresh_reload_equal']:assert value[key]
    for folder in ['isolation','isolation-scene','isolation-selection','isolation-creation','rng-rotation-isolation','isolation-primitive']:
        value=read_json(HERE/folder/'report.json');key='copied_binary_sha256' if folder=='isolation-primitive' else 'binary_sha256'
        assert value['passed'] and value[key]==BINARY and value['denial_control_exit_code']!=0
        assert 'not permitted' in value['denial_control_stderr'] or 'Permission denied' in value['denial_control_stderr']
    assert passed(HERE/'isolation/report.json')['native_calls']==27
    for folder,pixels in [('gpu',20350),('gpu-rng-legacy',12532),('gpu-mirror-legacy',14302)]:
        value=passed(HERE/folder/'manifest.json');assert '(Metal,' in value['gpu'] and value['changed_pixels']==pixels
        assert (HERE/folder/'after.png').read_bytes()==(HERE/folder/'reloaded.png').read_bytes()
    assert passed(HERE/'gpu/manifest.json')['raw_nonunit_quaternion_preserved']
    for name,count in [('raw-source-comparison-02.json',24),('retained-90-source-comparison-01.json',90),('retained-30-source-comparison-01.json',30)]:
        assert passed(HERE/'performance'/name)['samples']==count
    assert len(passed(HERE/'performance/retained-9-source-comparison-01.json',False)['records'])==9
    failed=read_json(HERE/'performance/diagnostics/raw-01/disposition.json')
    assert failed['timing_passed'] and not failed['source_input_binding_passed'] and not failed['required_full_gate_passed'] and failed['raw_samples_preserved']
    print(json.dumps({'local_evidence_valid':True,'implementation_commit':IMPLEMENTATION,'binary_sha256':BINARY,
        'complete_api_requests':10742,'rust_tests':263,'python_tests':152,'accepted_release_samples':153,
        'invalid_preparation_trial_samples_retained':24,'baseline_ready':False,'three_platform_ci':'unrun',
        'integration':'unrun','independent_codex_acceptance':'unrun','product_acceptance':'unrun','milestones_accepted':0}),flush=True)


if __name__=='__main__':main()
