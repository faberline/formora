#!/usr/bin/env python3
"""Compare both complete two-grid captures; do not claim Rust timing."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

from compare_selection_reference import require
from compare_snap_menu_reference import tree
from compare_multi_mesh_merge_reference import validate_run
from generate_multi_mesh_merge_capacity_cases import author
from multi_mesh_merge_capacity_inputs import input_paths

ROOT = Path(__file__).resolve().parents[1]
BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_capture(folder, suite_path, runs, focused):
    manifest = json.loads((folder / 'manifest.json').read_text())
    require(manifest['schema_version'] == 1 and manifest['product'] == 'blender'
            and manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880'
            and manifest['binary_sha256'] == BINARY and manifest['background'] is False,
            'native identity differs')
    require(manifest['product_acceptance'] == 'unrun', 'source capture claimed product acceptance')
    scope = 'focused_capacity_diagnostic' if focused else 'complete_30_two_class_A_merge_cases'
    require(manifest['scope'] == scope, 'capture scope differs')
    ids = [run['id'] for run in runs]
    require([row['id'] for row in manifest['runs']] == ids, 'missing/duplicate/reordered source cases')
    require({p.name for p in folder.glob('*.json.gz')} == {id+'.json.gz' for id in ids}, 'raw artifact set differs')
    receipt_folder = folder.with_name(folder.name + '-process')
    started = json.loads((receipt_folder / 'started.json').read_text())
    terminal = json.loads((receipt_folder / 'terminal.json').read_text())
    require(type(manifest['process_id']) is int and manifest['process_id'] > 0, 'invalid process ID')
    require(started['process_id'] == terminal['process_id'] == manifest['process_id'], 'process identity differs')
    require(terminal['terminal_exit_code'] == 0 and terminal['timed_out'] is False, 'native exit failed/missing')
    require(terminal['manifest_sha256'] == digest(folder / 'manifest.json'), 'terminal manifest differs')
    require(started['binary_sha256'] == BINARY and started['suite_sha256'] == digest(suite_path), 'started input differs')
    require(started['scope'] == scope, 'started scope differs')
    command = started['command_line']
    require(command[0] == '/Applications/Blender.app/Contents/MacOS/Blender'
            and command[1:3] == ['--factory-startup', '--python'] and '--background' not in command,
            'native command differs')
    require(command[3] == str(ROOT/'tools/blender_multi_mesh_merge_capacity_reference.py')
            and command[4:9] == ['--', '--suite', str(suite_path), '--output', str(folder)], 'capture command differs')
    require(manifest['command_line'][1:] == command[1:], 'actual source command differs')
    require(command[9:] == ([part for id in ids for part in ['--case', id]] if focused else []), 'requested cases differ')
    for name in ['stdout', 'stderr']:
        require(terminal[name+'_sha256'] == digest(receipt_folder/name), 'terminal stream differs')
    require(manifest['capture_lock_sha256'] == terminal['capture_lock_sha256'] == digest(folder/'capture-lock.json'),
            'capture lock differs')
    require(digest(folder/'operator-properties.json') == manifest['operator_properties_sha256'], 'RNA differs')
    inputs = manifest['input_hashes']
    require(inputs.get(suite_path.relative_to(ROOT).as_posix()) == digest(suite_path), 'suite hash differs')
    expected_paths = input_paths(suite_path)
    require(set(inputs) == {p.relative_to(ROOT).as_posix() for p in expected_paths},
            'provenance file set differs')
    for relative, sha in inputs.items():
        path = ROOT/relative
        require(path.resolve().is_relative_to(ROOT) and digest(path) == sha, 'capture input drift/' + relative)
    require(digest(folder/'capture-lock.json') == digest(ROOT/'baseline/lock.json'), 'baseline lock changed')
    return manifest



def compare(suite_path, first, second, case_ids):
    suite = json.loads(suite_path.read_text())
    require(suite == author(), 'independently authored capacity inputs differ')
    runs = suite['runs']
    require(len(runs) == 30 and len({run['id'] for run in runs}) == 30, 'full capacity coverage differs')
    forms = Counter((run['parameters']['type'], run['parameters']['uvs']) for run in runs)
    require(len(forms) == 10 and set(forms.values()) == {3}, 'required capacity samples differ')
    if case_ids:
        require(len(case_ids) == len(set(case_ids)) and set(case_ids) <= {r['id'] for r in runs}, 'unknown cases')
        runs = [run for run in runs if run['id'] in case_ids]
    manifests = [load_capture(folder, suite_path, runs, bool(case_ids)) for folder in [first, second]]
    require(manifests[0]['process_id'] != manifests[1]['process_id'], 'native process reused')
    require(manifests[0]['input_hashes'] == manifests[1]['input_hashes'], 'capacity inputs differ')
    require(manifests[0]['operator_properties_sha256'] == manifests[1]['operator_properties_sha256'], 'RNA differs')
    counts = Counter()
    native_durations = []
    for i, run in enumerate(runs):
        values = []
        for folder, manifest in zip([first, second], manifests):
            require(manifest['Rust_product_timing'] == 'unrun', 'native capture claimed Rust timing')
            row = manifest['runs'][i]
            require(row['file'] == run['id']+'.json.gz', 'capacity artifact path differs')
            path = folder/row['file']
            require(digest(path) == row['sha256'], 'stored raw digest differs')
            raw = gzip.decompress(path.read_bytes())
            require(hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes'],
                    'raw capacity JSON differs')
            record = json.loads(raw)
            require(set(record) == {'data', 'native_operator_clock'}, 'capacity record fields differ')
            clock = record['native_operator_clock']
            require(set(clock) == {'before_ns', 'after_ns', 'elapsed_ms', 'is_Rust_product_timing'},
                    'native clock fields differ')
            require(type(clock['before_ns']) is int and type(clock['after_ns']) is int
                    and clock['after_ns'] > clock['before_ns'] > 0, 'native operator clock missing/invalid')
            require(type(clock['elapsed_ms']) is float and math.isfinite(clock['elapsed_ms'])
                    and clock['elapsed_ms'] == (clock['after_ns']-clock['before_ns'])/1e6,
                    'native duration differs')
            require(clock['is_Rust_product_timing'] is False, 'native timing misclassified')
            value = record['data']
            require(value['result']['status'] == row['status'], 'capacity manifest status differs')
            values.append(value)
            native_durations.append({'process_id': manifest['process_id'], 'id': run['id'],
                                     'native_operator_ms': clock['elapsed_ms']})
        outcomes = [validate_run(suite, run, value) for value in values]
        tree(values[0], values[1], run['id'])
        require(outcomes[0] == outcomes[1] and outcomes[0]['enum_rejected'] == 0,
                'capacity source outcomes differ')
        counts.update(outcomes[0])
        print(json.dumps({'compared': i+1, 'total': len(runs)}), flush=True)
    return {'source_comparison_passed': True, 'cases': len(runs),
            'complete_capacity_source_gate': not bool(case_ids), 'outcomes': dict(counts),
            'native_processes': [m['process_id'] for m in manifests],
            'native_operator_durations_support_only': native_durations,
            'suite_sha256': digest(suite_path), 'checker_sha256': digest(__file__),
            'numeric_absolute_limit': 1e-6, 'Rust_product_timing': 'unrun',
            'product_acceptance': 'unrun', 'milestones_accepted': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--first', type=Path, required=True)
    parser.add_argument('--second', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[], dest='case_ids')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.suite.resolve(), args.first.resolve(), args.second.resolve(), args.case_ids)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result))
