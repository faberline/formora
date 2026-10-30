"""Bind complete capacity forms and pure grids before their source runs."""
import argparse
import builtins
from collections import Counter
import io
from itertools import product
import json
from pathlib import Path
from unittest.mock import patch

from generate_merge_distance_capacity import assets, registry
from merge_distance_capacity_inputs import load_assets


def verify(suite_path):
    suite = json.loads(suite_path.read_text()); grids = load_assets(suite_path, suite); reads = []
    def deny(*args, **kwargs): reads.append(str(args[0])); raise AssertionError('capacity constructor source access')
    with patch.object(builtins, 'open', deny), patch.object(io, 'open', deny):
        expected = assets(); expected_registry = registry(suite['capacity_assets'])
    assert not reads and grids == expected and suite == expected_registry, 'capacity pure regeneration'
    keys = [(run['factors']['options'], run['factors']['context'], run['factors']['selection'], run['normal_profile'], run['sample'])
            for run in suite['runs']]
    assert len(keys) == len(set(keys)) == 192, 'capacity sample uniqueness'
    assert set(keys) == set(product(range(8), ['single_a', 'multi_a_first'], ['all', 'alternating'],
                                    ['automatic', 'custom_constant'], range(3))), 'capacity form coverage'
    counts = Counter(key[:-1] for key in keys)
    assert len(counts) == 64 and set(counts.values()) == {3}, 'capacity three samples per form'
    return {'capacity_input_checks_passed': True, 'cases': len(keys), 'forms': len(counts), 'samples_each': 3,
            'constructor_file_reads': 0, 'distinct_grids': grids['mesh_a']['vertices'] != grids['mesh_b']['vertices'],
            'class_a_each': [10201, 20200, 10000], 'source_execution': 'unrun', 'product_timing': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = verify(args.suite)
    with args.output.open('x') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result))
