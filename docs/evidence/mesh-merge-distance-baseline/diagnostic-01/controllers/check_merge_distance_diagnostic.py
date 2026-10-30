"""Bind diagnostic native captures to inputs. Do not accept the full source gate."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from compare_snap_rotation_reference import matrix, compose
from compare_snap_delta_reference import world_point
from merge_distance_scene_inputs import scene, selection


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
        fields = {'vertices': authored['vertices'], 'edges': {i: sorted(p) for i, p in authored['edges'].items()},
                  'faces': {i: p['vertices'] for i, p in authored['polygons'].items()},
                  'face_smooth': {i: p['smooth'] for i, p in authored['polygons'].items()},
                  'face_materials': {i: p['material_slot'] for i, p in authored['polygons'].items()},
                  'edge_seams': {i: i in authored['edge_seams'] for i in authored['edges']},
                  'edge_sharp': {i: i in authored['sharp_edges'] for i in authored['edges']},
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
            same(authored['custom_corner_normals'], actual['normals']['corners'], name+'/requested-custom-normal')
    return approved_singular_queries


def check(suite_path, capture):
    suite = json.loads(suite_path.read_text()); manifest = json.loads((capture/'manifest.json').read_text())
    assert manifest['background'] is False and manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880'
    assert [r['id'] for r in manifest['runs']] == [r['id'] for r in suite['runs']]
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
        assert value['result'] == {'status': ['FINISHED'], 'error': None}
        errors = []
        try: classifications = initial(spec, value['before'])
        except AssertionError as error: errors.append(str(error)); classifications = []
        try:
            for name in spec['data_sharing']:
                for key in ['geometry', 'groups', 'source_component_ids', 'integer_attributes', 'normals']:
                    same(value['after']['meshes'][name][key], value['reloaded']['meshes'][name][key], name+'/reload/'+key)
        except AssertionError as error: errors.append(str(error))
        records.append({'id': run['id'], 'purpose': run['purpose'], 'checks_passed': not errors,
                        'errors': errors, 'approved_singular_local_queries': classifications})
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
