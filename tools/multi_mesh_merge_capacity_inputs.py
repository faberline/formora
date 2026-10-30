"""Freeze the capacity harness and its complete functional dependency set."""
from pathlib import Path

from multi_mesh_merge_inputs import input_paths as functional_paths

ROOT = Path(__file__).resolve().parents[1]


def input_paths(suite_path):
    names = [
        'tools/multi_mesh_merge_capacity_inputs.py',
        'tools/generate_multi_mesh_merge_capacity_cases.py',
        'tools/blender_multi_mesh_merge_capacity_reference.py',
        'tools/compare_multi_mesh_merge_capacity_reference.py',
        'tools/launch_multi_mesh_merge_capacity_reference.py',
        'docs/contracts/mesh-merge-multi-data-capacity.md',
    ]
    return [suite_path, *functional_paths(ROOT/'baseline/fixtures/mesh-merge-multi-data.json'),
            *[ROOT/name for name in names]]
