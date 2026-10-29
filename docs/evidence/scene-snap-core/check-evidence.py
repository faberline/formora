#!/usr/bin/env python3
"""Audit archived local evidence. This does not grant product acceptance."""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
import scene_snap_runtime_smoke as scene_snap
import snap_runtime_smoke as single_snap
import transform_runtime_smoke as transform
from compare_snap_menu_reference import tree
from runtime_artifacts import read_json

IMPLEMENTATION='dcb484218708959ac28b4a1ac79d5ef8b4156a02'
BINARY='896fdd2583d684a1170e95fd4475351f7da254a9044d0174a5fb67eed840d1d5'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def passed(path,binary=True):
    value=read_json(path);assert value['passed'] is True,path
    if binary:assert value['binary_sha256']==BINARY,path
    return value


def audit_runtime(kind,count):
    directory=HERE/('runtime-'+kind);report=passed(directory/'report.json')
    assert report['checks']==count and report['required_full_gate_passed'] and len(report['runs'])==count
    for name,digest in report['input_hashes'].items():assert sha(ROOT/name)==digest,name
    suite_name='mesh-transform.json' if kind=='transform' else 'snap-menu.json'
    suite=read_json(ROOT/'baseline/fixtures'/suite_name);cases={r['id']:r for r in suite['runs']}
    folder='mesh-transform' if kind=='transform' else 'snap-menu'
    references=[ROOT/'baseline/reference/blender-5.2.3'/name for name in [folder,folder+'-repeat']]
    covered=set(cases) if kind=='transform' else {id for id,r in cases.items() if (scene_snap.covered(r) if kind=='full' else single_snap.covered(r))}
    counts=collections.Counter();seen=set()
    for index,entry in enumerate(report['runs']):
        pair=(entry['interface'],entry['id']);assert pair not in seen;seen.add(pair)
        assert entry['status']=='passed' and entry['id'] in covered
        path=directory/entry['file'];assert sha(path)==entry['sha256'];raw=read_json(path);case=cases[entry['id']]
        assert raw['case']==case and raw['status']=='passed' and raw['comparison_error'] is None
        module=scene_snap if kind=='full' else single_snap if kind=='single' else transform
        assert raw['setup']==module.setup(suite,case) and raw['request']==module.request_for(case)
        for reference in references:
            source=read_json(reference/(case['id']+'.json'))
            if kind=='full':
                scene_snap.compare_state(source['before'],raw['before']);scene_snap.compare_state(source['after'],raw['after'])
                result=scene_snap.check_result(source,raw['request'],raw['before'],raw['after'],raw['result'],raw['error'],raw['before_scene'],raw['after_scene'])
            elif kind=='single':
                result=single_snap.compare_output(case,source,raw['before'],raw['after'],raw['result'],raw['error'],raw['request'],raw['before_scene'],raw['after_scene'])['comparison_kind']
            else:
                result=transform.compare_output(case,source,raw['before'],raw['after'],raw['result'],raw['error'],raw['request'])
            if kind!='full':
                for phase in ['before','after']:
                    matrix=copy.deepcopy(source[phase]['objects']['target']['matrix_world'])
                    if kind=='single':
                        for i in range(3):matrix[i][3]*=single_snap.factor(case)
                    tree(matrix,raw['world_queries'][phase]['world_matrix'],kind+'/'+phase+'/world frame')
        counts[str(result)]+=1
        if (index+1)%500==0:print(json.dumps({'runtime':kind,'audited':index+1}),flush=True)
    assert seen=={(interface,id) for interface in ['cli','official_mcp_sdk'] for id in covered}
    return {'checks':count,'outcomes':dict(counts),'raw_source_comparisons_rechecked':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=Path);args=parser.parse_args()
    if args.binary:assert sha(args.binary)==BINARY
    for folder in ['src','tests','tools','docs/contracts']:
        for p in sorted((ROOT/folder).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
            relative=p.relative_to(ROOT).as_posix()
            assert subprocess.check_output(['git','show',IMPLEMENTATION+':'+relative],cwd=ROOT)==p.read_bytes(),relative
    local=read_json(HERE/'local/commands.json');assert local['implementation_commit']==IMPLEMENTATION and local['binary_sha256']==BINARY
    for name,digest in local['artifacts'].items():assert sha(HERE/'local'/name)==digest
    rust=(HERE/'local/rust.stdout').read_text();rows=re.findall(r'test result: ok. (\d+) passed; (\d+) failed; (\d+) ignored;',rust)
    assert sum(int(r[0]) for r in rows)==250 and all(r[1:]==('0','0') for r in rows)
    python=(HERE/'local/python.stderr').read_text();assert 'Ran 118 tests' in python and python.rstrip().endswith('OK')
    assert not (HERE/'local/format.stderr').read_bytes()
    assert 'Finished' in (HERE/'local/clippy.stderr').read_text() and 'error:' not in (HERE/'local/clippy.stderr').read_text()
    metadata=read_json(HERE/'local/metadata.json');strict=read_json(HERE/'local/strict-metadata-02.json')
    assert metadata==strict and metadata['structurally_valid'] and not metadata['baseline_ready'] and not metadata['problems']
    assert not read_json(ROOT/'baseline/inventory.json')['complete_products']
    runtime={name:audit_runtime(name,count) for name,count in [('full',1100),('single',2244),('transform',2406)]}
    assert runtime['full']['outcomes']=={'defined_numeric_source_comparison':1094,'explicit_cancellation':4,'explicit_atomic_rejection':2}
    assert runtime['single']['outcomes']=={'defined_numeric_source_comparison':2072,'explicit_cancellation':136,'explicit_atomic_rejection':36}
    retained=passed(HERE/'retained/report.json');assert retained['verification_inputs_unchanged']
    assert {r['name']:r['actual_checks'] for r in retained['checks']}=={'primitive':162,'scale':8,'selection':1060,'creation':262,'payload':57,'normal':42,'rng':96,'mcp':None}
    assert all(r['passed'] and r['exit_code']==0 for r in retained['checks'])
    assert passed(HERE/'rng-one-shot/report.json')['checks']==48
    assert len(passed(HERE/'source-oracle/report.json')['cases'])==6
    for folder in ['recipe','recipe-legacy']:
        value=passed(HERE/folder/'report.json');assert value['native_terminal_exit']==value['fresh_process_exit']==0
        assert value['cursor_only_preserves_recipe'] and value['geometry_edit_marks_recipe'] and value['failed_batch_preserves_recipe_and_disk']
        assert value['undo_replay_checked'] and value['regeneration_restores_original_authored_geometry_and_attributes'] and value['fresh_reload_equal']
    isolation=passed(HERE/'isolation/report.json');assert isolation['native_calls']==25 and isolation['native_terminal_exit']==isolation['fresh_process_exit']==0
    assert isolation['denial_control_exit_code']!=0 and isolation['fresh_reload_equal'] and isolation['cursor_rotation_exactly_preserved']
    for folder in ['isolation-primitive','isolation-selection','isolation-creation','rng-rotation-isolation']:
        value=read_json(HERE/folder/'report.json')
        field='copied_binary_sha256' if folder=='isolation-primitive' else 'binary_sha256'
        assert value[field]==BINARY and value.get('passed',True) is True and value['denial_control_exit_code']!=0
        assert 'not permitted' in value['denial_control_stderr'] or 'Permission denied' in value['denial_control_stderr']
    for folder,vertices,pixels in [('gpu',25,6860),('gpu-rng-legacy',18,12532),('gpu-mirror-legacy',15,14302)]:
        value=passed(HERE/folder/'manifest.json');assert '(Metal,' in value['gpu'] and value['changed_vertices']==vertices and value['changed_pixels']==pixels
        assert (HERE/folder/'after.png').read_bytes()==(HERE/folder/'reloaded.png').read_bytes()
    perf=passed(HERE/'performance/source-comparison-10.json');assert perf['required_full_gate_passed'] and not perf['diagnostic_failed_timings'] and perf['samples']==90
    assert all(r['passed'] and r['source_match'] for r in perf['runs'])
    controller=read_json(HERE/'performance/one-process-10/controller-report.json');assert controller['passed'] and controller['terminal_exit_code']==0 and controller['verification_inputs_unchanged']
    for row in controller['groups']:
        path=HERE/'performance/one-process-10/samples'/row['report'];assert sha(path)==row['report_sha256']
        for r in read_json(path)['runs']:
            assert r['maximum_core_ms']==(500 if row['class']=='C' else 250) and r['maximum_pipeline_ms']==(4000 if row['class']=='C' else 2000)
            assert r['passed'] and r['core_ms']<=r['maximum_core_ms'] and r['operation_save_reload_ms']<=r['maximum_pipeline_ms']
    assert passed(HERE/'performance/retained-single-source-comparison.json')['samples']==30
    assert len(passed(HERE/'legacy-performance/source-comparison-report.json',False)['records'])==9
    old=read_json(HERE/'performance/fixed-controller-report.json');new=read_json(HERE/'performance/fixed-controller-report-09.json')
    assert not old['passed'] and not new['passed']
    diagnostic=read_json(HERE/'performance/source-comparison-diagnostic-09.json');assert not diagnostic['passed'] and not diagnostic['required_full_gate_passed'] and diagnostic['source_comparisons_passed']
    archive=read_json(HERE/'performance/final-samples-scenes-07-archive.json');path=HERE/'performance'/archive['archive']
    assert sha(path)==archive['archive_sha256'] and archive['exact_byte_round_trip'] and not archive['raw_copies_removed']
    with zipfile.ZipFile(path) as z:
        assert len(z.namelist())==90
        for row in archive['files']:
            raw=z.read(row['file']);assert hashlib.sha256(raw).hexdigest()==row['raw_sha256'] and len(raw)==row['raw_bytes']
            assert raw==(HERE/'performance/final-samples'/row['file']).read_bytes()
    print(json.dumps({'local_evidence_valid':True,'implementation_commit':IMPLEMENTATION,'runtime_checks':5750,'rust_tests':250,'python_tests':118,
        'new_performance_samples':90,'retained_performance_samples':39,'baseline_ready':False,'milestones_accepted':0,
        'required_cross_platform_ci':'unrun','integration':'unrun','independent_codex_acceptance':'unrun','product_acceptance':'unrun'}),flush=True)


if __name__=='__main__':main()
