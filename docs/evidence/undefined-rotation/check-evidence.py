"""Read-only integrity and gate checks for this bounded RNG candidate."""
from pathlib import Path
import hashlib
import json
import math
import re
import struct
import subprocess

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[2]


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = load(FOLDER / 'manifest.json')
    assert manifest['candidate'] == '0e992339d70b2fb61457b20665e746698f2a95ca'
    actual = {str(p.relative_to(FOLDER)) for p in FOLDER.rglob('*')
              if p.is_file() and p != FOLDER / 'manifest.json'}
    assert actual == set(manifest['artifacts'])
    for name, expected in manifest['artifacts'].items():
        assert sha(FOLDER / name) == expected, name
    for name, expected in manifest['shared_source_evidence'].items():
        assert sha(ROOT / name) == expected, name
    lock = load(ROOT / 'baseline/lock.json')
    previous = json.loads(subprocess.check_output([
        'git', 'show', 'cefd3f27d0ac0f6d70d6c5a837d99ff440917bc6:baseline/lock.json'], cwd=ROOT))
    assert len(lock['artifacts']) == 3807 and len(previous['artifacts']) == 3805
    assert lock['artifacts'][:3805] == previous['artifacts']
    for row in lock['artifacts']:
        assert sha(ROOT / row['path']) == row['sha256'], row['path']
    checks = FOLDER / 'checks'
    assert sum(map(int, re.findall(r'test result: ok\. (\d+) passed; 0 failed; 0 ignored;',
                                  (checks / 'rust.stdout').read_text()))) == 229
    python = (checks / 'python.stderr').read_text()
    assert re.search(r'Ran 90 tests in ', python) and re.search(r'\nOK\s*$', python)
    assert all(row['exit_code'] == 0 for row in load(checks / 'final-checks.json'))
    statuses = {row['name']: row['exit_code'] for row in load(checks / 'regressions.json')}
    assert len(statuses) == 10 and statuses['full'] == 0 and statuses['strict'] == 2
    assert all(code == 0 for name, code in statuses.items() if name not in ['full', 'strict'])
    for name in ['baseline', 'strict']:
        result = load(checks / (name + '.stdout'))
        assert result['structurally_valid'] and not result['baseline_ready'] and result['problems'] == []
        assert (result['sources'], result['pending_sources'], result['pending_features']) == (9047, 9003, 31)
    reference = ROOT / 'baseline/reference/blender-5.2.3/random-falloff'
    source = load(reference / 'report.json')
    assert source['passed'] and not source['operator_sequence_acceptance']
    assert source['processes'][0]['pid'] != source['processes'][1]['pid']
    assert source['draws_per_seed'] == 4096 and len(source['seeds']) == 10
    for name, expected in source['artifacts'].items():
        assert sha(reference / name) == expected
    for name, expected in source['input_hashes'].items():
        assert sha(ROOT / name) == expected
    for kind in ['sequence', 'distribution']:
        assert (reference / ('first-' + kind + '.bin')).read_bytes() == (reference / ('repeat-' + kind + '.bin')).read_bytes()
    values = [row[0] for row in struct.iter_unpack('<f', (reference / 'first-distribution.bin').read_bytes())]
    assert len(values) == 1048576 and all(math.isfinite(v) and 0 <= v <= 1 for v in values)
    mean = math.fsum(values) / len(values)
    variance = math.fsum((v - mean) ** 2 for v in values) / len(values)
    correlation = (math.fsum((a - mean) * (b - mean) for a, b in zip(values, values[1:]))
                   / (len(values)-1) / variance)
    bins = [0] * 256
    for value in values:
        bins[min(255, int(value * 256))] += 1
    assert abs(mean - 0.5) <= 0.002 and abs(variance - 1/12) <= 0.001 and abs(correlation) < 0.01
    assert all(abs(n-4096)/4096 <= 0.12 for n in bins)
    assert (mean, variance, correlation, bins) == tuple(source['statistics'][k]
                                                      for k in ['mean', 'variance', 'lag_one_correlation', 'histogram'])
    runtime = load(FOLDER / 'rng/report.json')
    full = load(FOLDER / 'full/report.json')
    assert runtime['passed'] and runtime['checks'] == 96
    assert full['checks'] == 2406 and full['scope'] == 'full_1203_cases_both_interfaces'
    assert full['required_full_gate_passed'] and full['passed']
    assert sum(r['status'] == 'failed' for r in full['runs']) == 0
    assert (full['defined_deterministic_source_checks'], full['stochastic_support_checks'], full['approved_source_rejection_checks']) == (2344, 48, 14)
    binary_sha = manifest['binary_sha256']
    for report in [runtime, full, load(FOLDER / 'normal/manifest.json')]:
        assert report['binary_sha256'] == binary_sha
        for name, expected in report['input_hashes'].items():
            assert sha(ROOT / name) == expected, name
    storage = load(FOLDER / 'full/raw-result-storage.json')
    assert storage['all_captured_bytes_checked'] and storage['captured_results'] == 2406
    assert (storage['retained_unchanged_results'], storage['changed_policy_results']) == (2392, 14)
    assert set(storage['rows']) == {row['file'] for row in full['runs']}
    error = 'mesh transform rotation cannot constrain all three axes: undefined Blender 5.2.3 source behavior'
    policy_count = 0
    for row in full['runs']:
        kept = storage['rows'][row['file']]
        raw = ROOT / kept['retained_path']
        data = raw.read_bytes()
        assert sha(raw) == kept['sha256'] == row['sha256']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == kept['git_blob']
        if row.get('comparison_kind') == 'human_approved_undefined_rotation_rejection':
            policy_count += 1
            assert not kept['reused'] and raw.parent == FOLDER / 'full'
            value = json.loads(data)
            assert value['status'] == 'passed' and value['error'] == error and value['result'] is None
            assert value['before'] == value['after'] and value['world_queries']['before'] == value['world_queries']['after']
            assert not value['comparison_policy']['numeric_source_match_claimed']
            assert value['comparison_policy']['policy_outcome'] == 'REJECTED'
            evidence = value['policy_evidence']
            assert evidence['before_scene'] == evidence['after_scene']
            assert evidence['saved_scene_before_sha256'] == evidence['saved_scene_after_sha256']
            assert value['request']['commands'][0]['transform']['constraint_axis'] == [True, True, True]
            previous_raw = load(ROOT / 'docs/evidence/random-falloff/full' / row['file'])
            assert previous_raw['status'] == 'failed'
        else:
            assert kept['reused'] and kept['parent_commit'] == 'cefd3f27d0ac0f6d70d6c5a837d99ff440917bc6'
            assert data == (ROOT / 'docs/evidence/random-falloff/full' / row['file']).read_bytes()
    assert policy_count == 14
    for row in runtime['records']:
        assert sha(FOLDER / 'rng' / row['file']) == row['sha256']
        raw = load(FOLDER / 'rng' / row['file'])
        assert raw['passed'] and len(raw['rejected_requests']) == 5
        assert raw['result']['transforms'] == raw['replay']['transforms']
        assert raw['rejected_requests'][-1]['error'] == error and raw['failed_rotation_batch'] == error
        assert raw['after']['scene']['mesh_assets'] == raw['fresh_reload']['scene']['mesh_assets']
        if row['interface'] == 'cli':
            assert raw['one_shot_cli']['result']['transforms'] == raw['result']['transforms']
    assert sha(FOLDER / 'rng/scene-apply-schema.json') == runtime['scene_apply_schema_sha256']
    reports = {'normal': ('manifest.json', 'cases', 42), 'scale': ('report.json', 'checks', 8),
               'selection': ('report.json', 'checks', 1060), 'creation': ('report.json', 'checks', 262)}
    for name, (file, key, count) in reports.items():
        report = load(FOLDER / name / file)
        assert report['passed'] and report[key] == count
    for name in ['primitives', 'polygon']:
        assert load(FOLDER / name / 'report.json')['passed']
    perf = load(FOLDER / 'performance/report.json')
    assert perf['passed'] and len(perf['runs']) == 9
    assert (FOLDER / 'performance/capture-driver.rs').read_bytes() == (ROOT / 'docs/evidence/mesh-transform-core/frame-performance/capture-driver.rs').read_bytes()
    for row in perf['runs']:
        assert row['core_ms'] == (row['core_end_ns'] - row['core_start_ns']) / 1e6
        assert row['operation_save_reload_ms'] == (row['pipeline_end_ns'] - row['pipeline_start_ns']) / 1e6
        assert row['maximum_core_ms'] == 250 and row['maximum_pipeline_ms'] == 2000
        assert row['core_ms'] <= 250 and row['operation_save_reload_ms'] <= 2000 and row['passed']
        assert row['reload_equal'] and row['topology_preserved'] and row['editing_preserved']
    comparison = load(FOLDER / 'performance/source-comparison-report.json')
    assert comparison['passed'] and comparison['fixed_tolerance'] == 1e-6
    assert comparison['source_repeat_geometry_and_normals_exact'] and len(comparison['records']) == 9
    assert comparison['comparison_driver_sha256'] == sha(FOLDER / 'performance/source-comparison.py')
    assert comparison['reference_binary_sha256'] == 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    for row in comparison['records']:
        assert row['passed'] and row['components'] == 180603
        assert row['scene_sha256'] == sha(FOLDER / 'performance' / f"{row['operation']}-{row['run']}.json")
        assert all(error == 0 for error in row['maximum_absolute_errors'].values())
    for name in ['gpu', 'gpu-legacy']:
        report = load(FOLDER / name / 'manifest.json')
        assert report['passed'] and '(Metal,' in report['gpu'] and report['fresh_reload_identical']
        assert report['binary_sha256'] == binary_sha and report['driver_sha256'] == sha(FOLDER / name / 'capture-driver.py')
        assert report['changed_pixels'] > 500 and report['changed_vertices'] > 1
        assert (FOLDER / name / 'after.png').read_bytes() == (FOLDER / name / 'reloaded.png').read_bytes()
        for file, expected in report['artifacts'].items():
            assert sha(FOLDER / name / file) == expected
    probe = load(FOLDER / 'source-probe/report.json')
    assert probe['passed'] and probe['unmodified_callback_body']
    assert not probe['probe_reads_uninitialized_memory'] and not probe['all_three_axis_callback_writes_output']
    assert probe['binary_sha256'] == 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert len(probe['cases']) == 8 and probe['cases'][-1] == {'mask': 7, 'axis': [41,-43,47]}
    assert probe['cases'] == [json.loads(line) for line in (FOLDER / 'source-probe/probe.stdout').read_text().splitlines()]
    body = (FOLDER / 'source-probe/callback.cc').read_text().removesuffix('\n')
    assert hashlib.sha256(body.encode()).hexdigest() == probe['callback_sha256']
    assert body in (ROOT / 'baseline/sources/mesh-transform-core/transform_constraints.cc').read_text()
    vector = load(FOLDER / 'defect-sources/manifest.json')
    vector_data = (FOLDER / 'defect-sources/BLI_math_vector_types.hh').read_bytes()
    assert vector['commit'] == 'e13b728c6880d3084d9d57c30031ed5df8b39dee'
    assert hashlib.sha256(vector_data).hexdigest() == vector['sha256']
    assert hashlib.sha1(b'blob '+str(len(vector_data)).encode()+b'\0'+vector_data).hexdigest() == vector['git_blob']
    assert b'VecBase() = default;' in vector_data
    for name, expected in probe['input_hashes'].items():
        assert sha(ROOT / name) == expected
    for name, expected in probe['artifacts'].items():
        assert sha(FOLDER / 'source-probe' / name) == expected
    isolated = load(FOLDER / 'isolation/report.json')
    assert isolated['new_rotation_rejection_checked']

    assert isolated['passed'] and isolated['new_source_rng_undo_replay_checked']
    assert isolated['binary_sha256'] == binary_sha and isolated['denial_control_exit_code'] != 0
    assert isolated['driver_sha256'] == sha(FOLDER / 'isolation/capture-driver.py')
    world = load(FOLDER / 'source-oracle/report.json')
    assert world['passed'] and world['binary_sha256'] == binary_sha and len(world['cases']) == 6
    assert all(row['matrix_exact'] and row['point_exact'] and row['queries_preserve_disk'] for row in world['cases'])
    assert manifest['milestones_accepted'] == 0 and manifest['required_transform_gate_passed']
    print(json.dumps({'passed': True, 'candidate': manifest['candidate'],
                      'artifact_files': len(manifest['artifacts']), 'new_interface_checks': 96,
                      'original_results_byte_identical': 2392, 'approved_rejection_checks': 14, 'failed_checks': 0,
                      'milestones_accepted': 0}))


if __name__ == '__main__':
    main()
