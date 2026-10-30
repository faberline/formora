#!/usr/bin/env python3
"""Capture selection in the frozen Blender. This is not product runtime code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

import bmesh
import bpy

DOMAINS = ['VERT', 'EDGE', 'FACE']
OPERATORS = ['select_mode', 'select_non_manifold', 'select_loose',
             'select_interior_faces', 'select_face_by_sides', 'select_by_pole_count',
             'select_ungrouped']
LAYERS = ['formora_v_id', 'formora_e_id', 'formora_f_id']


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024*1024), b''):
            result.update(part)
    return result.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False,
                               separators=(',', ':')) + '\n')


def logical_id(element, layers):
    domain = 0 if isinstance(element, bmesh.types.BMVert) else 1 if isinstance(element, bmesh.types.BMEdge) else 2
    return 'vef'[domain] + f'{element[layers[domain]]:06}'


def snapshot(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.normal_update()
    collections = [bm.verts, bm.edges, bm.faces]
    layers = [collection.layers.int[name] for collection, name in zip(collections, LAYERS)]
    key = lambda element: logical_id(element, layers)
    geometry = {
        'vertices': {key(v): list(v.co) for v in bm.verts},
        'edges': {key(e): sorted(key(v) for v in e.verts) for e in bm.edges},
        'faces': {key(f): [key(v) for v in f.verts] for f in bm.faces},
        'face_smooth': {key(f): f.smooth for f in bm.faces},
        'face_materials': {key(f): f.material_index for f in bm.faces},
        'edge_seams': {key(e): e.seam for e in bm.edges},
        'material_slots': [material.name for material in obj.data.materials],
        'uv_layers': {name: {key(f): [list(loop[layer].uv) for loop in f.loops]
                            for f in bm.faces}
                      for name in bm.loops.layers.uv.keys()
                      for layer in [bm.loops.layers.uv[name]]},
        'uv_layer_order': [layer.name for layer in obj.data.uv_layers],
        'active_uv_index': obj.data.uv_layers.active_index,
    }
    deform = bm.verts.layers.deform.active
    groups = {'names': [group.name for group in obj.vertex_groups],
              'weights': {key(v): {obj.vertex_groups[i].name: weight
                                   for i, weight in v[deform].items()} if deform else {}
                          for v in bm.verts}}
    return {
        'geometry': geometry, 'groups': groups,
        'selected': {domain: sorted(key(e) for e in elements if e.select)
                     for domain, elements in zip(DOMAINS, collections)},
        'hidden': {domain: sorted(key(e) for e in elements if e.hide)
                   for domain, elements in zip(DOMAINS, collections)},
        'mode': [domain for domain, enabled in zip(DOMAINS, bpy.context.tool_settings.mesh_select_mode) if enabled],
        'history': [{'domain': DOMAINS[0] if isinstance(e, bmesh.types.BMVert)
                    else DOMAINS[1] if isinstance(e, bmesh.types.BMEdge) else DOMAINS[2],
                     'id': key(e)} for e in bm.select_history],
        'active_face': None if bm.faces.active is None else key(bm.faces.active),
    }


def create(mesh_input, run):
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    mesh = bpy.data.meshes.new('SelectionFixture')
    mesh.from_pydata(mesh_input['vertices'], mesh_input['edges'], mesh_input['faces'])
    obj = bpy.data.objects.new('SelectionFixture', mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    for name, domain, elements in zip(LAYERS, ['POINT','EDGE','FACE'],
                                      [mesh.vertices, mesh.edges, mesh.polygons]):
        attribute = mesh.attributes.new(name, 'INT', domain)
        for i in range(len(elements)):
            attribute.data[i].value = i
    for name in mesh_input['material_slots']:
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mesh.materials.append(material)
    for face in mesh.polygons:
        face.material_index = mesh_input['face_materials'][face.index]
        face.use_smooth = mesh_input['face_smooth'][face.index]
    for edge in mesh.edges:
        edge.use_seam = mesh_input['edge_seams'][edge.index]
    for specification in mesh_input['uv_layers']:
        layer = mesh.uv_layers.new(name=specification['name'])
        for face in mesh.polygons:
            for i, corner in enumerate(face.loop_indices):
                layer.data[corner].uv = specification['faces'][face.index][i]
    mesh.uv_layers.active_index = mesh_input['active_uv_index']
    groups=mesh_input['group_scenarios'][run['groups']]
    for name in groups['names']:
        obj.vertex_groups.new(name=name)
    for vertex, memberships in groups['weights'].items():
        for name, weight in memberships.items():
            obj.vertex_groups[name].add([int(vertex[1:])],weight,'REPLACE')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.mesh_select_mode = tuple(d in run['initial_mode'] for d in DOMAINS)
    bm = bmesh.from_edit_mesh(mesh)
    bm.select_mode = set(run['initial_mode'])
    collections = [bm.verts, bm.edges, bm.faces]
    for elements in collections:
        elements.ensure_lookup_table()
        for element in elements:
            element.select = False
    for elements, name in zip(collections, ['vertices','edges','faces']):
        for index in mesh_input['hidden'][name]:
            elements[index].hide_set(True)
    bm.select_history.clear()
    bm.faces.active = None
    selected = collections[DOMAINS.index(run['seed']['domain'])]
    for index in run['seed']['indices']:
        selected[index].select_set(True)
        bm.select_history.add(selected[index])
        if run['seed']['domain'] == 'FACE':
            bm.faces.active = selected[index]
    bm.select_flush_mode()
    bm.select_history.validate()
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    return obj


def properties():
    result = {}
    for name in OPERATORS:
        values = {}
        for prop in getattr(bpy.ops.mesh, name).get_rna_type().properties:
            if prop.identifier == 'rna_type':
                continue
            value = {'type': prop.type, 'description': prop.description}
            for key in ['default', 'hard_min', 'hard_max']:
                if hasattr(prop, key):
                    value[key] = getattr(prop, key)
            if prop.type == 'ENUM':
                value['enum'] = [item.identifier for item in prop.enum_items]
            values[prop.identifier] = value
        result[name] = values
    return result


def main():
    started = datetime.now(timezone.utc).isoformat()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    suite = json.loads(args.suite.read_bytes())
    build = bpy.app.build_hash.decode()
    assert suite['schema_version'] == 1
    assert list(bpy.app.version) == suite['reference']['version'] and build == suite['reference']['build_hash']
    assert not args.output.exists(), 'never overwrite reference output'
    ids = [r['id'] for r in suite['runs']]
    assert len(ids) == len(set(ids)) == 530
    assert all(name and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name) for name in ids)
    assert all(r['operator'] in OPERATORS for r in suite['runs'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='formora-selection-stage-', dir=args.output.parent) as temporary:
        stage = Path(temporary)/'capture'
        stage.mkdir()
        write(stage/'operator-properties.json', properties())
        records = []
        for i, run in enumerate(suite['runs']):
            obj = create(suite['mesh'], run)
            before = snapshot(obj)
            try:
                status = sorted(getattr(bpy.ops.mesh, run['operator'])(**run['parameters']))
                assert run['expected_error'] is None, 'expected negative case unexpectedly succeeded'
                assert status == run['expected_status'], f"{run['id']}: unexpected reference status {status}"
                result = {'status': status, 'error': None,
                          'outcome': 'completed' if status == ['FINISHED'] else 'unchanged'}
            except RuntimeError as error:
                if not run['expected_error'] or run['expected_error'] not in str(error):
                    raise
                result = {'status': ['POLL_REJECTED'], 'error': str(error),
                          'outcome': 'invalid_selection_domain' if 'vertex selection mode' in str(error)
                          else 'missing_vertex_weights'}
            after = snapshot(obj)
            for key in ['geometry', 'groups', 'hidden']:
                assert before[key] == after[key], f"{run['id']}: selection changed {key}"
            if result['status'] != ['FINISHED']:
                assert before == after, 'rejected request changed selection state'
            data = {'run_id': run['id'], 'operator': run['operator'],
                    'parameters': run['parameters'], 'before': before, 'after': after,
                    'result': result, 'expected_negative': run['expected_error'] is not None}
            path = stage/(run['id']+'.json')
            write(path, data)
            records.append({'id':run['id'], 'feature':run['feature'], 'file':path.name,
                            'sha256':digest(path), 'result':result['status']})
            if (i+1)%50 == 0:
                print(f'Captured {i+1}/530 selection references', flush=True)
        executable = Path(bpy.app.binary_path)
        write(stage/'manifest.json', {
            'schema_version':1, 'product':'blender', 'version':list(bpy.app.version),
            'process_id':os.getpid(), 'capture_started_utc':started, 'command_line':sys.argv,
            'build_hash':build, 'platform':platform.platform(), 'binary_sha256':digest(executable),
            'suite_sha256':digest(args.suite), 'adapter_sha256':digest(__file__),
            'operator_properties_sha256':digest(stage/'operator-properties.json'),
            'runs':records, 'expected_negative_cases':20, 'expected_unchanged_cases':30,
            'product_acceptance':'unrun'})
        stage.rename(args.output)
    print(json.dumps({'captured':len(records), 'expected_negative':20,
                      'product_acceptance':'unrun'}), flush=True)


if __name__ == '__main__':
    main()
