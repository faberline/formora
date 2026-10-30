"""Compare every semantic field from two fresh sealed source captures."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

from check_merge_distance_diagnostic import check, same
from merge_distance_source_seal import digest, verify


def compare(suite, seal_path, first, second):
    seal = verify(suite, seal_path)
    checks = [check(suite, folder/'capture', seal_path) for folder in [first, second]]
    assert all(result['diagnostic_checks_passed'] for result in checks), 'complete source case checks failed'
    manifests = [json.loads((folder/'capture/manifest.json').read_text()) for folder in [first, second]]
    assert manifests[0]['process_id'] != manifests[1]['process_id'], 'fresh process identity'
    assert manifests[0]['native_original_files'] != manifests[1]['native_original_files'], 'fresh native directory'
    assert manifests[0]['input_hashes'] == manifests[1]['input_hashes'], 'two-capture input identity'
    records = []
    fields = ['run', 'executed_parameters', 'scene_spec', 'before', 'after', 'reloaded', 'result', 'save_status', 'reopen_status']
    for left, right in zip(manifests[0]['runs'], manifests[1]['runs']):
        assert left['id'] == right['id'], 'case identity differs'
        values = [json.loads(gzip.decompress((folder/'capture'/row['file']).read_bytes()))
                  for folder, row in zip([first, second], [left, right])]
        for field in fields: same(values[0][field], values[1][field], left['id']+'/two-fresh/'+field)
        records.append({'id': left['id'], 'semantic_fields_matched': fields,
                        'first_raw_sha256': left['raw_sha256'], 'second_raw_sha256': right['raw_sha256']})
    assert len(records) == seal['cases'], 'full frozen source count'
    return {'both_complete_functional_captures_passed': True, 'cases': len(records), 'records': records,
            'source_pids': [manifest['process_id'] for manifest in manifests], 'source_seal_sha256': digest(seal_path),
            'argument_classifications_per_capture': dict(Counter(row['operation_classification'] for row in checks[0]['records'])),
            'source_capacity': 'unrun', 'full_source_gate': 'pending_capacity_and_admission', 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['suite', 'seal', 'first', 'second', 'output']: parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); result = compare(args.suite.resolve(), args.seal.resolve(), args.first.resolve(), args.second.resolve())
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'records'}))
