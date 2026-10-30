#!/usr/bin/env python3
"""Recheck complete raw multi-data evidence without executing product operations."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import subprocess

from compare_multi_mesh_merge_reference import digest
from generate_multi_mesh_merge_cases import author
from multi_mesh_merge_runtime import source_preflight, references
from multi_mesh_merge_runtime_check import check_record, ROOT
from plan_multi_mesh_merge_pilot import plan
from runtime_artifacts import write_json


def header(report, suite, source):
    assert report['complete'] is True and report['failed_records'] == 0, 'incomplete/failed runtime'
    assert report['required_interfaces'] == ['cli', 'official_mcp_sdk'], 'missing actual interface'
    assert report['source_gate'] == source, 'source identity/gate differs'
    if report['scope'] == 'full_13440_per_interface':
        cases = suite['runs']
    else:
        assert report['scope'] == 'focused_pilot', 'unknown evidence scope'
        ids = set(plan(suite)['case_ids'])
        cases = [r for r in suite['runs'] if r['id'] in ids]
    expected = [(interface, case['id']) for interface in report['required_interfaces'] for case in cases]
    assert [(r['interface'], r['id']) for r in report['records']] == expected, 'missing/duplicate/reordered runtime cases'
    assert report['required_records'] == report['executed_records'] == len(expected), 'false record counts'
    assert all(r['status'] == 'passed' and r['error'] is None for r in report['records']), 'failed record marked passed'
    return cases


def audit(capture):
    report = json.loads((capture/'report.json').read_text())
    suite = author()
    folders, manifests, source = source_preflight(ROOT/'baseline/fixtures/mesh-merge-multi-data.json', suite)
    cases = header(report, suite, source)
    expected_source = [digest(f/'manifest.json') for f in folders]
    assert expected_source == report['source_manifest_sha256'], 'source manifests differ'
    tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', report['head'], '--',
                                      'src', 'tests', 'tools'], text=True).splitlines()
    tracked = {p for p in tracked if '__pycache__' not in Path(p).parts and not p.endswith('.pyc')}
    expected_inputs = tracked | {'Cargo.toml', 'Cargo.lock', 'baseline/fixtures/mesh-merge-multi-data.json',
        'docs/contracts/mesh-merge-multi-data-core.md',
        'docs/evidence/mesh-merge-multi-data-core/interface-evidence-contract.md',
        'docs/evidence/mesh-merge-core/continuation/pilot-native.py',
        'docs/evidence/mesh-merge-core/continuation/runtime-cli-mcp.py'}
    assert set(report['input_hashes']) == expected_inputs, 'frozen input registry differs'
    assert report['input_hashes'] == {name: digest(ROOT/name) for name in expected_inputs}, 'runtime input drift'
    assert digest(Path(report['binary'])) == report['binary_sha256'], 'product binary changed'
    case_index = {r['id']: (index, r) for index, r in enumerate(suite['runs'])}
    outcomes = Counter()
    for index, row in enumerate(report['records']):
        path = capture/row['file']
        assert path.relative_to(capture).parts[:2] == (row['interface'], row['id'])
        assert digest(path) == row['sha256'], 'raw record digest differs'
        record = json.loads(gzip.decompress(path.read_bytes()))
        assert record['interface'] == row['interface'] and record['status'] == 'passed'
        source_index, run = case_index[row['id']]
        refs = references(suite, run, source_index, folders, manifests)
        kind = check_record(suite, run, record, refs)
        assert row['kind'] == kind
        outcomes[kind] += 1
        assert json.loads((path.parent/'scene.json').read_text()) == record['saved_after']
        for call in record['calls']:
            if call['interface'] == 'cli':
                assert call['command'][0] == report['binary']
        if record['interface'] == 'official_mcp_sdk':
            for name in ['started', 'terminal']:
                assert json.loads((path.parent/'mcp-process'/(name+'.json')).read_text()) == record['mcp_process'][name]
            assert record['mcp_process']['started']['binary_sha256'] == report['binary_sha256']
            assert record['mcp_process']['terminal']['stderr_sha256'] == digest(path.parent/'mcp-process/stderr')
        if (index+1) % 250 == 0:
            print(json.dumps({'raw_records_verified': index+1, 'required': len(report['records'])}), flush=True)
    assert dict(outcomes) == report['outcomes'], 'runtime classifications differ'
    return {'raw_evidence_passed': True, 'scope': report['scope'], 'records': len(report['records']),
        'raw_calls_bound': 32*len(report['records']), 'source_cases_each': len(cases),
        'outcomes': dict(outcomes), 'report_sha256': digest(capture/'report.json'),
        'full_interface_matrix_passed': report['scope'] == 'full_13440_per_interface',
        'other_required_gates': 'pending', 'independent_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.capture.resolve())
    write_json(args.output, result)
    print(json.dumps(result))
