#!/usr/bin/env python3
"""Capture actual object scale locks and native file roundtrips."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_multi_mesh_merge_reference as base
from generate_multi_mesh_merge_cases import author as base_inputs

ROOT = Path(__file__).resolve().parents[1]


def inputs(suite):
    names = ['tools/generate_object_state_cases.py', 'tools/blender_object_state_reference.py',
             'tools/launch_object_state_reference.py', 'tools/compare_object_state_reference.py',
             'tools/generate_multi_mesh_merge_cases.py', 'tools/blender_multi_mesh_merge_reference.py',
             'tools/blender_mesh_merge_reference.py', 'tools/blender_snap_menu_reference.py',
             'tools/blender_transform_reference.py', 'tools/blender_selection_reference.py',
             'tools/multi_mesh_merge_inputs.py', 'docs/contracts/object-state-query.md',
             'tools/compare_selection_reference.py', 'tools/compare_snap_menu_reference.py',
             'tools/compare_snap_rotation_reference.py', 'tools/compare_transform_reference.py',
             'tools/generate_snap_menu_cases.py', 'tools/generate_snap_rotation_cases.py',
             'tools/generate_mesh_transform_cases.py', 'tools/check_object_state_controls.py',
             'baseline/sources/object-state/manifest.json', 'baseline/sources/object-state/rna_object.cc']
    return [suite, *[ROOT/name for name in names]]


def snapshot():
    scene = bpy.context.scene
    result = {}
    sharing = {}
    for name in ['parent', 'a', 'alias', 'b', 'untouched']:
        obj = scene.objects[name]
        result[name] = {'lock_scale': list(obj.lock_scale), 'mode': obj.mode,
                        'matrix_world': [list(row) for row in obj.matrix_world],
                        'matrix_basis': [list(row) for row in obj.matrix_basis],
                        'matrix_parent_inverse': [list(row) for row in obj.matrix_parent_inverse],
                        'parent': obj.parent.name if obj.parent else None, 'type': obj.type}
        if obj.type == 'MESH':
            result[name]['geometry_counts'] = [len(obj.data.vertices), len(obj.data.edges), len(obj.data.polygons)]
            sharing.setdefault(obj.data.as_pointer(), []).append(name)
    return {'objects': result, 'sharing': sorted(sorted(group) for group in sharing.values()),
            'mode': bpy.context.mode}


class Capture:
    def __init__(self, args):
        assert list(bpy.app.version) == [5, 2, 3] and not bpy.app.background
        assert bpy.app.build_hash.decode() == 'e13b728c6880'
        assert base.digest(bpy.app.binary_path) == base.BINARY
        self.args = args
        self.suite = json.loads(args.suite.read_text())
        assert len(self.suite['runs']) == 160
        self.paths = inputs(args.suite)
        self.hashes = {p.relative_to(ROOT).as_posix(): base.digest(p) for p in self.paths}
        self.stage = args.output.with_name(args.output.name+'.staging')
        assert not args.output.exists() and not self.stage.exists()
        self.stage.mkdir(parents=True)
        self.mesh_suite = base_inputs()
        self.records = []
        self.native_files = Path(tempfile.mkdtemp(prefix='formora-object-state-blends-'))
        self.pending = None

    def step(self):
        # File loading invalidates the old UI context. A persistent timer
        # yields to Blender before reading the reopened scene or starting
        # another case. Only input-derived JSON survives that boundary.
        if not hasattr(bpy.context, 'object'):
            return .1
        if self.pending is not None:
            value = self.pending
            bpy.context.view_layer.update()
            value['reloaded'] = snapshot()
            run = value['run']
            path = self.stage/(run['id']+'.json')
            base.write(path, value)
            self.records.append({'id': run['id'], 'file': path.name, 'sha256': base.digest(path),
                'native_file': run['id']+'.blend.gz',
                'native_file_sha256': base.digest(self.stage/(run['id']+'.blend.gz'))})
            self.pending = None
            if len(self.records) % 20 == 0:
                print(json.dumps({'captured': len(self.records), 'required': 160}), flush=True)
            return .01
        if len(self.records) == len(self.suite['runs']):
            assert self.hashes == {p.relative_to(ROOT).as_posix(): base.digest(p) for p in self.paths}
            base.write(self.stage/'manifest.json', {
                'scope': 'complete_160_object_scale_lock_cases', 'version': list(bpy.app.version),
                'build_hash': bpy.app.build_hash.decode(), 'binary_sha256': base.digest(bpy.app.binary_path),
                'background': bpy.app.background, 'process_id': os.getpid(), 'command_line': sys.argv,
                'captured_utc': datetime.now(timezone.utc).isoformat(), 'input_hashes': self.hashes,
                'native_original_files': str(self.native_files), 'runs': self.records,
                'product_acceptance': 'unrun'})
            self.stage.rename(self.args.output)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(0)
        run = self.suite['runs'][len(self.records)]
        setup = {'id': run['id'], 'context': self.suite['base_context'], 'selection': 'both',
                 'history': 'both_vertex', 'mode': ['VERT'], 'frame': run['frame']}
        objects, _, _ = base.create(self.mesh_suite, setup)
        if run['mode'] == 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for name, value in self.suite['initial_locks'].items():
            objects[name].lock_scale = value
        bpy.context.view_layer.update()
        before = snapshot()
        objects[run['target']].lock_scale = run['lock_scale']
        bpy.context.view_layer.update()
        after = snapshot()
        native_file = self.native_files/(run['id']+'.blend')
        assert not native_file.exists()
        saved = sorted(bpy.ops.wm.save_as_mainfile(filepath=str(native_file), check_existing=False))
        file_bytes = native_file.read_bytes()
        (self.stage/(run['id']+'.blend.gz')).write_bytes(gzip.compress(file_bytes, mtime=0))
        self.pending = {'run': run, 'before': before, 'after': after,
            'save_status': saved, 'native_file_sha256': hashlib.sha256(file_bytes).hexdigest(),
            'native_file_bytes': len(file_bytes), 'native_file_stored': run['id']+'.blend.gz'}
        self.pending['reopen_status'] = sorted(bpy.ops.wm.open_mainfile(filepath=str(native_file)))
        return .1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])

    state = None

    def start():
        global state
        try:
            if state is None:
                state = Capture(args)
            return state.step()
        except BaseException:
            traceback.print_exc()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)

    bpy.app.timers.register(start, first_interval=.5, persistent=True)
