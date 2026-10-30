#!/usr/bin/env python3
"""Prove that source binding rejects forged data; never run forged operations."""
import argparse
import copy
import gzip
import json
from pathlib import Path

from compare_multi_mesh_merge_reference import bind_suite, digest, validate_run, load_capture
from generate_multi_mesh_merge_cases import author

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def check(folder, control_root, output):
    suite_path = ROOT/'baseline/fixtures/mesh-merge-multi-data.json'
    suite = json.loads(suite_path.read_text())
    bind_suite(suite)
    manifest = json.loads((folder/'manifest.json').read_text())
    ids = [row['id'] for row in manifest['runs']]
    runs = [run for run in suite['runs'] if run['id'] in set(ids)]
    focused = manifest['scope'] == 'focused_diagnostic'
    load_capture(folder, suite_path, runs, focused)
    originals = [json.loads(gzip.decompress((folder/row['file']).read_bytes()))
                 for row in manifest['runs']]
    center = next(value for value in originals if value['run']['parameters']['type'] == 'CENTER'
                  and value['run']['selection'] == 'both')
    first = next(value for value in originals if value['run']['parameters']['type'] == 'FIRST'
                 and not value['run']['expected_enum_unavailable'] and value['run']['selection'] == 'both')
    rejected = next(value for value in originals if value['run']['expected_enum_unavailable'])
    for value in [center, first, rejected]:
        validate_run(suite, value['run'], value)
    control_root.mkdir(parents=True, exist_ok=False)
    rows = []

    def reject(name, action, reason):
        try:
            action()
        except (ValueError, AssertionError, FileNotFoundError) as error:
            if reason is not None:
                assert reason in str(error), (name, reason, str(error))
            rows.append({'name': name, 'rejected': True, 'error': str(error)})
        else:
            raise AssertionError('forged control passed: ' + name)

    leaked = copy.deepcopy(suite)
    leaked['mesh_assets']['mesh_a']['vertices'] = copy.deepcopy(center['after']['meshes']['a']['geometry']['vertices'])
    reject('source_answer_spliced_into_authored_inputs', lambda: bind_suite(leaked), 'authored inputs differ')

    def corrupt_record(name, original, mutate, reason):
        forged = copy.deepcopy(original)
        mutate(forged)
        write(control_root/(name+'.json'), {'forged_control_only': True, 'executed': False,
                                           'source_record': original['run']['id'], 'data': forged})
        reject(name, lambda: validate_run(suite, original['run'], forged), reason)

    corrupt_record('initial_geometry_answer_leak', center,
                   lambda value: value['before']['meshes']['a'].update(geometry=copy.deepcopy(value['after']['meshes']['a']['geometry'])),
                   'authored/mesh_a')
    corrupt_record('initial_signed_attribute_change', center,
                   lambda value: value['before']['meshes']['a']['integer_attributes']['VERT']['vertices_signed'].update(v000000=77),
                   'authored integers')
    corrupt_record('reversed_native_provider_order', center,
                   lambda value: value['before']['edit_context']['unique_data_iteration'].reverse(),
                   'provider membership/order')
    corrupt_record('shared_data_visited_twice', center,
                   lambda value: value['before']['edit_context']['unique_data_iteration'].append('alias'),
                   'provider membership/order')
    corrupt_record('linked_user_falsely_in_edit_mode', center,
                   lambda value: value['before']['edit_context']['edit_objects'].append('alias'),
                   'provider membership/order')
    corrupt_record('typed_history_substitution', first,
                   lambda value: value['before']['meshes'][value['before']['active_object']]['history'].reverse(),
                   'authored typed history')
    other = next(name for name in ['a', 'b'] if suite['data_sharing'][name] !=
                 suite['data_sharing'][first['before']['active_object']])
    corrupt_record('first_merge_mutates_other_data', first,
                   lambda value: value['after']['meshes'][other]['groups']['names'].append('forged'),
                   'unprocessed data')
    corrupt_record('enum_rejection_relabelled_finished', rejected,
                   lambda value: value.update(result={'status': ['FINISHED'], 'error': None}),
                   'enum rejection differs')
    corrupt_record('wrong_authored_operation', center,
                   lambda value: value['run']['parameters'].update(type='LAST'), 'authored request differs')

    # Header forgeries retain raw files and refresh terminal manifest hashes.
    # This ensures semantic checks reject the change, beyond a stale digest.
    def header(name, mutate, reason):
        target = control_root/name
        target.mkdir()
        receipt = target.with_name(target.name+'-process')
        receipt.mkdir()
        m = copy.deepcopy(manifest)
        original_receipt = folder.with_name(folder.name+'-process')
        started = json.loads((original_receipt/'started.json').read_text())
        terminal = json.loads((original_receipt/'terminal.json').read_text())
        for key in ['capture-lock.json', 'operator-properties.json']:
            (target/key).write_bytes((folder/key).read_bytes())
        for row in manifest['runs']:
            (target/row['file']).symlink_to(folder/row['file'])
        for key in ['stdout', 'stderr']:
            (receipt/key).write_bytes((original_receipt/key).read_bytes())
        started['command_line'][8] = str(target)
        m['command_line'][8] = str(target)
        mutate(m, started, terminal)
        write(target/'manifest.json', m)
        terminal['manifest_sha256'] = digest(target/'manifest.json')
        write(receipt/'started.json', started)
        if name != 'missing_terminal_receipt':
            write(receipt/'terminal.json', terminal)
        reject(name, lambda: load_capture(target, suite_path, runs, focused), reason)

    header('wrong_native_version', lambda m, s, t: m.update(version=[5, 2, 2]), 'native identity')
    header('wrong_native_binary', lambda m, s, t: m.update(binary_sha256='0'*64), 'native identity')
    header('background_capture', lambda m, s, t: m.update(background=True), 'native identity')
    header('missing_source_case', lambda m, s, t: m['runs'].pop(), 'source cases')
    header('duplicate_source_case', lambda m, s, t: m['runs'].append(m['runs'][0]), 'source cases')
    header('reordered_source_cases', lambda m, s, t: m['runs'].reverse(), 'source cases')
    header('failed_terminal_exit', lambda m, s, t: t.update(terminal_exit_code=1), 'native exit')
    header('timed_out_native_process', lambda m, s, t: t.update(timed_out=True), 'native exit')
    header('missing_terminal_receipt', lambda m, s, t: None, None)
    header('different_process_identity', lambda m, s, t: s.update(process_id=s['process_id']+1), 'process identity')
    header('missing_provenance_input', lambda m, s, t: m['input_hashes'].pop('tools/compare_snap_menu_reference.py'),
           'provenance file set')
    header('forged_provenance_hash', lambda m, s, t: m['input_hashes'].update({'tools/compare_snap_menu_reference.py':'0'*64}),
           'capture input drift')
    result = {'negative_controls_passed': True, 'controls': len(rows), 'rows': rows,
              'forgeries_executed': False, 'source_capture': str(folder),
              'source_manifest_sha256': digest(folder/'manifest.json'),
              'control_script_sha256': digest(__file__), 'product_acceptance': 'unrun'}
    write(output, result)
    print(json.dumps({'negative_controls_passed': True, 'controls': len(rows), 'product_acceptance': 'unrun'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--controls', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check(args.capture.resolve(), args.controls.resolve(), args.output.resolve())
