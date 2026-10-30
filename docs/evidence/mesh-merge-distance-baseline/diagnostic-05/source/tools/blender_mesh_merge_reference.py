#!/usr/bin/env python3
"""Capture native merge data without losing duplicate inherited capture tags."""
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_snap_menu_reference as snap
base = snap.base
physical_factor = snap.physical_factor
ROOT = Path(__file__).resolve().parents[1]
BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as output:
        json.dump(value, output, indent=2, allow_nan=False); output.write('\n')


def capture_inputs(suite):
    names = ['tools/blender_mesh_merge_reference.py', 'tools/blender_snap_menu_reference.py',
             'tools/blender_transform_reference.py', 'tools/blender_selection_reference.py',
             'tools/generate_mesh_merge_cases.py', 'tools/generate_snap_menu_cases.py',
             'tools/generate_mesh_transform_cases.py', 'baseline/fixtures/mesh-selection.json',
             'docs/contracts/mesh-merge-baseline.md', 'baseline/lock.json',
             'baseline/sources/mesh-merge/manifest.json']
    source = json.loads((ROOT / names[-1]).read_text())
    for row in source['reused_manifests']:
        assert digest(ROOT / row['path']) == row['sha256']; names.append(row['path'])
    for row in source['files']:
        assert digest(ROOT / row['repository_path']) == row['sha256']; names.append(row['repository_path'])
    return [suite, *[ROOT / name for name in names]]


def mesh_state(obj,factor):
    # A linked object can stay in OBJECT mode while its shared Mesh has a live
    # edit BMesh. Read the live data for every user of that Mesh.
    edit=obj.data.is_editmode
    bm=bmesh.from_edit_mesh(obj.data) if edit else bmesh.new()
    if not edit:bm.from_mesh(obj.data)
    try:
        bm.normal_update();collections=[bm.verts,bm.edges,bm.faces]
        layers=[items.layers.int[name] for items,name in zip(collections,base.LAYERS)]
        keys={item:f'{prefix}{index:06}' for prefix,items in zip('vef',collections) for index,item in enumerate(items)}
        key=lambda item:keys[item]
        geometry={'vertices':{key(v):list(v.co) for v in bm.verts},
            'edges':{key(e):sorted(key(v) for v in e.verts) for e in bm.edges},
            'faces':{key(f):[key(v) for v in f.verts] for f in bm.faces},
            'face_smooth':{key(f):f.smooth for f in bm.faces},
            'face_materials':{key(f):f.material_index for f in bm.faces},
            'edge_seams':{key(e):e.seam for e in bm.edges},
            'material_slots':[m.name for m in obj.data.materials],
            'uv_layers':{name:{key(f):[list(loop[layer].uv) for loop in f.loops] for f in bm.faces}
                         for name in bm.loops.layers.uv.keys() for layer in [bm.loops.layers.uv[name]]},
            'uv_layer_order':[layer.name for layer in obj.data.uv_layers],
            'active_uv_index':obj.data.uv_layers.active_index}
        deform=bm.verts.layers.deform.active
        groups={'names':[group.name for group in obj.vertex_groups],
                'weights':{key(v):{obj.vertex_groups[i].name:weight for i,weight in v[deform].items()} if deform else {} for v in bm.verts}}
        temporary=bpy.data.meshes.new('SnapNormalSnapshot')
        try:
            bm.to_mesh(temporary);temporary.update();temporary.calc_loop_triangles()
            corners=temporary.corner_normals
            normals={'faces':{},'corners':{}}
            for face in temporary.polygons:
                id=f'f{face.index:06}'
                assert list(face.vertices)==[int(key(v)[1:]) for v in list(bm.faces)[face.index].verts]
                normals['faces'][id]=list(face.normal)
                normals['corners'][id]=[list(corners[index].vector) for index in face.loop_indices]
        finally:bpy.data.meshes.remove(temporary)
        world={key(v):list(obj.matrix_world@v.co) for v in bm.verts}
        return {'geometry':geometry,'groups':groups,'data_edit_mode':edit,
                'source_component_ids':{domain:{key(item):item[layer] for item in items} for domain,items,layer in zip(base.DOMAINS,collections,layers)},
                'selected':{domain:sorted(key(item) for item in items if item.select) for domain,items in zip(base.DOMAINS,collections)},
                'hidden':{domain:sorted(key(item) for item in items if item.hide) for domain,items in zip(base.DOMAINS,collections)},
                'mode':[domain for domain,on in zip(base.DOMAINS,bpy.context.tool_settings.mesh_select_mode) if on] if edit else [],
                'history':[{'domain':'VERT' if isinstance(item,bmesh.types.BMVert) else 'EDGE' if isinstance(item,bmesh.types.BMEdge) else 'FACE','id':key(item)} for item in bm.select_history] if edit else [],
                'active_face':key(bm.faces.active) if edit and bm.faces.active is not None else None,
                'flags':{'mirror_x':obj.data.use_mirror_x,'mirror_y':obj.data.use_mirror_y,
                         'mirror_z':obj.data.use_mirror_z,'mirror_topology':obj.data.use_mirror_topology},
                'active_material_index':obj.active_material_index,'normals':normals,'world_vertices':world,
                'vertices_metres':{id:[v*factor for v in p] for id,p in geometry['vertices'].items()},
                'world_vertices_metres':{id:[v*factor for v in p] for id,p in world.items()}}
    finally:
        if not edit:bm.free()


def snapshot(objects,area,run):
    factor=physical_factor(run['context']);scene=bpy.context.scene;settings=scene.tool_settings
    names={item.as_pointer():name for name,item in objects.items()}
    matrix=lambda m:[list(row) for row in m]
    frames={}
    for name,item in sorted(objects.items()):
        frames[name]={'type':item.type,'mode':item.mode,'parent':None if item.parent is None else names[item.parent.as_pointer()],
            'location':list(item.location),'rotation':list(item.rotation_euler),'rotation_mode':item.rotation_mode,
            'scale':list(item.scale),'matrix_world':matrix(item.matrix_world),'matrix_local':matrix(item.matrix_local),
            'matrix_basis':matrix(item.matrix_basis),'matrix_parent_inverse':matrix(item.matrix_parent_inverse),
            'delta_location':list(item.delta_location),'delta_rotation':list(item.delta_rotation_euler),'delta_scale':list(item.delta_scale),
            'lock_location':list(item.lock_location),'lock_rotation':list(item.lock_rotation),'lock_scale':list(item.lock_scale),
            'selected':item.select_get(),'animation_data':item.animation_data is not None,
            'constraints':len(item.constraints),'modifiers':len(item.modifiers)}
    meshes={name:mesh_state(item,factor) for name,item in sorted(objects.items()) if item.type=='MESH'}
    shared={}
    for name,item in objects.items():
        if item.type=='MESH':shared.setdefault(item.data.as_pointer(),[]).append(name)
    view=area.spaces.active.region_3d
    return {'mode':bpy.context.mode,'objects':frames,'meshes':meshes,
        'sharing':sorted(sorted(group) for group in shared.values()),
        'active_object':None if bpy.context.view_layer.objects.active is None else names[bpy.context.view_layer.objects.active.as_pointer()],
        'cursor':{'location':list(scene.cursor.location),'rotation':list(scene.cursor.rotation_euler),
                  'rotation_mode':scene.cursor.rotation_mode,'matrix':matrix(scene.cursor.matrix)},
        'cursor_metres':[v*factor for v in scene.cursor.location],'physical_metres_factor':factor,
        'settings':{'pivot':settings.transform_pivot_point,'skip_children':settings.use_transform_skip_children,
            'correct_face_attributes':settings.use_transform_correct_face_attributes,
            'keep_connected':settings.use_transform_correct_keep_connected,
            'automerge':settings.use_mesh_automerge,'automerge_and_split':settings.use_mesh_automerge_and_split,
            'origins_only':settings.use_transform_data_origin,'autokey':settings.use_keyframe_insert_auto,
            'locations_only':settings.use_transform_pivot_point_align,'unit_system':scene.unit_settings.system,
            'unit_scale_length':scene.unit_settings.scale_length,'grid_spacing':area.spaces.active.overlay.grid_scale,
            'grid_subdivisions':area.spaces.active.overlay.grid_subdivisions,
            'view_perspective':view.view_perspective,'view_rotation':list(view.view_rotation),
            'view_location':list(view.view_location),'view_distance':view.view_distance,
            'view_matrix':matrix(view.view_matrix),'region_size':[[r.width,r.height] for r in area.regions if r.type=='WINDOW'][0]}}



def properties():
    result = {}
    for prop in bpy.ops.mesh.merge.get_rna_type().properties:
        if prop.identifier == 'rna_type': continue
        value = {'type': prop.type, 'description': prop.description}
        if hasattr(prop, 'default'): value['default'] = prop.default
        if prop.type == 'ENUM': value['enum'] = [item.identifier for item in prop.enum_items]
        result[prop.identifier] = value
    return result


def capture(args):
    suite = json.loads(args.suite.read_text())
    assert len(suite['runs']) == 1024 and list(bpy.app.version) == [5, 2, 3]
    assert not bpy.app.background and bpy.app.build_hash.decode() == 'e13b728c6880'
    assert digest(bpy.app.binary_path) == BINARY
    stage = args.output.with_name(args.output.name + '.staging')
    assert not args.output.exists() and not stage.exists()
    paths = capture_inputs(args.suite)
    inputs = {str(p.resolve()): digest(p) for p in paths}
    runs = suite['runs']
    if args.case_ids:
        assert set(args.case_ids) <= {r['id'] for r in runs}
        runs = [r for r in runs if r['id'] in args.case_ids]
    stage.mkdir(parents=True)
    with (stage / 'capture-lock.json').open('xb') as output:
        output.write((ROOT / 'baseline/lock.json').read_bytes())
    write(stage / 'operator-properties.json', properties())
    records = []
    for index, run in enumerate(runs):
        objects, area, region = snap.create(suite, run)
        before = snapshot(objects, area, run)
        with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
            assert bpy.ops.mesh.merge.poll(), ('invalid source setup', run['id'])
            try:
                result = {'status': sorted(bpy.ops.mesh.merge(**copy.deepcopy(run['parameters']))), 'error': None}
            except TypeError as error:
                assert run['expected_empty_enum_boundary'] and 'enum' in str(error).lower(), str(error)
                result = {'status': ['ENUM_REJECTED'], 'error': str(error)}
        bpy.context.view_layer.update()
        raw = (json.dumps({'run': run, 'before': before, 'after': snapshot(objects, area, run),
                           'result': result}, indent=2, allow_nan=False) + '\n').encode()
        path = stage / (run['id'] + '.json.gz')
        with path.open('xb') as output:
            with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as compressed:
                compressed.write(raw)
        assert gzip.decompress(path.read_bytes()) == raw
        records.append({'id': run['id'], 'file': path.name, 'sha256': digest(path),
                        'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
                        'status': result['status']})
        if (index + 1) % 100 == 0: print(json.dumps({'captured': index + 1, 'total': len(runs)}), flush=True)
    assert inputs == {str(p.resolve()): digest(p) for p in paths}
    write(stage / 'manifest.json', {'schema_version': 1, 'product': 'blender',
        'version': list(bpy.app.version), 'build_hash': bpy.app.build_hash.decode(),
        'process_id': os.getpid(), 'binary_sha256': digest(bpy.app.binary_path),
        'scope': 'focused_diagnostic' if args.case_ids else 'complete_1024_authored_mesh_merge_cases',
        'captured_utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
        'command_line': sys.argv, 'background': bpy.app.background, 'input_hashes': inputs,
        'operator_properties_sha256': digest(stage / 'operator-properties.json'),
        'capture_lock_sha256': digest(stage / 'capture-lock.json'), 'runs': records,
        'product_acceptance': 'unrun'})
    stage.rename(args.output)
    print(json.dumps({'captured': len(records), 'product_acceptance': 'unrun'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[], dest='case_ids')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    def start():
        try: capture(args)
        except BaseException:
            traceback.print_exc(); sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
        sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
    bpy.app.timers.register(start, first_interval=.5)
