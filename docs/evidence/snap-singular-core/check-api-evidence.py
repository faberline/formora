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
import delta_snap_runtime as delta
import singular_snap_runtime as singular
import scene_snap_runtime_smoke as scene
import snap_runtime_smoke as single
import transform_runtime_smoke as transform
from runtime_artifacts import read_json
from compare_snap_menu_reference import tree

IMPLEMENTATION='aa2afb53b804d84dc530b6a1c8f5d98fe75d4c97'
BINARY='e31f7db014dc1842a69424c090120cf3ddbb0fa7103d6b968d8c47cde7e2a4fc'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def passed(path,binary=True):
    value=read_json(path);assert value['passed'] is True,path
    if binary:assert value['binary_sha256']==BINARY,path
    return value


def audit(kind,count):
    folder=Path('/private/tmp/formora-zero-retained-api-02')/{'full':'delta','rotation':'raw-rotation','scene':'scene-snap','single':'single-snap','transform':'mesh-transform'}[kind];report=passed(folder/'report.json')
    assert report['checks']==count and report['required_full_gate_passed'] and len(report['runs'])==count
    for name,digest in report['input_hashes'].items():assert sha(ROOT/name)==digest,name
    family={'full':'snap-delta','rotation':'snap-rotation','scene':'snap-menu','single':'snap-menu','transform':'mesh-transform'}[kind]
    suite=read_json(ROOT/'baseline/fixtures'/(family+'.json'));cases={r['id']:r for r in suite['runs']}
    compact={key:value for key,value in suite.items() if key!='runs'}
    module={'full':delta,'rotation':rotation,'scene':scene,'single':single,'transform':transform}[kind]
    covered={id for id,r in cases.items() if kind in ['full','rotation','transform'] or (scene.covered(r) if kind=='scene' else single.covered(r))}
    refs=[ROOT/'baseline/reference/blender-5.2.3'/name for name in [family,family+'-repeat']]
    seen=set();counts=collections.Counter();setup_cache={}
    for index,row in enumerate(report['runs']):
        pair=(row['interface'],row['id']);assert pair not in seen and row['id'] in covered;seen.add(pair)
        assert row['status']=='passed';path=folder/row['file'];assert sha(path)==row['sha256']
        raw=read_json(path);case=cases[row['id']]
        assert raw['case']==case and raw['status']=='passed' and raw['comparison_error'] is None
        if kind!='transform':assert raw['fresh_reload_matches']
        if row['id'] not in setup_cache:setup_cache[row['id']]=module.setup(compact,case)
        assert raw['setup']==setup_cache[row['id']] and raw['request']==(rotation.request_for(case) if kind in ['full','rotation'] else module.request_for(case))
        for ref in refs:
            source=read_json(ref/(row['id']+('.json.gz' if kind in ['full','rotation'] else '.json')))
            if kind in ['full','rotation']:
                for phase in ['before','after']:
                    assert raw[phase+'_scene']==raw['scene_inspections'][phase]['scene']
                    actual=module.snapshot(raw['scene_inspections'][phase],raw['queries'][phase],raw['world_queries'][phase])
                    assert actual==raw[phase];module.compare_state(source[phase],actual)
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



def audit_zero():
    folder=Path('/private/tmp/formora-zero-runtime-full-02');report=passed(folder/'report.json')
    assert report['checks']==3528 and report['required_full_gate_passed'] and len(report['runs'])==3528
    assert report['verification_inputs_unchanged']
    for name,digest in report['input_hashes'].items():assert sha(ROOT/name)==digest,name
    source_checked=report['source_checked']
    assert source_checked['approved_local_query_policy_baseline_passed']
    assert source_checked['cases']==1764 and source_checked['unavailable_local_queries']==12
    assert source_checked['available_numeric_local_queries']==12224
    suite=read_json(ROOT/'baseline/fixtures/snap-singular.json');cases={r['id']:r for r in suite['runs']}
    compact={k:v for k,v in suite.items() if k!='runs'}
    refs=[ROOT/'docs/evidence/snap-singular-baseline'/n for n in ['diagnostic-01','diagnostic-02']]
    seen=set();available=0;unavailable=0
    for index,row in enumerate(report['runs']):
        pair=row['interface'],row['id'];assert pair not in seen and row['id'] in cases;seen.add(pair)
        assert row['status']=='passed';path=folder/row['file'];assert sha(path)==row['sha256']
        raw=read_json(path);case=cases[row['id']]
        assert raw['case']==case and raw['status']=='passed' and raw['comparison_error'] is None and raw['error'] is None
        assert raw['fresh_reload_matches'] and raw['setup']==singular.setup(compact,case)
        assert raw['request']==rotation.request_for(case)
        states={}
        for phase in ['before','after']:
            assert raw[phase+'_scene']==raw['scene_inspections'][phase]['scene']
            actual=singular.snapshot(raw['scene_inspections'][phase],raw['queries'][phase],raw['world_queries'][phase])
            assert actual==raw[phase];states[phase]=actual
            for obj in actual['objects'].values():
                if obj['matrix_local'] is None:
                    assert obj['matrix_local_error']=='cannot_invert';unavailable+=1
                else:
                    assert 'matrix_local_error' not in obj;available+=1
        for ref in refs:
            native=read_json(ref/(row['id']+'.json.gz'))
            singular.compare_state(native['before'],states['before']);singular.compare_state(native['after'],states['after'])
        rotation.check_result(raw['request'],raw['before'],raw['after'],raw['result'],raw['error'],raw['before_scene'],raw['after_scene'])
        if (index+1)%500==0:print(json.dumps({'runtime':'zero','audited':index+1}),flush=True)
    assert seen=={(interface,id) for interface in ['cli','official_mcp_sdk'] for id in cases}
    assert available==24448 and unavailable==24
    return {'requests':3528,'all_physical_cases_checked':True,'available_numeric_local_queries':available,
            'explicit_unavailable_local_queries':unavailable,'unavailable_queries_are_numeric_matches':False,
            'raw_API_snapshot_and_receipt_bindings_checked':True,'both_native_source_processes_checked':True}

def main():
    for name in ['src','tests','tools','docs/contracts']:
        for p in sorted((ROOT/name).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts or p.suffix=='.pyc':continue
            assert subprocess.check_output(['git','show',IMPLEMENTATION+':'+p.relative_to(ROOT).as_posix()],cwd=ROOT)==p.read_bytes(),p
    runtime={kind:audit(kind,n) for kind,n in [('full',3584),('rotation',4992),('scene',1100),('single',2244),('transform',2406)]}
    assert runtime['full']['outcomes']=={'defined_numeric_source_comparison':3584}
    assert runtime['rotation']['outcomes']=={'defined_numeric_source_comparison':4992}
    assert runtime['scene']['outcomes']=={'defined_numeric_source_comparison':1094,'explicit_cancellation':4,'explicit_atomic_rejection':2}
    assert runtime['single']['outcomes']=={'defined_numeric_source_comparison':2072,'explicit_cancellation':136,'explicit_atomic_rejection':36}
    result={'complete_api_evidence_valid':True,'implementation_commit':IMPLEMENTATION,'binary_sha256':BINARY,
        'complete_requests':sum(v['requests'] for v in runtime.values()),'gates':runtime,
        'original_source_rejection_checks_not_numeric_passes':14,'product_acceptance':'unrun',
        'three_platform_ci':'unrun','integration':'unrun','independent_codex_acceptance':'unrun','milestones_accepted':0}
    assert result['complete_requests']==14326
    zero=audit_zero()
    result['zero_scale']=zero
    result['complete_requests']+=zero['requests']
    assert result['complete_requests']==17854
    with Path('/private/tmp/formora-zero-complete-api-evidence-01.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
