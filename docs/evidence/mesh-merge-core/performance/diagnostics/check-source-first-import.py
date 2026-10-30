#!/usr/bin/env python3
"""Verify before-code native merge grid data without product code or answers."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from compare_snap_menu_reference import tree, f32, IDENTITY, SELECTION
from compare_snap_rotation_reference import compose, matrix
from compare_snap_delta_reference import world_point
from compare_transform_reference import finite


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weighted(values):
    weight = f32(1. / len(values)); result = 0.
    for value in values:
        result = f32(result + f32(f32(value) * weight))
    return result


def rounded_integer(values):
    result = weighted(values)
    return math.floor(result + .5) if result >= 0. else math.ceil(result - .5)


def expected_initial(asset):
    geometry = {'vertices': asset['vertices'], 'edges': asset['edges'],
        'faces': {id: p['vertices'] for id, p in asset['polygons'].items()},
        'face_smooth': {id: p['smooth'] for id, p in asset['polygons'].items()},
        'face_materials': {id: p['material_slot'] or 0 for id, p in asset['polygons'].items()},
        'edge_seams': {id: id in asset.get('edge_seams', []) for id in asset['edges']},
        'material_slots': [], 'uv_layer_order': asset['uv_layout']['layers'], 'active_uv_index': 1,
        'uv_layers': {name: {id: p['uv_layers'][name] for id, p in asset['polygons'].items()}
                      for name in asset['uv_layout']['layers']}}
    return {'geometry': geometry, 'groups': {'names': asset['vertex_groups'], 'weights': asset['vertex_weights']},
        'selected': {'VERT': sorted(asset['vertices']), 'EDGE': sorted(asset['edges']), 'FACE': sorted(asset['polygons'])},
        'hidden': {'VERT': [], 'EDGE': [], 'FACE': []}, 'mode': ['VERT'],
        'history': [{'domain': 'VERT', 'id': asset['editing']['history'][0]['id']}], 'active_face': None}


def validate(source, terminal):
    scene = json.loads((HERE / 'authored-grid.json').read_text())
    forms = json.loads((HERE / 'authored-forms.json').read_text())
    manifest = json.loads((source / 'manifest.json').read_text())
    receipt = json.loads(terminal.read_text())
    assert receipt['terminal_exit_code'] == 0 and receipt['process_id'] == manifest['process_id']
    assert receipt['manifest_sha256'] == digest(source / 'manifest.json')
    assert manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880'
    assert manifest['binary_sha256'] == 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert not manifest['background'] and manifest['product_acceptance'] == 'unrun'
    assert manifest['scope'] == 'ten_before_code_attributed_merge_grid_forms'
    assert [r['id'] for r in manifest['runs']] == [f['id'] for f in forms['forms']]
    assert {p.name for p in source.glob('*.json.gz')} == {f['id'] + '.json.gz' for f in forms['forms']}
    assert len(manifest['runs']) == 10
    assert digest(source / 'operator-properties.json') == manifest['operator_properties_sha256']
    assert forms['grid_sha256'] == digest(HERE / 'authored-grid.json')
    assert forms['base_grid_sha256'] == digest(ROOT / forms['base_grid_path'])
    for name, sha in manifest['input_hashes'].items():
        assert digest(Path(name)) == sha, name
    spec = importlib.util.spec_from_file_location('fixed_merge_author', HERE / 'author-inputs.py')
    author = importlib.util.module_from_spec(spec); spec.loader.exec_module(author)
    authored_scene, authored_forms = author.author()
    assert scene == authored_scene and forms['forms'] == authored_forms
    asset = scene['mesh_assets']['grid']; initial = expected_initial(asset)
    profiles = {name: {'location': data['transform']['translation'],
                      'rotation': data['transform']['rotation']['angles'],
                      'scale': data['transform']['scale']} for name, data in scene['entities'].items()}
    def world(name):
        value = matrix(profiles[name]); parent = scene['entities'][name]['parent']
        return value if parent is None else compose(world(parent), value)
    checks = []
    for form, row in zip(forms['forms'], manifest['runs']):
        path = source / row['file']; assert path.name == form['id'] + '.json.gz'
        assert digest(path) == row['sha256']; raw = gzip.decompress(path.read_bytes())
        assert len(raw) == row['raw_bytes'] and hashlib.sha256(raw).hexdigest() == row['raw_sha256']
        value = json.loads(raw); finite(value)
        assert value['form'] == form and value['result'] == {'status': ['FINISHED'], 'error': None}
        assert value['run']['parameters'] == {'type': form['method'], 'uvs': form['uvs']}
        before, after = value['before'], value['after']
        assert before['mode'] == 'EDIT_MESH' and before['active_object'] == 'target'
        assert before['sharing'] == [['secondary', 'target']]
        assert set(before['objects']) == {'target', 'secondary', 'child'}
        for key in set(before) - {'meshes'}:
            tree(before[key], after[key], 'unchanged context/' + key, 0.)
        tree(scene['authoring_context']['cursor_location'], before['cursor']['location'], 'authored cursor', 0.)
        tree(scene['authoring_context']['cursor_rotation'], before['cursor']['rotation'], 'authored cursor rotation', 0.)
        tree([1., 0., 0., 0.], before['settings']['view_rotation'], 'authored view rotation', 0.)
        for key, expected in [('skip_children', False), ('origins_only', False), ('automerge', False),
                              ('autokey', False), ('unit_system', 'NONE'), ('unit_scale_length', 1.)]:
            tree(expected, before['settings'][key], 'authored setting/' + key, 0.)
        for name, obj in before['objects'].items():
            assert obj['parent'] == scene['entities'][name]['parent']
            assert obj['type'] == ('EMPTY' if name == 'child' else 'MESH')
            assert obj['mode'] == ('EDIT' if name == 'target' else 'OBJECT')
            assert obj['selected'] == (name != 'child')
            assert obj['rotation_mode'] == 'XYZ' and not obj['animation_data']
            assert obj['constraints'] == obj['modifiers'] == 0
            for key in ['location', 'rotation', 'scale']:
                tree(profiles[name][key], obj[key], 'authored channels/' + name + '/' + key, 0.)
            tree(matrix(profiles[name]), obj['matrix_basis'], 'authored basis/' + name)
            tree(matrix(profiles[name]), obj['matrix_local'], 'authored local/' + name)
            tree(IDENTITY, obj['matrix_parent_inverse'], 'authored parent inverse/' + name, 0.)
            tree(world(name), obj['matrix_world'], 'authored world/' + name)
        for state in [before, after]:
            assert set(state['meshes']) == {'target', 'secondary'}
            a, b = state['meshes']['target'], state['meshes']['secondary']
            for key in set(a) - {'world_vertices', 'world_vertices_metres'}:
                tree(a[key], b[key], 'actual shared data/' + key, 0.)
            for name, mesh in state['meshes'].items():
                assert mesh['data_edit_mode'] and mesh['mode'] == ['VERT']
                geometry = mesh['geometry']
                assert set(geometry['vertices']) == set(mesh['vertices_metres']) == set(mesh['world_vertices']) == set(mesh['world_vertices_metres'])
                for id, point in geometry['vertices'].items():
                    tree(point, mesh['vertices_metres'][id], 'local physical/' + id, 0.)
                    expected = world_point(world(name), point)
                    tree(expected, mesh['world_vertices'][id], 'world physical/' + id, 0.)
                    tree(expected, mesh['world_vertices_metres'][id], 'world metres/' + id, 0.)
                attrs = mesh['integer_attributes']
                assert set(attrs) == {'vertices', 'edges', 'polygons', 'triangles'}
                for domain, table in [('vertices', 'vertices'), ('edges', 'edges'), ('polygons', 'faces')]:
                    assert set(attrs[domain]) == set(asset['integer_attributes'][domain])
                    for name, values in attrs[domain].items():
                        assert set(values) == set(geometry[table]) and all(type(v) is int for v in values.values())
                assert attrs['triangles'] == {}
        before_mesh = before['meshes']['target']; after_mesh = after['meshes']['target']
        tree(initial, {k: before_mesh[k] for k in SELECTION}, 'authored initial mesh', 0.)
        tree(asset['integer_attributes'], before_mesh['integer_attributes'], 'authored integer data', 0.)
        for name, count, prefix in [('VERT', 10201, 'v'), ('EDGE', 20200, 'e'), ('FACE', 10000, 'f')]:
            tree({f'{prefix}{i:06}': i for i in range(count)}, before_mesh['source_component_ids'][name], 'authored tags', 0.)
        geometry = after_mesh['geometry']
        assert len(geometry['vertices']) == 1 and not geometry['edges'] and not geometry['faces']
        tree(['Detail', 'Layout'], geometry['uv_layer_order'], 'retained UV layers', 0.)
        assert geometry['active_uv_index'] == 1 and all(not v for v in geometry['uv_layers'].values())
        tree(asset['vertex_groups'], after_mesh['groups']['names'], 'retained group names', 0.)
        actual_id = next(iter(geometry['vertices']))
        point = scene['authoring_context']['cursor_location'] if form['method'] == 'CURSOR' else (
            asset['vertices'][asset['editing']['history'][0]['id']] if form['method'] in ['FIRST', 'LAST'] else [50., 50., 0.])
        tree(point, geometry['vertices'][actual_id], 'analytic merged position')
        if form['method'] in ['CENTER', 'CURSOR']:
            for name, values in asset['integer_attributes']['vertices'].items():
                expected = rounded_integer([values[id] for id in sorted(values)])
                tree(expected, after_mesh['integer_attributes']['vertices'][name][actual_id], 'source integer interpolation', 0.)
            expected_weights = {name: weighted([asset['vertex_weights'][id][name] for id in sorted(asset['vertices'])])
                                for name in asset['vertex_groups']}
            tree(expected_weights, after_mesh['groups']['weights'][actual_id], 'source weight interpolation', 0.)
        else:
            # Explicit/edge-collapse welds retain their actual survivor's data.
            # For collapse this checks lineage consistency, not an independent
            # oracle for the BMesh walker's survivor choice.
            tag = after_mesh['integer_attributes']['vertices']['formora_v_id'][actual_id]
            original = f'v{tag:06}'; assert original in asset['vertices']
            if form['method'] in ['FIRST', 'LAST']:
                assert original == asset['editing']['history'][0]['id']
            for name, values in asset['integer_attributes']['vertices'].items():
                tree(values[original], after_mesh['integer_attributes']['vertices'][name][actual_id], 'retained integer data', 0.)
            tree(asset['vertex_weights'][original], after_mesh['groups']['weights'][actual_id], 'retained group data', 0.)
        checks.append({'form': form['id'], 'passed': True})
        print(json.dumps({'checked_form': form['id']}), flush=True)
    return {'passed': True, 'forms': checks, 'source_process_id': manifest['process_id'],
            'source_terminal_exit': 0, 'source_manifest_sha256': digest(source / 'manifest.json'),
            'authored_grid_sha256': digest(HERE / 'authored-grid.json'),
            'checker_sha256': digest(Path(__file__)), 'product_code_changed': False,
            'product_samples': 'unrun', 'product_acceptance': 'unrun', 'milestones_accepted': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--terminal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.source, args.terminal)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False); output.write('\n')
    print(json.dumps(result))
