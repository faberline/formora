#!/usr/bin/env python3
"""Recheck full raw product records and reject fabricated property evidence."""
import argparse
import copy
import gzip
import json
from pathlib import Path

from compare_object_state_reference import compare, digest
from generate_object_state_cases import author
from object_state_runtime import ROOT, NAMES, check_record
from runtime_artifacts import write_json


def bind_calls(value):
    expected = []
    for phase in ['before', 'after', 'reloaded']:
        if phase == 'after':
            expected.append(('scene_apply', value['request'], value['applied']))
        part = value[phase]
        expected.append(('scene_inspect', {}, {'revision': part['scene']['revision'], 'scene': part['scene']}))
        for name in NAMES:
            expected.append(('scene_inspect', {'entity': name, 'object_state': True}, part['states'][name]))
            expected.append(('scene_inspect', {'entity': name, 'world': True}, part['worlds'][name]))
    assert len(expected) == len(value['calls']) == 34, 'raw call coverage differs'
    for index, ((name, args, result), call) in enumerate(zip(expected, value['calls'])):
        assert call['request'] == args, 'raw request differs'
        if call['interface'] == 'cli':
            assert type(call['process_id']) is int and call['process_id'] > 0
            assert call['terminal_exit_code'] == 0, 'raw CLI terminal failed'
            assert json.loads(call['stdout']) == result, 'raw CLI result differs'
            assert call['command'][1] == 'scene' and call['command'][2] == name.removeprefix('scene_')
        else:
            assert value['interface'] == 'official_mcp_sdk' and index < 23
            assert call['name'] == name and call['response']['isError'] is False
            assert call['response']['structuredContent'] == result, 'raw MCP result differs'
            assert json.loads(call['response']['content'][0]['text']) == result, 'raw MCP text differs'


def verify(output):
    report = json.loads((output/'report.json').read_text())
    suite = author()
    assert report['complete'] is True and report['passed_cases'] == report['required_cases'] == 320
    assert report['product_acceptance'] == 'local_property_matrix_passed_only'
    expected = [(interface, run['id']) for interface in ['cli', 'official_mcp_sdk'] for run in suite['runs']]
    assert [(r['interface'], r['id']) for r in report['records']] == expected, 'missing/duplicate product cases'
    folders = [ROOT/'docs/evidence/object-state-query'/name for name in ['native-02', 'native-03']]
    source = compare(ROOT/'baseline/fixtures/object-state.json', *folders)
    # JSON stores the validator's observed mode tuples as arrays.
    assert json.loads(json.dumps(source)) == report['source_gate']
    assert report['inputs'] == {name: digest(ROOT/name) for name in report['inputs']}, 'runtime input drift'
    for row, (_, id) in zip(report['records'], expected):
        path = output/row['path']
        assert row['sha256'] == digest(path), 'raw product record changed'
        value = json.loads(gzip.decompress(path.read_bytes()))
        run = next(r for r in suite['runs'] if r['id'] == id)
        references = [json.loads((f/(id+'.json')).read_text()) for f in folders]
        bind_calls(value)
        check_record(suite, run, value, references)
        assert json.loads((path.parent/'scene.json').read_text()) == value['saved_after']
        if value['interface'] == 'official_mcp_sdk':
            assert value['initialize']['protocolVersion'] == '2025-11-25'
            process = value['mcp_process']
            assert process['started'] == json.loads((path.parent/'mcp-process/started.json').read_text())
            assert process['terminal'] == json.loads((path.parent/'mcp-process/terminal.json').read_text())
            assert process['started']['binary_sha256'] == report['binary_sha256']
            assert process['started']['process_id'] == process['terminal']['process_id']
            assert process['terminal']['terminal_exit_code'] == 0
            assert process['terminal']['stderr_sha256'] == digest(path.parent/'mcp-process/stderr')
    return report, suite, folders


def controls(output, suite, folders):
    path = output/'cli/object_state_001/record.json.gz'
    original = json.loads(gzip.decompress(path.read_bytes()))
    original_hash = digest(path)
    run = suite['runs'][1]
    references = [json.loads((f/(run['id']+'.json')).read_text()) for f in folders]
    rows = []

    def reject(name, mutate, reason, checker):
        value = copy.deepcopy(original)
        mutate(value)
        try:
            checker(value)
        except (AssertionError, KeyError, ValueError) as error:
            assert reason in str(error), (name, reason, str(error))
            rows.append({'control': name, 'rejected': True, 'error': str(error)})
        else:
            raise AssertionError('forged product record admitted: '+name)

    semantic = lambda v: check_record(suite, run, v, references)
    reject('missing_query_value', lambda v: v['after']['states']['parent']['object_state'].pop('lock_scale'),
           'lock_scale', semantic)
    reject('fabricated_query_value', lambda v: v['after']['states']['parent']['object_state'].update(lock_scale=[True, False, False]),
           'real saved state', semantic)
    reject('numeric_query_value', lambda v: v['after']['states']['parent']['object_state'].update(lock_scale=[0, 0, 0]),
           'invalid scale lock', semantic)
    reject('wrong_saved_value', lambda v: v['saved_after']['object_context']['states']['parent'].update(lock_scale=[True, False, False]),
           '', semantic)
    reject('missing_raw_call', lambda v: v['calls'].pop(), 'coverage differs', bind_calls)
    reject('failed_raw_cli_terminal', lambda v: v['calls'][0].update(terminal_exit_code=1), 'terminal failed', bind_calls)
    reject('fabricated_raw_cli_result', lambda v: v['calls'][0].update(stdout='{}'), 'result differs', bind_calls)
    reject('wrong_raw_request', lambda v: v['calls'][0].update(request={'entity': 'alias'}), 'request differs', bind_calls)
    assert digest(path) == original_hash
    return {'negative_controls_passed': True, 'controls': len(rows), 'rows': rows,
            'forged_operations_executed': False, 'original_record_unchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report, suite, folders = verify(args.capture.resolve())
    result = {'raw_records_verified': 320, 'source_and_product_gate_passed': True,
              'raw_calls_bound': 320*34, 'report_sha256': digest(args.capture/'report.json'),
              'negative_controls': controls(args.capture.resolve(), suite, folders),
              'ci_integration_and_independent_acceptance': 'pending'}
    write_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'negative_controls'}))
