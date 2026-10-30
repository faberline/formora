"""Validate every raw capacity record and preserve native budget overruns."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from check_merge_distance_diagnostic import initial, postconditions, same, receipt
from validate_merge_distance_state import validate
from merge_distance_capacity_inputs import load_assets, authored_scene
from merge_distance_capacity_seal import input_paths, verify, digest


def check(suite_path, seal_path, native, case_ids=()):
    seal = verify(suite_path, seal_path)
    suite = json.loads(suite_path.read_text()); grids = load_assets(suite_path, suite)
    capture = native/'capture'; manifest = json.loads((capture/'manifest.json').read_text())
    started = json.loads((native/'started.json').read_text()); terminal = json.loads((native/'terminal.json').read_text())
    receipt(manifest, started, terminal, (native/'stdout').read_bytes(), (native/'stderr').read_bytes())
    assert manifest['hardware'] == started['hardware'] == seal['hardware'], 'capacity captured hardware'
    assert started['capacity_seal_sha256'] == terminal['capacity_seal_sha256'] == digest(seal_path), 'capacity parent seal'
    assert started['suite_sha256'] == digest(suite_path), 'capacity parent input'
    assert manifest['capacity_seal'] == {'file': str(seal_path.resolve()), 'sha256': digest(seal_path)}, 'capacity capture seal'
    paths = [*input_paths(suite_path), seal_path.resolve()]
    assert manifest['input_hashes'] == {str(path): digest(path) for path in paths}, 'capacity input registry'
    runs = suite['runs']
    if case_ids:
        assert len(set(case_ids)) == len(case_ids) and set(case_ids) <= {run['id'] for run in runs}, 'capacity diagnostic case IDs'
        runs = [run for run in runs if run['id'] in case_ids]
    expected_scope = 'focused_distance_class_a_source_diagnostic' if case_ids else 'complete_distance_class_a_source_observations'
    assert manifest['scope'] == expected_scope and started['case_ids'] == list(case_ids), 'capacity complete/diagnostic scope'
    assert [row['id'] for row in manifest['runs']] == [run['id'] for run in runs], 'capacity case membership'
    names = {'manifest.json'} | {run['id']+suffix for run in runs for suffix in ['.json.gz', '.before.json.gz', '.blend.gz']}
    assert {path.name for path in capture.iterdir()} == names, 'capacity file membership'
    sha = lambda raw: hashlib.sha256(raw).hexdigest(); results = []
    for run, row in zip(runs, manifest['runs']):
        assert row['file'] == run['id']+'.json.gz' and row['native_file'] == run['id']+'.blend.gz', 'capacity source file identity'
        compressed = (capture/row['file']).read_bytes(); raw = gzip.decompress(compressed)
        assert sha(compressed) == row['sha256'] and sha(raw) == row['raw_sha256'] and len(raw) == row['raw_bytes'], 'capacity source record digest'
        value = json.loads(raw); same(run, value['run'], 'capacity run', 0.)
        spec = authored_scene(suite, run, grids); same(spec, value['scene_spec'], 'capacity authored scene', 0.)
        checkpoint = value['checkpoint']; assert checkpoint['file'] == run['id']+'.before.json.gz'
        packed_before = (capture/checkpoint['file']).read_bytes(); raw_before = gzip.decompress(packed_before)
        assert sha(packed_before) == checkpoint['sha256'] and sha(raw_before) == checkpoint['raw_sha256'], 'capacity checkpoint identity'
        same({'run': run, 'scene_spec': spec, 'phase': 'creation', 'before': value['before']}, json.loads(raw_before), 'capacity checkpoint', 0.)
        assert value['result'] == {'status': ['FINISHED'], 'error': None}, 'capacity operation status'
        assert value['save_status'] == value['reopen_status'] == ['FINISHED'], 'capacity native save/reopen status'
        assert value['native_file_stored'] == row['native_file'], 'capacity native identity'
        blend = gzip.decompress((capture/row['native_file']).read_bytes())
        assert sha(blend) == value['native_file_sha256'] and len(blend) == value['native_file_bytes'], 'capacity native file digest'
        initial(spec, value['before'])
        postconditions(run, spec, value['before'], value['after'])
        for phase in ['before', 'after', 'reloaded']: validate(spec, run, value[phase])
        same(value['after'], value['reloaded'], 'capacity complete reload')
        clock = value['native_clocks']
        assert all(type(clock[key]) is int for key in ['before_ns', 'core_after_ns', 'pipeline_after_ns']), 'capacity clock type'
        assert 0 < clock['before_ns'] <= clock['core_after_ns'] <= clock['pipeline_after_ns'], 'capacity clock order'
        assert clock['core_ms'] == (clock['core_after_ns']-clock['before_ns'])/1e6 and math.isfinite(clock['core_ms']), 'capacity core clock'
        assert clock['pipeline_ms'] == (clock['pipeline_after_ns']-clock['before_ns'])/1e6 and math.isfinite(clock['pipeline_ms']), 'capacity pipeline clock'
        assert clock['full_validation_inside_clock'] is True and clock['is_rust_product_timing'] is False, 'capacity validation/timing scope'
        count = len(spec['object_context']['edit_objects'])
        expected = {'edited_data': count, 'core_limit_ms': 250*count, 'pipeline_limit_ms': 2000*count,
                    'native_core_within_product_budget': clock['core_ms'] <= 250*count,
                    'native_pipeline_within_product_budget': clock['pipeline_ms'] <= 2000*count,
                    'is_rust_product_timing': False, 'rust_acceptance': 'unrun'}
        same(expected, value['native_budget_observations'], 'capacity budget observations', 0.)
        results.append({'id': run['id'], 'native_ms': {'core': clock['core_ms'], 'pipeline': clock['pipeline_ms']},
                        'budget_observations': expected, 'checks_passed': True, 'raw_sha256': row['raw_sha256']})
    assert manifest['rust_product_timing'] == manifest['product_acceptance'] == 'unrun'
    return {'source_capture_checks_passed': True, 'scope': expected_scope, 'cases': len(results), 'records': results,
            'source_pid': manifest['process_id'], 'capacity_seal_sha256': digest(seal_path),
            'source_over_budget_samples': {'core': sum(not r['budget_observations']['native_core_within_product_budget'] for r in results),
                                           'pipeline': sum(not r['budget_observations']['native_pipeline_within_product_budget'] for r in results)},
            'complete_capacity_source_gate': 'pending_two_fresh_complete_captures' if not case_ids else 'unrun',
            'rust_product_timing': 'unrun', 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['suite', 'capacity-seal', 'native', 'output']: parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--case', action='append', default=[])
    args = parser.parse_args(); result = check(args.suite.resolve(), args.capacity_seal.resolve(), args.native.resolve(), args.case)
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'records'}))
