"""Run the complete diagnostic checker against retained, rehashed forged data."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from check_merge_distance_diagnostic import check


def controls(suite, native, output, seal=None):
    output.mkdir(exist_ok=False)
    assert check(suite, native/'capture', seal)['diagnostic_checks_passed'], 'genuine diagnostic must pass first'
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    manifest = json.loads((native/'capture/manifest.json').read_text())
    rows = []

    def reject(name, reason, record_id=None, mutation=None, envelope=None, suite_mutation=None, missing=None):
        # Each control gets its own preserved copy. Never alter a genuine receipt.
        scratch = Path(tempfile.mkdtemp(prefix='formora-distance-forged-'))/'native'
        shutil.copytree(native, scratch)
        stored = output/name; stored.mkdir()
        changed = []
        candidate_suite = suite
        if missing is not None:
            path = scratch/missing
            retained = path.with_name(path.name+'.retained')
            path.rename(retained); changed.append(retained)
        if record_id is not None:
            index = next(i for i, row in enumerate(manifest['runs']) if row['id'] == record_id)
            record_path = scratch/'capture'/manifest['runs'][index]['file']
            value = json.loads(gzip.decompress(record_path.read_bytes()))
            mutation(value)
            raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
            compressed = gzip.compress(raw, mtime=0); record_path.write_bytes(compressed)
            altered = copy.deepcopy(manifest)
            altered['runs'][index]['sha256'] = sha(compressed)
            altered['runs'][index]['raw_sha256'] = sha(raw)
            (scratch/'capture/manifest.json').write_text(json.dumps(altered, indent=2)+'\n')
            changed += [record_path, scratch/'capture/manifest.json']
        if envelope is not None:
            relative, mutate = envelope
            path = scratch/relative
            value = json.loads(path.read_text()); mutate(value)
            path.write_text(json.dumps(value, indent=2)+'\n'); changed.append(path)
        if suite_mutation is not None:
            value = json.loads(suite.read_text()); suite_mutation(value)
            candidate_suite = stored/'forged-suite.json'
            candidate_suite.write_text(json.dumps(value, indent=2)+'\n')
        try:
            result = check(candidate_suite, scratch/'capture', seal)
            error = '\n'.join(error for row in result['records'] for error in row['errors'])
            assert not result['diagnostic_checks_passed'], 'forged diagnostic accepted'
        except (AssertionError, KeyError, FileNotFoundError) as caught:
            result = None; error = str(caught)
        assert reason in error, (name, 'wrong rejection', reason, error)
        for path in changed:
            target = stored/path.name
            with target.open('xb') as stream: stream.write(path.read_bytes())
        row = {'control': name, 'rejected': True, 'expected_check': reason, 'error': error,
               'preserved_forged_copy': str(scratch), 'result': result}
        with (stored/'result.json').open('x') as stream: json.dump(row, stream, indent=2); stream.write('\n')
        rows.append({key: value for key, value in row.items() if key != 'result'})

    reject('wrong_pair_centroid', 'source-cluster/vertices', 'distance_diag_003',
           lambda x: x['after']['meshes']['a']['geometry']['vertices']['v000000'].__setitem__(0, .0626))
    reject('wrong_equal_distance_boundary', 'source-cluster/vertices', 'distance_diag_001',
           lambda x: x['after']['meshes']['a']['geometry']['vertices'].update(v000001=[.125, 0., 0.]))
    reject('wrong_lower_distance_boundary', 'source-cluster/vertices', 'distance_diag_000',
           lambda x: x['after']['meshes']['a']['geometry']['vertices'].pop('v000001'))
    reject('executed_parameters_changed', 'executed-native-parameters', 'distance_diag_000',
           lambda x: x['executed_parameters'].__setitem__('threshold', .5))
    reject('executed_parameters_missing', 'executed_parameters', 'distance_diag_000',
           lambda x: x.pop('executed_parameters'))
    reject('native_file_substitution', 'native save file identity', 'distance_diag_000',
           lambda x: x.update(native_file_stored='distance_diag_001.blend.gz'))
    reject('wrong_transitive_chain_merge', 'source-cluster/vertices', 'distance_diag_005',
           lambda x: x['after']['meshes']['a']['geometry'].__setitem__('vertices', {'v000000': [.09375, 0., 0.]}))
    reject('unselected_outside_data_changed', 'unedited-mesh/untouched', 'distance_diag_000',
           lambda x: x['after']['meshes']['untouched']['geometry']['vertices']['v000000'].__setitem__(0, 9.))
    reject('object_world_changed', 'unchanged-scene/objects', 'distance_diag_000',
           lambda x: x['after']['objects']['a']['matrix_world'][0].__setitem__(3, .5))
    reject('shared_mesh_detached', 'unchanged-scene/sharing', 'distance_diag_000',
           lambda x: x['after'].__setitem__('sharing', [['a'], ['alias'], ['b'], ['untouched']]))
    reject('wrong_edit_data_provider', 'edit-context/unique_data_iteration', 'distance_diag_013',
           lambda x: x['before']['edit_context'].__setitem__('unique_data_iteration', ['a', 'b']))
    reject('missing_uv_corner', 'a/geometry/uv_layers', 'distance_diag_012',
           lambda x: x['before']['meshes']['a']['geometry']['uv_layers']['Detail']['f000000'].pop())
    reject('explicit_zero_weight_lost', 'a/groups/weights', 'distance_diag_000',
           lambda x: x['before']['meshes']['a']['groups']['weights']['v000000'].pop('pin'))
    reject('integer_replaced_by_boolean', 'a/integers', 'distance_diag_000',
           lambda x: x['before']['meshes']['a']['integer_attributes']['VERT']['vertices_signed'].__setitem__('v000000', True))
    reject('packed_normal_off_by_one', 'a/encoded-custom-normal', 'distance_diag_015',
           lambda x: x['before']['meshes']['a']['packed_custom_normals']['f000000'][0].__setitem__(0, 19929))
    reject('decoded_normal_over_limit', 'a/source-decoded-custom-normal', 'distance_diag_015',
           lambda x: x['before']['meshes']['a']['normals']['corners']['f000000'][0].__setitem__(0, 9.))
    reject('native_reload_attribute_lost', 'complete-source-reload/meshes/a/integer_attributes', 'distance_diag_000',
           lambda x: x['reloaded']['meshes']['a']['integer_attributes']['VERT'].pop('vertices_signed'))
    reject('source_answer_in_authored_suite', 'pure-authored-suite',
           suite_mutation=lambda x: x['mesh_fixtures']['loose_pair'].update(source_expected={'vertices': {}}))
    reject('missing_case', 'source case membership', envelope=('capture/manifest.json', lambda x: x['runs'].pop()))
    reject('duplicate_case', 'source case membership', envelope=('capture/manifest.json', lambda x: x['runs'].append(copy.deepcopy(x['runs'][0]))))
    reject('source_binary_substitution', 'source binary', envelope=('capture/manifest.json', lambda x: x.update(binary_sha256='0'*64)))
    reject('failed_native_terminal', 'native terminal failed', envelope=('terminal.json', lambda x: x.update(terminal_exit_code=1)))
    reject('boolean_native_terminal', 'native terminal type', envelope=('terminal.json', lambda x: x.update(terminal_exit_code=False)))
    reject('float_native_terminal', 'native terminal type', envelope=('terminal.json', lambda x: x.update(terminal_exit_code=0.0)))
    reject('missing_native_terminal_field', 'terminal_exit_code', envelope=('terminal.json', lambda x: x.pop('terminal_exit_code')))
    reject('missing_native_terminal_file', 'terminal.json', missing='terminal.json')
    reject('timed_out_native_terminal', 'native terminal failed', envelope=('terminal.json', lambda x: x.update(timed_out=True)))
    reject('wrong_native_pid', 'native PID binding', envelope=('terminal.json', lambda x: x.update(process_id=1)))
    reject('wrong_native_log_identity', 'native log identity', envelope=('terminal.json', lambda x: x.update(stdout_sha256='0'*64)))
    reject('missing_input_hash', 'source input hash membership', envelope=('capture/manifest.json', lambda x: x['input_hashes'].pop(next(iter(x['input_hashes'])))))
    reject('empty_input_hashes', 'source input hash membership', envelope=('capture/manifest.json', lambda x: x.update(input_hashes={})))
    reject('extra_input_hash', 'source input hash membership', envelope=('capture/manifest.json', lambda x: x['input_hashes'].update({'/private/tmp/not-an-admitted-input': '0'*64})))
    reject('wrong_parent_suite_hash', 'parent suite identity', envelope=('started.json', lambda x: x.update(suite_sha256='0'*64)))
    if any(run['purpose'].startswith('smooth_cyclic_') for run in json.loads(suite.read_text())['runs']):
        reject('smooth_fan_sharp_edge_changed', 'a/geometry/edge_sharp', 'distance_diag_021',
               lambda x: x['before']['meshes']['a']['geometry']['edge_sharp'].__setitem__('e000000', True))
        reject('cyclic_fan_packed_normal_changed', 'a/encoded-custom-normal', 'distance_diag_027',
               lambda x: x['before']['meshes']['a']['packed_custom_normals']['f000000'][0].__setitem__(0, 1))
        reject('cyclic_fan_zero_default_changed', 'a/source-decoded-custom-normal', 'distance_diag_031',
               lambda x: x['before']['meshes']['a']['normals']['corners']['f000000'][0].__setitem__(0, 9.))
    nan_case = next((run for run in json.loads(suite.read_text())['runs'] if run['purpose'] == 'native_nonfinite_threshold_nan'), None)
    if nan_case:
        reject('native_nan_probe_changes_data', 'native-nan-no-change', nan_case['id'],
               lambda x: x['after']['meshes']['a']['geometry']['vertices']['v000000'].__setitem__(0, .5))
    repeat_case = next((run for run in json.loads(suite.read_text())['runs'] if run['purpose'] == 'unique_data_once_repeat_sensitive' and
                        run['factors']['context'] == 'multi_alias_first'), None)
    if repeat_case:
        def duplicate_process(value):
            for name in ['a', 'alias']:
                value['after']['meshes'][name]['geometry']['vertices'] = {'v000000': [.125, 0., 0.]}
        reject('shared_data_processed_twice', 'source-cluster/vertices', repeat_case['id'], duplicate_process)
    result = {'genuine_diagnostic_passed': True, 'forged_controls_rejected': len(rows), 'controls': rows,
              'source_manifest_sha256': sha((native/'capture/manifest.json').read_bytes()),
              'checker_sha256': sha(Path(__file__).with_name('check_merge_distance_diagnostic.py').read_bytes()),
              'control_script_sha256': sha(Path(__file__).read_bytes()),
              'forged_operations_executed': False, 'full_source_gate': 'unrun', 'product_acceptance': 'unrun'}
    with (output/'report.json').open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    return {'genuine_diagnostic_passed': True, 'forged_controls_rejected': len(rows), 'forged_operations_executed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['suite', 'native', 'output']: parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--seal', type=Path)
    args = parser.parse_args()
    print(json.dumps(controls(args.suite, args.native, args.output, args.seal)))
