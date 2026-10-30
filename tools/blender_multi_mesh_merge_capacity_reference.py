#!/usr/bin/env python3
"""Capture the frozen two-grid workload; native duration is not Rust timing."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_multi_mesh_merge_reference as native
from multi_mesh_merge_capacity_inputs import input_paths

ROOT = Path(__file__).resolve().parents[1]


def capture(args):
    suite = json.loads(args.suite.read_text())
    assert len(suite['runs']) == 30
    assert list(bpy.app.version) == [5, 2, 3] and not bpy.app.background
    assert bpy.app.build_hash.decode() == 'e13b728c6880'
    assert native.digest(bpy.app.binary_path) == native.BINARY
    for name in ['mesh_a', 'mesh_b']:
        mesh = suite['mesh_assets'][name]
        assert [len(mesh[key]) for key in ['vertices', 'edges', 'polygons']] == [10201, 20200, 10000]
    paths = input_paths(args.suite)
    inputs = {p.relative_to(ROOT).as_posix(): native.digest(p) for p in paths}
    stage = args.output.with_name(args.output.name+'.staging')
    assert not args.output.exists() and not stage.exists()
    stage.mkdir(parents=True)
    (stage/'capture-lock.json').write_bytes((ROOT/'baseline/lock.json').read_bytes())
    native.write(stage/'operator-properties.json', native.single.properties())
    runs = suite['runs']
    if args.case_ids:
        assert len(args.case_ids) == len(set(args.case_ids))
        assert set(args.case_ids) <= {run['id'] for run in runs}
        runs = [run for run in runs if run['id'] in args.case_ids]
    records = []
    for run in runs:
        print(json.dumps({'starting_case': run['id']}), flush=True)
        objects, area, region = native.create(suite, run)
        before = native.snapshot(objects, area, suite)
        with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
            assert bpy.ops.mesh.merge.poll()
            started = time.perf_counter_ns()
            status = sorted(bpy.ops.mesh.merge(**run['parameters']))
            ended = time.perf_counter_ns()
        bpy.context.view_layer.update()
        record = {'data': {'run': run, 'before': before, 'after': native.snapshot(objects, area, suite),
                           'result': {'status': status, 'error': None}},
                  'native_operator_clock': {'before_ns': started, 'after_ns': ended,
                                            'elapsed_ms': (ended-started)/1e6,
                                            'is_Rust_product_timing': False}}
        raw = (json.dumps(record, indent=2, allow_nan=False)+'\n').encode()
        path = stage/(run['id']+'.json.gz')
        with path.open('xb') as stream:
            with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as compressed:
                compressed.write(raw)
        assert gzip.decompress(path.read_bytes()) == raw
        records.append({'id': run['id'], 'file': path.name, 'sha256': native.digest(path),
                        'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
                        'status': status})
        print(json.dumps({'captured': len(records), 'total': len(runs)}), flush=True)
    assert inputs == {p.relative_to(ROOT).as_posix(): native.digest(p) for p in paths}
    native.write(stage/'manifest.json', {
        'schema_version': 1, 'product': 'blender', 'version': list(bpy.app.version),
        'build_hash': bpy.app.build_hash.decode(), 'binary_sha256': native.digest(bpy.app.binary_path),
        'process_id': os.getpid(), 'background': bpy.app.background,
        'command_line': sys.argv, 'platform': platform.platform(),
        'captured_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'focused_capacity_diagnostic' if args.case_ids else 'complete_30_two_class_A_merge_cases',
        'input_hashes': inputs,
        'operator_properties_sha256': native.digest(stage/'operator-properties.json'),
        'capture_lock_sha256': native.digest(stage/'capture-lock.json'),
        'runs': records, 'product_acceptance': 'unrun', 'Rust_product_timing': 'unrun',
    })
    stage.rename(args.output)
    print(json.dumps({'captured': len(records), 'Rust_product_timing': 'unrun'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[], dest='case_ids')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])

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
