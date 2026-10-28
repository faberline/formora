#!/usr/bin/env python3
"""Capture mesh creation contexts without changing the first frozen adapter."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile

import bpy
from mathutils import Euler

BASE_PATH = Path(__file__).with_name('blender_mesh_reference.py')
spec = importlib.util.spec_from_file_location('primitive_reference', BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                               sort_keys=True, separators=(',', ':'))+'\n', encoding='utf-8')


def reset(state):
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        if material.users == 0:
            bpy.data.materials.remove(material)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.cursor.location = state['cursor_location']
    scene.cursor.rotation_euler = state['cursor_rotation']
    area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    area.spaces.active.region_3d.view_rotation = Euler(state['view_rotation'], 'XYZ').to_quaternion()
    area.spaces.active.region_3d.view_perspective = 'ORTHO'
    return area, region


def seed_mesh(state):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(4.0,-3.0,2.0), rotation=(0.1,0.2,0.3))
    obj = bpy.context.object
    while obj.data.uv_layers:
        obj.data.uv_layers.remove(obj.data.uv_layers[0])
    for i in range(state['seed_uv_layers']):
        layer = obj.data.uv_layers.new(name=['SeedUV','OtherUV'][i])
        for corner in layer.data:
            corner.uv = [(0.125,0.875),(0.25,0.75)][i]
    if obj.data.uv_layers:
        obj.data.uv_layers.active_index = len(obj.data.uv_layers)-1
    for i in range(2):
        obj.data.materials.append(bpy.data.materials.new(name=f'SeedMaterial{i}'))
    for i, face in enumerate(obj.data.polygons):
        face.material_index = i % 2
    obj.active_material_index = 1
    bpy.context.view_layer.update()
    before = base.snapshot(obj)
    before['face_materials'] = [p.material_index for p in obj.data.polygons]
    before['material_slots'] = [material.name if material else None for material in obj.data.materials]
    bpy.ops.object.mode_set(mode='EDIT')
    return before


def capture(run):
    state = run['state']
    area, region = reset(state)
    before = seed_mesh(state) if state['creation_kind'] == 'append_mesh' else None
    with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
        status = base.OPERATORS[run['operator']](**run['parameters'])
    if status != {'FINISHED'}:
        raise ValueError('primitive operation did not finish: '+run['id'])
    obj = bpy.context.object
    if obj is None or obj.type != 'MESH' or len(bpy.data.objects) != 1:
        raise ValueError('unexpected object ownership: '+run['id'])
    mode = obj.mode
    if mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    data = base.snapshot(obj)
    data.update({
        'run_id': run['id'], 'creation_kind': state['creation_kind'],
        'object_count': len(bpy.data.objects), 'reference_mode_after': mode,
        'active_uv_index': obj.data.uv_layers.active_index if obj.data.uv_layers else -1,
        'material_slot_count': len(obj.data.materials),
        'material_slots': [material.name if material else None for material in obj.data.materials],
        'active_material_index': obj.active_material_index,
        'face_materials': [p.material_index for p in obj.data.polygons],
        'vertex_selected': [v.select for v in obj.data.vertices],
        'edge_selected': [e.select for e in obj.data.edges],
        'face_selected': [p.select for p in obj.data.polygons],
    })
    n = len(before['vertices']) if before else 0
    data['vertex_origin'] = ['existing' if i < n else 'created' for i in range(len(data['vertices']))]
    for field, geometry in [('edge_origin', 'edges'), ('face_origin', 'faces')]:
        count = len(before[geometry]) if before else 0
        data[field] = ['existing' if i < count else 'created' for i in range(len(data[geometry]))]
    if before:
        for key in ['vertices','edges','faces','face_normals','smooth_faces','corner_normals','face_materials']:
            if data[key][:len(before[key])] != before[key]:
                raise ValueError('existing mesh data changed: '+run['id']+' / '+key)
        if data['matrix_world'] != before['matrix_world']:
            raise ValueError('existing object transform changed: '+run['id'])
        if data['material_slots'] != before['material_slots']:
            raise ValueError('existing material bindings changed: '+run['id'])
        for i, old in enumerate(before['uv_layers']):
            new = data['uv_layers'][i]
            if new['name'] != old['name'] or new['faces'][:len(old['faces'])] != old['faces']:
                raise ValueError('existing UV data changed: '+run['id'])
    data['reference_seed_preserved'] = before is not None
    undefined = 0
    for layer in data['uv_layers']:
        for face in layer['faces']:
            for corner in face:
                for i, value in enumerate(corner):
                    if math.isnan(value):
                        if (run['operator'] != 'circle' or run['parameters'].get('radius') != 0.0
                                or run['parameters'].get('fill_type') not in ['NGON', 'TRIFAN']):
                            raise ValueError('unexpected undefined UV outside the fixed zero-circle policy: '+run['id'])
                        corner[i] = {'reference_nonfinite': 'nan'}
                        undefined += 1
                    elif not math.isfinite(value):
                        raise ValueError('unexpected infinite UV: '+run['id'])
    data['reference_nonfinite_uv_components'] = undefined
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    suite = json.loads(args.suite.read_bytes())
    if suite['schema_version'] != 1 or list(bpy.app.version) != suite['reference']['version'] or bpy.app.build_hash.decode() != suite['reference']['build_hash']:
        raise ValueError('suite or Blender version differs from the pin')
    if args.output.exists():
        raise ValueError('output already exists')
    ids = set()
    for run in suite['runs']:
        name = run['id']
        if not name or name in ids or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name):
            raise ValueError('run IDs must be unique safe filenames')
        ids.add(name)
        if run['operator'] not in base.OPERATORS or run['state']['creation_kind'] not in ['new_object','append_mesh']:
            raise ValueError('unsupported primitive or creation context')
    if not ids:
        raise ValueError('suite must contain runs')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='formora-mesh-context-', dir=args.output.parent))
    try:
        records = []
        for run in suite['runs']:
            data = capture(run)
            filename = run['id']+'.json'
            write_json(stage/filename, data)
            records.append({'id':run['id'],'file':filename,'sha256':base.digest(stage/filename),
                            'vertex_count':len(data['vertices']),'edge_count':len(data['edges']),
                            'face_count':len(data['faces']),'uv_layer_count':len(data['uv_layers'])})
        write_json(stage/'manifest.json', {
            'schema_version':1,'reference':suite['reference'],
            'suite_sha256':base.digest(args.suite),'adapter_sha256':base.digest(Path(__file__)),
            'base_adapter_sha256':base.digest(BASE_PATH),
            'executable_sha256':base.digest(Path(bpy.app.binary_path)),
            'runs':records,'formora_execution':'unrun','product_acceptance':'unrun'})
        stage.rename(args.output)
        print(json.dumps({'reference_runs':len(records),'output':str(args.output),'product_acceptance':'unrun'}))
    except BaseException:
        shutil.rmtree(stage)
        raise


if __name__ == '__main__':
    main()
