"""Bind diagnostic native captures to inputs. Do not accept the full source gate."""
import argparse
import builtins
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from unittest.mock import patch

from compare_snap_rotation_reference import matrix, compose
from compare_snap_delta_reference import world_point
from merge_distance_scene_inputs import scene, selection
from merge_distance_fan_reference import custom_fans
from merge_distance_cluster_reference import vertex_result
from generate_merge_distance_diagnostic import diagnostic
from generate_merge_distance_normal_diagnostic import normal_diagnostic
from generate_merge_distance_fan_diagnostic import fan_diagnostic
from generate_merge_distance_parameter_diagnostic import parameter_diagnostic
from merge_distance_parameter_reference import converted


def authored_suite(suite):
    reads = []
    def deny(*args, **kwargs):
        reads.append(str(args[0])); raise AssertionError('constructor source read')
    with patch.object(builtins, 'open', deny), patch.object(io, 'open', deny):
        expected = parameter_diagnostic() if suite['scope'] == 'targeted_source_scalar_parameter_diagnostics_only' else (
            fan_diagnostic() if suite['scope'] == 'targeted_source_cluster_and_smooth_fan_diagnostics_only' else (
            normal_diagnostic() if len(suite['runs']) == 21 else diagnostic()))
    assert not reads, 'constructor source reads'
    same(expected, suite, 'pure-authored-suite', 0.)


def receipt(manifest, started, terminal, stdout, stderr):
    assert manifest['background'] is False, 'background source process'
    assert manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880', 'source version'
    binary = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert manifest['binary_sha256'] == started['binary_sha256'] == binary, 'source binary'
    assert terminal['terminal_exit_code'] == 0 and terminal['timed_out'] is False, 'native terminal failed'
    assert type(manifest['process_id']) is int and manifest['process_id'] > 0, 'native PID type'
    assert manifest['process_id'] == started['process_id'] == terminal['process_id'], 'native PID binding'
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    assert sha(stdout) == terminal['stdout_sha256'] and sha(stderr) == terminal['stderr_sha256'], 'native log identity'
    assert started['command_line'] == manifest['command_line'], 'native command binding'


def membership(suite, manifest, capture):
    expected = [run['id'] for run in suite['runs']]
    assert len(expected) == len(set(expected)), 'duplicate authored case'
    assert [row['id'] for row in manifest['runs']] == expected, 'source case membership'
    assert all(row['file'] == row['id']+'.json.gz' and row['native_file'] == row['id']+'.blend.gz'
               for row in manifest['runs']), 'source file identity'
    names = {'manifest.json'} | {name+'.'+suffix for name in expected for suffix in ['json.gz', 'blend.gz']}
    assert {path.name for path in capture.iterdir()} == names, 'source file membership'


def postconditions(run, spec, before, after):
    for key in ['objects', 'sharing', 'active_object', 'mode', 'edit_context', 'materials', 'settings']:
        same(before[key], after[key], 'unchanged-scene/'+key, 0.)
    edited = {spec['data_sharing'][name] for name in spec['object_context']['edit_objects']}
    conversion = converted(run['parameters'])
    if conversion['classification'] == 'rejected_no_operation':
        same(before, after, 'rejected-input-no-operation', 0.)
        return
    for name in spec['object_context']['edit_objects']:
        mesh = spec['mesh_assets'][spec['data_sharing'][name]]
        prediction = vertex_result(mesh, selection(mesh, spec, True), conversion['parameters'])
        same(prediction['vertices'], after['meshes'][name]['geometry']['vertices'], 'source-cluster/vertices/'+name)
        actual_removed = len(mesh['vertices'])-len(after['meshes'][name]['geometry']['vertices'])
        same(prediction['removed'], actual_removed, 'source-cluster/removed/'+name, 0.)
    for name, data in spec['data_sharing'].items():
        if data not in edited:
            same(before['meshes'][name], after['meshes'][name], 'unedited-mesh/'+name, 0.)
    if spec['selection'] == 'none':
        same(before, after, 'empty-selection-skip', 0.)
    # These independently authored two-point inputs have exact binary distances.
    # The fixed find-doubles source compares <= threshold. The fixed weld source
    # retains one point or computes the centroid, as requested.
    if run['purpose'] in ['pair_below', 'pair_equal', 'pair_above_keep', 'pair_above_centroid', 'pair_zero_parent']:
        mesh = spec['mesh_assets']['mesh_a']
        points = list(mesh['vertices'].values()); assert len(points) == 2
        threshold = run['parameters']['threshold']
        if math.dist(*points) > threshold:
            expected = mesh['vertices']
        else:
            value = [sum(p[i] for p in points)/2. for i in range(3)] if run['parameters']['use_centroid'] else points[0]
            expected = {'v000000': value}
        same(expected, after['meshes']['a']['geometry']['vertices'], 'analytic-pair/vertices', 0.)
        assert len(points)-len(expected) == len(before['meshes']['a']['geometry']['vertices'])-len(after['meshes']['a']['geometry']['vertices']), 'analytic-pair/removed-count'
        for key in ['edges', 'faces']:
            same({}, after['meshes']['a']['geometry'][key], 'analytic-pair/'+key, 0.)
    for name in spec['data_sharing']:
        mesh = after['meshes'][name]
        world = {key: world_point(after['objects'][name]['matrix_world'], point) for key, point in mesh['geometry']['vertices'].items()}
        same(world, mesh['world_vertices'], 'after-physical-world/'+name, 0.)


def same(expected, actual, path, limit=1e-6):
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and set(expected) == set(actual), (path, 'fields differ')
        for key in expected: same(expected[key], actual[key], path+'/'+str(key), limit)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(expected) == len(actual), (path, 'length differs')
        for i, (a, b) in enumerate(zip(expected, actual)): same(a, b, path+'/'+str(i), limit)
    elif type(expected) is float:
        assert type(actual) is float and math.isfinite(expected) and math.isfinite(actual), (path, 'float differs')
        assert abs(expected-actual) <= limit, (path, expected, actual, abs(expected-actual), limit)
    else:
        assert type(actual) is type(expected) and expected == actual, (path, expected, actual)


def initial(spec, state):
    ctx = spec['object_context']; owners = ctx['edit_objects']
    same(ctx['active'], state['active_object'], 'active', 0.)
    same('EDIT_MESH', state['mode'], 'mode', 0.)
    expected_context = {'view_layer_order': ctx['order'],
                        'edit_objects': [name for name in ctx['order'] if name in owners],
                        'unique_data_iteration': owners, 'python_unique_data_objects': owners}
    same(expected_context, state['edit_context'], 'edit-context', 0.)
    same([['a', 'alias'], ['b'], ['untouched']], state['sharing'], 'sharing', 0.)
    frames = spec['entity_frames']; bases = {}
    for name, frame in frames.items():
        t = frame['transform']
        bases[name] = matrix({'location': t['translation'], 'scale': t['scale']},
                             {'mode': t['rotation']['order'].upper(), 'euler': t['rotation']['angles']})
    def world(name):
        parent = frames[name]['parent']
        return compose(world(parent), bases[name]) if parent else bases[name]
    approved_singular_queries = []
    for name, frame in frames.items():
        obj = state['objects'][name]; t = frame['transform']; parent = frame['parent']
        for field, value in [('parent', parent), ('location', t['translation']), ('rotation', t['rotation']['angles']),
                              ('scale', t['scale']), ('rotation_mode', t['rotation']['order'].upper()),
                              ('selected', name in ctx['selected']), ('mode', 'EDIT' if name in owners else 'OBJECT')]:
            same(value, obj[field], name+'/'+field, 0.)
        same(bases[name], obj['matrix_basis'], name+'/basis')
        same(world(name), obj['matrix_world'], name+'/world')
        if parent and 0. in frames[parent]['transform']['scale']:
            approved_singular_queries.append({'entity': name, 'classification': 'cannot_invert',
                                              'raw_source_matrix_local': obj['matrix_local'], 'numeric_match_claimed': False})
        else: same(bases[name], obj['matrix_local'], name+'/local')
    edited = {spec['data_sharing'][name] for name in owners}
    for name, data in spec['data_sharing'].items():
        authored = spec['mesh_assets'][data]; actual = state['meshes'][name]; g = actual['geometry']
        reference = custom_fans(authored) if authored.get('custom_corner_normals') else None
        fields = {'vertices': authored['vertices'], 'edges': {i: sorted(p) for i, p in authored['edges'].items()},
                  'faces': {i: p['vertices'] for i, p in authored['polygons'].items()},
                  'face_smooth': {i: p['smooth'] for i, p in authored['polygons'].items()},
                  'face_materials': {i: p['material_slot'] for i, p in authored['polygons'].items()},
                  'edge_seams': {i: i in authored['edge_seams'] for i in authored['edges']},
                  'edge_sharp': {i: i in (reference['sharp_edges'] if reference else authored['sharp_edges']) for i in authored['edges']},
                  'material_slots': authored['material_slots'],
                  'uv_layers': {layer: {i: p['uv_layers'][layer] for i, p in authored['polygons'].items()}
                                for layer in authored['uv_layout']['layers']},
                  'uv_layer_order': authored['uv_layout']['layers'],
                  'active_uv_index': authored['uv_layout']['layers'].index(authored['uv_layout']['active'])}
        same(fields, {key: g[key] for key in fields}, name+'/geometry', 0.)
        same({'names': authored['vertex_groups'], 'weights': authored['vertex_weights']}, actual['groups'], name+'/groups', 0.)
        same({domain: authored['integer_attributes'][table] for domain, table in
              [('VERT', 'vertices'), ('EDGE', 'edges'), ('FACE', 'polygons')]}, actual['integer_attributes'], name+'/integers', 0.)
        same(data in edited, actual['data_edit_mode'], name+'/edit-data', 0.)
        intended = selection(authored, spec, data in edited)
        for key in ['selected', 'hidden', 'history', 'active_face']: same(intended[key], actual[key], name+'/'+key, 0.)
        same(spec['mode'] if data in edited else [], actual['mode'], name+'/mask', 0.)
        expected_world = {i: world_point(state['objects'][name]['matrix_world'], p) for i, p in authored['vertices'].items()}
        same(expected_world, actual['world_vertices'], name+'/physical-world', 0.)
        if authored.get('custom_corner_normals'):
            same(True, actual['custom_normals_present'], name+'/custom-present', 0.)
            same(reference['encoded'], actual['packed_custom_normals'], name+'/encoded-custom-normal', 0.)
            same(reference['decoded'], actual['normals']['corners'], name+'/source-decoded-custom-normal')
    return approved_singular_queries


def check(suite_path, capture):
    suite = json.loads(suite_path.read_text()); manifest = json.loads((capture/'manifest.json').read_text())
    authored_suite(suite)
    parent = capture.parent
    receipt(manifest, json.loads((parent/'started.json').read_text()), json.loads((parent/'terminal.json').read_text()),
            (parent/'stdout').read_bytes(), (parent/'stderr').read_bytes())
    membership(suite, manifest, capture)
    sha = lambda b: hashlib.sha256(b).hexdigest()
    assert all(sha(Path(name).read_bytes()) == digest for name, digest in manifest['input_hashes'].items())
    records = []
    for run, row in zip(suite['runs'], manifest['runs']):
        path = capture/row['file']; compressed = path.read_bytes(); raw = gzip.decompress(compressed)
        assert sha(compressed) == row['sha256'] and sha(raw) == row['raw_sha256']
        value = json.loads(raw); assert value['run'] == run
        spec = scene(suite, run); same(spec, value['scene_spec'], run['id']+'/authored-input', 0.)
        native = gzip.decompress((capture/value['native_file_stored']).read_bytes())
        assert sha(native) == value['native_file_sha256'] and len(native) == value['native_file_bytes']
        assert value['save_status'] == value['reopen_status'] == ['FINISHED']
        conversion = converted(run['parameters'])
        if conversion['classification'] == 'rejected_no_operation':
            assert value['result']['status'] == ['OPERATOR_EXCEPTION'] and value['result']['error_type'] == 'TypeError'
            assert conversion['parameter'] in value['result']['error'], 'source input rejection parameter'
        else:
            assert value['result'] == {'status': ['FINISHED'], 'error': None}
        errors = []
        try: classifications = initial(spec, value['before'])
        except AssertionError as error: errors.append(str(error)); classifications = []
        try: postconditions(run, spec, value['before'], value['after'])
        except AssertionError as error: errors.append(str(error))
        try:
            for name in spec['data_sharing']:
                for key in ['geometry', 'groups', 'source_component_ids', 'integer_attributes', 'normals']:
                    same(value['after']['meshes'][name][key], value['reloaded']['meshes'][name][key], name+'/reload/'+key)
        except AssertionError as error: errors.append(str(error))
        records.append({'id': run['id'], 'purpose': run['purpose'], 'checks_passed': not errors,
                        'errors': errors, 'approved_singular_local_queries': classifications,
                        'operation_classification': conversion['classification']})
    return {'diagnostic_checks_passed': all(r['checks_passed'] for r in records), 'cases': len(records),
            'records': records, 'comparison_limit': 1e-6, 'discrete': 'exact',
            'full_source_gate': 'unrun', 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    result = check(args.suite, args.capture)
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result), flush=True)
    raise SystemExit(0 if result['diagnostic_checks_passed'] else 1)
