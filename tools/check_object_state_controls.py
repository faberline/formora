#!/usr/bin/env python3
"""Reject corrupted source records. Never execute a forged operation."""
import argparse
import copy
import json
from pathlib import Path

from compare_object_state_reference import validate_run, load_capture, digest
from generate_object_state_cases import author


def check(suite_path, folder, output):
    suite = json.loads(suite_path.read_text())
    assert suite == author()
    manifest = load_capture(folder, suite_path, suite)
    run = suite['runs'][1]
    original = json.loads((folder/(run['id']+'.json')).read_text())
    validate_run(suite, run, original)
    rows = []

    def reject(name, mutate, reason):
        value = copy.deepcopy(original)
        mutate(value)
        try:
            validate_run(suite, run, value)
        except (AssertionError, ValueError, KeyError) as error:
            assert reason in str(error), (name, reason, str(error))
            rows.append({'control': name, 'rejected': True, 'error': str(error)})
        else:
            raise AssertionError('forged source passed: '+name)

    def wrong_value(value):
        value['after']['objects'][run['target']]['lock_scale'][0] ^= True

    def wrong_other(value):
        value['after']['objects']['alias']['lock_scale'][0] ^= True

    reject('wrong_assigned_value', wrong_value, 'authored boolean value')
    reject('shared_user_state_conflated', wrong_other, 'authored boolean value')
    reject('lost_saved_value', lambda v: v['reloaded']['objects'][run['target']]['lock_scale'].__setitem__(0, True),
           'authored boolean value')
    reject('geometry_changed', lambda v: v['after']['objects']['a']['geometry_counts'].__setitem__(0, 1),
           'source geometry changed')
    reject('frame_changed', lambda v: v['after']['objects']['a']['matrix_world'][0].__setitem__(3, 99.),
           'authored world')
    reject('sharing_changed', lambda v: v['reloaded'].update(sharing=[['a'], ['alias'], ['b'], ['untouched']]),
           'source sharing')
    reject('save_failed', lambda v: v.update(save_status=['CANCELLED']), 'save/reopen failed')
    reject('wrong_request', lambda v: v['run'].update(target='alias'), 'authored source request')
    reject('missing_object', lambda v: v['reloaded']['objects'].pop('a'), 'object identity')
    reject('numeric_boolean', lambda v: v['after']['objects'][run['target']].update(lock_scale=[0, 0, 0]),
           'authored boolean value')
    assert original == json.loads((folder/(run['id']+'.json')).read_text())
    report = {'negative_controls_passed': True, 'controls': len(rows), 'rows': rows,
              'forged_operations_executed': False, 'source_manifest_sha256': digest(folder/'manifest.json'),
              'source_records_unchanged': True, 'product_acceptance': 'unrun'}
    with output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'negative_controls_passed': True, 'controls': len(rows)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check(args.suite.resolve(), args.capture.resolve(), args.output.resolve())
