#!/usr/bin/env python3
"""Bind zero-scale source captures to authored inputs and compare native processes."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

from compare_selection_reference import require, validate_state
from compare_snap_menu_reference import f32, floats, tree, selection_input, IDENTITY, snapped
from compare_snap_rotation_reference import rotation_matrix, matrix, compose, SELECTION
from compare_transform_reference import finite
from generate_snap_singular_cases import author, effective_suite

ROOT = Path(__file__).resolve().parents[1]
BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def world_point(world, point):
    # mathutils_Vector.cc column_vector_multiplication accumulates four f32
    # products sequentially in double. Python's compensated sum can differ
    # at an f32 halfway boundary. Preserve the actual source accumulation.
    result = []
    for row in world[:3]:
        dot = 0.
        for a, b in zip(row, [*point, 1.]):
            dot += f32(a * b)
        result.append(f32(dot))
    return result


def delta_matrix(profile, normal, delta):
    """Compose authored channels in pinned source order, without measured frames."""
    r = rotation_matrix(normal)
    d = rotation_matrix({'mode': normal['mode'], 'euler': delta['euler'],
        'quaternion_wxyz': delta['quaternion_wxyz'], 'axis_angle': [0., 0., 1., 0.]})
    # mul_m3_m3m3 uses left-associated f32 scalar products and additions.
    rotation = [[f32(f32(f32(d[i][0] * r[0][j]) + f32(d[i][1] * r[1][j]))
                         + f32(d[i][2] * r[2][j])) for j in range(3)] for i in range(3)]
    scale = [f32(f32(a) * f32(b)) for a, b in zip(profile['scale'], delta['scale'])]
    location = [f32(f32(a) + f32(b)) for a, b in zip(profile['location'], delta['location'])]
    return [[f32(rotation[i][j] * scale[j]) for j in range(3)] + [location[i]]
            for i in range(3)] + [[0., 0., 0., 1.]]


def authored_objects(suite, run):
    profile = suite['profiles'][run['context']['profile']]
    profiles = {'target': profile, **suite['object_inputs']}
    parents = {'target': 'parent' if profile['parent'] else None, 'secondary': None, 'child': 'target'}
    if profile['parent']:
        profiles['parent'] = profile['parent']
        parents['parent'] = None
    rotations = {}; deltas = {}; basis = {}
    for name, p in profiles.items():
        rotations[name] = run['rotations']['objects'] if name in ['target', 'secondary'] else {
            'mode': 'XYZ', 'euler': p['rotation'], 'quaternion_wxyz': [1., 0., 0., 0.],
            'axis_angle': [0., 0., 1., 0.]}
        deltas[name] = run['deltas'] if name in ['target', 'secondary'] else suite['role_deltas'][name]
        basis[name] = delta_matrix(p, rotations[name], deltas[name])
    return profiles, parents, rotations, deltas, basis



def zero_column(matrix):
    return any(all(matrix[row][column] == 0. for row in range(4)) for column in range(3))


def check_local(suite, run, name, state, basis):
    """Check the pinned getter only where the independent oracle is defined.

    Singular dense frames still have every raw component compared across
    processes. No approximate determinant threshold invents an inverse oracle.
    """
    obj = state['objects'][name]
    parent = obj['parent']
    if parent is None:
        expected = basis
    elif zero_column(state['objects'][parent]['matrix_world']):
        expected = [[0.] * 4 for _ in range(4)]
    else:
        # The affected target/parent ancestor can remain singular after a
        # rotation fills its zero column. Keep its raw getter, but do not
        # replace its unstable native Eigen inverse with a Python estimate.
        affected = run['zero_scale']['role']
        chain = []
        ancestor = parent
        while ancestor is not None:
            chain.append(ancestor)
            ancestor = state['objects'][ancestor]['parent']
        if affected in chain:
            return
        expected = compose(obj['matrix_parent_inverse'], basis)
    tree(expected, obj['matrix_local'], name + '/source local getter')

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
        check_local(suite, run, name, state, basis[name])
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
                'scale', 'matrix_world', 'matrix_local', 'matrix_basis', 'matrix_parent_inverse',
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
            check_local(suite, run, name, state, basis[name])

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
        for field in set(old) - {'location', 'rotation', 'matrix_world', 'matrix_local', 'matrix_basis', 'matrix_parent_inverse'}:
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


def compare_case(suite, run, first, second):
    for value in [first, second]:
        validate_run(suite, run, value)
    tree(first, second, run['id'])


def provenance_inputs(folder, manifest, suite_path):
    source_path = ROOT / 'baseline/sources/snap-singular/manifest.json'
    source = json.loads(source_path.read_text())
    names = ['tools/blender_snap_singular_reference.py', 'tools/blender_snap_delta_reference.py',
        'tools/blender_snap_rotation_reference.py',
        'tools/blender_snap_menu_reference.py', 'tools/blender_transform_reference.py',
        'tools/blender_selection_reference.py', 'tools/generate_snap_delta_cases.py',
        'tools/generate_snap_rotation_cases.py', 'tools/generate_snap_menu_cases.py',
        'tools/generate_mesh_transform_cases.py', 'tools/generate_snap_singular_cases.py',
        'docs/contracts/snap-singular-baseline.md',
        'baseline/lock.json', 'baseline/sources/snap-singular/manifest.json',
        *[r['path'] for r in source['reused_manifests']], *[r['repository_path'] for r in source['files']]]
    paths = [suite_path, *[ROOT / n for n in names]]
    expected = {p.relative_to(ROOT).as_posix(): p for p in paths}
    require(len(manifest['input_hashes']) == len(expected), 'input hash set differs')
    roots = set()
    for relative, path in expected.items():
        rows = [(n, s) for n, s in manifest['input_hashes'].items() if n.endswith('/' + relative)]
        require(len(rows) == 1, 'missing/duplicate provenance/' + relative)
        name, sha = rows[0]; roots.add(name[:-len(relative)])
        actual = folder / 'capture-lock.json' if relative == 'baseline/lock.json' else path
        require(digest(actual) == sha, 'capture provenance changed/' + relative)
    require(len(roots) == 1, 'capture roots differ')
    historical = json.loads((folder / 'capture-lock.json').read_text())
    current = json.loads((ROOT / 'baseline/lock.json').read_text())
    require(current['artifacts'][:len(historical['artifacts'])] == historical['artifacts'], 'old source pins changed')
    require({k:v for k,v in current.items() if k != 'artifacts'} ==
            {k:v for k,v in historical.items() if k != 'artifacts'}, 'baseline criteria changed')
    for row in historical['artifacts']:
        require(digest(ROOT / row['path']) == row['sha256'], 'historical bytes changed/' + row['path'])


def compare(suite_path, first, second, receipts_path):
    suite_path = suite_path.resolve()
    first, second, receipts_path = first.resolve(), second.resolve(), receipts_path.resolve()
    suite = json.loads(suite_path.read_text()); require(suite == author(), 'authored suite differs')
    require(Counter(r['label'] for r in suite['runs']) == suite['groups_expected'], 'case families differ')
    manifests = [json.loads((p / 'manifest.json').read_text()) for p in [first, second]]
    a, b = manifests
    require(a['process_id'] != b['process_id'], 'same native process')
    require(a['input_hashes'] == b['input_hashes'], 'capture inputs differ')
    require(a['operator_properties_sha256'] == b['operator_properties_sha256'], 'source RNA differs')
    receipts = json.loads(receipts_path.read_text())['runs']
    ids = [r['id'] for r in suite['runs']]
    for folder, manifest in zip([first, second], manifests):
        require(manifest['schema_version'] == 1 and manifest['product'] == 'blender'
            and manifest['product_acceptance'] == 'unrun', 'source identity differs')
        require(type(manifest['process_id']) is int and manifest['process_id'] > 0, 'invalid process ID')
        require(manifest['scope'] == 'complete_1764_authored_snap_singular_cases'
            and not manifest['background'], 'incomplete/native mode differs')
        require(manifest['version'] == [5,2,3] and manifest['build_hash'] == 'e13b728c6880'
            and manifest['binary_sha256'] == BINARY, 'fixed source binary differs')
        require([r['id'] for r in manifest['runs']] == ids, 'missing/reordered source case')
        require({p.name for p in folder.glob('*.json.gz')} == {i + '.json.gz' for i in ids}, 'artifact set differs')
        require(digest(folder / 'operator-properties.json') == manifest['operator_properties_sha256'], 'RNA hash differs')
        properties = json.loads((folder / 'operator-properties.json').read_text())
        require(properties['delta_axis_angle_exposed'] is False, 'invented public delta axis-angle property')
        require('delta_rotation_axis_angle' not in properties['rotation']['object'], 'axis-angle exposure differs')
        matching = [r for r in receipts if r['process_id'] == manifest['process_id']]
        require(len(matching) == 1 and matching[0]['terminal_exit_code'] == 0, 'native terminal exit missing/failed')
        require(matching[0]['manifest_sha256'] == digest(folder / 'manifest.json'), 'terminal manifest differs')
        require(matching[0]['capture_lock_sha256'] == digest(folder / 'capture-lock.json') == manifest['capture_lock_sha256'], 'terminal lock differs')
        provenance_inputs(folder, manifest, suite_path)
    for index, run in enumerate(suite['runs']):
        values = []
        for folder, manifest in zip([first, second], manifests):
            row = manifest['runs'][index]; path = folder / row['file']
            require(path.name == run['id'] + '.json.gz', 'artifact path differs')
            require(digest(path) == row['sha256'], 'stored raw hash differs')
            raw = gzip.decompress(path.read_bytes())
            require(hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes'], 'exact JSON hash differs')
            value = json.loads(raw); require(value['result']['status'] == row['status'], 'manifest status differs')
            values.append(value)
        compare_case(suite, run, *values)
        if (index + 1) % 250 == 0:
            print(json.dumps({'compared': index + 1}), flush=True)
    return {'passed': True, 'cases': 1764, 'native_processes': [m['process_id'] for m in manifests],
        'binary_sha256': BINARY, 'suite_sha256': digest(suite_path),
        'comparison_script_sha256': digest(Path(__file__)), 'native_terminal_receipts_sha256': digest(receipts_path),
        'position_channel_matrix_limit': 1e-6, 'initial_inputs_independently_bound': True,
        'product_acceptance': 'unrun', 'milestones_accepted': 0}


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
