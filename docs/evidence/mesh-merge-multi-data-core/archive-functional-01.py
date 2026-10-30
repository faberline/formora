"""Archive only completed functional proofs. Keep all originals and failures."""
from pathlib import Path
import gzip
import hashlib
import json

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
OUT = ROOT/'docs/evidence/mesh-merge-multi-data-core/completed-functional-01'
TEMP = Path('/private/tmp')
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


single = load(TEMP/'formora-multi-merge-single-retained-api-01/report.json')
single_audit = load(TEMP/'formora-multi-merge-single-retained-audit-01/report.json')
assert single['passed'] and single['checks'] == 2048 and single['required_full_gate_passed']
assert single_audit['passed'] and single_audit['checks'] == 2048 and len(single_audit['negative_controls']) == 11
delta_root = TEMP/'formora-multi-merge-retained-api-01'
delta = load(delta_root/'delta/report.json')
delta_audit = load(TEMP/'formora-multi-merge-retained-api-audit-01/delta.json')
delta_terminal = next(row for row in load(delta_root/'progress.json') if row['name'] == 'delta')
assert delta['passed'] and delta['required_full_gate_passed'] and delta['checks'] == 3584
assert delta_audit['passed'] and delta_audit['requests'] == 3584
assert delta_terminal['passed'] and delta_terminal['terminal_exit_code'] == 0
assert delta_terminal['report_sha256'] == sha((delta_root/'delta/report.json').read_bytes())
assert load(TEMP/'formora-multi-merge-native-controls-02/denied-report.json')['passed']
assert load(TEMP/'formora-multi-merge-unseen-save-01/report.json')['passed']
gpu = load(TEMP/'formora-multi-merge-gpu-01/report.json')
assert gpu['passed'] and gpu['changed_pixels'] == 8478 and gpu['fresh_scene_queries_and_render_equal']
assert load(TEMP/'formora-multi-merge-gpu-01/visual-qa.json')['artifact_render_review_passed']
retained_recipe = load(TEMP/'formora-multi-merge-retained-recipe-01/report.json')
recipe = load(TEMP/'formora-multi-merge-recipes-01/report.json')
recipe_audit = load(TEMP/'formora-multi-merge-recipe-audit-01.json')
assert retained_recipe['passed'] and retained_recipe['cases'] == 20 and retained_recipe['negative_atomic_controls'] == 120
assert recipe['passed'] and recipe['cases'] == 20 and recipe['negative_atomic_controls'] == 120
assert recipe_audit['passed'] and recipe_audit['records'] == 20 and recipe_audit['raw_calls_bound'] == 600
assert len(recipe_audit['corrupted_evidence_controls']) == 6

OUT.mkdir(exist_ok=False)
rows, empty_directories = [], []


def archive(source, relative):
    assert source.is_file() and not source.is_symlink(), source
    raw = source.read_bytes()
    keep = source.suffix in ['.gz', '.png', '.py'] or source.name in [
        'report.json', 'bindings.json', 'started.json', 'terminal.json', 'visual-qa.json', 'diagnostic.json']
    stored = OUT/(relative if keep else relative+'.gz')
    payload = raw if keep else gzip.compress(raw, mtime=0, compresslevel=6)
    if not keep:
        assert gzip.decompress(payload) == raw
    stored.parent.mkdir(parents=True, exist_ok=True)
    with stored.open('xb') as f:
        f.write(payload)
    assert source.read_bytes() == raw and stored.read_bytes() == payload
    rows.append({'source': str(source), 'stored': stored.relative_to(OUT).as_posix(),
                 'raw_sha256': sha(raw), 'stored_sha256': sha(payload), 'raw_bytes': len(raw)})


folders = [
    ('single-api', TEMP/'formora-multi-merge-single-retained-api-01'),
    ('single-process', TEMP/'formora-multi-merge-single-retained-process-01'),
    ('single-audit', TEMP/'formora-multi-merge-single-retained-audit-01'),
    ('single-audit-process', TEMP/'formora-multi-merge-single-audit-process-01'),
    ('single-audit-drivers', TEMP/'formora-multi-merge-single-audit-drivers-01'),
    ('single-controls', TEMP/'formora-multi-merge-single-controls-01'),
    ('delta-api', delta_root/'delta'),
    ('delta-audit-process', TEMP/'formora-multi-merge-delta-audit-process-01'),
    ('retained-driver', TEMP/'formora-multi-merge-retained-drivers-01'),
    ('retained-audit-drivers', TEMP/'formora-multi-merge-retained-audit-drivers-01'),
    ('native-first-diagnostic', TEMP/'formora-multi-merge-native-controls-01'),
    ('native-denied', TEMP/'formora-multi-merge-native-controls-02'),
    ('unseen-failed-save', TEMP/'formora-multi-merge-unseen-save-01'),
    ('metal', TEMP/'formora-multi-merge-gpu-01'),
    ('retained-recipe', TEMP/'formora-multi-merge-retained-recipe-01'),
    ('retained-recipe-driver', TEMP/'formora-multi-merge-retained-recipe-drivers-01'),
    ('multi-recipe', TEMP/'formora-multi-merge-recipes-01'),
]
for label, source in folders:
    assert source.is_dir()
    for path in sorted(source.rglob('*')):
        if path.is_file():
            archive(path, label+'/'+path.relative_to(source).as_posix())
        elif path.is_dir() and not list(path.iterdir()):
            empty_directories.append({'source': str(path), 'scope': label, 'original_preserved': True})
files = [
    ('delta-audit.json', TEMP/'formora-multi-merge-retained-api-audit-01/delta.json'),
    ('recipe-audit.json', TEMP/'formora-multi-merge-recipe-audit-01.json'),
]
for name in ['formora-multi-merge-native-denied-01.py', 'formora-multi-merge-native-denied-02.py',
             'formora-multi-merge-unseen-save-01.py', 'formora-multi-merge-gpu-01.py',
             'formora-multi-merge-recipes-01.py', 'formora-multi-merge-recipe-audit-01.py']:
    files.append(('controllers/'+name, TEMP/name))
for name in ['formora-multi-merge-retained-recipe-01.stdout', 'formora-multi-merge-retained-recipe-01.stderr',
             'formora-multi-merge-recipes-01.stdout', 'formora-multi-merge-recipes-01.stderr',
             'formora-multi-merge-recipe-audit-01.stdout', 'formora-multi-merge-recipe-audit-01.stderr']:
    files.append(('process-logs/'+name, TEMP/name))
for name in ['delta.stdout', 'delta.stderr', 'delta-started.json']:
    files.append(('delta-process/'+name, delta_root/name))
for relative, source in files:
    archive(source, relative)
with (OUT/'delta-terminal-snapshot.json').open('x') as f:
    json.dump(delta_terminal, f, indent=2)
    f.write('\n')
with (OUT/'archive-manifest.json').open('x') as f:
    json.dump({'lossless_copies_verified': True, 'originals_preserved': True, 'files': rows,
        'preserved_empty_directories': empty_directories,
        'completed_interface_records': 5632, 'single_merge_records': 2048, 'delta_records': 3584,
        'retained_parent_remaining_corpora': 'still running; no whole-parent acceptance',
        'full_multi_data_26880_matrix': 'still running; unaccepted',
        'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}, f, indent=2)
    f.write('\n')
print(json.dumps({'lossless_files_verified': len(rows), 'completed_interface_records': 5632,
                  'all_originals_preserved': True}))
