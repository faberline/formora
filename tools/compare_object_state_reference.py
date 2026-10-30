#!/usr/bin/env python3
"""Bind every object-state source result and compare independent captures."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

from compare_selection_reference import require
from compare_snap_menu_reference import tree, IDENTITY
from compare_snap_rotation_reference import matrix, compose
from compare_transform_reference import finite
from generate_object_state_cases import author
from generate_multi_mesh_merge_cases import author as base_inputs

ROOT = Path(__file__).resolve().parents[1]
BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
INPUTS = ['tools/generate_object_state_cases.py', 'tools/blender_object_state_reference.py',
          'tools/launch_object_state_reference.py', 'tools/compare_object_state_reference.py',
          'tools/generate_multi_mesh_merge_cases.py', 'tools/blender_multi_mesh_merge_reference.py',
          'tools/blender_mesh_merge_reference.py', 'tools/blender_snap_menu_reference.py',
          'tools/blender_transform_reference.py', 'tools/blender_selection_reference.py',
          'tools/multi_mesh_merge_inputs.py', 'docs/contracts/object-state-query.md',
          'tools/compare_selection_reference.py', 'tools/compare_snap_menu_reference.py',
          'tools/compare_snap_rotation_reference.py', 'tools/compare_transform_reference.py',
          'tools/generate_snap_menu_cases.py', 'tools/generate_snap_rotation_cases.py',
          'tools/generate_mesh_transform_cases.py', 'tools/check_object_state_controls.py',
          'baseline/sources/object-state/manifest.json', 'baseline/sources/object-state/rna_object.cc']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_run(suite, run, value):
    require(value['run'] == run, 'authored source request differs')
    require(value['save_status'] == value['reopen_status'] == ['FINISHED'], 'native save/reopen failed')
    finite(value)
    base = base_inputs()
    names = set(suite['initial_locks'])
    frames = base['entity_frames'][run['frame']]
    bases = {name: matrix({'location': f['transform']['translation'], 'scale': f['transform']['scale']},
                          {'mode': f['transform']['rotation']['order'].upper(),
                           'euler': f['transform']['rotation']['angles']}) for name, f in frames.items()}

    def world(name):
        parent = frames[name]['parent']
        return bases[name] if parent is None else compose(world(parent), bases[name])

    for phase in ['before', 'after', 'reloaded']:
        state = value[phase]
        require(set(state['objects']) == names, 'source object identity differs')
        require(state['sharing'] == [['a', 'alias'], ['b'], ['untouched']], 'source sharing differs')
        require(state['mode'] in ['OBJECT', 'EDIT_MESH'], 'unexpected source mode')
        for name, item in state['objects'].items():
            expected = suite['initial_locks'][name]
            if phase != 'before' and name == run['target']:
                expected = run['lock_scale']
            require(item['lock_scale'] == expected and all(type(x) is bool for x in item['lock_scale']),
                    'authored boolean value differs')
            tree(bases[name], item['matrix_basis'], name+'/authored basis')
            tree(world(name), item['matrix_world'], name+'/authored world')
            tree(IDENTITY, item['matrix_parent_inverse'], name+'/authored parent inverse', 0.)
            require(item['parent'] == frames[name]['parent'], 'authored parent differs')
            require(item['type'] == ('EMPTY' if name == 'parent' else 'MESH'), 'source object type differs')
            require(item['mode'] in ['OBJECT', 'EDIT'], 'unexpected object mode')
            if name != 'parent':
                mesh = base['mesh_assets'][base['data_sharing'][name]]
                require(item['geometry_counts'] == [len(mesh['vertices']), len(mesh['edges']), len(mesh['polygons'])],
                        'source geometry changed')
        if phase == 'before':
            require(state['mode'] == run['mode'], 'authored initial mode differs')
            for name, item in state['objects'].items():
                expected_edit = run['mode'] == 'EDIT_MESH' and name in ['a', 'b']
                require(item['mode'] == ('EDIT' if expected_edit else 'OBJECT'), 'authored edit owner differs')
    changed = copy.deepcopy(value['before'])
    changed['objects'][run['target']]['lock_scale'] = run['lock_scale']
    tree(changed, value['after'], 'setter affected other data', 0.)
    # Preserve actual native UI mode restoration in the raw record. The
    # property, object frames and geometry remain strictly bound above.


def load_capture(folder, suite_path, suite):
    m = json.loads((folder/'manifest.json').read_text())
    require(m['scope'] == 'complete_160_object_scale_lock_cases' and m['version'] == [5, 2, 3]
            and m['build_hash'] == 'e13b728c6880' and m['binary_sha256'] == BINARY
            and m['background'] is False and m['product_acceptance'] == 'unrun', 'source identity differs')
    require(type(m['process_id']) is int and m['process_id'] > 0, 'invalid native PID')
    ids = [r['id'] for r in suite['runs']]
    require([r['id'] for r in m['runs']] == ids, 'missing/duplicate/reordered source cases')
    require({p.name for p in folder.glob('object_state_*.json')} == {id+'.json' for id in ids}, 'raw artifact set differs')
    receipt = folder.with_name(folder.name+'-process')
    s = json.loads((receipt/'started.json').read_text())
    t = json.loads((receipt/'terminal.json').read_text())
    require(s['process_id'] == t['process_id'] == m['process_id'], 'native process identity differs')
    require(t['terminal_exit_code'] == 0 and t['timed_out'] is False, 'native terminal failed/missing')
    require(t['manifest_sha256'] == digest(folder/'manifest.json'), 'terminal manifest differs')
    require(s['binary_sha256'] == BINARY and s['suite_sha256'] == digest(suite_path), 'started input differs')
    command = ['/Applications/Blender.app/Contents/MacOS/Blender', '--factory-startup', '--python',
               str(ROOT/'tools/blender_object_state_reference.py'), '--', '--suite', str(suite_path),
               '--output', str(folder)]
    require(s['command_line'] == m['command_line'] == command, 'actual source command differs')
    for name in ['stdout', 'stderr']:
        require(t[name+'_sha256'] == digest(receipt/name), 'terminal stream differs')
    expected = {suite_path.relative_to(ROOT).as_posix(): digest(suite_path)}
    expected.update({name: digest(ROOT/name) for name in INPUTS})
    require(m['input_hashes'] == expected, 'source input drift or missing input')
    pin = json.loads((ROOT/'baseline/sources/object-state/manifest.json').read_text())
    require(pin['commit'] == suite['source_commit'] and pin['sha256'] ==
            digest(ROOT/'baseline/sources/object-state/rna_object.cc'), 'pinned property source differs')
    return m


def compare(suite_path, first, second):
    suite = json.loads(suite_path.read_text())
    require(suite == author(), 'independently authored inputs differ')
    manifests = [load_capture(folder, suite_path, suite) for folder in [first, second]]
    require(manifests[0]['process_id'] != manifests[1]['process_id'], 'native process reused')
    require(manifests[0]['input_hashes'] == manifests[1]['input_hashes'], 'native inputs differ')
    modes = []
    for i, run in enumerate(suite['runs']):
        values = []
        for folder, m in zip([first, second], manifests):
            row = m['runs'][i]
            require(row['file'] == run['id']+'.json' and digest(folder/row['file']) == row['sha256'], 'raw source digest differs')
            value = json.loads((folder/row['file']).read_text())
            validate_run(suite, run, value)
            require(row['native_file'] == value['native_file_stored'] == run['id']+'.blend.gz', 'native file path differs')
            stored = folder/row['native_file']
            require(digest(stored) == row['native_file_sha256'], 'stored native file differs')
            raw = gzip.decompress(stored.read_bytes())
            require(hashlib.sha256(raw).hexdigest() == value['native_file_sha256']
                    and len(raw) == value['native_file_bytes'], 'exact native file differs')
            values.append(value)
        for phase in ['before', 'after', 'reloaded']:
            tree(values[0][phase], values[1][phase], run['id']+'/'+phase)
        modes.append([values[0][p]['mode'] for p in ['before', 'after', 'reloaded']])
    return {'source_gate_passed': True, 'cases': 160,
            'native_processes': [m['process_id'] for m in manifests],
            'source_suite_sha256': digest(suite_path), 'checker_sha256': digest(Path(__file__)),
            'booleans': 'exact', 'matrix_limit': 1e-6,
            'observed_modes': sorted({tuple(m) for m in modes}), 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--first', type=Path, required=True)
    parser.add_argument('--second', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.suite.resolve(), args.first.resolve(), args.second.resolve())
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(report))
