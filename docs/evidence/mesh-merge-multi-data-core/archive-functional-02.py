"""Archive completed retained checks. Never archive the live new matrix as passed."""
from pathlib import Path
import gzip
import hashlib
import json

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
TEMP = Path('/private/tmp')
OUT = ROOT/'docs/evidence/mesh-merge-multi-data-core/completed-functional-02'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
load = lambda p: json.loads(Path(p).read_text())
retained = TEMP/'formora-multi-merge-retained-api-01'
parent = load(retained/'report.json')
assert parent['passed'] and parent['verification_inputs_unchanged']
assert all(row['passed'] and row['terminal_exit_code'] == 0 for row in parent['records'])
expected = {'delta': 3584, 'rotation': 4992, 'scene': 1100, 'single': 2244, 'transform': 2406}
audits = TEMP/'formora-multi-merge-retained-api-audit-01'
for name, count in expected.items():
    report = load(audits/(name+'.json'))
    assert report['passed'] and report['requests'] == count
assert load(TEMP/'formora-multi-merge-single-retained-audit-01/report.json')['checks'] == 2048
assert sum(expected.values())+2048 == 16374
asset_audit = load(TEMP/'formora-multi-merge-asset-audit-01.json')
assert asset_audit['passed'] and asset_audit['checks'] == 1687 and len(asset_audit['forged_result_controls']) == 7
assert load(TEMP/'formora-multi-merge-retained-small-gates-01/report.json')['passed']
assert load(TEMP/'formora-multi-merge-retained-native-gates-01/report.json')['passed']
assert load(TEMP/'formora-multi-merge-retained-gpu-01/report.json')['passed']
assert load(TEMP/'formora-multi-merge-retained-compile-01/report.json')['passed']

OUT.mkdir(exist_ok=False)
rows, empty = [], []


def archive(source, relative):
    assert source.is_file() and not source.is_symlink(), source
    raw = source.read_bytes()
    keep = source.suffix in ['.gz', '.png', '.py'] or source.name in [
        'report.json', 'manifest.json', 'bindings.json', 'started.json', 'terminal.json', 'visual-qa.json']
    target = OUT/(relative if keep else relative+'.gz')
    payload = raw if keep else gzip.compress(raw, mtime=0, compresslevel=6)
    if not keep:
        assert gzip.decompress(payload) == raw
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as f:
        f.write(payload)
    assert source.read_bytes() == raw and target.read_bytes() == payload
    rows.append({'source': str(source), 'stored': target.relative_to(OUT).as_posix(),
                 'raw_bytes': len(raw), 'raw_sha256': sha(raw), 'stored_sha256': sha(payload)})


folders = [(name, retained/name) for name in [
    'raw-rotation', 'scene-snap', 'single-snap', 'mesh-transform',
    'primitive', 'scale', 'selection', 'creation', 'payload', 'normal', 'rng']]
folders += [
    ('retained-audits', audits),
    ('rotation-audit-process', TEMP/'formora-multi-merge-rotation-audit-process-01'),
    ('scene-audit-process', TEMP/'formora-multi-merge-scene-audit-process-01'),
    ('single-audit-process', TEMP/'formora-multi-merge-snap-audit-process-01'),
    ('transform-audit-process', TEMP/'formora-multi-merge-transform-audit-process-01'),
    ('small-gates', TEMP/'formora-multi-merge-retained-small-gates-01'),
    ('small-gate-drivers', TEMP/'formora-multi-merge-retained-small-drivers-01'),
    ('isolation', TEMP/'formora-multi-merge-retained-isolation-01'),
    ('local-lifecycle', TEMP/'formora-multi-merge-retained-local-01'),
    ('native-drivers', TEMP/'formora-multi-merge-retained-native-drivers-01'),
    ('native-gates', TEMP/'formora-multi-merge-retained-native-gates-01'),
    ('failed-save', TEMP/'formora-multi-merge-retained-failed-save-01'),
    ('rng-one-shot', TEMP/'formora-multi-merge-retained-rng-one-shot-01'),
    ('euler-oracle', TEMP/'formora-multi-merge-retained-source-oracle-01'),
    ('metal-drivers', TEMP/'formora-multi-merge-retained-gpu-drivers-01'),
    ('metal', TEMP/'formora-multi-merge-retained-gpu-01'),
    ('single-merge-metal', TEMP/'formora-multi-merge-retained-merge-gpu-01'),
    ('timing-compile-only', TEMP/'formora-multi-merge-retained-compile-01'),
    ('timing-wrappers-unrun', TEMP/'formora-multi-merge-timing-runners-01')]
for label, folder in folders:
    assert folder.is_dir(), folder
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            archive(path, label+'/'+path.relative_to(folder).as_posix())
        elif path.is_dir() and not list(path.iterdir()):
            empty.append({'source': str(path), 'original_preserved': True})
files = [('asset-audit.json', TEMP/'formora-multi-merge-asset-audit-01.json'),
         ('retained-parent-report.json', retained/'report.json'),
         ('retained-parent-progress.json', retained/'progress.json')]
for path in sorted(retained.iterdir()):
    if path.is_file() and path.name not in ['report.json', 'progress.json']:
        files.append(('retained-process/'+path.name, path))
for name in [
    'formora-multi-merge-retained-small-01.py', 'formora-multi-merge-prepare-native-01.py',
    'formora-multi-merge-run-retained-native-01.py', 'formora-multi-merge-retained-gpu-01.py',
    'formora-multi-merge-audit-assets-01.py', 'formora-multi-merge-compile-retained-01.py',
    'formora-multi-merge-prepare-timing-runners-01.py']:
    files.append(('controllers/'+name, TEMP/name))
for prefix in ['retained-api-01', 'retained-small-gates-01', 'retained-native-gates-01',
               'retained-gpu-01', 'asset-audit-01', 'performance-compile-01']:
    for suffix in ['stdout', 'stderr']:
        name = 'formora-multi-merge-'+prefix+'.'+suffix
        files.append(('process-logs/'+name, TEMP/name))
files.append(('timing-compile-only/single-merge-compile-bindings.json', TEMP/'formora-multi-merge-performance-compile-01.json'))
compiled = load(TEMP/'formora-multi-merge-retained-compile-01/report.json')
for row in compiled['drivers']:
    path = Path(row['command'][7])
    assert row['terminal_exit_code'] == 0 and sha(path.read_bytes()) == row['driver_sha256']
    files.append(('timing-compile-only/binaries/'+path.name, path))
files.append(('timing-compile-only/binaries/formora-multi-merge-performance-driver-01', TEMP/'formora-multi-merge-performance-driver-01'))
for relative, source in files:
    archive(source, relative)
with (OUT/'archive-manifest.json').open('x') as f:
    json.dump({'lossless_copies_verified': True, 'originals_preserved': True, 'files': rows,
        'preserved_empty_directories': empty, 'newly_archived_interface_records': 10742,
        'previous_batch_interface_records': 5632, 'total_retained_interfaces': 16374,
        'raw_asset_checks': 1687, 'all_retained_corruptions_and_rejections_keep_original_classification': True,
        'new_multi_data_26880_matrix': 'live and unaccepted', 'retained_timing_207_samples': 'unrun',
        'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}, f, indent=2)
    f.write('\n')
print(json.dumps({'lossless_files_verified': len(rows), 'retained_interfaces_in_both_batches': 16374,
                  'asset_raw_checks': 1687, 'timing_acceptance': 'unrun'}))
