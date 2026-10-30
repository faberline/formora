#!/usr/bin/env python3
"""Compare real physical results and local-query availability separately."""
import argparse
import asyncio
import copy
from pathlib import Path

import delta_snap_runtime as delta
import rotation_snap_runtime as rotation
from compare_snap_menu_reference import tree
from compare_snap_singular_policy_reference import compare, numeric_matrix
from generate_snap_singular_cases import effective_suite

ROOT = Path(__file__).resolve().parents[1]


def setup(suite, case):
    return delta.setup(effective_suite(suite, case), case)


def snapshot(inspection, queries, worlds):
    result = delta.snapshot(inspection, queries, worlds)
    for name, world in worlds.items():
        frame = world['object_frames']
        if 'matrix_local_error' in frame:
            result['objects'][name]['matrix_local_error'] = frame['matrix_local_error']
    return result


def compare_local(expected, actual, error=None):
    if numeric_matrix(expected):
        assert error is None, 'false local-query error'
        assert numeric_matrix(actual), 'available matrix missing or nonnumeric'
        tree(expected, actual, 'actual available local matrix')
        return 'available_numeric'
    assert isinstance(expected, list) and len(expected) == 4
    for row in expected:
        assert isinstance(row, list) and len(row) == 4
        for value in row:
            tag = value['__source_nonfinite_diagnostic__']
            assert tag['repr'] == 'nan' and tag['f32_little_endian_hex'] == '0000c07f'
            assert tag['f64_little_endian_hex'] == '000000000000f87f'
    assert actual is None, 'unavailable local matrix replaced by numbers'
    assert error == 'cannot_invert', 'missing typed local-query error'
    return 'unavailable_query'


def compare_state(reference, actual):
    # Remove only the derived getter from the physical validation projection.
    # Keep the actual response and native tags unchanged in the raw artifact.
    reference, actual = copy.deepcopy(reference), copy.deepcopy(actual)
    assert set(reference['objects']) == set(actual['objects'])
    for name, frame in actual['objects'].items():
        expected = reference['objects'][name].pop('matrix_local')
        if numeric_matrix(expected):
            assert 'matrix_local_error' not in frame, 'available getter must omit the error field'
        local = frame.pop('matrix_local')
        error = frame.pop('matrix_local_error', None)
        compare_local(expected, local, error)
    delta.compare_state(reference, actual)


def source(suite, first, second):
    return compare(suite, first, second,
                   ROOT / 'docs/evidence/snap-singular-baseline/native-processes.json')


async def run(binary, output, case_ids=(), interfaces=('cli', 'official_mcp_sdk'), gzip_output=False):
    return await rotation.run(binary, output, case_ids, interfaces, gzip_output,
        suite_path=ROOT / 'baseline/fixtures/snap-singular.json',
        folders=[ROOT / 'docs/evidence/snap-singular-baseline' / name
                 for name in ['diagnostic-01', 'diagnostic-02']],
        source_verifier=source, expected_cases=1764, setup_case=setup,
        take_snapshot=snapshot, compare_snapshot=compare_state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--case', action='append', default=[], dest='case_ids')
    parser.add_argument('--interface', action='append', choices=['cli', 'official_mcp_sdk'])
    parser.add_argument('--gzip-output', action='store_true')
    args = parser.parse_args()
    asyncio.run(run(args.binary.resolve(), args.output.resolve(), args.case_ids,
                   args.interface or ('cli', 'official_mcp_sdk'), args.gzip_output))
