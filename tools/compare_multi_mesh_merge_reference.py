#!/usr/bin/env python3
"""Bind multi-data inputs, validate native outcomes, and compare fresh processes."""
import argparse
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path

from compare_selection_reference import require
from compare_snap_menu_reference import f32, floats, tree, IDENTITY
from compare_snap_rotation_reference import matrix, compose
from compare_transform_reference import finite
from compare_mesh_merge_reference import (validate_state_full, expected_positions,
                                         match_positions)
from generate_multi_mesh_merge_cases import author
from multi_mesh_merge_inputs import input_paths

ROOT = Path(__file__).resolve().parents[1]
BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
DOMAINS = ['VERT', 'EDGE', 'FACE']
TABLES = ['vertices', 'edges', 'faces']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def context(suite, run):
    return next(c for c in suite['contexts'] if c['id'] == run['context'])


def edit_providers(suite, run):
    """Pinned object_edit.cc enters active first, then selected base order."""
    c = context(suite, run)
    order = [c['active'], *[name for name in c['order'] if name != c['active']]]
    seen = set()
    providers = []
    for name in order:
        if name in ['a', 'alias', 'b'] and suite['data_sharing'][name] not in seen:
            providers.append(name)
            seen.add(suite['data_sharing'][name])
    return providers


def selected_data(suite, run, data):
    active = suite['data_sharing'][context(suite, run)['active']] == data
    return run['selection'] == 'both' or (run['selection'] == 'active_empty' and not active) or (
        run['selection'] == 'other_empty' and active)


def authored_history(suite, run, data):
    if not selected_data(suite, run, data):
        return []
    asset = suite['mesh_assets'][data]
    verts, edges = list(asset['vertices']), list(asset['edges'])
    active = suite['data_sharing'][context(suite, run)['active']] == data
    pattern = run['history']
    if pattern == 'both_reverse':
        return [{'domain': 'VERT', 'id': verts[-1]}, {'domain': 'VERT', 'id': verts[0]}]
    if pattern == 'active_first_only' and active:
        return [{'domain': 'VERT', 'id': verts[0]}, {'domain': 'EDGE', 'id': edges[-1]}]
    if pattern == 'active_last_only' and active:
        return [{'domain': 'EDGE', 'id': edges[0]}, {'domain': 'VERT', 'id': verts[-1]}]
    if (pattern == 'active_none' and active) or (pattern == 'other_none' and not active):
        return []
    return [{'domain': 'VERT', 'id': verts[0]}, {'domain': 'VERT', 'id': verts[-1]}]


def bind_mesh(asset, actual, run, data, suite):
    polygons = asset['polygons']
    expected = {
        'vertices': floats(asset['vertices']),
        'edges': {id: sorted(pair) for id, pair in asset['edges'].items()},
        'faces': {id: p['vertices'] for id, p in polygons.items()},
        'face_smooth': {id: p['smooth'] for id, p in polygons.items()},
        'face_materials': {id: p['material_slot'] for id, p in polygons.items()},
        'edge_seams': {id: id in asset['edge_seams'] for id in asset['edges']},
        'material_slots': asset['material_slots'],
        'uv_layers': {layer: {id: floats(p['uv_layers'][layer]) for id, p in polygons.items()}
                      for layer in asset['uv_layout']['layers']},
        'uv_layer_order': asset['uv_layout']['layers'],
        'active_uv_index': asset['uv_layout']['layers'].index(asset['uv_layout']['active']),
    }
    tree(expected, actual['geometry'], 'authored/' + data, 0.)
    tree({'names': asset['vertex_groups'], 'weights': floats(asset['vertex_weights'])},
         actual['groups'], 'authored groups/' + data, 0.)
    integers = {domain: asset['integer_attributes'][table]
                for domain, table in zip(DOMAINS, ['vertices', 'edges', 'polygons'])}
    tree(integers, actual['integer_attributes'], 'authored integers/' + data, 0.)
    edit = data in suite['active_edit_data']
    require(actual['data_edit_mode'] == edit, 'authored mesh edit mode differs')
    selected = edit and selected_data(suite, run, data)
    for domain, table in zip(DOMAINS, TABLES):
        ids = list(expected[table])
        require(actual['selected'][domain] == (sorted(ids) if selected else []), 'authored selection differs')
        require(actual['hidden'][domain] == [], 'unexpected hidden input')
    require(actual['history'] == (authored_history(suite, run, data) if edit else []),
            'authored typed history differs')
    require(actual['active_face'] == (list(polygons)[-1] if selected else None), 'authored active face differs')
    require(actual['mode'] == (run['mode'] if edit else []), 'authored mask differs')
    require(actual['active_material_index'] == 0, 'authored active material differs')
    require(actual['flags'] == dict(mirror_x=False, mirror_y=False, mirror_z=False,
                                   mirror_topology=False), 'unexpected mesh flags')


def bind_initial(suite, run, state):
    c = context(suite, run)
    providers = edit_providers(suite, run)
    require(set(state['objects']) == set(c['order']), 'authored object identity differs')
    require(set(state['meshes']) == set(suite['data_sharing']), 'authored mesh users differ')
    require(state['active_object'] == c['active'] and state['mode'] == 'EDIT_MESH', 'active edit context differs')
    require(state['sharing'] == [['a', 'alias'], ['b'], ['untouched']], 'authored data sharing differs')
    require(state['edit_context'] == {
        'view_layer_order': c['order'],
        'edit_objects': [name for name in c['order'] if name in providers],
        'unique_data_iteration': providers,
        'python_unique_data_objects': providers,
    }, 'authored edit provider membership/order differs')
    frames = suite['entity_frames'][run['frame']]
    bases = {name: matrix({'location': frame['transform']['translation'],
                           'scale': frame['transform']['scale']},
                          {'mode': frame['transform']['rotation']['order'].upper(),
                           'euler': frame['transform']['rotation']['angles']})
             for name, frame in frames.items()}

    def world(name):
        parent = frames[name]['parent']
        return bases[name] if parent is None else compose(world(parent), bases[name])

    for name, frame in frames.items():
        actual = state['objects'][name]
        transform = frame['transform']
        require(actual['type'] == ('EMPTY' if name == 'parent' else 'MESH'), 'authored object type differs')
        require(actual['parent'] == frame['parent'], 'authored parent differs')
        require(actual['selected'] == (name in ['a', 'b', 'alias']), 'authored object selection differs')
        require(actual['mode'] == ('EDIT' if name in providers else 'OBJECT'), 'edit owner differs')
        require(actual['rotation_mode'] == transform['rotation']['order'].upper(), 'authored Euler order differs')
        for field, expected in [('location', transform['translation']),
                                ('rotation', transform['rotation']['angles']), ('scale', transform['scale'])]:
            tree(floats(expected), actual[field], name + '/' + field, 0.)
        for field in ['matrix_basis', 'matrix_local']:
            tree(bases[name], actual[field], name + '/' + field)
        tree(world(name), actual['matrix_world'], name + '/world')
        tree(IDENTITY, actual['matrix_parent_inverse'], name + '/parent inverse', 0.)
        for field, expected in [('delta_location', [0.] * 3), ('delta_rotation', [0.] * 3),
                                ('delta_scale', [1.] * 3)]:
            tree(expected, actual[field], name + '/' + field, 0.)
        require(not actual['animation_data'] and actual['constraints'] == actual['modifiers'] == 0,
                'unexpected object dependencies')
        require(all(actual[field] == [False] * 3 for field in ['lock_location', 'lock_rotation', 'lock_scale']),
                'unexpected object locks')
    for name, data in suite['data_sharing'].items():
        bind_mesh(suite['mesh_assets'][data], state['meshes'][name], run, data, suite)
    tree(floats(suite['materials']), state['materials'], 'authored materials', 0.)
    for field, key in [('location', 'cursor_location'), ('rotation', 'cursor_rotation')]:
        tree(floats(suite['authoring_context'][key]), state['cursor'][field], 'authored cursor/' + field, 0.)
    expected_settings = {
        'pivot': 'MEDIAN_POINT', 'skip_children': False, 'correct_face_attributes': False,
        'keep_connected': False, 'automerge': False, 'automerge_and_split': False,
        'origins_only': False, 'autokey': False, 'locations_only': False,
        'unit_system': 'NONE', 'unit_scale_length': 1., 'grid_spacing': 1.,
        'grid_subdivisions': 10, 'view_perspective': 'ORTHO', 'view_location': [0., 0., 0.],
        'view_distance': 10.,
    }
    for key, expected in expected_settings.items():
        tree(expected, state['settings'][key], 'authored settings/' + key, 0.)


def validate_state(suite, run, state):
    # Keep all single-data geometry, finite, normals, world-coordinate and
    # sharing checks. Strip only fields newly checked below.
    reduced = {k: v for k, v in state.items() if k not in ['edit_context', 'materials']}
    reduced['meshes'] = {name: {k: v for k, v in mesh.items() if k != 'integer_attributes'}
                         for name, mesh in state['meshes'].items()}
    validate_state_full(reduced, {'context': suite['units'], 'initial_mode': run['mode']})
    finite(state)
    for name, actual in state['meshes'].items():
        data = suite['data_sharing'][name]
        asset = suite['mesh_assets'][data]
        integers = actual['integer_attributes']
        require(set(integers) == set(DOMAINS), 'integer domains differ')
        for domain, table, authored_table, tag in zip(
                DOMAINS, TABLES, ['vertices', 'edges', 'polygons'],
                ['formora_v_id', 'formora_e_id', 'formora_f_id']):
            require(set(integers[domain]) == set(asset['integer_attributes'][authored_table]),
                    'integer layer names differ')
            for layer, values in integers[domain].items():
                require(set(values) == set(actual['geometry'][table]), 'integer IDs differ')
                require(all(type(value) is int and -(2**31) <= value < 2**31 for value in values.values()),
                        'invalid signed integer value')
            require(integers[domain][tag] == actual['source_component_ids'][domain], 'integer capture tag differs')
    tree(state['meshes']['a']['integer_attributes'], state['meshes']['alias']['integer_attributes'],
         'shared integer layers', 0.)


def validate_run(suite, run, data):
    require(set(data) == {'run', 'before', 'after', 'result'} and data['run'] == run, 'authored request differs')
    before, after = data['before'], data['after']
    bind_initial(suite, run, before)
    validate_state(suite, run, before)
    validate_state(suite, run, after)
    for key in set(before) - {'meshes'}:
        tree(before[key], after[key], 'preserved context/' + key, 0.)
    if run['expected_enum_unavailable']:
        result = data['result']
        require(set(result) == {'status', 'error'} and result['status'] == ['ENUM_REJECTED']
                and isinstance(result['error'], str) and 'enum' in result['error'].lower(),
                'predicted enum rejection differs')
        tree(before, after, 'rejected mutation', 0.)
        return {'enum_rejected': 1, 'changed_data': 0, 'unchanged_data': 3, 'skipped_data': 2}
    require(data['result'] == {'status': ['FINISHED'], 'error': None}, 'unexpected native result')
    processed = []
    for name in edit_providers(suite, run):
        mesh = before['meshes'][name]
        if not mesh['selected']['VERT']:
            continue
        method = run['parameters']['type']
        if method in ['FIRST', 'LAST']:
            endpoint = mesh['history'][0 if method == 'FIRST' else -1] if mesh['history'] else None
            if endpoint is None or endpoint['domain'] != 'VERT' or endpoint['id'] not in mesh['selected']['VERT']:
                continue
        processed.append(name)
        if method in ['FIRST', 'LAST']:
            break
    changed_data = set()
    processed_data = {suite['data_sharing'][name] for name in processed}
    for name, data_name in suite['data_sharing'].items():
        initial, final = before['meshes'][name], after['meshes'][name]
        if data_name not in processed_data:
            tree(initial, final, 'unprocessed data/' + name, 0.)
            continue
        owner = next(owner for owner in processed if suite['data_sharing'][owner] == data_name)
        mesh = copy.deepcopy(before['meshes'][owner])
        if run['parameters']['type'] in ['FIRST', 'LAST']:
            endpoint = mesh['history'][0 if run['parameters']['type'] == 'FIRST' else -1]
            mesh['history'] = [endpoint]
        shim = {'meshes': {'target': mesh}, 'objects': {'target': before['objects'][owner]},
                'cursor': before['cursor']}
        expected = expected_positions(run, shim)
        match_positions(expected, list(final['geometry']['vertices'].values()))
        if initial['geometry'] != final['geometry']:
            changed_data.add(data_name)
        for key in ['data_edit_mode', 'mode', 'flags', 'active_material_index']:
            tree(initial[key], final[key], 'preserved mesh/' + key, 0.)
        for key in ['material_slots', 'uv_layer_order', 'active_uv_index']:
            tree(initial['geometry'][key], final['geometry'][key], 'preserved layout/' + key, 0.)
        tree(initial['groups']['names'], final['groups']['names'], 'preserved group names', 0.)
        if 'VERT' not in run['mode']:
            require(all(not ids for ids in final['selected'].values()), 'nonvertex merge retained selection')
    return {'enum_rejected': 0, 'changed_data': len(changed_data), 'unchanged_data': 3-len(changed_data),
            'skipped_data': 2-len(processed_data)}


def load_capture(folder, suite_path, runs, focused):
    manifest = json.loads((folder / 'manifest.json').read_text())
    require(manifest['schema_version'] == 1 and manifest['product'] == 'blender'
            and manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880'
            and manifest['binary_sha256'] == BINARY and manifest['background'] is False,
            'native identity differs')
    require(manifest['product_acceptance'] == 'unrun', 'source capture claimed product acceptance')
    scope = 'focused_diagnostic' if focused else 'complete_13440_multi_data_merge_cases'
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
    require(command[3] == str(ROOT/'tools/blender_multi_mesh_merge_reference.py')
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
    require(suite == author(), 'independently authored inputs differ')
    runs = suite['runs']
    if case_ids:
        require(len(case_ids) == len(set(case_ids)) and set(case_ids) <= {r['id'] for r in runs}, 'unknown/duplicate cases')
        runs = [r for r in runs if r['id'] in case_ids]
    manifests = [load_capture(folder, suite_path, runs, bool(case_ids)) for folder in [first, second]]
    require(manifests[0]['process_id'] != manifests[1]['process_id'], 'source process reused')
    require(manifests[0]['input_hashes'] == manifests[1]['input_hashes'], 'source inputs differ')
    require(manifests[0]['operator_properties_sha256'] == manifests[1]['operator_properties_sha256'], 'source RNA differs')
    counts = Counter()
    for i, run in enumerate(runs):
        values = []
        for folder, manifest in zip([first, second], manifests):
            row = manifest['runs'][i]
            require(row['file'] == run['id']+'.json.gz', 'raw file path differs')
            path = folder/row['file']
            require(digest(path) == row['sha256'], 'stored raw hash differs')
            raw = gzip.decompress(path.read_bytes())
            require(hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes'], 'raw JSON differs')
            value = json.loads(raw)
            require(value['result']['status'] == row['status'], 'manifest result differs')
            values.append(value)
        outcomes = [validate_run(suite, run, value) for value in values]
        tree(values[0], values[1], run['id'])
        require(outcomes[0] == outcomes[1], 'source classification differs')
        counts.update(outcomes[0])
        if (i+1) % 250 == 0:
            print(json.dumps({'compared': i+1, 'total': len(runs)}), flush=True)
    if not case_ids:
        require(counts['enum_rejected'] == 4352 and len(runs)-counts['enum_rejected'] == 9088,
                'frozen source result counts differ')
    return {'source_comparison_passed': True, 'cases': len(runs),
            'complete_source_gate': not bool(case_ids), 'outcomes': dict(counts),
            'native_processes': [m['process_id'] for m in manifests],
            'suite_sha256': digest(suite_path), 'checker_sha256': digest(__file__),
            'numeric_absolute_limit': 1e-6, 'product_acceptance': 'unrun', 'milestones_accepted': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--first', type=Path, required=True)
    parser.add_argument('--second', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[], dest='case_ids')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.suite.resolve(), args.first.resolve(), args.second.resolve(), args.case_ids)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')
    print(json.dumps(result))
