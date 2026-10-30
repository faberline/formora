"""List the exact local script/source dependencies for native capture binding."""
import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def input_paths(suite):
    paths = {suite.resolve(), ROOT/'docs/contracts/mesh-merge-distance-source.md',
             ROOT/'baseline/fixtures/mesh-merge-distance-source-lock-01.json',
             ROOT/'baseline/fixtures/mesh-merge-distance-draft.json'}
    scripts = ['blender_merge_distance_reference.py', 'check_merge_distance_diagnostic.py',
               'compare_merge_distance_complete.py', 'launch_merge_distance_complete.py',
               'check_merge_distance_complete_inputs.py', 'check_merge_distance_diagnostic_controls.py',
               'audit_merge_distance_outcomes.py', 'archive_merge_distance_diagnostic.py']
    pending = [ROOT/'tools'/name for name in scripts]
    while pending:
        path = pending.pop().resolve()
        if path in paths: continue
        assert path.parent == ROOT/'tools', 'local script outside tools'
        paths.add(path)
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in modules:
                local = ROOT/'tools'/(name.split('.')[0]+'.py')
                if local.is_file() and local.resolve() not in paths: pending.append(local)
    paths.update(path.resolve() for path in (ROOT/'baseline/sources/mesh-merge-distance').iterdir() if path.is_file())
    pending = [ROOT/'baseline/sources/mesh-merge/manifest.json']
    seen = set()
    while pending:
        path = pending.pop().resolve()
        if path in seen: continue
        seen.add(path); paths.add(path)
        manifest = json.loads(path.read_text())
        for row in manifest.get('files', []):
            local = ((ROOT/row['repository_path']) if 'repository_path' in row else path.parent/row['file']).resolve()
            assert local.is_relative_to(ROOT/'baseline/sources') and local.is_file(), 'missing pinned source file'
            assert hashlib.sha256(local.read_bytes()).hexdigest() == row['sha256'], 'pinned source file changed'
            paths.add(local)
        for row in manifest.get('reused_manifests', []):
            local = (ROOT/row['path']).resolve()
            assert local.is_relative_to(ROOT/'baseline/sources') and local.is_file(), 'missing reused source manifest'
            assert hashlib.sha256(local.read_bytes()).hexdigest() == row['sha256'], 'reused source manifest changed'
            pending.append(local)
    return sorted(paths)
