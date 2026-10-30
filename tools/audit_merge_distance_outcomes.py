"""Separate source completion, unchanged data, empty skips and input rejection."""
import argparse
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path

from check_merge_distance_diagnostic import check, same
from merge_distance_cluster_reference import vertex_result
from merge_distance_parameter_reference import converted
from merge_distance_scene_inputs import scene, selection


def outcome(run, spec, value):
    conversion = converted(run['parameters'])
    if conversion['classification'] == 'rejected_no_operation':
        assert value['result']['status'] == ['OPERATOR_EXCEPTION'], 'rejected source input status'
        assert value['result']['error_type'] == 'TypeError', 'rejected source input type'
        assert conversion['parameter'] in value['result']['error'], 'rejected source input parameter'
        same(value['before'], value['after'], 'rejected-source-data', 0.)
        return {'id': run['id'], 'operation': 'rejected_no_operation', 'numeric_match_claimed': False,
                'data': [], 'cancelled': False, 'source_defect': False}
    assert value['result'] == {'status': ['FINISHED'], 'error': None}, 'finished source input status'
    if conversion['classification'] == 'native_nonfinite_source_probe':
        if conversion['native_token'] == 'nan': same(value['before'], value['after'], 'native-nan-source-data', 0.)
        else:
            for owner in spec['object_context']['edit_objects']:
                mesh = spec['mesh_assets'][spec['data_sharing'][owner]]
                result = vertex_result(mesh, selection(mesh, spec, True), conversion['parameters'])
                same(result['vertices'], value['after']['meshes'][owner]['geometry']['vertices'], 'native-infinite-source-data/'+owner)
        return {'id': run['id'], 'operation': 'finished_native_nonfinite_probe', 'numeric_match_claimed': False,
                'native_token': conversion['native_token'], 'data': [], 'cancelled': False, 'source_defect': False,
                'json_numeric_input_admitted': False}
    data = []
    for owner in spec['object_context']['edit_objects']:
        mesh = spec['mesh_assets'][spec['data_sharing'][owner]]
        result = vertex_result(mesh, selection(mesh, spec, True), conversion['parameters'])
        actual = value['after']['meshes'][owner]['geometry']['vertices']
        same(result['vertices'], actual, 'classified-source-vertices/'+owner)
        same(result['removed'], len(mesh['vertices'])-len(actual), 'classified-source-removal/'+owner, 0.)
        if result['classification'] == 'skipped_empty_selection':
            same(value['before']['meshes'][owner], value['after']['meshes'][owner], 'empty-source-data', 0.)
        data.append({'owner': owner, 'asset': spec['data_sharing'][owner], 'classification': result['classification'],
                     'removed': result['removed'], 'numeric_match_claimed': result['classification'] != 'skipped_empty_selection'})
    categories = {row['classification'] for row in data}
    operation = 'finished_with_merge' if 'merged' in categories else (
        'finished_all_data_skipped_empty_selection' if categories == {'skipped_empty_selection'} else 'finished_unchanged')
    return {'id': run['id'], 'operation': operation,
            'numeric_match_claimed': any(row['numeric_match_claimed'] for row in data),
            'data': data, 'cancelled': False, 'source_defect': False}


def audit(suite_path, native, output, seal=None):
    diagnostic = check(suite_path, native/'capture', seal)
    assert diagnostic['diagnostic_checks_passed'], 'base diagnostic failed'
    suite = json.loads(suite_path.read_text()); manifest = json.loads((native/'capture/manifest.json').read_text())
    records = []; values = []
    for run, row in zip(suite['runs'], manifest['runs']):
        value = json.loads(gzip.decompress((native/'capture'/row['file']).read_bytes()))
        spec = scene(suite, run); result = outcome(run, spec, value)
        result['raw_source_sha256'] = row['raw_sha256']; records.append(result); values.append((run, spec, value))
    controls = []
    def reject(name, case, mutation, reason):
        run, spec, value = next(row for row in values if row[0]['purpose'] == case)
        forged = copy.deepcopy(value); mutation(forged)
        try: outcome(run, spec, forged)
        except AssertionError as error:
            assert reason in str(error), (name, 'wrong check', str(error))
            controls.append({'control': name, 'rejected': True, 'error': str(error)})
        else: raise AssertionError('forged classification accepted: '+name)
    reject('source_rejection_disguised_as_finish', 'threshold_numeric_string',
           lambda x: x.update(result={'status': ['FINISHED'], 'error': None}), 'rejected source input status')
    reject('source_finish_disguised_as_rejection', 'pair_above_centroid',
           lambda x: x.update(result={'status': ['OPERATOR_EXCEPTION'], 'error': 'threshold', 'error_type': 'TypeError'}), 'finished source input status')
    reject('empty_skip_changes_data', 'empty_selection',
           lambda x: x['after']['meshes']['a']['groups']['weights']['v000000'].__setitem__('pin', .5), 'empty-source-data')
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    paths = [Path(__file__), Path(__file__).with_name('merge_distance_cluster_reference.py'),
             Path(__file__).with_name('merge_distance_parameter_reference.py'), suite_path, native/'capture/manifest.json', native/'terminal.json']
    result = {'source_diagnostic_passed': True, 'cases': len(records),
              'operation_counts': dict(Counter(row['operation'] for row in records)),
              'data_counts': dict(Counter(data['classification'] for row in records for data in row['data'])),
              'controls': controls, 'records': records, 'input_hashes': {str(path): sha(path) for path in paths},
              'numeric_rejection_matches_claimed': 0, 'forged_operations_executed': False,
              'full_source_gate': 'unrun', 'product_acceptance': 'unrun'}
    with output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    return {key: result[key] for key in ['source_diagnostic_passed', 'cases', 'operation_counts', 'data_counts', 'numeric_rejection_matches_claimed']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['suite', 'native', 'output']: parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--seal', type=Path)
    args = parser.parse_args(); print(json.dumps(audit(args.suite, args.native, args.output, args.seal)))
