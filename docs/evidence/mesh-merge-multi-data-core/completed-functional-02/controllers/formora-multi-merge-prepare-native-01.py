"""Prepare safe copies of retained tests. This program executes no test code."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
BASE = ROOT/'docs/evidence/mesh-merge-core/continuation'
OUT = Path('/private/tmp/formora-multi-merge-retained-native-drivers-01')
OUT.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
old_policy = Path('/private/tmp/formora-merge-regen-unseen-after-01/profile.sb').read_text().strip()
policy = json.loads(Path('/private/tmp/formora-multi-merge-native-controls-02/denied-report.json').read_text())['policy']
prefix = '(version 1)(allow default)'
assert policy.startswith(prefix)
with (OUT/'profile.sb').open('x') as f:
    f.write(old_policy+policy[len(prefix):]+'\n')
rows = []
for name in ['regenerate-failed-save-proof-01.py', 'regenerate-retained-rng-one-shot-01.py',
             'regenerate-retained-source-oracle-01.py']:
    source = BASE/name
    old = source.read_text()
    new = old
    replacements = [("ROOT=Path(__file__).resolve().parents[4]", "ROOT=Path('/private/tmp/formora-mesh-merge-multi-data-core')"),
        ('/private/tmp/formora-mesh-merge-sparse', str(ROOT)),
        ('/private/tmp/formora-merge-regen-target-actual185/debug/formora', '/private/tmp/formora-multi-merge-target-actual185/debug/formora'),
        ('/private/tmp/formora-merge-regen-failed-save-01', '/private/tmp/formora-multi-merge-retained-failed-save-01'),
        ('/private/tmp/formora-merge-regen-rng-one-shot-01', '/private/tmp/formora-multi-merge-retained-rng-one-shot-01'),
        ('/private/tmp/formora-merge-regen-source-oracle-01', '/private/tmp/formora-multi-merge-retained-source-oracle-01'),
        ('/private/tmp/formora-merge-regen-unseen-after-01/profile.sb', str(OUT/'profile.sb')),
        ('5a69c8851107e2ce30ef523d78f75d4b6d6e2d5d', 'bd13f3d424f2649b4b25c16305c4e5b0eb7f8542')]
    applied = []
    for before, after in replacements:
        if before in new:
            new = new.replace(before, after)
            applied.append((before, after))
    cleanup = None
    if name == 'regenerate-failed-save-proof-01.py':
        tree = ast.parse(new)
        nodes = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == 'rmdir'
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'scene']
        assert len(nodes) == 1
        node = nodes[0]
        assert node.lineno == node.end_lineno
        lines = new.splitlines(keepends=True)
        line = lines[node.lineno-1]
        original = ast.get_source_segment(new, node)
        replacement = "scene.rename(OUTPUT/'failed-save-directory')"
        assert line[node.col_offset:node.end_col_offset] == original
        lines[node.lineno-1] = line[:node.col_offset]+replacement+line[node.end_col_offset:]
        new = ''.join(lines)
        cleanup = (original, replacement)
    restored = new
    if cleanup:
        restored = restored.replace(cleanup[1], cleanup[0])
    for before, after in reversed(applied):
        restored = restored.replace(after, before)
    assert restored == old
    assertions = lambda text: [ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Assert)]
    assert assertions(old) == assertions(new)
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in ['rmdir', 'unlink', 'rmtree'] for n in ast.walk(ast.parse(new)))
    target = OUT/name
    with target.open('x') as f:
        f.write(new)
    rows.append({'source': str(source), 'source_sha256': sha(source), 'copy': str(target),
        'copy_sha256': sha(target), 'path_bindings': applied, 'safe_cleanup_change': cleanup,
        'reverse_mapping_recovers_exact_original': True, 'all_assertion_syntax_trees_unchanged': True,
        'diff': list(difflib.unified_diff(old.splitlines(True), new.splitlines(True)))})
with (OUT/'bindings.json').open('x') as f:
    json.dump({'drivers': rows, 'denial_policy': 'Keep all original denials and add current source and answer denials.',
        'cleanup': 'Retain and rename only the empty directory made by this test. No deletion call remains.'}, f, indent=2)
    f.write('\n')
print(json.dumps({'native_drivers_prepared': 3, 'all_assertions_unchanged': True, 'no_deletion_calls': True}))
