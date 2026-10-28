#!/usr/bin/env python3
"""Run inside the pinned Blender, with factory settings and automatic scripts disabled.

This is an upstream test adapter. It is not part of the Formora product runtime.
The output directory must be new. A failed capture never publishes partial data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

import bpy

OPERATORS = {
    name: getattr(bpy.ops.mesh, 'primitive_' + name + '_add')
    for name in ('plane', 'cube', 'circle', 'uv_sphere', 'ico_sphere',
                 'cylinder', 'cone', 'torus', 'grid', 'monkey')
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False,
                               sort_keys=True, separators=(',', ':')) + '\n')


def text(value):
    return value.decode() if isinstance(value, bytes) else value


def operator_properties():
    result = {}
    for name, operator in OPERATORS.items():
        properties = {}
        for prop in operator.get_rna_type().properties:
            if prop.identifier == 'rna_type':
                continue
            value = {'type': prop.type, 'description': prop.description}
            if hasattr(prop, 'default'):
                value['default'] = prop.default
            if hasattr(prop, 'default_array'):
                value['default_array'] = list(prop.default_array)
            if hasattr(prop, 'hard_min'):
                value.update(min=prop.hard_min, max=prop.hard_max)
            if prop.type == 'ENUM':
                value['enum'] = [item.identifier for item in prop.enum_items]
            properties[prop.identifier] = value
        result[name] = properties
    return result


def snapshot(obj):
    mesh = obj.data
    mesh.update()
    mesh.calc_loop_triangles()
    local = [list(v.co) for v in mesh.vertices]
    world = [list(obj.matrix_world @ v.co) for v in mesh.vertices]
    if not local:
        raise ValueError('primitive produced no vertices')
    return {
        'vertices': local,
        'edges': [list(e.vertices) for e in mesh.edges],
        'faces': [list(p.vertices) for p in mesh.polygons],
        'face_normals': [list(p.normal) for p in mesh.polygons],
        'smooth_faces': [p.use_smooth for p in mesh.polygons],
        'corner_normals': [list(n.vector) for n in mesh.corner_normals],
        'triangles': [list(t.vertices) for t in mesh.loop_triangles],
        'uv_layers': [
            {'name': layer.name,
             'faces': [[list(layer.data[i].uv) for i in p.loop_indices]
                       for p in mesh.polygons]}
            for layer in mesh.uv_layers
        ],
        'matrix_world': [list(row) for row in obj.matrix_world],
        'bounds_local': [[min(v[i] for v in local) for i in range(3)],
                         [max(v[i] for v in local) for i in range(3)]],
        'bounds_world': [[min(v[i] for v in world) for i in range(3)],
                         [max(v[i] for v in world) for i in range(3)]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    args = parser.parse_args(argv)
    suite = json.loads(args.suite.read_text())
    if suite.get('schema_version') != 1:
        raise ValueError('unsupported suite schema')
    pin = suite['reference']
    if list(bpy.app.version) != pin['version'] or text(bpy.app.build_hash) != pin['build_hash']:
        raise ValueError('Blender version or build hash differs from the frozen reference')
    if args.output.exists():
        raise ValueError('output already exists; reference data must not be overwritten')
    ids = set()
    for run in suite['runs']:
        name = run['id']
        if not name or name in ids or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name):
            raise ValueError('run IDs must be unique safe filenames')
        ids.add(name)
        if run['operator'] not in OPERATORS:
            raise ValueError('operator is outside the mesh primitive allowlist')
        if not isinstance(run['parameters'], dict):
            raise ValueError('operator parameters must be an object')
    if not ids:
        raise ValueError('suite must contain runs')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='formora-reference-', dir=args.output.parent))
    try:
        write_json(stage / 'operator-properties.json', operator_properties())
        records = []
        for run in suite['runs']:
            for obj in list(bpy.data.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            for mesh in list(bpy.data.meshes):
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            bpy.context.scene.unit_settings.system = 'METRIC'
            bpy.context.scene.unit_settings.scale_length = 1.0
            bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
            bpy.context.scene.cursor.rotation_euler = (0.0, 0.0, 0.0)
            status = OPERATORS[run['operator']](**run['parameters'])
            if status != {'FINISHED'}:
                raise ValueError(f"operator did not finish: {run['id']}")
            bpy.context.view_layer.update()
            obj = bpy.context.object
            if obj is None or obj.type != 'MESH' or len(bpy.data.objects) != 1 or obj.mode != 'OBJECT':
                raise ValueError(f"unexpected primitive output: {run['id']}")
            data = snapshot(obj)
            data['run_id'] = run['id']
            filename = run['id'] + '.json'
            write_json(stage / filename, data)
            records.append({
                'id': run['id'], 'file': filename, 'sha256': digest(stage / filename),
                'vertex_count': len(data['vertices']), 'edge_count': len(data['edges']),
                'face_count': len(data['faces']), 'uv_layer_count': len(data['uv_layers']),
            })
        executable = Path(bpy.app.binary_path)
        write_json(stage / 'manifest.json', {
            'schema_version': 1,
            'reference': {
                'version': list(bpy.app.version), 'version_string': bpy.app.version_string,
                **{name: text(getattr(bpy.app, name)) for name in
                   ('build_hash', 'build_branch', 'build_date', 'build_time', 'build_platform', 'build_type')},
                'executable_sha256': digest(executable),
            },
            'suite_sha256': digest(args.suite),
            'adapter_sha256': digest(Path(__file__)),
            'operator_properties_sha256': digest(stage / 'operator-properties.json'),
            'runs': records,
            'formora_execution': 'unrun',
            'product_acceptance': 'unrun',
        })
        stage.rename(args.output)
        print(json.dumps({'reference_runs': len(records), 'output': str(args.output),
                          'formora_execution': 'unrun', 'product_acceptance': 'unrun'}))
    except BaseException:
        shutil.rmtree(stage)
        raise


if __name__ == '__main__':
    main()
