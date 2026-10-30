"""Check two generated edit assets, recipe flags, regeneration and transactions."""
import asyncio
import copy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
OUT = Path('/private/tmp/formora-multi-merge-recipes-01')
BINARY = Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
EXPECTED = '64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(path, value):
    raw = (json.dumps(value, allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


async def trial(interface, method, uvs):
    from jsonschema import Draft202012Validator
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    folder = OUT/f'{interface}-{method}-{uvs}'
    folder.mkdir()
    path = folder/'scene.json'
    value = {'interface': interface, 'method': method, 'uvs': uvs, 'calls': [], 'cli_processes': [], 'passed': False}

    def cli(action):
        command = [str(BINARY), 'scene', action, '--scene', str(path)]
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = child.communicate(timeout=30)
        value['cli_processes'].append({'command': command, 'process_id': child.pid,
            'terminal_exit_code': child.returncode, 'stdout': stdout, 'stderr': stderr})
        assert child.returncode == 0, (stdout, stderr)
        return json.loads(stdout)

    cli('init')

    async def exercise(call):
        async def inspect():
            return (await call('scene_inspect', {}))['scene']

        async def apply(revision, commands, error=False):
            return await call('scene_apply', {'expected_revision': revision, 'commands': commands}, error)

        def entity(name, data, translation, scale):
            return {'operation': 'create_entity', 'id': name, 'entity': {'name': name, 'parent': None,
                'transform': {'translation': translation, 'rotation': [0., 0., 0., 1.], 'scale': scale, 'precision': 'f32'},
                'content': {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': data}, 'material': None}}}

        empty = {'mode': ['vertex'], 'selected': {}, 'hidden': {}, 'history': [], 'active_face': None, 'preview': False}
        setup = [{'operation': 'create_mesh_primitive', 'id': data, 'primitive': {'kind': 'cube', 'size': size}}
                 for data, size in [('mesh_a', 1.75), ('mesh_b', 2.25)]]
        setup += [entity('a', 'mesh_a', [4., 1., 0.], [1., 1., 1.]),
                  entity('alias', 'mesh_a', [3.125, -1.75, .625], [-2., .5, 4.]),
                  entity('b', 'mesh_b', [-2.25, .375, 1.5], [.25, 2., -.5])]
        setup += [{'operation': 'set_mesh_asset', 'id': 'outside', 'asset': {
            'vertices': {'untouched': [9.125, -4.25, .875]}, 'triangles': {}, 'material_slots': []}}]
        setup += [{'operation': 'set_mesh_editing', 'id': data, 'editing': empty} for data in ['mesh_a', 'mesh_b']]
        setup += [{'operation': 'set_object_context', 'context': {'order': ['a', 'b', 'alias'],
            'selected': ['a', 'alias', 'b'], 'active': 'alias', 'edit_objects': ['alias', 'b'],
            'states': {'alias': {'lock_scale': [True, False, True]}}}},
            {'operation': 'set_authoring_context', 'context': {'cursor_location': [-1.375, .875, .125],
                'cursor_rotation': [.125, -.25, .375], 'view_rotation': [.25, -.125, .5]}}]
        await apply(0, setup)
        generated = await inspect()
        originals = copy.deepcopy(generated['mesh_assets'])
        for data in ['mesh_a', 'mesh_b']:
            assert originals[data]['recipe']['edited'] is False and len(originals[data]['vertices']) == 8
        noop = await apply(generated['revision'], [{'operation': 'merge_edit_meshes',
            'merge': {'method': 'center', 'uvs': uvs}}])
        empty_after = await inspect()
        assert empty_after['mesh_assets'] == originals
        assert [p['outcome'] for p in noop['edit_merges'][0]['providers']] == ['skipped_empty_selection']*2
        selections = []
        for data in ['mesh_a', 'mesh_b']:
            asset = originals[data]
            ids = sorted(asset['vertices'])
            editing = {'mode': ['vertex'], 'selected': {'vertices': ids, 'edges': sorted(asset['edges']),
                'faces': [{'kind': 'polygon', 'id': id} for id in sorted(asset['polygons'])]}, 'hidden': {},
                'history': [{'domain': 'vertex', 'id': ids[0]}, {'domain': 'vertex', 'id': ids[-1]}],
                'active_face': None, 'preview': False}
            selections.append({'operation': 'set_mesh_editing', 'id': data, 'editing': editing})
        await apply(empty_after['revision'], selections)
        before = await inspect()
        request = {'operation': 'merge_edit_meshes', 'merge': {'method': method, 'uvs': uvs}}
        extreme = copy.deepcopy(before['mesh_assets']['mesh_a'])
        extreme['integer_attributes'] = {'vertices': {'extreme': {id: 2147483647 for id in extreme['vertices']}},
                                         'edges': {}, 'polygons': {}, 'triangles': {}}
        huge = copy.deepcopy(before['mesh_assets']['mesh_a'])
        huge['vertices'] = {id: [1e100]*3 for id in huge['vertices']}
        invalid = [
            ('stale', before['revision']-1, [request], 'revision'),
            ('budget', before['revision'], [{'operation': 'merge_edit_meshes', 'merge': {'method': method, 'uvs': uvs, 'max_components': 1}}], 'budget'),
            ('unknown', before['revision'], [{'operation': 'merge_edit_meshes', 'merge': {'method': method, 'uvs': uvs, 'reference_path': 'forbidden-answer.json'}}], 'unknown field'),
            ('late_batch', before['revision'], [request, {'operation': 'set_mesh_vertices', 'id': 'missing', 'positions': {'a': [0., 0., 0.]}}], 'unknown mesh asset'),
            ('integer_overflow', before['revision'], [{'operation': 'set_mesh_asset', 'id': 'mesh_a', 'asset': extreme},
                {'operation': 'merge_edit_meshes', 'merge': {'method': 'center', 'uvs': uvs}}], 'integer vertex interpolation exceeds i32 range'),
            ('coordinate_overflow', before['revision'], [{'operation': 'set_mesh_asset', 'id': 'mesh_a', 'asset': huge},
                {'operation': 'merge_edit_meshes', 'merge': {'method': 'center', 'uvs': uvs}}], 'mesh snap coordinates must fit finite f32 values')]
        rejected = []
        for name, revision, commands, message in invalid:
            saved = path.read_bytes()
            error = await apply(revision, commands, True)
            assert message in error, error
            assert await inspect() == before and path.read_bytes() == saved
            rejected.append({'control': name, 'error': error})
        primary = await apply(before['revision'], [request])
        after = await inspect()
        affected = {'mesh_a'} if method in ['first', 'last'] else {'mesh_a', 'mesh_b'}
        assert primary['edit_merges'][0]['provider_order'] == ['alias', 'b']
        for data in ['mesh_a', 'mesh_b']:
            if data in affected:
                assert after['mesh_assets'][data]['recipe']['edited'] is True and len(after['mesh_assets'][data]['vertices']) == 1
            else:
                assert after['mesh_assets'][data] == before['mesh_assets'][data]
        for key in set(before)-{'revision', 'mesh_assets'}:
            assert after[key] == before[key]
        assert after['mesh_assets']['outside'] == before['mesh_assets']['outside']
        await call('scene_undo', {'expected_revision': after['revision']})
        restored = await inspect()
        expected = copy.deepcopy(before)
        expected['revision'] = restored['revision']
        assert restored == expected
        replay = await apply(restored['revision'], [request])
        replayed = await inspect()
        assert replay['edit_merges'] == primary['edit_merges'] and replayed['mesh_assets'] == after['mesh_assets']
        regeneration = [{'operation': 'regenerate_mesh_primitive', 'id': data} for data in ['mesh_a', 'mesh_b']]
        await apply(replayed['revision'], regeneration)
        regenerated = await inspect()
        expected_assets = copy.deepcopy(originals)
        for data in ['mesh_a', 'mesh_b']:
            expected_assets[data]['editing'] = {'mode': ['vertex'],
                'selected': {'vertices': [], 'edges': [], 'faces': []},
                'hidden': {'vertices': [], 'edges': [], 'faces': []},
                'history': [], 'active_face': None, 'preview': False}
        assert regenerated['mesh_assets'] == expected_assets
        assert regenerated['entities'] == before['entities'] and regenerated['object_context'] == before['object_context']
        await call('scene_undo', {'expected_revision': regenerated['revision']})
        undone = await inspect()
        assert undone['mesh_assets'] == after['mesh_assets']
        await apply(undone['revision'], regeneration)
        final = await inspect()
        assert final['mesh_assets'] == expected_assets and final['entities'] == before['entities']
        value.update(generated=generated, before=before, after=after, regenerated=regenerated, final=final,
            noop=noop, primary=primary, replay=replay, rejected=rejected,
            both_generated_recipe_states_checked=True, regeneration_undo_replay_checked=True)

    try:
        if interface == 'native_cli_server':
            command = [str(BINARY), 'scene', 'serve', '--scene', str(path)]
            with (folder/'native.stderr').open('x') as stderr:
                child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True)
                write(folder/'started.json', {'process_id': child.pid, 'command': command})

                async def call(name, args, error=False):
                    request = {'id': len(value['calls'])+1, 'name': name, 'arguments': args}
                    raw = json.dumps(request, allow_nan=False)+'\n'
                    child.stdin.write(raw)
                    child.stdin.flush()
                    response = child.stdout.readline()
                    result = json.loads(response)
                    value['calls'].append({'request_bytes': raw, 'response_bytes': response})
                    assert result['id'] == request['id'] and result['ok'] is (not error), result
                    return result['error'] if error else result['result']

                try:
                    await exercise(call)
                finally:
                    child.stdin.close()
                    code = child.wait(timeout=20)
                    child.stdout.close()
                    write(folder/'terminal.json', {'process_id': child.pid, 'terminal_exit_code': code})
                assert code == 0
        else:
            params = StdioServerParameters(command=sys.executable, args=[str(ROOT/'tools/object_state_process_bridge.py'),
                '--binary', str(BINARY), '--scene', str(path), '--receipt', str(folder/'mcp-process')])
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer, read_timeout_seconds=30) as client:
                    initialized = await client.initialize()
                    value['mcp_initialization'] = initialized.model_dump(mode='json', by_alias=True)
                    schemas = {t.name: t.input_schema for t in (await client.list_tools()).tools}
                    value['schemas'] = schemas

                    async def call(name, args, error=False):
                        if not error:
                            Draft202012Validator(schemas[name]).validate(args)
                        result = await client.call_tool(name, args)
                        value['calls'].append({'name': name, 'request': args, 'response': result.model_dump(mode='json', by_alias=True)})
                        assert result.is_error is error, value['calls'][-1]
                        return result.content[0].text if error else result.structured_content

                    await exercise(call)
            started = json.loads((folder/'mcp-process/started.json').read_text())
            terminal = json.loads((folder/'mcp-process/terminal.json').read_text())
            assert started['process_id'] == terminal['process_id'] and terminal['terminal_exit_code'] == 0
            assert started['binary_sha256'] == EXPECTED
            value['mcp_process'] = {'started': started, 'terminal': terminal}
        fresh = cli('inspect')
        assert fresh['scene'] == value['final'] and json.loads(path.read_text()) == value['final']
        value.update(passed=True, fresh_reload_equal=True, saved_scene_sha256=sha(path), binary_sha256=sha(BINARY))
    except BaseException as error:
        value.update(error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        write(folder/'record.json.gz', value)
    return {'interface': interface, 'method': method, 'uvs': uvs, 'passed': True,
            'calls': len(value['calls']), 'file': str((folder/'record.json.gz').relative_to(OUT)), 'sha256': sha(folder/'record.json.gz')}


async def main():
    assert sha(BINARY) == EXPECTED
    OUT.mkdir(exist_ok=False)
    paths = [p for name in ['src', 'tests', 'tools', 'docs/contracts'] for p in (ROOT/name).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    report = {'passed': False, 'required_cases': 20, 'records': [], 'binary_sha256': EXPECTED,
              'input_hashes': hashes, 'driver_sha256': sha(__file__), 'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}
    try:
        for interface in ['native_cli_server', 'official_mcp_sdk']:
            for method in ['center', 'cursor', 'collapse', 'first', 'last']:
                for uvs in [False, True]:
                    row = await trial(interface, method, uvs)
                    report['records'].append(row)
                    print(json.dumps(row), flush=True)
        assert len(report['records']) == 20 and sha(BINARY) == EXPECTED
        assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in paths}
        report.update(passed=True, cases=20, negative_atomic_controls=120, noop_requests=20,
                      two_data_recipe_flags_regeneration_undo_replay_fresh_load=True, inputs_unchanged=True)
    finally:
        write(OUT/'report.json', report)
    print(json.dumps({key: report[key] for key in ['passed', 'cases', 'negative_atomic_controls']}))


if __name__ == '__main__':
    asyncio.run(main())
