"""Capture diagnostic distance merges with real native save and reopen."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import traceback

import bmesh
import bpy
from mathutils import Euler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_multi_mesh_merge_reference as base
from merge_distance_scene_inputs import scene, selection

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ['VERT', 'EDGE', 'FACE']


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def encoded(value):
    if isinstance(value, dict): return {key: encoded(item) for key, item in value.items()}
    if isinstance(value, list): return [encoded(item) for item in value]
    if type(value) is float and not math.isfinite(value):
        return {'$nonfinite': 'nan' if math.isnan(value) else ('positive_infinity' if value > 0 else 'negative_infinity')}
    return value


def area_context():
    window = bpy.context.window
    area = next(area for area in window.screen.areas if area.type == 'VIEW_3D')
    region = next(region for region in area.regions if region.type == 'WINDOW')
    return window, area, region


def create(spec):
    if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    # This is a dedicated factory-startup process. These IDs belong to this test.
    for obj in list(bpy.data.objects): bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0: bpy.data.meshes.remove(mesh)
    for name, value in spec['materials'].items():
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        material.diffuse_color = value['base_color']; material.roughness = value['roughness']; material.metallic = value['metallic']
    meshes = {}
    for name, authored in spec['mesh_assets'].items():
        mesh = base.create_mesh(name, authored)
        for edge, identifier in zip(mesh.edges, authored['edge_order']):
            edge.use_edge_sharp = identifier in authored['sharp_edges']
        if authored.get('custom_corner_normals'):
            normals = [normal for identifier in authored['face_order'] for normal in authored['custom_corner_normals'][identifier]]
            mesh.normals_split_custom_set(normals)
        meshes[name] = mesh
    objects = {}
    for name in spec['object_context']['order']:
        data = meshes[spec['data_sharing'][name]] if name in spec['data_sharing'] else None
        obj = bpy.data.objects.new(name, data); bpy.context.collection.objects.link(obj); objects[name] = obj
    for name, mesh in meshes.items():
        owner = next(obj for obj in objects.values() if obj.data == mesh)
        authored = spec['mesh_assets'][name]
        for group in authored['vertex_groups']: owner.vertex_groups.new(name=group)
        for i, identifier in enumerate(authored['vertex_order']):
            for group, weight in authored['vertex_weights'][identifier].items():
                owner.vertex_groups[group].add([i], weight, 'REPLACE')
        for obj in objects.values():
            if obj.data == mesh: assert [g.name for g in obj.vertex_groups] == authored['vertex_groups']
    for name, frame in spec['entity_frames'].items():
        obj = objects[name]; transform = frame['transform']; obj.parent = objects.get(frame['parent'])
        obj.location = transform['translation']; obj.rotation_mode = transform['rotation']['order'].upper()
        obj.rotation_euler = transform['rotation']['angles']; obj.scale = transform['scale']
        obj.select_set(name in spec['object_context']['selected'])
    bpy.context.view_layer.objects.active = objects[spec['object_context']['active']]
    settings = bpy.context.scene.tool_settings
    settings.mesh_select_mode = tuple(name in spec['mode'] for name in DOMAINS)
    settings.use_mesh_automerge = False; settings.use_mesh_automerge_and_split = False
    settings.use_keyframe_insert_auto = False
    bpy.context.scene.unit_settings.system = spec['units']['unit_system']
    bpy.context.scene.unit_settings.scale_length = spec['units']['unit_scale_length']
    bpy.ops.object.mode_set(mode='EDIT')
    for name in spec['object_context']['edit_objects']:
        obj = objects[name]; assert obj.mode == 'EDIT'
        mesh = spec['mesh_assets'][spec['data_sharing'][name]]
        intended = selection(mesh, spec, True)
        bm = bmesh.from_edit_mesh(obj.data); bm.select_mode = set(spec['mode'])
        collections = [bm.verts, bm.edges, bm.faces]; lookup = {}
        for domain, prefix, items in zip(DOMAINS, 'vef', collections):
            items.ensure_lookup_table()
            for i, item in enumerate(items):
                identifier = f'{prefix}{i:06}'; lookup[(domain, identifier)] = item
                item.hide = identifier in intended['hidden'][domain]
                item.select = False
        # A later deselected edge or face can clear earlier vertex selection.
        # Clear all domains first. Then add the authored selection only.
        for domain, prefix, items in zip(DOMAINS, 'vef', collections):
            for i, item in enumerate(items):
                if f'{prefix}{i:06}' in intended['selected'][domain]:
                    item.select_set(True)
        bm.select_flush_mode(); bm.select_history.clear()
        for item in intended['history']: bm.select_history.add(lookup[(item['domain'], item['id'])])
        bm.select_history.validate()
        bm.faces.active = lookup[('FACE', intended['active_face'])] if intended['active_face'] else None
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    window, area, region = area_context(); view = area.spaces.active.region_3d
    view.view_rotation = Euler([.25, -.375, .5], 'XYZ').to_quaternion()
    view.view_location = [0., 0., 0.]; view.view_distance = 10.; view.view_perspective = 'ORTHO'
    bpy.context.view_layer.update()
    with bpy.context.temp_override(window=window, area=area, region=region): view.update()
    return objects


def snapshot(spec):
    objects = {name: bpy.context.scene.objects[name] for name in spec['object_context']['order']}
    _, area, _ = area_context()
    state = base.snapshot(objects, area, spec)
    for name, obj in objects.items():
        if obj.type != 'MESH': continue
        edit = obj.data.is_editmode; bm = bmesh.from_edit_mesh(obj.data) if edit else bmesh.new()
        if not edit: bm.from_mesh(obj.data)
        temporary = bpy.data.meshes.new('DistanceNormalSnapshot')
        try:
            state['meshes'][name]['geometry']['edge_sharp'] = {f'e{i:06}': not edge.smooth for i, edge in enumerate(bm.edges)}
            bm.to_mesh(temporary); temporary.update()
            state['meshes'][name]['custom_normals_present'] = temporary.has_custom_normals
            attribute = temporary.attributes.get('custom_normal')
            if attribute is not None:
                assert attribute.data_type == 'INT16_2D' and attribute.domain == 'CORNER'
                public = [p for p in attribute.data[0].bl_rna.properties if p.identifier != 'rna_type' and
                          p.type == 'INT' and getattr(p, 'array_length', 0) == 2] if len(attribute.data) else []
                assert len(public) == 1 or not len(attribute.data)
                values = [list(getattr(item, public[0].identifier)) for item in attribute.data]
                state['meshes'][name]['packed_custom_normals'] = {
                    f'f{face.index:06}': [values[i] for i in face.loop_indices] for face in temporary.polygons}
            else:
                state['meshes'][name]['packed_custom_normals'] = {}
            state['meshes'][name]['native_attributes'] = [
                {'name': attr.name, 'type': attr.data_type, 'domain': attr.domain, 'length': len(attr.data)}
                for attr in temporary.attributes]
        finally:
            bpy.data.meshes.remove(temporary)
            if not edit: bm.free()
    return encoded(state)


class Capture:
    def __init__(self, args):
        assert list(bpy.app.version) == [5, 2, 3] and bpy.app.build_hash.decode() == 'e13b728c6880'
        assert not bpy.app.background and base.digest(bpy.app.binary_path) == base.BINARY
        self.args = args; self.suite = json.loads(args.suite.read_text()); self.records = []; self.pending = None
        self.stage = args.output.with_name(args.output.name+'.staging')
        assert not args.output.exists() and not self.stage.exists(); self.stage.mkdir(parents=True)
        self.native_files = Path(tempfile.mkdtemp(prefix='formora-distance-blends-'))
        names = ['generate_merge_distance_cases.py', 'merge_distance_scene_inputs.py', 'blender_merge_distance_reference.py',
                 'blender_multi_mesh_merge_reference.py', 'blender_mesh_merge_reference.py',
                 'blender_snap_menu_reference.py', 'blender_transform_reference.py', 'blender_selection_reference.py']
        names += ['check_merge_distance_diagnostic.py', 'merge_distance_normal_reference.py',
                  'generate_merge_distance_diagnostic.py', 'generate_merge_distance_normal_diagnostic.py',
                  'compare_snap_rotation_reference.py', 'compare_snap_delta_reference.py',
                  'merge_distance_cluster_reference.py']
        self.paths = [args.suite, *[ROOT/'tools'/name for name in names],
                      *sorted((ROOT/'baseline/sources/mesh-merge-distance').glob('*')),
                      *[ROOT/'baseline/sources/mesh-merge'/name for name in
                        ['manifest.json', 'bmo_removedoubles.cc', 'editmesh_tools.cc', 'customdata.cc', 'deform.cc']]]
        self.hashes = {str(path): base.digest(path) for path in self.paths}

    def step(self):
        if not hasattr(bpy.context, 'object'): return .1
        if self.pending is not None:
            value = self.pending; bpy.context.view_layer.update()
            value['reloaded'] = snapshot(value['scene_spec'])
            raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
            path = self.stage/(value['run']['id']+'.json.gz')
            with path.open('xb') as f: f.write(gzip.compress(raw, mtime=0))
            self.records.append({'id': value['run']['id'], 'file': path.name, 'sha256': base.digest(path),
                                 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'native_file': value['native_file_stored']})
            self.pending = None
            print(json.dumps({'captured': len(self.records), 'required': len(self.suite['runs'])}), flush=True)
            return .01
        if len(self.records) == len(self.suite['runs']):
            assert self.hashes == {str(path): base.digest(path) for path in self.paths}
            write(self.stage/'manifest.json', {'scope': 'diagnostic_distance_merge_capture', 'version': list(bpy.app.version),
                'build_hash': bpy.app.build_hash.decode(), 'binary_sha256': base.digest(bpy.app.binary_path),
                'background': bpy.app.background, 'process_id': os.getpid(), 'command_line': sys.argv,
                'captured_utc': datetime.now(timezone.utc).isoformat(), 'input_hashes': self.hashes,
                'native_original_files': str(self.native_files), 'runs': self.records,
                'full_source_gate': 'unrun', 'product_acceptance': 'unrun'})
            self.stage.rename(self.args.output); sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
        run = self.suite['runs'][len(self.records)]; spec = scene(self.suite, run); create(spec)
        before = snapshot(spec); window, area, region = area_context()
        with bpy.context.temp_override(window=window, area=area, region=region):
            assert bpy.ops.mesh.remove_doubles.poll()
            try:
                result = {'status': sorted(bpy.ops.mesh.remove_doubles(**run['parameters'])), 'error': None}
            except (TypeError, RuntimeError) as error:
                result = {'status': ['OPERATOR_EXCEPTION'], 'error': str(error)}
        bpy.context.view_layer.update(); after = snapshot(spec)
        native = self.native_files/(run['id']+'.blend'); assert not native.exists()
        saved = sorted(bpy.ops.wm.save_as_mainfile(filepath=str(native), check_existing=False))
        raw = native.read_bytes(); stored = run['id']+'.blend.gz'
        with (self.stage/stored).open('xb') as stream: stream.write(gzip.compress(raw, mtime=0))
        self.pending = {'run': run, 'scene_spec': spec, 'before': before, 'after': after, 'result': result,
                        'save_status': saved, 'native_file_sha256': hashlib.sha256(raw).hexdigest(),
                        'native_file_stored': stored, 'native_file_bytes': len(raw)}
        self.pending['reopen_status'] = sorted(bpy.ops.wm.open_mainfile(filepath=str(native)))
        return .1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:]); state = None
    def start():
        global state
        try:
            if state is None: state = Capture(args)
            return state.step()
        except BaseException:
            traceback.print_exc(); sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
    bpy.app.timers.register(start, first_interval=.5, persistent=True)
