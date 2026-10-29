#!/usr/bin/env python3
"""Run every authored delta snap through the real CLI and official MCP."""
import argparse
import asyncio
import copy
from pathlib import Path

from compare_snap_delta_reference import compare as verify_source
from compare_snap_menu_reference import floats, tree
import rotation_snap_runtime as rotation

ROOT = Path(__file__).resolve().parents[1]


def setup(suite, case):
    """Only authored channels prepare the scene; no reference output is read."""
    result = rotation.setup(suite, case)
    for command in result['commands']:
        if command['operation'] == 'create_entity':
            name = command['id']
            delta = case['deltas'] if name in ['target', 'secondary'] else suite['role_deltas'][name]
            delta = floats(delta)
            command['entity']['transform']['delta'] = {
                'translation': delta['location'], 'euler': delta['euler'],
                'quaternion_wxyz': delta['quaternion_wxyz'], 'scale': delta['scale']}
        if command['operation'] == 'set_object_context':
            for name in ['target', 'secondary']:
                command['context']['states'][name]['lock_location'] = case['context']['lock_location']
    return result


def snapshot(inspection, queries, worlds):
    result = rotation.snapshot(inspection, queries, worlds)
    result['delta_channels'] = {}
    for name, entity in inspection['scene']['entities'].items():
        delta = entity['transform'].get('delta', {'translation':[0.]*3, 'euler':[0.]*3,
            'quaternion_wxyz':[1.,0.,0.,0.], 'scale':[1.]*3})
        result['delta_channels'][name] = {'location':copy.deepcopy(delta['translation']),
            **{key:copy.deepcopy(delta[key]) for key in ['euler', 'quaternion_wxyz', 'scale']}}
        result['objects'][name].update(delta_location=copy.deepcopy(delta['translation']),
            delta_rotation=copy.deepcopy(delta['euler']), delta_scale=copy.deepcopy(delta['scale']))
        result['rotation_channels'][name].update(delta_euler=copy.deepcopy(delta['euler']),
            delta_quaternion_wxyz=copy.deepcopy(delta['quaternion_wxyz']))
    return result


def compare_state(reference, actual):
    rotation.compare_state(reference, actual)
    tree(reference['delta_channels'], actual['delta_channels'], 'actual saved delta channels')


def source(suite, first, second):
    return verify_source(suite, first, second, ROOT/'docs/evidence/snap-delta-baseline/native-processes.json')


async def run(binary, output, case_ids=(), interfaces=('cli', 'official_mcp_sdk'), gzip_output=False):
    return await rotation.run(binary, output, case_ids, interfaces, gzip_output,
        suite_path=ROOT/'baseline/fixtures/snap-delta.json',
        folders=[ROOT/'baseline/reference/blender-5.2.3'/name for name in ['snap-delta', 'snap-delta-repeat']],
        source_verifier=source, expected_cases=1792, setup_case=setup,
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
