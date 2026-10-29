#!/usr/bin/env python3
"""Exercise versioned random falloff through the real CLI and official MCP SDK."""
import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from random_falloff_reference import SEEDS, DRAWS

ROOT = Path(__file__).resolve().parents[1]
VERTICES = {'z_selected': [0, 0, 0], 'h_depth': [0, 0, 2], 'g_coincident': [0, 0, 0],
            'e_near': [0.5, 0, 0], 'd_boundary': [1, 0, 0], 'c_outside': [2, 0, 0],
            'b_hidden': [0.125, 0, 0], 'a_selected': [0, 0, 0]}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def setup():
    return {'expected_revision': 0, 'commands': [
        {'operation': 'set_mesh_asset', 'id': 'mesh', 'asset': {
            'vertices': VERTICES, 'edges': {'a_near': ['a_selected', 'e_near'],
                                         'near_boundary': ['e_near', 'd_boundary']},
            'triangles': {}, 'material_slots': []}},
        {'operation': 'set_mesh_editing', 'id': 'mesh', 'editing': {
            'mode': ['vertex'], 'selected': {'vertices': ['a_selected', 'z_selected']},
            'hidden': {'vertices': ['b_hidden']}, 'history': []}},
        *[{'operation': 'create_entity', 'id': name, 'entity': {
            'name': name, 'parent': None,
            'transform': {'translation': [0, 0, 0], 'rotation': [0, 0, 0, 1], 'scale': [1, 1, 1]},
            'content': {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': 'mesh'}, 'material': None}}}
          for name in ['target', 'instance']]]}


def operation(seed, algorithm, connected=False, projected=False):
    p = {'radius': 1, 'falloff': 'random', 'seed': seed, 'connected': connected, 'projected': projected}
    if algorithm is not None:
        p['random_algorithm'] = algorithm
    return {'operation': 'transform_mesh', 'transform': {
        'entity': 'target', 'change': {'kind': 'translate', 'value': [0, 0, 1]}, 'proportional': p}}


def expected_weights(case, reference):
    seed, algorithm, connected, projected = case
    if algorithm == 'blender_5_2':
        offset = SEEDS.index(seed) * DRAWS * 4
        draws = struct.unpack_from('<4f', reference, offset)
    else:
        state = seed
        draws = []
        for _ in range(4):
            mask = (1 << 64) - 1
            state = (state + 0x9e3779b97f4a7c15) & mask
            z = ((state ^ (state >> 30)) * 0xbf58476d1ce4e5b9) & mask
            z = ((z ^ (z >> 27)) * 0x94d049bb133111eb) & mask
            draws.append(f32(((z ^ (z >> 31)) >> 40) / 16777216))
    weights = {'a_selected': 1.0, 'e_near': f32(draws[1] * 0.5), 'z_selected': 1.0}
    if not connected:
        weights['g_coincident'] = draws[2]
        if projected:
            weights['h_depth'] = draws[3]
    return {key: value for key, value in weights.items() if value > 0}


async def run(binary, output):
    binary = binary.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = [ROOT / 'Cargo.toml', ROOT / 'Cargo.lock', ROOT / 'baseline/lock.json',
              ROOT / 'docs/contracts/random-falloff-sequence.md', Path(__file__),
              *sorted((ROOT / 'src').rglob('*.rs')),
              *sorted((ROOT / 'baseline/reference/blender-5.2.3/random-falloff').iterdir())]
    inputs = [p for p in inputs if p.is_file()]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    binary_hash = sha(binary)
    reference = (ROOT / 'baseline/reference/blender-5.2.3/random-falloff/first-sequence.bin').read_bytes()
    cases = [(seed, 'blender_5_2', connected, projected) for seed in SEEDS
             for connected, projected in [(False, False), (True, False), (False, True), (True, True)]]
    cases += [(seed, algorithm, False, False) for seed in [0, 4294967295, 4294967296, (1 << 64)-1]
              for algorithm in [None, 'splitmix64_v1']]
    records = []
    with tempfile.TemporaryDirectory(prefix='formora-random-runtime-') as tmp:
        for interface in ['cli', 'official_mcp_sdk']:
            for index, case in enumerate(cases):
                scene = Path(tmp) / f'{interface}-{index}.json'
                def cli(action, request=None):
                    p = subprocess.run([str(binary), 'scene', action, '--scene', str(scene),
                                        *(['--request', '-'] if request is not None else [])],
                                       input=json.dumps(request) if request is not None else None,
                                       capture_output=True, text=True)
                    value = json.loads(p.stdout) if p.stdout else {'error': p.stderr}
                    return value, p.returncode != 0
                assert not cli('init')[1]
                async def exercise(call, schema):
                    initialized, error = await call('scene_apply', setup())
                    assert not error and initialized['revision'] == 1
                    before, error = await call('scene_inspect', {})
                    assert not error
                    seed, algorithm, connected, projected = case
                    request = {'expected_revision': 1, 'commands': [operation(*case)]}
                    if schema is not None:
                        Draft202012Validator(schema).validate(request)
                        encoded_schema = json.dumps(schema)
                        assert 'blender_5_2' in encoded_schema and 'splitmix64_v1' in encoded_schema
                    applied, error = await call('scene_apply', request)
                    assert not error and applied['revision'] == 2
                    after, error = await call('scene_inspect', {})
                    assert not error and after['scene'] == json.loads(scene.read_text())
                    weights = expected_weights(case, reference)
                    receipt = applied['transforms'][0]
                    assert receipt['influence'] == weights
                    assert receipt['random_seed'] == seed
                    assert receipt.get('random_algorithm') == algorithm
                    assert ('random_algorithm' in receipt) == (algorithm is not None)
                    assert receipt['shared_instances'] == ['instance', 'target']
                    expected = copy.deepcopy(before['scene']['mesh_assets']['mesh'])
                    for name, weight in weights.items():
                        expected['vertices'][name][2] = f32(expected['vertices'][name][2] + weight)
                    assert after['scene']['mesh_assets']['mesh'] == expected
                    assert after['scene']['entities'] == before['scene']['entities']
                    assert set(receipt['changed']['vertices']) == set(weights)
                    saved = scene.read_bytes()
                    rejected = []
                    for patch in [{'seed': None}, {'seed': 4294967296, 'random_algorithm': 'blender_5_2'},
                                  {'falloff': 'linear', 'seed': None, 'random_algorithm': 'blender_5_2'},
                                  {'random_algorithm': 'unversioned'}]:
                        bad = operation(*case)
                        bad['transform']['proportional'].update(patch)
                        failure, error = await call('scene_apply', {'expected_revision': 2, 'commands': [bad]})
                        assert error and scene.read_bytes() == saved
                        rejected.append({'command': bad, 'error': failure})
                    invalid = {'expected_revision': 2, 'commands': [operation(*case), operation(4294967296, 'blender_5_2')]}
                    failure, error = await call('scene_apply', invalid)
                    assert error and scene.read_bytes() == saved
                    current, error = await call('scene_inspect', {})
                    assert not error and current == after
                    undone, error = await call('scene_undo', {'expected_revision': 2})
                    assert not error and undone['revision'] == 3
                    current, error = await call('scene_inspect', {})
                    assert not error and current['scene']['mesh_assets'] == before['scene']['mesh_assets']
                    replay = copy.deepcopy(request)
                    replay['expected_revision'] = 3
                    repeated, error = await call('scene_apply', replay)
                    assert not error and repeated['transforms'] == applied['transforms']
                    final, error = await call('scene_inspect', {})
                    assert not error and final['scene']['mesh_assets'] == after['scene']['mesh_assets']
                    fresh, failed = cli('inspect')
                    assert not failed and fresh == final
                    return {'request': request, 'setup': setup(), 'before': before, 'result': applied,
                            'after': after, 'failed_batch': failure, 'replay': repeated,
                            'rejected_requests': rejected, 'fresh_reload': fresh, 'passed': True}
                if interface == 'cli':
                    # Undo belongs to a live session. One-shot apply processes
                    # intentionally do not retain undo history after exit.
                    process = subprocess.Popen([str(binary), 'scene', 'serve', '--scene', str(scene)],
                                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE, text=True)
                    sequence = 0
                    async def call(name, arguments):
                        nonlocal sequence
                        sequence += 1
                        process.stdin.write(json.dumps({'id': sequence, 'name': name, 'arguments': arguments}) + '\n')
                        process.stdin.flush()
                        response = json.loads(process.stdout.readline())
                        assert response['id'] == sequence
                        return (response['error'], True) if not response['ok'] else (response['result'], False)
                    try:
                        result = await exercise(call, None)
                    finally:
                        process.stdin.close()
                        process.wait(timeout=15)
                        stderr = process.stderr.read()
                        process.stdout.close()
                        process.stderr.close()
                        assert process.returncode == 0, stderr
                    scene = Path(tmp) / f'oneshot-{index}.json'
                    assert not cli('init')[1]
                    assert not cli('apply', setup())[1]
                    one_shot, error = cli('apply', result['request'])
                    assert not error and one_shot['transforms'] == result['result']['transforms']
                    loaded, error = cli('inspect')
                    assert not error and loaded['scene']['mesh_assets'] == result['after']['scene']['mesh_assets']
                    result['one_shot_cli'] = {'result': one_shot, 'fresh_reload': loaded}
                else:
                    params = StdioServerParameters(command=str(binary), args=['mcp', '--scene', str(scene)])
                    async with stdio_client(params) as (reader, writer):
                        async with ClientSession(reader, writer, read_timeout_seconds=10) as client:
                            await client.initialize()
                            schema = next(t.input_schema for t in (await client.list_tools()).tools if t.name == 'scene_apply')
                            schema_path = output / 'scene-apply-schema.json'
                            if schema_path.exists():
                                assert json.loads(schema_path.read_text()) == schema
                            else:
                                schema_path.write_text(json.dumps(schema, indent=2) + '\n')
                            async def call(name, arguments):
                                response = await client.call_tool(name, arguments)
                                return (response.content[0].text, True) if response.is_error else (response.structured_content, False)
                            result = await exercise(call, schema)
                file = output / f'{interface}-{index:03}.json'
                file.write_text(json.dumps(result, indent=2) + '\n')
                records.append({'interface': interface, 'case': case, 'file': file.name, 'sha256': sha(file)})
            print(json.dumps({'interface': interface, 'cases': len(cases), 'passed': True}), flush=True)
    assert binary_hash == sha(binary) and hashes == {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    report = {'passed': True, 'checks': len(records), 'binary_sha256': binary_hash,
              'input_hashes': hashes, 'records': records,
              'scene_apply_schema_sha256': sha(output / 'scene-apply-schema.json'),
              'product_acceptance': 'unrun'}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.binary, args.output))
