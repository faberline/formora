"""Recheck complete local evidence without granting integration or acceptance."""
import collections
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
import rotation_snap_runtime as rotation
import delta_snap_runtime as delta
import scene_snap_runtime_smoke as scene
import snap_runtime_smoke as single
import transform_runtime_smoke as transform
from runtime_artifacts import read_json
from compare_snap_menu_reference import tree

IMPLEMENTATION='5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d'
BINARY='0e882777416ca728e55ca7212259d1b65a1bc6703706ded440bd822b7e70d2aa'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def passed(path,binary=True):
    value=read_json(path);assert value['passed'] is True,path
    if binary:assert value['binary_sha256']==BINARY,path
    return value


def audit(kind,count):
    folder=Path('/private/tmp/formora-merge-regen-retained-api-01')/{'full':'delta','rotation':'raw-rotation','scene':'scene-snap','single':'single-snap','transform':'mesh-transform'}[kind];report=passed(folder/'report.json')
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


