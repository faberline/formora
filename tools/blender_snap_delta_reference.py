#!/usr/bin/env python3
"""Capture frozen delta snapping cases in one native viewport process."""
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

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_snap_rotation_reference as rotation

ROOT = Path(__file__).resolve().parents[1]
BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write('\n')


def capture_inputs(suite):
    names = ['tools/blender_snap_delta_reference.py', 'tools/blender_snap_rotation_reference.py',
             'tools/blender_snap_menu_reference.py', 'tools/blender_transform_reference.py',
             'tools/blender_selection_reference.py', 'tools/generate_snap_delta_cases.py',
             'tools/generate_snap_rotation_cases.py', 'tools/generate_snap_menu_cases.py',
             'tools/generate_mesh_transform_cases.py', 'docs/contracts/snap-delta-baseline.md',
             'baseline/lock.json', 'baseline/sources/snap-delta/manifest.json']
    source = json.loads((ROOT / names[-1]).read_text())
    for row in source['reused_manifests']:
        assert digest(ROOT / row['path']) == row['sha256']
        names.append(row['path'])
    for row in source['files']:
        assert digest(ROOT / row['repository_path']) == row['sha256']
        names.append(row['repository_path'])
    return [suite, *[ROOT / name for name in names]]


def create(suite, run):
    objects, area, region = rotation.create(suite, run)
    for name, item in objects.items():
        authored = run['deltas'] if name in ['target', 'secondary'] else suite['role_deltas'][name]
        item.delta_location = authored['location']
        item.delta_rotation_euler = authored['euler']
        item.delta_rotation_quaternion = authored['quaternion_wxyz']
        item.delta_scale = authored['scale']
        item.lock_location = run['context']['lock_location'] if name in ['target', 'secondary'] else [False] * 3
    bpy.context.view_layer.update()
    return objects, area, region


def snapshot(objects, area, run):
    state = rotation.snapshot(objects, area, run)
    state['delta_channels'] = {name: {'location': list(item.delta_location),
        'euler': list(item.delta_rotation_euler), 'quaternion_wxyz': list(item.delta_rotation_quaternion),
        'scale': list(item.delta_scale)} for name, item in sorted(objects.items())}
    return state


def capture(args):
    suite = json.loads(args.suite.read_text())
    assert len(suite['runs']) == 1792 and list(bpy.app.version) == [5, 2, 3]
    assert not bpy.app.background and bpy.app.build_hash.decode() == 'e13b728c6880'
    assert digest(bpy.app.binary_path) == BINARY
    assert 'delta_rotation_axis_angle' not in bpy.types.Object.bl_rna.properties
    stage = args.output.with_name(args.output.name + '.staging')
    assert not args.output.exists() and not stage.exists(), 'refuse existing output/staging'
    paths = capture_inputs(args.suite)
    inputs = {str(p.resolve()): digest(p) for p in paths}
    runs = suite['runs']
    if args.case_ids:
        assert set(args.case_ids) <= {r['id'] for r in runs}
        runs = [r for r in runs if r['id'] in args.case_ids]
    stage.mkdir(parents=True)
    with (stage / 'capture-lock.json').open('xb') as output:
        output.write((ROOT / 'baseline/lock.json').read_bytes())
    metadata = {'operators': rotation.snap.properties(), 'rotation': rotation.rotation_properties(),
                'delta_axis_angle_exposed': False}
    metadata['delta_properties'] = {}
    for name in ['delta_location', 'delta_rotation_euler', 'delta_rotation_quaternion', 'delta_scale']:
        p = bpy.types.Object.bl_rna.properties[name]
        metadata['delta_properties'][name] = {'type': p.type, 'array_length': p.array_length,
            'description': p.description, 'default': list(p.default_array)}
    write(stage / 'operator-properties.json', metadata)
    records = []
    for index, run in enumerate(runs):
        objects, area, region = create(suite, run)
        before = snapshot(objects, area, run)
        op = getattr(bpy.ops.view3d, run['operator'])
        with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
            assert op.poll(), ('invalid source setup', run['id'])
            try:
                result = {'status': sorted(op(**copy.deepcopy(run['parameters']))), 'error': None}
            except RuntimeError as error:
                result = {'status': ['ERROR'], 'error': str(error)}
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
        if (index + 1) % 100 == 0:
            print(json.dumps({'captured': index + 1, 'total': len(runs)}), flush=True)
    assert inputs == {str(p.resolve()): digest(p) for p in paths}, 'capture input changed'
    write(stage / 'manifest.json', {'schema_version': 1, 'product': 'blender',
        'version': list(bpy.app.version), 'build_hash': bpy.app.build_hash.decode(),
        'process_id': os.getpid(), 'binary_sha256': digest(bpy.app.binary_path),
        'scope': 'focused_diagnostic' if args.case_ids else 'complete_1792_authored_snap_delta_cases',
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
