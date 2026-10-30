"""Compare all192 cases from two fresh complete native capacity captures."""
import argparse
import gzip
import json
from pathlib import Path

from check_merge_distance_capacity_reference import check
from check_merge_distance_diagnostic import same


def compare(suite, seal, first, second):
    reports = [check(suite, seal, folder) for folder in [first, second]]
    assert reports[0]['source_pid'] != reports[1]['source_pid'], 'fresh capacity process identities'
    assert all(report['cases'] == 192 and report['source_capture_checks_passed'] for report in reports), 'complete capacity source checks'
    manifests = [json.loads((folder/'capture/manifest.json').read_text()) for folder in [first, second]]
    assert manifests[0]['native_original_files'] != manifests[1]['native_original_files'], 'fresh capacity native files'
    assert manifests[0]['input_hashes'] == manifests[1]['input_hashes'], 'two capacity code/input identities'
    rows = []
    for left, right in zip(manifests[0]['runs'], manifests[1]['runs']):
        assert left['id'] == right['id']
        values = [json.loads(gzip.decompress((folder/'capture'/row['file']).read_bytes()))
                  for folder, row in zip([first, second], [left, right])]
        for key in ['run', 'scene_spec', 'before', 'after', 'reloaded', 'result', 'save_status', 'reopen_status']:
            same(values[0][key], values[1][key], left['id']+'/two-capacity/'+key)
        rows.append({'id': left['id'], 'semantic_fields_match': True,
                     'raw_sha256': [left['raw_sha256'], right['raw_sha256']]})
    return {'both_complete_capacity_sources_passed': True, 'samples_per_capture': 192, 'forms': 64, 'samples_per_form': 3,
            'records': rows, 'source_pids': [report['source_pid'] for report in reports],
            'source_over_budget_samples_per_capture': [report['source_over_budget_samples'] for report in reports],
            'rust_product_timing': 'unrun', 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['suite', 'capacity-seal', 'first', 'second', 'output']: parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); result = compare(args.suite.resolve(), args.capacity_seal.resolve(), args.first.resolve(), args.second.resolve())
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'records'}))
