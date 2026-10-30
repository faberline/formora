#!/usr/bin/env python3
"""Capture all ten authored merge grid forms before Rust product changes."""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

import bmesh
import bpy
from mathutils import Euler

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
import blender_mesh_merge_reference as merge

GRID_PATH = ROOT / 'docs/evidence/scene-snap-core/performance/blender-grid-reference.py'
spec = importlib.util.spec_from_file_location('fixed_grid_setup', GRID_PATH)
grid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as output:
        json.dump(value, output, indent=2, allow_nan=False); output.write('\n')


def mesh_input(asset):
    vertices, edges, faces = [sorted(asset[k]) for k in ['vertices', 'edges', 'polygons']]
    assert (len(vertices), len(edges), len(faces)) == (10201, 20200, 10000)
    index = {id: i for i, id in enumerate(vertices)}
    return {'vertices': [asset['vertices'][id] for id in vertices],
        'edges': [[index[v] for v in asset['edges'][id]] for id in edges],
        'faces': [[index[v] for v in asset['polygons'][id]['vertices']] for id in faces],
        'face_smooth': [asset['polygons'][id]['smooth'] for id in faces],
        'face_materials': [asset['polygons'][id]['material_slot'] or 0 for id in faces],
        'edge_seams': [id in asset.get('edge_seams', []) for id in edges],
        'material_slots': [], 'uv_layers': [{'name': name, 'faces': [
            asset['polygons'][id]['uv_layers'][name] for id in faces]} for name in asset['uv_layout']['layers']],
        'active_uv_index': 1, 'active_material_index': 0,
        'hidden': {'vertices': [], 'edges': [], 'faces': []},
        'group_scenarios': {'authored': {'names': asset['vertex_groups'], 'weights': asset['vertex_weights']}}}


def assign_integer_attributes(objects, scene):
    bm = bmesh.from_edit_mesh(objects['target'].data)
    authored = scene['mesh_assets']['grid']['integer_attributes']
    for domain, prefix, elements in [('vertices', 'v', bm.verts), ('edges', 'e', bm.edges),
                                     ('polygons', 'f', bm.faces)]:
        for name, values in authored[domain].items():
            layer = elements.layers.int.get(name) or elements.layers.int.new(name)
            # Creating a CustomData layer can invalidate prior Python element
            # wrappers. Read fresh wrappers after each layer has been created.
            items = list(elements)
            assert set(values) == {f'{prefix}{i:06}' for i in range(len(items))}
            for i, item in enumerate(items):
                value = values[f'{prefix}{i:06}']
                assert type(value) is int and -(2**31) <= value < 2**31
                item[layer] = value
    bmesh.update_edit_mesh(objects['target'].data, loop_triangles=False, destructive=False)


def snapshot(objects, area, run, scene):
    state = merge.snapshot(objects, area, run)
    names = scene['mesh_assets']['grid']['integer_attributes']
    bm = bmesh.from_edit_mesh(objects['target'].data)
    for owner in state['meshes']:
        actual = {'vertices': {}, 'edges': {}, 'polygons': {}, 'triangles': {}}
        for domain, prefix, items in [('vertices', 'v', bm.verts), ('edges', 'e', bm.edges),
                                      ('polygons', 'f', bm.faces)]:
            for name in names[domain]:
                layer = items.layers.int.get(name)
                assert layer is not None
                actual[domain][name] = {f'{prefix}{i:06}': item[layer] for i, item in enumerate(items)}
        state['meshes'][owner]['integer_attributes'] = actual
    return state


def capture(output):
    assert not bpy.app.background and list(bpy.app.version) == [5, 2, 3]
    assert bpy.app.build_hash.decode() == 'e13b728c6880'
    assert digest(Path(bpy.app.binary_path)) == merge.BINARY
    stage = output.with_name(output.name + '.staging')
    assert not output.exists() and not stage.exists()
    metadata = json.loads((HERE / 'authored-forms.json').read_text())
    scene = json.loads((HERE / 'authored-grid.json').read_text())
    assert metadata['grid_sha256'] == digest(HERE / 'authored-grid.json')
    assert metadata['base_grid_sha256'] == digest(ROOT / metadata['base_grid_path'])
    assert (metadata['total_samples'], metadata['maximum_core_ms'], metadata['maximum_pipeline_ms']) == (30, 250, 2000)
    manifest = json.loads((ROOT / 'baseline/sources/mesh-merge/manifest.json').read_text())
    paths = [HERE / 'authored-grid.json', HERE / 'authored-forms.json', HERE / 'author-inputs.py',
             Path(__file__), GRID_PATH, ROOT / metadata['base_grid_path'],
             ROOT / 'docs/contracts/mesh-merge-core.md', ROOT / 'tools/blender_mesh_merge_reference.py',
             ROOT / 'tools/blender_snap_menu_reference.py', ROOT / 'tools/blender_transform_reference.py',
             ROOT / 'tools/blender_selection_reference.py', ROOT / 'baseline/fixtures/snap-menu.json',
             ROOT / 'baseline/lock.json', ROOT / 'baseline/sources/mesh-merge/manifest.json',
             *[ROOT / r['path'] for r in manifest['reused_manifests']],
             *[ROOT / r['repository_path'] for r in manifest['files']]]
    hashes = {str(p.resolve()): digest(p) for p in paths}
    stage.mkdir(parents=True)
    write(stage / 'operator-properties.json', merge.properties())
    records = []
    for form in metadata['forms']:
        suite = json.loads((ROOT / 'baseline/fixtures/snap-menu.json').read_text())
        suite['mesh'] = mesh_input(scene['mesh_assets']['grid'])
        run = copy.deepcopy(suite['runs'][0])
        run.update(id=form['id'], operator='merge', feature='mesh.merge', mode='EDIT_MESH',
                   label='fixed attributed grid', initial_mode=['VERT'], groups='authored',
                   seed={'domain': 'VERT', 'indices': list(range(10201))},
                   parameters={'type': form['method'], 'uvs': form['uvs']})
        run['context'].update(grid_spacing=.75, unit_system='NONE', unit_scale_length=1.,
                              multi_object=True, linked_data=True, origins_only=False,
                              skip_children=False, object_selection=['target', 'secondary'],
                              active_object='target',
                              cursor_location=scene['authoring_context']['cursor_location'],
                              cursor_rotation=scene['authoring_context']['cursor_rotation'])
        objects, area, region = grid.create(suite, run, scene)
        view = area.spaces.active.region_3d
        view.view_rotation = Euler(scene['authoring_context']['view_rotation'], 'XYZ').to_quaternion()
        view.view_location = [0., 0., 0.]
        view.view_distance = 10.
        with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
            view.update()
        assert set(objects) == {'target', 'secondary', 'child'}
        assert objects['target'].data == objects['secondary'].data
        names = list(scene['mesh_assets']['grid']['vertex_groups'])
        for name in ['target', 'secondary']:
            obj = objects[name]
            if not obj.vertex_groups:
                for group in names: obj.vertex_groups.new(name=group)
            assert [g.name for g in obj.vertex_groups] == names
        assign_integer_attributes(objects, scene)
        before = snapshot(objects, area, run, scene)
        with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
            assert bpy.ops.mesh.merge.poll()
            result = {'status': sorted(bpy.ops.mesh.merge(**run['parameters'])), 'error': None}
        bpy.context.view_layer.update()
        after = snapshot(objects, area, run, scene)
        assert result == {'status': ['FINISHED'], 'error': None}
        value = {'form': form, 'run': run, 'before': before, 'after': after, 'result': result}
        raw = (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode()
        payload = gzip.compress(raw, mtime=0)
        assert gzip.decompress(payload) == raw
        file = form['id'] + '.json.gz'
        with (stage / file).open('xb') as stream: stream.write(payload)
        records.append({'id': form['id'], 'file': file, 'sha256': digest(stage / file),
                        'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw)})
        print(json.dumps({'captured_form': form['id']}), flush=True)
    assert hashes == {str(p.resolve()): digest(p) for p in paths}
    write(stage / 'manifest.json', {'version': list(bpy.app.version),
        'build_hash': bpy.app.build_hash.decode(), 'binary_sha256': merge.BINARY,
        'process_id': os.getpid(), 'background': bpy.app.background, 'command_line': sys.argv,
        'scope': 'ten_before_code_attributed_merge_grid_forms', 'input_hashes': hashes,
        'operator_properties_sha256': digest(stage / 'operator-properties.json'), 'runs': records,
        'product_acceptance': 'unrun'})
    stage.rename(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    def start():
        try: capture(args.output)
        except BaseException:
            traceback.print_exc(); sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
        sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
    bpy.app.timers.register(start, first_interval=.5)
