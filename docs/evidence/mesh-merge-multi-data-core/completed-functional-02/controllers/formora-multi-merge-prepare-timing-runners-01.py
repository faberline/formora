"""Prepare unchanged retained timing wrappers. Do not run timing samples."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
BASE = ROOT/'docs/evidence/mesh-merge-core/continuation'
OUT = Path('/private/tmp/formora-multi-merge-timing-runners-01')
OUT.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
compile_report = json.loads(Path('/private/tmp/formora-multi-merge-retained-compile-01/report.json').read_text())
assert compile_report['passed'] and len(compile_report['drivers']) == 5
for row in compile_report['drivers']:
    assert row['terminal_exit_code'] == 0 and sha(row['command'][7]) == row['driver_sha256']
    assert sha(row['command'][5]) == row['driver_source_sha256']
single = json.loads(Path('/private/tmp/formora-multi-merge-performance-compile-01.json').read_text())
assert single['compile_exit_code'] == 0 and sha(single['binary']) == single['binary_sha256']
rows = []
for filename in ['regenerate-retained-run-90-01.py', 'regenerate-retained-run-39-01.py',
    'regenerate-retained-run-rotation-01.py', 'regenerate-retained-run-delta-01.py',
    'regenerate-retained-timing-controller-01.py', 'regenerate-run-performance-01.py']:
    source = BASE/filename
    old = source.read_text()
    new = old
    replacements = [("ROOT=Path(__file__).resolve().parents[4]", "ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')"),
        ('/private/tmp/formora-merge-regen-target-actual185/', '/private/tmp/formora-multi-merge-target-actual185/'),
        ('/private/tmp/formora-merge-regen-retained-', '/private/tmp/formora-multi-merge-retained-'),
        ('/private/tmp/formora-merge-regen-performance-', '/private/tmp/formora-multi-merge-performance-'),
        ('5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d', 'bd13f3d424f2649b4b25c16305c4e5b0eb7f8542')]
    applied = []
    for before, after in replacements:
        if before in new:
            new = new.replace(before, after)
            applied.append((before, after))
    restored = new
    for before, after in reversed(applied):
        restored = restored.replace(after, before)
    assert restored == old
    asserts = lambda value: [ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(value)) if isinstance(n, ast.Assert)]
    assert asserts(old) == asserts(new)
    target = OUT/filename
    with target.open('x') as f:
        f.write(new)
    rows.append({'source': str(source), 'source_sha256': sha(source), 'copy': str(target),
        'copy_sha256': sha(target), 'only_path_head_bindings_changed': applied,
        'reverse_mapping_recovers_exact_original': True, 'all_assertion_syntax_trees_unchanged': True,
        'diff': list(difflib.unified_diff(old.splitlines(True), new.splitlines(True)))})
with (OUT/'bindings.json').open('x') as f:
    json.dump({'wrappers': rows, 'frozen_native_sources_unchanged': True, 'timing_samples_executed': 0,
        'required_samples': 207, 'performance_acceptance': 'unrun',
        'execution_precondition': 'Wait for the full functional matrix and raw audit to stop before timing.'}, f, indent=2)
    f.write('\n')
print(json.dumps({'wrappers_prepared': 6, 'assertions_unchanged': True, 'timing_samples_executed': 0}))
