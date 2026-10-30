#!/usr/bin/env python3
"""Capture independently authored multi-data merges in a fixed viewport process."""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import traceback

import bmesh
import bpy
from mathutils import Euler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_mesh_merge_reference as single
from multi_mesh_merge_inputs import input_paths

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ['VERT', 'EDGE', 'FACE']
TABLES = ['vertices', 'edges', 'polygons']
BINARY = single.BINARY


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write('\n')


def create_mesh(name, asset):
    mesh = bpy.data.meshes.new(name)
    vertex_ids = list(asset['vertices'])
    index = {id: i for i, id in enumerate(vertex_ids)}
    mesh.from_pydata(list(asset['vertices'].values()),
                     [[index[id] for id in pair] for pair in asset['edges'].values()],
                     [[index[id] for id in face['vertices']]
                      for face in asset['polygons'].values()])
    for table, domain in zip(TABLES, ['POINT', 'EDGE', 'FACE']):
        for name, values in asset['integer_attributes'][table].items():
            attribute = mesh.attributes.new(name, 'INT', domain)
            for item, value in zip(attribute.data, values.values()):
                item.value = value
    for name in asset['material_slots']:
        mesh.materials.append(bpy.data.materials[name])
    for actual, authored in zip(mesh.polygons, asset['polygons'].values()):
        actual.material_index = authored['material_slot']
        actual.use_smooth = authored['smooth']
    for actual, id in zip(mesh.edges, asset['edges']):
        actual.use_seam = id in asset['edge_seams']
    for name in asset['uv_layout']['layers']:
        layer = mesh.uv_layers.new(name=name)
        for face, authored in zip(mesh.polygons, asset['polygons'].values()):
            for corner, uv in zip(face.loop_indices, authored['uv_layers'][name]):
                layer.data[corner].uv = uv
    mesh.uv_layers.active_index = asset['uv_layout']['layers'].index(asset['uv_layout']['active'])
    mesh.update()
    return mesh


def apply_selection(obj, suite, run, active_data):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.select_mode = set(run['mode'])
    collections = [bm.verts, bm.edges, bm.faces]
    selected = run['selection'] == 'both' or (
        run['selection'] == 'active_empty' and not active_data) or (
        run['selection'] == 'other_empty' and active_data)
    for items in collections:
        items.ensure_lookup_table()
        for item in items:
            item.hide_set(False)
            item.select = selected
    bm.select_flush_mode()
    bm.select_history.clear()
    bm.faces.active = bm.faces[-1] if selected and len(bm.faces) else None
    pattern = run['history']
    history = []
    if selected:
        if pattern == 'both_reverse':
            history = [bm.verts[-1], bm.verts[0]]
        elif pattern == 'active_first_only' and active_data:
            history = [bm.verts[0], bm.edges[-1]]
        elif pattern == 'active_last_only' and active_data:
            history = [bm.edges[0], bm.verts[-1]]
        elif not ((pattern == 'active_none' and active_data)
                  or (pattern == 'other_none' and not active_data)):
            history = [bm.verts[0], bm.verts[-1]]
    for item in history:
        bm.select_history.add(item)
    bm.select_history.validate()
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def create(suite, run):
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    # Only this dedicated factory-startup process owns these temporary IDs.
    for item in list(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)
    for item in list(bpy.data.meshes):
        if item.users == 0:
            bpy.data.meshes.remove(item)
    for name, specification in suite['materials'].items():
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        material.diffuse_color = specification['base_color']
        material.roughness = specification['roughness']
        material.metallic = specification['metallic']
    meshes = {name: create_mesh(name, asset)
              for name, asset in suite['mesh_assets'].items()}
    context = next(c for c in suite['contexts'] if c['id'] == run['context'])
    objects = {}
    for name in context['order']:
        data = meshes[suite['data_sharing'][name]] if name in suite['data_sharing'] else None
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        objects[name] = obj
    for data_name, mesh in meshes.items():
        owner = next(obj for obj in objects.values() if obj.data == mesh)
        asset = suite['mesh_assets'][data_name]
        if not owner.vertex_groups:
            for name in asset['vertex_groups']:
                owner.vertex_groups.new(name=name)
        assert [g.name for g in owner.vertex_groups] == asset['vertex_groups']
        for id, weights in asset['vertex_weights'].items():
            for group, weight in weights.items():
                owner.vertex_groups[group].add([int(id[1:])], weight, 'REPLACE')
        for obj in objects.values():
            if obj.data == mesh:
                assert [g.name for g in obj.vertex_groups] == asset['vertex_groups']
    for name, specification in suite['entity_frames'][run['frame']].items():
        obj = objects[name]
        transform = specification['transform']
        obj.parent = objects.get(specification['parent'])
        obj.location = transform['translation']
        obj.rotation_mode = transform['rotation']['order'].upper()
        obj.rotation_euler = transform['rotation']['angles']
        obj.scale = transform['scale']
        obj.select_set(name in ['a', 'b', 'alias'])
    bpy.context.view_layer.objects.active = objects[context['active']]
    scene = bpy.context.scene
    settings = scene.tool_settings
    settings.mesh_select_mode = tuple(domain in run['mode'] for domain in DOMAINS)
    settings.transform_pivot_point = 'MEDIAN_POINT'
    settings.use_transform_skip_children = False
    settings.use_transform_data_origin = False
    settings.use_keyframe_insert_auto = False
    settings.use_transform_pivot_point_align = False
    settings.use_transform_correct_face_attributes = False
    settings.use_transform_correct_keep_connected = False
    settings.use_mesh_automerge = False
    settings.use_mesh_automerge_and_split = False
    scene.cursor.rotation_mode = 'XYZ'
    scene.cursor.location = suite['authoring_context']['cursor_location']
    scene.cursor.rotation_euler = suite['authoring_context']['cursor_rotation']
    scene.unit_settings.system = suite['units']['unit_system']
    scene.unit_settings.scale_length = suite['units']['unit_scale_length']
    bpy.ops.object.mode_set(mode='EDIT')
    active_mesh = objects[context['active']].data
    for obj in objects.values():
        if obj.mode == 'EDIT':
            apply_selection(obj, suite, run, obj.data == active_mesh)
    area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    view = area.spaces.active.region_3d
    view.view_rotation = Euler([.25, -.375, .5], 'XYZ').to_quaternion()
    view.view_location = [0., 0., 0.]
    view.view_distance = 10.
    view.view_perspective = 'ORTHO'
    area.spaces.active.overlay.grid_scale = 1.
    area.spaces.active.overlay.grid_subdivisions = 10
    bpy.context.view_layer.update()
    with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
        view.update()
    return objects, area, region


def snapshot(objects, area, suite):
    state = single.snapshot(objects, area, {'context': suite['units']})
    names = {item.as_pointer(): name for name, item in objects.items()}
    layer_order = [names[obj.as_pointer()] for obj in bpy.context.view_layer.objects]
    active = state['active_object']
    # BKE_layer.hh passes the active base first, then the view-layer base order.
    order = [active, *[name for name in layer_order if name != active]]
    seen = set()
    providers = []
    for name in order:
        obj = objects[name]
        if obj.mode == 'EDIT' and obj.data.as_pointer() not in seen:
            providers.append(name)
            seen.add(obj.data.as_pointer())
    state['edit_context'] = {
        'view_layer_order': layer_order,
        'edit_objects': [name for name in layer_order if objects[name].mode == 'EDIT'],
        'unique_data_iteration': providers,
        'python_unique_data_objects': [names[obj.as_pointer()]
                                     for obj in bpy.context.objects_in_mode_unique_data],
    }
    for name, obj in objects.items():
        if obj.type != 'MESH':
            continue
        edit = obj.data.is_editmode
        bm = bmesh.from_edit_mesh(obj.data) if edit else bmesh.new()
        if not edit:
            bm.from_mesh(obj.data)
        try:
            state['meshes'][name]['integer_attributes'] = {
                domain: {layer: {f'{prefix}{i:06}': item[items.layers.int[layer]]
                                 for i, item in enumerate(items)}
                         for layer in sorted(items.layers.int.keys())}
                for domain, items, prefix in zip(DOMAINS, [bm.verts, bm.edges, bm.faces], 'vef')
            }
        finally:
            if not edit:
                bm.free()
    state['materials'] = {name: {'base_color': list(bpy.data.materials[name].diffuse_color),
                                'roughness': bpy.data.materials[name].roughness,
                                'metallic': bpy.data.materials[name].metallic}
                          for name in suite['materials']}
    return state


def capture(args):
    suite = json.loads(args.suite.read_text())
    assert len(suite['runs']) == 13440
    assert list(bpy.app.version) == [5, 2, 3]
    assert not bpy.app.background and bpy.app.build_hash.decode() == 'e13b728c6880'
    assert digest(bpy.app.binary_path) == BINARY
    paths = input_paths(args.suite)
    inputs = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    stage = args.output.with_name(args.output.name + '.staging')
    assert not args.output.exists() and not stage.exists()
    stage.mkdir(parents=True)
    (stage / 'capture-lock.json').write_bytes((ROOT / 'baseline/lock.json').read_bytes())
    write(stage / 'operator-properties.json', single.properties())
    runs = suite['runs']
    if args.case_ids:
        assert len(args.case_ids) == len(set(args.case_ids))
        assert set(args.case_ids) <= {run['id'] for run in runs}
        runs = [run for run in runs if run['id'] in args.case_ids]
    records = []
    for index, run in enumerate(runs):
        objects, area, region = create(suite, run)
        before = snapshot(objects, area, suite)
        with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
            assert bpy.ops.mesh.merge.poll(), ('invalid setup', run['id'])
            try:
                result = {'status': sorted(bpy.ops.mesh.merge(**copy.deepcopy(run['parameters']))),
                          'error': None}
            except TypeError as error:
                # Record the actual source result. The independent checker
                # decides whether it matches the frozen authored prediction.
                assert 'enum' in str(error).lower(), str(error)
                result = {'status': ['ENUM_REJECTED'], 'error': str(error)}
        bpy.context.view_layer.update()
        raw = (json.dumps({'run': run, 'before': before, 'after': snapshot(objects, area, suite),
                           'result': result}, indent=2, allow_nan=False) + '\n').encode()
        path = stage / (run['id'] + '.json.gz')
        with path.open('xb') as stream:
            with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as compressed:
                compressed.write(raw)
        assert gzip.decompress(path.read_bytes()) == raw
        records.append({'id': run['id'], 'file': path.name, 'sha256': digest(path),
                        'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
                        'status': result['status']})
        if (index + 1) % 100 == 0:
            print(json.dumps({'captured': index + 1, 'total': len(runs)}), flush=True)
    assert inputs == {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    write(stage / 'manifest.json', {
        'schema_version': 1, 'product': 'blender', 'version': list(bpy.app.version),
        'build_hash': bpy.app.build_hash.decode(), 'binary_sha256': digest(bpy.app.binary_path),
        'process_id': os.getpid(), 'background': bpy.app.background,
        'command_line': sys.argv, 'platform': platform.platform(),
        'captured_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'focused_diagnostic' if args.case_ids else 'complete_13440_multi_data_merge_cases',
        'input_hashes': inputs,
        'operator_properties_sha256': digest(stage / 'operator-properties.json'),
        'capture_lock_sha256': digest(stage / 'capture-lock.json'),
        'runs': records, 'product_acceptance': 'unrun',
    })
    stage.rename(args.output)
    print(json.dumps({'captured': len(records), 'product_acceptance': 'unrun'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[], dest='case_ids')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])

    def start():
        try:
            capture(args)
        except BaseException:
            traceback.print_exc()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)

    bpy.app.timers.register(start, first_interval=.5)
