"""Create and verify an immutable before-execution source/code seal."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from generate_merge_distance_complete import SCOPE, complete
from merge_distance_provenance import ROOT, input_paths


BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
COMMIT = 'e13b728c6880d3084d9d57c30031ed5df8b39dee'
LIMITS = {'continuous_absolute_limit': 1e-6, 'discrete': 'exact',
          'class_a': {'vertices': 10201, 'edges': 20200, 'quads': 10000},
          'per_data_core_ms': 250, 'per_data_save_fresh_read_ms': 2000,
          'two_data_core_ms': 500, 'two_data_save_fresh_read_ms': 4000,
          'required_capacity_samples_per_form': 3, 'full_validation_inside_clock': True}


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline_compatible():
    historical = json.loads((ROOT/'baseline/fixtures/mesh-merge-distance-source-lock-01.json').read_text())
    current = json.loads((ROOT/'baseline/lock.json').read_text())
    assert {key: value for key, value in historical.items() if key != 'artifacts'} == {
        key: value for key, value in current.items() if key != 'artifacts'}, 'fixed baseline criteria changed'
    assert current['artifacts'][:len(historical['artifacts'])] == historical['artifacts'], 'historical source pins changed'


def verify(suite_path, seal_path):
    suite = json.loads(suite_path.read_text()); seal = json.loads(seal_path.read_text())
    assert suite['scope'] == SCOPE and suite == complete(), 'sealed complete registry differs'
    assert seal['schema_version'] == 1 and seal['scope'] == SCOPE, 'source seal schema'
    assert seal['source_commit'] == COMMIT and seal['binary_sha256'] == BINARY, 'source seal identity'
    assert seal['acceptance_limits'] == LIMITS, 'source seal limits'
    assert seal['suite_sha256'] == digest(suite_path) and seal['cases'] == len(suite['runs']), 'source seal suite binding'
    paths = input_paths(suite_path)
    expected = {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}
    assert seal['input_hashes'] == expected, 'source seal code/source binding'
    assert seal['complete_source_execution_at_seal'] == 'unrun' and seal['rust_distance_implementation_at_seal'] == 'unrun', 'before-execution source seal'
    assert seal['independent_product_acceptance'] == 'unrun', 'source seal acceptance'
    baseline_compatible()
    assert len(seal['code_commit']) == 40, 'source code commit identity'
    subprocess.run(['git', 'merge-base', '--is-ancestor', seal['code_commit'], 'HEAD'], cwd=ROOT, check=True, capture_output=True)
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        blob = subprocess.check_output(['git', 'show', seal['code_commit']+':'+relative], cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest() == expected[relative], 'source seal committed input differs: '+relative
    return seal


def create(suite_path, output):
    suite = json.loads(suite_path.read_text())
    assert suite == complete() and suite['scope'] == SCOPE, 'complete registry required'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    paths = input_paths(suite_path)
    hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}
    for relative, actual in hashes.items():
        raw = subprocess.check_output(['git', 'show', commit+':'+relative], cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest() == actual, 'commit source code and inputs before sealing'
    result = {'schema_version': 1, 'scope': SCOPE, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'code_commit': commit, 'source_commit': COMMIT, 'binary_sha256': BINARY,
              'suite_sha256': digest(suite_path), 'cases': len(suite['runs']), 'input_hashes': hashes,
              'acceptance_limits': LIMITS, 'complete_source_execution_at_seal': 'unrun',
              'rust_distance_implementation_at_seal': 'unrun', 'independent_product_acceptance': 'unrun'}
    with output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    verify(suite_path, output)
    return {'sealed_cases': result['cases'], 'sealed_inputs': len(hashes), 'code_commit': commit,
            'source_seal_sha256': digest(output), 'complete_source_execution': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(create(args.suite.resolve(), args.output.resolve())))
