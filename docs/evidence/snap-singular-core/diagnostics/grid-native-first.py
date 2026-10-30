#!/usr/bin/env python3
"""Capture all twenty authored zero-scale grid forms before product code."""
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

import bpy

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
import blender_snap_delta_reference as delta
import blender_snap_rotation_reference as rotation
from blender_snap_singular_diagnostic import encode_invalid

GRID = ROOT / 'docs/evidence/scene-snap-core/performance/blender-grid-reference.py'
spec = importlib.util.spec_from_file_location('frozen_grid', GRID)
grid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture(output):
    assert not bpy.app.background and list(bpy.app.version) == [5, 2, 3]
    assert bpy.app.build_hash.decode() == 'e13b728c6880'
    assert sha(bpy.app.binary_path) == 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    config = json.loads((HERE / 'authored-forms.json').read_bytes())
    assert len(config['frames']) == 2 and len(config['forms']) == 10
    assert sha(ROOT / config['base_grid_path']) == config['base_grid_sha256']
    paths = [Path(__file__), HERE / 'authored-forms.json', GRID, grid.ADAPTER,
             grid.snap.ADAPTER, grid.snap.transform.BASE_PATH,
             ROOT / 'docs/contracts/snap-singular-core.md',
             ROOT / 'docs/contracts/snap-singular-local-matrix-policy.md',
             ROOT / 'tools/blender_snap_delta_reference.py',
             ROOT / 'tools/blender_snap_rotation_reference.py',
             ROOT / 'tools/blender_snap_singular_diagnostic.py',
             ROOT / 'baseline/fixtures/snap-menu.json', ROOT / config['base_grid_path']]
    paths += [HERE / frame['scene'] for frame in config['frames']]
    inputs = {str(p.resolve()): sha(p) for p in paths}
    assert not output.exists()
    stage = output.with_name(output.name + '.staging')
    stage.mkdir(parents=True, exist_ok=False)
    records = []
    for frame in config['frames']:
        scene = json.loads((HERE / frame['scene']).read_bytes())
        assert sha(HERE / frame['scene']) == frame['sha256']
        suite = json.loads((ROOT / 'baseline/fixtures/snap-menu.json').read_bytes())
        suite['mesh'] = grid.mesh_input(scene['mesh_assets']['grid'])
        proxy = copy.deepcopy(scene)
        for entity in proxy['entities'].values():
            entity['transform']['rotation'] = {'kind': 'euler', 'order': 'xyz', 'angles': [0., 0., 0.]}
        for form in config['forms']:
            run = copy.deepcopy(frame['authored_case'])
            run.update(id=frame['id'] + '-' + form['id'], operator=form['operator'], parameters=form['parameters'])
            run['seed']['indices'] = list(range(10201))
            objects, area, region = grid.create(suite, run, proxy)
            for name, item in objects.items():
                transform = scene['entities'][name]['transform']
                channels = copy.deepcopy(transform['rotation']['channels'])
                channels['mode'] = channels['mode'].upper()
                rotation.assign(item, channels)
                d = transform['delta']
                item.delta_location = d['translation']
                item.delta_rotation_euler = d['euler']
                item.delta_rotation_quaternion = d['quaternion_wxyz']
                item.delta_scale = d['scale']
            cursor = copy.deepcopy(scene['authoring_context']['cursor_orientation'])
            cursor['mode'] = cursor['mode'].upper()
            rotation.assign(bpy.context.scene.cursor, cursor)
            bpy.context.view_layer.update()
            before = delta.snapshot(objects, area, run)
            with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
                op = getattr(bpy.ops.view3d, form['operator'])
                assert op.poll()
                try:
                    result = {'status': sorted(op(**copy.deepcopy(form['parameters']))), 'error': None}
                except RuntimeError as error:
                    result = {'status': ['ERROR'], 'error': str(error)}
            bpy.context.view_layer.update()
            value = {'frame': frame['id'], 'form': form['id'], 'run': run,
                     'before': before, 'after': delta.snapshot(objects, area, run), 'result': result}
            invalid = []
            value = encode_invalid(value, '', invalid)
            raw = (json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode()
            path = stage / (run['id'] + '.json.gz')
            path.write_bytes(gzip.compress(raw, mtime=0))
            assert gzip.decompress(path.read_bytes()) == raw
            records.append({'frame': frame['id'], 'form': form['id'], 'file': path.name,
                            'sha256': sha(path), 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                            'raw_bytes': len(raw), 'result': result, 'nonfinite_fields': invalid})
            print(json.dumps({'captured': len(records), 'frame': frame['id'], 'form': form['id'], 'status': result['status']}), flush=True)
    assert inputs == {str(p.resolve()): sha(p) for p in paths}
    manifest = {'version': list(bpy.app.version), 'build_hash': bpy.app.build_hash.decode(),
                'binary_sha256': sha(bpy.app.binary_path), 'background': False,
                'process_id': os.getpid(), 'input_hashes': inputs, 'runs': records,
                'product_acceptance': 'unrun'}
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    stage.rename(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])

    def start():
        try:
            capture(args.output)
        except BaseException:
            traceback.print_exc()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)

    bpy.app.timers.register(start, first_interval=.5)
