#!/usr/bin/env python3
"""Apply the human-approved unavailable local-query rule to complete source data."""
import argparse
from collections import Counter
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

from compare_snap_singular_reference import (ROOT, BINARY, require, tree, floats, f32,
    selection_input, IDENTITY, snapped, matrix, compose, SELECTION, finite,
    delta_matrix, authored_objects, world_point, effective_suite, validate_state,
    check_local, provenance_inputs, author)

POLICY = ROOT / 'docs/contracts/snap-singular-local-matrix-policy.md'
UNAVAILABLE = {'singular_snap_' + str(i).zfill(4) for i in
               [581, 583, 591, 593, 601, 603, 1549, 1551, 1553, 1555, 1557, 1559]}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind_initial(suite, run, state):
    suite = effective_suite(suite, run)
    profiles, parents, rotations, deltas, basis = authored_objects(suite, run)
    c = run['context']
    require(set(state['objects']) == set(profiles) == set(state['rotation_channels'])
            == set(state['delta_channels']), 'authored object identity differs')
    require(state['active_object'] == 'target' and state['mode'] == run['mode'], 'authored mode differs')
    require(state['sharing'] == [['secondary', 'target']], 'authored sharing differs')
    tree(floats(run['rotations']['cursor']), state['cursor_channels'], 'authored cursor channels', 0.)
    tree(floats(c['cursor_location']), state['cursor']['location'], 'authored cursor location', 0.)

    def world(name):
        return basis[name] if parents[name] is None else compose(world(parents[name]), basis[name])

    for name, p in profiles.items():
        o = state['objects'][name]; primary = name in ['target', 'secondary']
        normal = rotations[name]; delta = deltas[name]
        expected = {**floats(normal), 'lock_rotation': c['lock_rotation'] if primary else [False] * 3,
            'lock_rotation_w': run['rotations']['lock_rotation_w'] if primary else False,
            'lock_rotations_4d': run['rotations']['lock_rotations_4d'] if primary else False,
            'delta_euler': floats(delta['euler']), 'delta_quaternion_wxyz': floats(delta['quaternion_wxyz'])}
        tree(expected, state['rotation_channels'][name], name + '/authored channels', 0.)
        tree(floats(delta), state['delta_channels'][name], name + '/authored delta', 0.)
        require(o['parent'] == parents[name] and o['rotation_mode'] == normal['mode'], 'authored frame differs')
        require(o['type'] == ('MESH' if primary else 'EMPTY'), 'authored object kind differs')
        require(o['selected'] == primary, 'authored object selection differs')
        require(o['mode'] == ('EDIT' if name == 'target' and run['mode'] == 'EDIT_MESH' else 'OBJECT'), 'edit owner differs')
        for field in ['location', 'scale']:
            tree(floats(p[field]), o[field], name + '/' + field, 0.)
        for field, expected in [('lock_location', c['lock_location'] if primary else [False] * 3),
                                ('lock_scale', [False] * 3)]:
            tree(expected, o[field], name + '/' + field, 0.)
        require(not o['animation_data'] and o['constraints'] == o['modifiers'] == 0, 'unexpected dependencies')
        tree(basis[name], o['matrix_basis'], name + '/authored basis')
        tree(IDENTITY, o['matrix_parent_inverse'], name + '/authored inverse', 0.)
        tree(world(name), o['matrix_world'], name + '/authored world')
    edit = run['mode'] == 'EDIT_MESH'
    expected = selection_input(suite['mesh'], run, edit)
    require(set(state['meshes']) == {'target', 'secondary'}, 'authored mesh set differs')
    for name, m in state['meshes'].items():
        tree(expected, {k: m[k] for k in SELECTION}, name + '/authored geometry', 0.)
        require(m['data_edit_mode'] == edit, 'authored shared edit state differs')
        for id, p in expected['geometry']['vertices'].items():
            tree(world_point(world(name), p), m['world_vertices'][id], name + '/authored world vertex/' + id)
    for key, value in [('skip_children', c['skip_children']), ('origins_only', c['origins_only'])]:
        require(state['settings'][key] == value, 'authored settings differ')


def validate_run(suite, run, data):
    require(set(data) == {'run', 'before', 'after', 'result'}, 'capture fields differ')
    require(data['run'] == run, 'authored request differs'); finite(data)
    require(data['result']['status'] in [['FINISHED'], ['CANCELLED']] and data['result']['error'] is None,
            'source operator error/unknown outcome')
    before, after = data['before'], data['after']
    if data['result']['status'] == ['CANCELLED']:
        tree(before, after, 'cancelled source mutation', 0.)
    bind_initial(suite, run, before)
    for state in [before, after]:
        require(set(state) == {'mode', 'objects', 'meshes', 'sharing', 'active_object', 'cursor',
            'cursor_metres', 'physical_metres_factor', 'settings', 'rotation_channels', 'cursor_channels',
            'delta_channels'}, 'snapshot fields differ')
        require(state['physical_metres_factor'] == 1., 'physical units differ')
        require(set(state['objects']) == set(before['objects']), 'object identity changed')
        basis = {}
        for name, o in state['objects'].items():
            require(set(o) == {'type', 'mode', 'parent', 'location', 'rotation', 'rotation_mode',
                'scale', 'matrix_world', 'matrix_basis', 'matrix_parent_inverse',
                'delta_location', 'delta_rotation', 'delta_scale', 'lock_location', 'lock_rotation',
                'lock_scale', 'selected', 'animation_data', 'constraints', 'modifiers'}, 'object fields differ')
            r = state['rotation_channels'][name]; d = state['delta_channels'][name]
            require(set(r) == {'mode', 'euler', 'quaternion_wxyz', 'axis_angle', 'lock_rotation',
                'lock_rotation_w', 'lock_rotations_4d', 'delta_euler', 'delta_quaternion_wxyz'}, 'channel fields differ')
            require(set(d) == {'location', 'euler', 'quaternion_wxyz', 'scale'}, 'delta fields differ')
            tree(r['euler'], o['rotation'], 'actual Euler', 0.)
            require(r['mode'] == o['rotation_mode'], 'actual rotation mode differs')
            tree(r['lock_rotation'], o['lock_rotation'], 'actual rotation locks', 0.)
            for a, b in [('location', 'delta_location'), ('euler', 'delta_rotation'), ('scale', 'delta_scale')]:
                tree(d[a], o[b], 'actual delta/' + b, 0.)
            for a, b in [('euler', 'delta_euler'), ('quaternion_wxyz', 'delta_quaternion_wxyz')]:
                tree(d[a], r[b], 'actual duplicate delta/' + b, 0.)
            basis[name] = delta_matrix(o, r, d)
            tree(basis[name], o['matrix_basis'], name + '/evaluated basis')

        def world(name):
            o = state['objects'][name]
            return basis[name] if o['parent'] is None else compose(
                compose(world(o['parent']), o['matrix_parent_inverse']), basis[name])

        for name, o in state['objects'].items():
            tree(world(name), o['matrix_world'], name + '/evaluated world')
        cursor = state['cursor_channels']
        require(set(state['cursor']) == {'location', 'rotation', 'rotation_mode', 'matrix'}, 'cursor fields differ')
        require(set(cursor) == {'mode', 'euler', 'quaternion_wxyz', 'axis_angle'}, 'cursor channels differ')
        require(cursor['mode'] == state['cursor']['rotation_mode'], 'cursor mode differs')
        tree(cursor['euler'], state['cursor']['rotation'], 'cursor Euler', 0.)
        tree(matrix({'location': state['cursor']['location'], 'scale': [1.] * 3}, cursor),
             state['cursor']['matrix'], 'evaluated cursor')
        tree(state['cursor']['location'], state['cursor_metres'], 'physical cursor', 0.)
        for name, m in state['meshes'].items():
            require(set(m) == set(SELECTION) | {'data_edit_mode', 'active_material_index', 'flags',
                'normals', 'world_vertices', 'vertices_metres', 'world_vertices_metres'}, 'mesh fields differ')
            selected = {k: m[k] for k in SELECTION}
            if not m['data_edit_mode']:
                selected = {**selected, 'mode': run['initial_mode']}
            validate_state(selected)
            for id, p in m['geometry']['vertices'].items():
                tree(p, m['vertices_metres'][id], 'local physical', 0.)
                for key in ['world_vertices', 'world_vertices_metres']:
                    tree(world_point(state['objects'][name]['matrix_world'], p), m[key][id], 'actual world vertex', 0.)
            for id, face in m['geometry']['faces'].items():
                require(len(m['normals']['corners'][id]) == len(face), 'corner normal count differs')
                for n in [m['normals']['faces'][id], *m['normals']['corners'][id]]:
                    require(len(n) == 3 and (sum(v*v for v in n) <= 1e-12
                        or abs(math.sqrt(sum(v*v for v in n)) - 1) <= 1e-6), 'invalid normal')
        for field in SELECTION + ['data_edit_mode', 'normals', 'flags']:
            tree(state['meshes']['target'][field], state['meshes']['secondary'][field], 'shared/' + field, 0.)
    for key in ['sharing', 'active_object', 'mode', 'settings']:
        tree(before[key], after[key], 'preserved/' + key, 0.)
    tree(before['delta_channels'], after['delta_channels'], 'unchanged delta channels', 0.)
    for name, old in before['objects'].items():
        for field in set(old) - {'location', 'rotation', 'matrix_world', 'matrix_basis', 'matrix_parent_inverse'}:
            tree(old[field], after['objects'][name][field], 'preserved object/' + field, 0.)
    for name, old in before['rotation_channels'].items():
        new = after['rotation_channels'][name]
        for key in ['mode', 'lock_rotation', 'lock_rotation_w', 'lock_rotations_4d', 'delta_euler', 'delta_quaternion_wxyz']:
            tree(old[key], new[key], 'preserved rotation metadata/' + key, 0.)
        preserve = run['operator'] != 'snap_selected_to_cursor' or not run['parameters']['use_rotation'] \
            or run['mode'] == 'EDIT_MESH' or name not in ['target', 'secondary']
        active = 'quaternion_wxyz' if old['mode'] == 'QUATERNION' else 'axis_angle' if old['mode'] == 'AXIS_ANGLE' else 'euler'
        for field in ['euler', 'quaternion_wxyz', 'axis_angle']:
            if preserve or field != active:
                tree(old[field], new[field], 'preserved raw rotation/' + field, 0.)
        locks = [old['lock_rotation_w'], *old['lock_rotation']] if active != 'euler' else old['lock_rotation']
        for i, locked in enumerate(locks):
            if locked:
                tree(old[active][i], new[active][i], 'protected rotation', 0.)
        for i, locked in enumerate(before['objects'][name]['lock_location']):
            if locked:
                tree(before['objects'][name]['location'][i], after['objects'][name]['location'][i], 'protected location', 0.)
    if run['operator'].startswith('snap_selected'):
        tree(before['cursor'], after['cursor'], 'unchanged cursor', 0.)
        tree(before['cursor_channels'], after['cursor_channels'], 'unchanged cursor channels', 0.)
    elif run['operator'] == 'snap_cursor_to_center':
        tree(IDENTITY, after['cursor']['matrix'], 'origin cursor')
    else:
        tree(before['cursor_channels'], after['cursor_channels'], 'preserved cursor rotation', 0.)
        if run['operator'] == 'snap_cursor_to_grid':
            tree(snapped(before['cursor']['location'], .75), after['cursor']['location'], 'analytic grid', 0.)
    for name, old in before['meshes'].items():
        for field in ['groups', 'selected', 'hidden', 'mode', 'history', 'active_face', 'data_edit_mode', 'flags', 'active_material_index']:
            tree(old[field], after['meshes'][name][field], 'preserved mesh/' + field, 0.)
        for field in old['geometry']:
            if field != 'vertices' or (run['mode'] == 'OBJECT' and not run['context']['origins_only']):
                tree(old['geometry'][field], after['meshes'][name]['geometry'][field], 'preserved geometry/' + field, 0.)


def numeric_matrix(value):
    return isinstance(value, list) and len(value) == 4 and all(
        isinstance(row, list) and len(row) == 4 and all(
            type(v) in [int, float] and math.isfinite(v) for v in row) for row in value)


def local_queries(suite, run, data):
    counts = Counter(); tags = []
    if run['id'] in UNAVAILABLE:
        require(run['zero_scale']['role'] == 'parent' and run['zero_scale']['mask'] == 4
                and run['zero_scale']['channel'] in ['normal', 'delta']
                and run['rotations']['objects']['mode'] in ['YXZ', 'YZX', 'ZXY']
                and run['operator'] == 'snap_selected_to_cursor'
                and run['parameters']['use_rotation'] is True,
                'approved local-query input witness differs')
    for side in ['before', 'after']:
        state = data[side]
        require(numeric_matrix(state['cursor']['matrix']), 'invalid cursor matrix type')
        for name, obj in state['objects'].items():
            for field in ['matrix_world', 'matrix_basis', 'matrix_parent_inverse']:
                require(numeric_matrix(obj[field]), 'invalid physical matrix type/' + field)
            local = obj['matrix_local']
            unavailable = run['id'] in UNAVAILABLE and side == 'after' and name == 'child'
            if unavailable:
                require(isinstance(local, list) and len(local) == 4
                        and all(isinstance(row, list) and len(row) == 4 for row in local),
                        'unavailable getter shape differs')
                for i, row in enumerate(local):
                    for j, item in enumerate(row):
                        path = f'/after/objects/child/matrix_local/{i}/{j}'
                        expected = {'path': path, 'repr': 'nan',
                            'f32_little_endian_hex': '0000c07f',
                            'f64_little_endian_hex': '000000000000f87f'}
                        require(item == {'__source_nonfinite_diagnostic__': expected},
                                'approved unavailable getter tag/path/bits differ')
                        tags.append(expected)
                counts['unavailable_local_queries'] += 1
            else:
                require(numeric_matrix(local), 'unapproved unavailable/non-numeric local getter')
                basis = delta_matrix(obj, state['rotation_channels'][name], state['delta_channels'][name])
                check_local(suite, run, name, state, basis)
                counts['available_numeric_local_queries'] += 1
    return counts, tags


def physical_channel(data):
    """Separate the getter channel; never substitute a numeric matrix."""
    result = copy.deepcopy(data)
    for side in ['before', 'after']:
        for obj in result[side]['objects'].values():
            del obj['matrix_local']
    return result


def compare_case(suite, run, first, second):
    outcomes = []
    for value in [first, second]:
        require(value['run'] == run, 'authored source request differs')
        counts, tags = local_queries(suite, run, value)
        validate_run(suite, run, physical_channel(value))
        outcomes.append((counts, tags))
    tree(first, second, 'complete raw capture/' + run['id'])
    require(outcomes[0] == outcomes[1], 'local-query outcome differs')
    return outcomes[0]


def validate_capture(folder, manifest, suite_path, receipts):
    require(manifest['schema_version'] == 1 and manifest['product'] == 'blender'
            and manifest['product_acceptance'] == 'unrun', 'source identity differs')
    require(type(manifest['process_id']) is int and manifest['process_id'] > 0, 'invalid process ID')
    require(manifest['scope'] == 'all_1764_nonfinite_diagnostic_NOT_ACCEPTANCE'
            and not manifest['background'], 'incomplete/native capture mode differs')
    require(manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880'
            and manifest['binary_sha256'] == BINARY, 'fixed source binary differs')
    suite = json.loads(suite_path.read_text()); ids = [r['id'] for r in suite['runs']]
    require([r['id'] for r in manifest['runs']] == ids, 'missing/reordered source case')
    require({p.name for p in folder.glob('*.json.gz')} == {i + '.json.gz' for i in ids}, 'artifact set differs')
    require(digest(folder / 'operator-properties.json') == manifest['operator_properties_sha256'], 'RNA hash differs')
    matching = [r for r in receipts if r['process_id'] == manifest['process_id']]
    require(len(matching) == 1 and matching[0]['terminal_exit_code'] == 0, 'native terminal exit missing/failed')
    require(matching[0]['manifest_sha256'] == digest(folder / 'manifest.json'), 'terminal manifest differs')
    require(matching[0]['capture_lock_sha256'] == digest(folder / 'capture-lock.json')
            == manifest['capture_lock_sha256'], 'terminal lock differs')
    extra = [(n, s) for n, s in manifest['input_hashes'].items()
             if n.endswith('/tools/blender_snap_singular_diagnostic.py')]
    require(len(extra) == 1 and extra[0][1] == digest(ROOT / 'tools/blender_snap_singular_diagnostic.py'),
            'diagnostic adapter provenance differs')
    original = copy.deepcopy(manifest)
    del original['input_hashes'][extra[0][0]]
    provenance_inputs(folder, original, suite_path)


def compare(suite_path, first, second, receipts_path):
    suite_path = suite_path.resolve()
    first, second, receipts_path = first.resolve(), second.resolve(), receipts_path.resolve()
    suite = json.loads(suite_path.read_text()); require(suite == author(), 'authored suite differs')
    require(Counter(r['label'] for r in suite['runs']) == suite['groups_expected'], 'case families differ')
    require(UNAVAILABLE <= {r['id'] for r in suite['runs']} and len(UNAVAILABLE) == 12, 'approved catalogue differs')
    manifests = [json.loads((p / 'manifest.json').read_text()) for p in [first, second]]
    a, b = manifests
    require(a['process_id'] != b['process_id'], 'same native process')
    require(a['input_hashes'] == b['input_hashes'], 'capture inputs differ')
    require(a['operator_properties_sha256'] == b['operator_properties_sha256'], 'source RNA differs')
    receipts = json.loads(receipts_path.read_text())['runs']
    for folder, manifest in zip([first, second], manifests):
        validate_capture(folder, manifest, suite_path, receipts)
    totals = Counter(); unavailable_cases = []
    for index, run in enumerate(suite['runs']):
        values = []; declared_tags = []
        for folder, manifest in zip([first, second], manifests):
            row = manifest['runs'][index]
            require(row['file'] == run['id'] + '.json.gz', 'artifact path differs')
            path = folder / row['file']; require(digest(path) == row['sha256'], 'stored hash differs')
            raw = gzip.decompress(path.read_bytes())
            require(hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes'],
                    'exact JSON hash differs')
            value = json.loads(raw); require(value['result']['status'] == row['status'], 'manifest status differs')
            values.append(value); declared_tags.append(row['nonfinite_fields'])
        counts, tags = compare_case(suite, run, *values)
        require(declared_tags == [tags, tags], 'declared invalid source fields differ')
        totals.update(counts)
        if counts['unavailable_local_queries']:
            unavailable_cases.append(run['id'])
        if (index + 1) % 250 == 0: print(json.dumps({'compared': index + 1}), flush=True)
    require(set(unavailable_cases) == UNAVAILABLE and totals['unavailable_local_queries'] == 12,
            'approved unavailable-query count differs')
    return {'passed': True, 'approved_local_query_policy_baseline_passed': True,
            'original_strict_capture_passed': False, 'cases': 1764,
            'all_physical_cases_checked': True, **dict(totals),
            'unavailable_local_queries_are_numeric_matches': False,
            'unavailable_cases': unavailable_cases, 'policy_sha256': digest(POLICY),
            'policy_issue_comment': 6513201148, 'native_processes': [m['process_id'] for m in manifests],
            'binary_sha256': BINARY, 'suite_sha256': digest(suite_path),
            'comparison_script_sha256': digest(Path(__file__)),
            'native_terminal_receipts_sha256': digest(receipts_path),
            'position_channel_matrix_limit': 1e-6, 'product_acceptance': 'unrun', 'milestones_accepted': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--first', type=Path, required=True)
    parser.add_argument('--second', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.suite, args.first, args.second, args.receipts)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False); output.write('\n')
    print(json.dumps(result))

