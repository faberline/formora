"""Audit raw multi-data recipe exchanges, numeric results and regeneration."""
from pathlib import Path
import copy
import gzip
import hashlib
import json
import sys

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
sys.path.insert(0, str(ROOT/'tools'))
from multi_mesh_merge_runtime_check import aggregate_receipt

DATA = Path('/private/tmp/formora-multi-merge-recipes-01')
OUT = Path('/private/tmp/formora-multi-merge-recipe-audit-01.json')
BINARY = Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
report = json.loads((DATA/'report.json').read_text())
expected = [(interface, method, uvs) for interface in ['native_cli_server', 'official_mcp_sdk']
            for method in ['center', 'cursor', 'collapse', 'first', 'last'] for uvs in [False, True]]


def header(value):
    assert value['passed'] is True and value['cases'] == value['required_cases'] == 20
    assert value['negative_atomic_controls'] == 120 and value['noop_requests'] == 20
    assert [(r['interface'], r['method'], r['uvs']) for r in value['records']] == expected
    assert all(r['passed'] is True for r in value['records'])
    assert value['inputs_unchanged'] is True and sha(BINARY) == value['binary_sha256']


def shifted(value, revision):
    result = copy.deepcopy(value)
    result['revision'] = revision
    return result


def check(value):
    assert value['passed'] and value['fresh_reload_equal']
    method, uvs = value['method'], value['uvs']
    assert len(value['calls']) == 30
    responses, requests = [], []
    for index, call in enumerate(value['calls']):
        if value['interface'] == 'native_cli_server':
            request = json.loads(call['request_bytes'])
            response = json.loads(call['response_bytes'])
            assert request['id'] == response['id'] == index+1
            requests.append((request['name'], request['arguments']))
            responses.append((response.get('result'), None) if response['ok'] else (None, response['error']))
        else:
            response = call['response']
            requests.append((call['name'], call['request']))
            if response['isError']:
                assert response['structuredContent'] is None
                responses.append((None, response['content'][0]['text']))
            else:
                assert json.loads(response['content'][0]['text']) == response['structuredContent']
                responses.append((response['structuredContent'], None))
    assert [i for i, (_, error) in enumerate(responses) if error is not None] == list(range(6, 18, 2))
    assert len(value['rejected']) == 6
    for row, index in zip(value['rejected'], range(6, 18, 2)):
        assert row['error'] == responses[index][1]
    generated, before, after, regenerated, final = [value[k] for k in ['generated', 'before', 'after', 'regenerated', 'final']]
    scenes = {1: generated, 3: shifted(generated, 2), 5: before, 19: after,
              21: shifted(before, 5), 23: shifted(after, 6), 25: regenerated,
              27: shifted(after, 8), 29: final}
    scenes.update({i: before for i in range(7, 18, 2)})
    for index, scene in scenes.items():
        assert requests[index] == ('scene_inspect', {})
        assert responses[index] == ({'revision': scene['revision'], 'scene': scene}, None), 'raw scene response differs'
    assert responses[2] == (value['noop'], None)
    assert requests[2] == ('scene_apply', {'expected_revision': 1, 'commands': [
        {'operation': 'merge_edit_meshes', 'merge': {'method': 'center', 'uvs': uvs}}]})
    assert all(p['outcome'] == 'skipped_empty_selection' and p['merge'] is None
               for p in value['noop']['edit_merges'][0]['providers'])
    assert responses[18] == (value['primary'], None) and responses[22] == (value['replay'], None)
    for index, revision in [(18, 3), (22, 5)]:
        assert requests[index] == ('scene_apply', {'expected_revision': revision, 'commands': [
            {'operation': 'merge_edit_meshes', 'merge': {'method': method, 'uvs': uvs}}]})
    assert value['primary']['edit_merges'] == value['replay']['edit_merges']
    assert requests[0][0] == 'scene_apply' and requests[0][1]['expected_revision'] == 0
    primitives = [c for c in requests[0][1]['commands'] if c['operation'] == 'create_mesh_primitive']
    assert primitives == [{'operation': 'create_mesh_primitive', 'id': data,
                           'primitive': {'kind': 'cube', 'size': size}}
                          for data, size in [('mesh_a', 1.75), ('mesh_b', 2.25)]]
    suite = {'contexts': [{'id': 'recipe', 'active': 'alias', 'order': ['a', 'b', 'alias']}],
             'data_sharing': {'a': 'mesh_a', 'alias': 'mesh_a', 'b': 'mesh_b'}}
    run = {'context': 'recipe', 'selection': 'both', 'parameters': {'type': method.upper(), 'uvs': uvs}}
    aggregate_receipt(suite, run, before, after, value['primary'])
    for key in set(before)-{'revision', 'mesh_assets'}:
        assert before[key] == after[key]
    affected = ['mesh_a'] if method in ['first', 'last'] else ['mesh_a', 'mesh_b']
    for data in ['mesh_a', 'mesh_b']:
        original = before['mesh_assets'][data]
        actual = after['mesh_assets'][data]
        assert original['recipe']['edited'] is False
        if data not in affected:
            assert actual == original
            continue
        assert actual['recipe']['edited'] is True and len(actual['vertices']) == 1
        if method in ['center', 'collapse']:
            point = [0., 0., 0.]
        elif method == 'cursor':
            point = {'mesh_a': [2.25, 5.25, -.125], 'mesh_b': [3.5, .25, 2.75]}[data]
        else:
            id = original['editing']['history'][0 if method == 'first' else -1]['id']
            point = original['vertices'][id]
        assert list(actual['vertices'].values()) == [point], 'analytic merged point differs'
    wanted = copy.deepcopy(generated['mesh_assets'])
    for data in ['mesh_a', 'mesh_b']:
        wanted[data]['editing'] = {'mode': ['vertex'], 'selected': {'vertices': [], 'edges': [], 'faces': []},
            'hidden': {'vertices': [], 'edges': [], 'faces': []}, 'history': [], 'active_face': None, 'preview': False}
    assert regenerated['mesh_assets'] == final['mesh_assets'] == wanted
    assert regenerated['object_context'] == final['object_context'] == before['object_context']
    for row in value['cli_processes']:
        assert row['terminal_exit_code'] == 0
    assert json.loads(value['cli_processes'][-1]['stdout']) == {'revision': final['revision'], 'scene': final}


header(report)
assert report['input_hashes'] == {name: sha(ROOT/name) for name in report['input_hashes']}
records = []
for row in report['records']:
    path = DATA/row['file']
    assert sha(path) == row['sha256']
    value = json.loads(gzip.decompress(path.read_bytes()))
    assert (value['interface'], value['method'], value['uvs']) == (row['interface'], row['method'], row['uvs'])
    check(value)
    assert json.loads((path.parent/'scene.json').read_text()) == value['final']
    receipt = path.parent/('mcp-process' if row['interface'] == 'official_mcp_sdk' else '')
    started = json.loads((receipt/'started.json').read_text())
    terminal = json.loads((receipt/'terminal.json').read_text())
    assert started['process_id'] == terminal['process_id'] and terminal['terminal_exit_code'] == 0
    records.append(row)
controls = []
base = json.loads(gzip.decompress((DATA/records[-1]['file']).read_bytes()))
for name, mutate in [
    ('missing_raw_call', lambda v: v['calls'].pop()),
    ('false_query_scene', lambda v: v['after']['mesh_assets']['mesh_a']['vertices'].update(invented=[0., 0., 0.])),
    ('false_recipe_state', lambda v: v['after']['mesh_assets']['mesh_a']['recipe'].update(edited=False)),
    ('false_regeneration', lambda v: v['regenerated']['mesh_assets']['mesh_a']['vertices'].update(invented=[0., 0., 0.])),
    ('forged_raw_result', lambda v: v['calls'][1]['response'].update(structuredContent={})),
    ('wrong_operation', lambda v: v['calls'][18]['request']['commands'][0]['merge'].update(method='center')),
]:
    value = copy.deepcopy(base)
    mutate(value)
    try:
        check(value)
    except (AssertionError, KeyError, ValueError) as error:
        controls.append({'control': name, 'rejected': True, 'error': str(error) or type(error).__name__})
    else:
        raise AssertionError('forged recipe evidence admitted: '+name)
assert sha(DATA/records[-1]['file']) == records[-1]['sha256']
result = {'passed': True, 'records': 20, 'raw_calls_bound': 600, 'negative_atomic_controls': 120,
    'corrupted_evidence_controls': controls, 'actual_terminal_receipts_verified': 20,
    'analytic_two_data_points_checked': True, 'recipe_regeneration_and_undo_replay_checked': True,
    'report_sha256': sha(DATA/'report.json'), 'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}
with OUT.open('x') as f:
    json.dump(result, f, indent=2)
    f.write('\n')
print(json.dumps({k: v for k, v in result.items() if k != 'corrupted_evidence_controls'}))
