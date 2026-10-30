#!/usr/bin/env python3
"""Check diagnostic integrity. Never grant source or product acceptance."""
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from compare_snap_singular_reference import author, digest, provenance_inputs, tree, validate_run

folder = Path(__file__).resolve().parent
suite_path = ROOT / 'baseline/fixtures/snap-singular.json'
suite = json.loads(suite_path.read_text())
assert suite == author()
assert Counter(r['label'] for r in suite['runs']) == suite['groups_expected']
folders = [folder / 'diagnostic-01', folder / 'diagnostic-02']
manifests = [json.loads((p / 'manifest.json').read_text()) for p in folders]
assert manifests[0]['process_id'] != manifests[1]['process_id']
assert manifests[0]['input_hashes'] == manifests[1]['input_hashes']
assert manifests[0]['operator_properties_sha256'] == manifests[1]['operator_properties_sha256']
receipts = []
for capture, manifest in zip(folders, manifests):
    terminal = json.loads((folder / (capture.name + '-process') / 'terminal.json').read_text())
    assert terminal['terminal_exit_code'] == 0 and terminal['process_id'] == manifest['process_id']
    assert terminal['manifest_sha256'] == digest(capture / 'manifest.json')
    assert terminal['capture_lock_sha256'] == digest(capture / 'capture-lock.json')
    assert terminal['binary_sha256'] == manifest['binary_sha256']
    assert manifest['binary_sha256'] == 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    assert manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880'
    assert not manifest['background'] and manifest['scope'] == 'all_1764_nonfinite_diagnostic_NOT_ACCEPTANCE'
    assert manifest['product_acceptance'] == 'unrun'
    assert len(manifest['runs']) == 1764
    assert {p.name for p in capture.glob('*.json.gz')} == {r['id'] + '.json.gz' for r in suite['runs']}
    assert digest(capture / 'operator-properties.json') == manifest['operator_properties_sha256']
    assert digest(capture / 'capture-lock.json') == manifest['capture_lock_sha256']
    extra = [(n, s) for n, s in manifest['input_hashes'].items()
             if n.endswith('/tools/blender_snap_singular_diagnostic.py')]
    assert len(extra) == 1 and extra[0][1] == digest(ROOT / 'tools/blender_snap_singular_diagnostic.py')
    # The additional diagnostic adapter is checked above. All original
    # provenance is checked by the frozen strict comparator without changes.
    strict_provenance = copy.deepcopy(manifest)
    del strict_provenance['input_hashes'][extra[0][0]]
    provenance_inputs(capture, strict_provenance, suite_path)
    receipts.append(terminal)

report = {'diagnostic_integrity_passed': False, 'baseline_passed': False,
          'required_full_gate_passed': False, 'product_acceptance': 'unrun',
          'milestones_accepted': 0, 'cases': 1764, 'finite_cases': [], 'nonfinite_cases': [],
          'native_processes': [m['process_id'] for m in manifests],
          'terminal_receipts': receipts, 'position_channel_matrix_limit': 1e-6}
for index, run in enumerate(suite['runs']):
    values = []
    fields = []
    for capture, manifest in zip(folders, manifests):
        row = manifest['runs'][index]
        assert row['id'] == run['id'] and row['file'] == run['id'] + '.json.gz'
        stored = (capture / row['file']).read_bytes()
        assert hashlib.sha256(stored).hexdigest() == row['sha256']
        raw = gzip.decompress(stored)
        assert hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes']
        value = json.loads(raw)
        assert value['run'] == run and value['result'] == {'status': row['status'], 'error': None}
        actual = []
        def visit(v, path=''):
            if isinstance(v, dict):
                if '__source_nonfinite_diagnostic__' in v:
                    assert set(v) == {'__source_nonfinite_diagnostic__'}
                    item = v['__source_nonfinite_diagnostic__']
                    assert item['path'] == path
                    actual.append(item)
                else:
                    for k, x in v.items(): visit(x, path + '/' + k)
            elif isinstance(v, list):
                for i, x in enumerate(v): visit(x, path + '/' + str(i))
        visit(value)
        assert actual == row['nonfinite_fields']
        values.append(value); fields.append(actual)
    tree(values[0], values[1], run['id'])
    assert fields[0] == fields[1]
    if fields[0]:
        # Retain all tagged bits and paths. No substitution, projection or
        # numeric validation of invalid records is counted as a pass.
        report['nonfinite_cases'].append({'id': run['id'], 'fields': fields[0]})
    else:
        for value in values: validate_run(suite, run, value)
        report['finite_cases'].append(run['id'])
report['diagnostic_integrity_passed'] = True
report['nonfinite_case_count'] = len(report['nonfinite_cases'])
report['finite_case_count'] = len(report['finite_cases'])
report['checker_sha256'] = digest(Path(__file__))
with (folder / 'diagnostics/paired-diagnostic-check.json').open('x') as output:
    json.dump(report, output, indent=2, allow_nan=False); output.write('\n')
print(json.dumps({k: v for k, v in report.items() if k not in ['terminal_receipts', 'finite_cases', 'nonfinite_cases']}))
