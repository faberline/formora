"""Pure provenance for the multi-data source harness; no captured answers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'e13b728c6880d3084d9d57c30031ed5df8b39dee'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def input_paths(suite_path):
    names = [
        'tools/multi_mesh_merge_inputs.py',
        'tools/blender_multi_mesh_merge_reference.py',
        'tools/compare_multi_mesh_merge_reference.py',
        'tools/check_multi_mesh_merge_controls.py',
        'tools/launch_multi_mesh_merge_reference.py',
        'tools/generate_multi_mesh_merge_cases.py',
        'tools/blender_mesh_merge_reference.py',
        'tools/blender_snap_menu_reference.py',
        'tools/blender_transform_reference.py',
        'tools/blender_selection_reference.py',
        'tools/compare_selection_reference.py',
        'tools/compare_snap_menu_reference.py',
        'tools/compare_transform_reference.py',
        'tools/compare_mesh_merge_reference.py',
        'tools/compare_snap_delta_reference.py',
        'tools/compare_snap_rotation_reference.py',
        'tools/generate_mesh_merge_cases.py',
        'tools/generate_snap_menu_cases.py',
        'tools/generate_mesh_transform_cases.py',
        'tools/generate_snap_delta_cases.py',
        'tools/generate_snap_rotation_cases.py',
        'docs/contracts/mesh-merge-multi-data-baseline.md',
        'baseline/lock.json',
        'baseline/sources/mesh-merge-multi-data/manifest.json',
        'baseline/sources/mesh-merge/manifest.json',
    ]
    pinned = json.loads((ROOT/'baseline/sources/mesh-merge/manifest.json').read_text())
    assert pinned['blender_commit'] == COMMIT
    for row in pinned['reused_manifests']:
        assert digest(ROOT/row['path']) == row['sha256']
        names.append(row['path'])
    for row in pinned['files']:
        assert digest(ROOT/row['repository_path']) == row['sha256']
        names.append(row['repository_path'])
    new = json.loads((ROOT/'baseline/sources/mesh-merge-multi-data/manifest.json').read_text())
    assert new['commit'] == COMMIT
    for row in new['sources']:
        path = ROOT/'baseline/sources/mesh-merge-multi-data'/Path(row['path']).name
        assert digest(path) == row['sha256']
        names.append(path.relative_to(ROOT).as_posix())
    for name, sha in [
        ('layer_utils.cc', '647e98ae5c67a90d753b3b41acc809c856af724bc98f9e9ceaa77fddde83ec6b'),
        ('layer.cc', 'ce1a31dc9829bf4b07c8019be4cfd0c9659745b6c49a6dc787277366c2f61064'),
    ]:
        name = 'baseline/sources/scene-snap-core/' + name
        assert digest(ROOT/name) == sha
        names.append(name)
    # The inherited manifest can already include the directly checked layer
    # sources. Hash each physical file once, in stable first-use order.
    return [suite_path, *[ROOT/name for name in dict.fromkeys(names)]]
