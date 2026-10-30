"""Recheck every retained asset record against fixed source data and limits."""
from pathlib import Path
import copy
import hashlib
import json
import sys

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
sys.path.insert(0, str(ROOT/'tools'))
from compare_mesh_reference import compare
from primitive_reference_smoke import KINDS, BOUNDARIES, GEOMETRY
from selection_runtime_smoke import canonical_comparison
from creation_context_runtime import request_for
import normal_runtime_smoke as normal
import random_falloff_runtime as rng
from random_falloff_reference import SEEDS

DATA = Path('/private/tmp/formora-multi-merge-retained-api-01')
OUT = Path('/private/tmp/formora-multi-merge-asset-audit-01.json')
EXPECTED = '64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
load = lambda p: json.loads(Path(p).read_text())
rows = []
controls = []
examples = {}


def report(family, filename='report.json'):
    value = load(DATA/family/filename)
    assert value['passed'] and value['binary_sha256'] == EXPECTED
    for key in ['source_files_sha256', 'adapter_files_sha256', 'capture_inputs_sha256', 'input_hashes']:
        if key in value:
            assert value[key] == {name: sha(ROOT/name) for name in value[key]}, (family, key, 'input drift')
    return value


def record(family, row, hash_key='sha256'):
    path = DATA/family/row['file']
    assert path.parent == DATA/family and sha(path) == row[hash_key], (family, row, 'raw digest differs')
    return load(path)


def coverage(records, expected):
    assert [(r['interface'], r['id']) for r in records] == expected, 'missing/duplicate asset coverage'
    assert all(r.get('status', 'passed') == 'passed' and r.get('error') is None for r in records)


primitive_suite = load(ROOT/'baseline/fixtures/mesh-primitives.json')
context_suite = load(ROOT/'baseline/fixtures/mesh-creation-contexts.json')
primitive_cases = [(r, ROOT/'baseline/reference/blender-5.2.3/mesh-primitives', primitive_suite['comparison'], False)
                   for r in primitive_suite['runs'] if r['operator'] in KINDS]
primitive_cases += [(r, ROOT/'baseline/reference/blender-5.2.3/mesh-contexts', context_suite['comparison'], True)
                    for r in context_suite['runs'] if r['id'] in BOUNDARIES]
r = report('primitive')
assert len(primitive_cases) == 81 and len(r['runs']) == 162
coverage(r['runs'], [(interface, case['id']) for interface in ['cli', 'mcp'] for case, _, _, _ in primitive_cases])
cases = {case['id']: (folder, limits, boundary) for case, folder, limits, boundary in primitive_cases}
for row in r['runs']:
    value = record('primitive', row, 'candidate_sha256')
    folder, limits, boundary = cases[row['id']]
    source_path = folder/(row['id']+'.json')
    assert sha(source_path) == row['reference_sha256']
    source = load(source_path)
    source = {k: source[k] for k in GEOMETRY} if boundary else source
    result = compare(source, value, limits)
    if boundary:
        assert 'creation_attributes_match_reference' not in result
    assert row['generated_recipe']['edited'] is False
    if 'primitive' not in examples:
        examples['primitive'] = (value, lambda candidate, source=source, limits=limits: compare(source, candidate, limits))
rows.append({'family': 'primitive', 'checks': 162, 'scope': 'geometry and recorded recipe; full contexts unrun'})

r = report('scale')
required = {kind+'_'+scale for kind in ['ico_sphere', 'monkey'] for scale in ['negative_scale', 'zero_axis_scale']}
cases = [case for case in context_suite['runs'] if case['id'] in required]
coverage(r['runs'], [(interface, case['id']) for interface in ['cli', 'mcp'] for case in cases])
assert r['checks'] == len(r['runs']) == 8
for row in r['runs']:
    source_path = ROOT/'baseline/reference/blender-5.2.3/mesh-contexts'/(row['id']+'.json')
    assert sha(source_path) == row['source_sha256']
    source = load(source_path)
    source = {k: source[k] for k in GEOMETRY}
    value = record('scale', row, 'candidate_sha256')
    result = compare(source, value, context_suite['comparison'])
    assert 'creation_attributes_match_reference' not in result
    if 'scale' not in examples:
        examples['scale'] = (value, lambda candidate, source=source: compare(source, candidate, context_suite['comparison']))
rows.append({'family': 'scale', 'checks': 8, 'scope': 'additional geometry-only scale cases'})

r = report('payload')
assert len(r['runs']) == len(primitive_suite['runs']) == 57
assert [row['id'] for row in r['runs']] == [case['id'] for case in primitive_suite['runs']]
assert r['suite_sha256'] == sha(ROOT/'baseline/fixtures/mesh-primitives.json')
for row in r['runs']:
    source_path = ROOT/'baseline/reference/blender-5.2.3/mesh-primitives'/(row['id']+'.json')
    assert sha(source_path) == row['source_sha256']
    source = load(source_path)
    value = load(DATA/'payload'/(row['id']+'.json'))
    assert sha(DATA/'payload'/(row['id']+'.json')) == row['candidate_sha256']
    assert len(value['triangles']) == row['tessellated_triangles'] == len(source['triangles'])
    compare(source, value, primitive_suite['comparison'])
    if 'payload' not in examples:
        examples['payload'] = (value, lambda candidate, source=source: compare(source, candidate, primitive_suite['comparison']))
rows.append({'family': 'payload', 'checks': 57, 'scope': 'reference payload storage and tessellation; not generation'})

r = report('selection')
suite = load(ROOT/'baseline/fixtures/mesh-selection.json')
assert r['required_full_interfaces'] and r['checks'] == len(r['runs']) == 1060
coverage(r['runs'], [(interface, case['id']) for interface in ['cli', 'official_mcp_sdk'] for case in suite['runs']])
for row in r['runs']:
    value = record('selection', row)
    source = load(ROOT/'baseline/reference/blender-5.2.3/mesh-selection'/(row['id']+'.json'))
    canonical_comparison(source, value)
    assert row['reload_checked'] and row['undo_checked']
    if 'selection' not in examples:
        examples['selection'] = (value, lambda candidate, source=source: canonical_comparison(source, candidate))
rows.append({'family': 'selection', 'checks': 1060, 'scope': 'full authored selection cases on both interfaces'})

r = report('creation')
assert r['checks'] == len(r['runs']) == 262 and r['scope'] == 'full_131_contexts_both_interfaces'
coverage(r['runs'], [(interface, case['id']) for interface in ['cli', 'official_mcp_sdk'] for case in context_suite['runs']])
by_id = {case['id']: case for case in context_suite['runs']}
for row in r['runs']:
    value = record('creation', row)
    source_path = ROOT/'baseline/reference/blender-5.2.3/mesh-contexts'/(row['id']+'.json')
    assert sha(source_path) == row['reference_sha256']
    source = load(source_path)
    assert value['observed_request'] == request_for(by_id[row['id']])
    assert value['editability_checked'] and value['undo_checked'] and value['reload_checked']
    compare(source, value, context_suite['comparison'])
    if 'creation' not in examples:
        examples['creation'] = (value, lambda candidate, source=source: compare(source, candidate, context_suite['comparison']))
rows.append({'family': 'creation', 'checks': 262, 'scope': '131 authored creation contexts; full numeric domains unrun'})

r = report('normal', 'manifest.json')
suite = normal.author()
refs = normal.load_reference(ROOT, suite)
assert r['cases'] == len(r['records']) == 42
coverage(r['records'], [(interface, case['id']) for interface in ['cli', 'official_mcp_sdk'] for case in suite['cases']])
by_id = {case['id']: case for case in suite['cases']}
for row in r['records']:
    value = record('normal', row)
    case = by_id[row['id']]
    assert value['asset'] == normal.asset_from_case(case) and value['passed']
    result = normal.compare(case, refs[row['id']], value['query'])
    assert result['components'] == row['components'] and result['maximum_absolute_error'] == row['maximum_absolute_error']
    if 'normal' not in examples:
        examples['normal'] = (value, lambda candidate, case=case, ref=refs[row['id']]: normal.compare(case, ref, candidate['query']))
rows.append({'family': 'normal', 'checks': 42, 'scope': 'automatic normal queries; full custom normals unrun'})

r = report('rng')
assert r['checks'] == len(r['records']) == 96
cases = [(seed, 'blender_5_2', connected, projected) for seed in SEEDS
         for connected, projected in [(False, False), (True, False), (False, True), (True, True)]]
cases += [(seed, algorithm, False, False) for seed in [0, 4294967295, 4294967296, (1 << 64)-1]
          for algorithm in [None, 'splitmix64_v1']]
assert [(row['interface'], row['case']) for row in r['records']] == [(interface, list(case))
    for interface in ['cli', 'official_mcp_sdk'] for case in cases]
reference = (ROOT/'baseline/reference/blender-5.2.3/random-falloff/first-sequence.bin').read_bytes()


def random_check(value, case):
    assert value['passed'] and value['setup'] == rng.setup()
    assert value['request'] == {'expected_revision': 1, 'commands': [rng.operation(*case)]}
    weights = rng.expected_weights(case, reference)
    receipt = value['result']['transforms'][0]
    assert receipt['influence'] == weights and receipt['shared_instances'] == ['instance', 'target']
    asset = copy.deepcopy(value['before']['scene']['mesh_assets']['mesh'])
    for name, weight in weights.items():
        asset['vertices'][name][2] = rng.f32(asset['vertices'][name][2]+weight)
    assert value['after']['scene']['mesh_assets']['mesh'] == asset
    assert value['after']['scene']['entities'] == value['before']['scene']['entities']
    assert set(receipt['changed']['vertices']) == set(weights)
    for row in value['rejected_requests']:
        command = row['command']
        if command['transform']['change']['kind'] == 'rotate':
            assert row['error'] == rng.UNDEFINED_ROTATION_ERROR


for row in r['records']:
    value = record('rng', row)
    case = tuple(row['case'])
    random_check(value, case)
    if 'rng' not in examples:
        examples['rng'] = (value, lambda candidate, case=case: random_check(candidate, case))
rows.append({'family': 'rng', 'checks': 96, 'scope': 'versioned sequence, actual weights and approved rotation rejection'})

for family, (original, check) in examples.items():
    value = copy.deepcopy(original)
    if family in ['primitive', 'scale', 'payload', 'creation']:
        value['vertices'][0][0] += 99.
    elif family == 'selection':
        value['after']['selected']['VERT'].append('invented')
    elif family == 'normal':
        value['query']['normals']['faces'][0]['normal'][0] += 99.
    else:
        value['after']['scene']['mesh_assets']['mesh']['vertices']['a_selected'][2] += 99.
    try:
        check(value)
    except (AssertionError, KeyError, ValueError) as error:
        controls.append({'family': family, 'forged_result_rejected': True, 'error': str(error) or type(error).__name__})
    else:
        raise AssertionError('corrupted asset admitted: '+family)
assert sum(row['checks'] for row in rows) == 1687 and len(controls) == 7
assert sha('/private/tmp/formora-multi-merge-target-actual185/debug/formora') == EXPECTED
with OUT.open('x') as f:
    json.dump({'passed': True, 'checks': 1687, 'families': rows, 'forged_result_controls': controls,
        'all_original_limits_and_scopes_retained': True, 'forged_operations_executed': False,
        'binary_sha256': EXPECTED, 'audit_driver_sha256': sha(__file__),
        'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}, f, indent=2)
    f.write('\n')
print(json.dumps({'asset_raw_checks_passed': True, 'checks': 1687, 'families': 7, 'forged_results_rejected': 7}))
