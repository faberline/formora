"""Capture complete class-A source state and clocks with all validation inside.

Native clocks are observations. They never establish Rust timing acceptance.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_merge_distance_reference as native
from merge_distance_capacity_inputs import load_assets, authored_scene
from check_merge_distance_diagnostic import initial, postconditions, same
from validate_merge_distance_state import validate
from merge_distance_capacity_seal import input_paths, verify, hardware


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def store(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    encoded = gzip.compress(raw, mtime=0)
    with path.open('xb') as stream: stream.write(encoded)
    return {'file': path.name, 'sha256': hashlib.sha256(encoded).hexdigest(),
            'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw)}


class Capture:
    def __init__(self, args):
        assert list(bpy.app.version) == [5, 2, 3] and bpy.app.build_hash.decode() == 'e13b728c6880'
        assert not bpy.app.background and digest(Path(bpy.app.binary_path)) == native.base.BINARY
        self.args = args; self.suite = json.loads(args.suite.read_text())
        assert self.suite['scope'] == 'complete_distance_merge_class_a_capacity_registry'
        self.grids = load_assets(args.suite, self.suite)
        self.seal = verify(args.suite, args.capacity_seal, True)
        self.paths = [*input_paths(args.suite), args.capacity_seal.resolve()]
        self.hashes = {str(path): digest(path) for path in self.paths}
        self.runs = self.suite['runs']
        if args.case_ids:
            assert len(set(args.case_ids)) == len(args.case_ids) and set(args.case_ids) <= {r['id'] for r in self.runs}
            self.runs = [run for run in self.runs if run['id'] in args.case_ids]
        self.stage = args.output.with_name(args.output.name+'.staging')
        assert not args.output.exists(); self.stage.mkdir(parents=True, exist_ok=False)
        self.native_files = Path(tempfile.mkdtemp(prefix='formora-distance-capacity-blends-'))
        self.records = []; self.pending = None; self.current = None

    def step(self):
        if not hasattr(bpy.context, 'object'): return .1
        if self.pending is not None:
            value = self.pending; spec = value['scene_spec']; run = value['run']
            bpy.context.view_layer.update(); reloaded = native.snapshot(spec)
            validate(spec, run, reloaded)
            same(value['after'], reloaded, 'capacity-complete-reload')
            ended = time.perf_counter_ns(); value['reloaded'] = reloaded
            clock = value['native_clocks']; clock['pipeline_after_ns'] = ended
            clock['pipeline_ms'] = (ended-clock['before_ns'])/1e6
            data_count = len(spec['object_context']['edit_objects'])
            value['native_budget_observations'] = {
                'edited_data': data_count, 'core_limit_ms': 250*data_count, 'pipeline_limit_ms': 2000*data_count,
                'native_core_within_product_budget': clock['core_ms'] <= 250*data_count,
                'native_pipeline_within_product_budget': clock['pipeline_ms'] <= 2000*data_count,
                'is_rust_product_timing': False, 'rust_acceptance': 'unrun'}
            native_path = Path(value.pop('native_original_file'))
            raw = native_path.read_bytes(); value['native_file_sha256'] = hashlib.sha256(raw).hexdigest()
            value['native_file_bytes'] = len(raw)
            name = run['id']+'.blend.gz'
            with (self.stage/name).open('xb') as stream: stream.write(gzip.compress(raw, mtime=0))
            value['native_file_stored'] = name
            record = store(self.stage/(run['id']+'.json.gz'), value)
            self.records.append({'id': run['id'], **record, 'native_file': name})
            self.pending = None; self.current = None
            print(json.dumps({'captured': len(self.records), 'required': len(self.runs)}), flush=True)
            return .01
        if len(self.records) == len(self.runs):
            assert self.hashes == {str(path): digest(path) for path in self.paths}, 'capacity inputs changed during capture'
            manifest = {'scope': 'focused_distance_class_a_source_diagnostic' if self.args.case_ids else 'complete_distance_class_a_source_observations', 'runs': self.records,
                        'process_id': os.getpid(), 'command_line': sys.argv, 'background': bpy.app.background,
                        'version': list(bpy.app.version), 'build_hash': bpy.app.build_hash.decode(),
                        'binary_sha256': digest(Path(bpy.app.binary_path)),
                        'captured_utc': datetime.now(timezone.utc).isoformat(),
                        'native_original_files': str(self.native_files), 'rust_product_timing': 'unrun',
                        'product_acceptance': 'unrun', 'capacity_seal': {'file': str(self.args.capacity_seal.resolve()), 'sha256': digest(self.args.capacity_seal)},
                        'input_hashes': self.hashes, 'hardware': self.seal['hardware']}
            native.write(self.stage/'manifest.json', manifest)
            self.stage.rename(self.args.output); sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
        run = self.runs[len(self.records)]; spec = authored_scene(self.suite, run, self.grids)
        self.current = {'run': run, 'scene_spec': spec, 'phase': 'creation'}
        native.create(spec); before = native.snapshot(spec); self.current['before'] = before
        checkpoint = store(self.stage/(run['id']+'.before.json.gz'), self.current)
        self.current['phase'] = 'timed_initial_validation'
        started = time.perf_counter_ns()
        initial(spec, before); validate(spec, run, before)
        window, area, region = native.area_context()
        with bpy.context.temp_override(window=window, area=area, region=region):
            status = sorted(bpy.ops.mesh.remove_doubles(**run['parameters']))
        assert status == ['FINISHED'], 'capacity native operation did not finish'
        bpy.context.view_layer.update(); after = native.snapshot(spec); self.current['after'] = after
        postconditions(run, spec, before, after); validate(spec, run, after)
        core_after = time.perf_counter_ns(); self.current['phase'] = 'timed_native_save_reopen'
        native_path = self.native_files/(run['id']+'.blend')
        saved = sorted(bpy.ops.wm.save_as_mainfile(filepath=str(native_path), check_existing=False))
        assert saved == ['FINISHED'], 'capacity native save failed'
        self.pending = {'run': run, 'scene_spec': spec, 'before': before, 'after': after,
                        'result': {'status': status, 'error': None}, 'checkpoint': checkpoint,
                        'save_status': saved, 'native_original_file': str(native_path),
                        'native_clocks': {'before_ns': started, 'core_after_ns': core_after,
                                          'core_ms': (core_after-started)/1e6, 'full_validation_inside_clock': True,
                                          'is_rust_product_timing': False}}
        self.pending['reopen_status'] = sorted(bpy.ops.wm.open_mainfile(filepath=str(native_path)))
        assert self.pending['reopen_status'] == ['FINISHED'], 'capacity native reopen failed'
        return .1

    def retain_failure(self, error):
        value = {'current': self.current, 'pending': self.pending, 'error_type': type(error).__name__,
                 'error': str(error), 'process_id': os.getpid(), 'captured_cases': len(self.records),
                 'failed_required_sample': True, 'rust_product_timing': 'unrun', 'product_acceptance': 'unrun'}
        store(self.stage/'failed-required-sample.json.gz', native.encoded(value))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capacity-seal', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[], dest='case_ids')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    state = None
    def start():
        global state
        try:
            if state is None: state = Capture(args)
            return state.step()
        except BaseException as error:
            traceback.print_exc()
            if state is not None:
                try: state.retain_failure(error)
                except BaseException: traceback.print_exc()
            sys.stdout.flush(); sys.stderr.flush(); os._exit(1)
    bpy.app.timers.register(start, first_interval=.5, persistent=True)
