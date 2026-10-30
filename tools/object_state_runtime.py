#!/usr/bin/env python3
"""Exercise all 160 authored property cases through CLI and official MCP."""
import argparse
import asyncio
import copy
import json
from pathlib import Path
import subprocess
import sys
import traceback

from compare_object_state_reference import compare, digest
from compare_snap_menu_reference import tree
from generate_multi_mesh_merge_cases import author as base_inputs
from generate_object_state_cases import author
from multi_mesh_merge_product_inputs import scene as base_scene
from runtime_artifacts import write_json

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['parent', 'a', 'alias', 'b', 'untouched']


def setup(suite, run):
    """Only authored inputs enter the product. No measured answer is read."""
    proxy = {'context': suite['base_context'], 'selection': 'both',
             'history': 'both_vertex', 'mode': ['VERT'], 'frame': run['frame']}
    scene = base_scene(base_inputs(), proxy)
    context = scene['object_context']
    if run['mode'] == 'OBJECT':
        context['edit_objects'] = []
    context['states'] = {name: {'lock_scale': flags.copy()}
                         for name, flags in suite['initial_locks'].items()}
    return scene


def snapshot(scene, states, worlds):
    objects, sharing = {}, {}
    for name, entity in scene['entities'].items():
        state, world = states[name], worlds[name]
        assert state['id'] == world['id'] == name
        assert state['revision'] == world['revision'] == scene['revision']
        assert state['entity'] == world['entity'] == entity
        lock = state['object_state']['lock_scale']
        assert len(lock) == 3 and all(type(v) is bool for v in lock), 'missing/invalid scale lock query'
        stored = scene['object_context']['states'].get(name, {}).get('lock_scale', [False]*3)
        assert lock == stored, 'query differs from real saved state'
        frame = world['object_frames']
        item = {'lock_scale': lock, 'matrix_world': world['world_matrix'],
                'matrix_basis': frame['matrix_basis'], 'matrix_parent_inverse': frame['matrix_parent_inverse'],
                'parent': entity['parent'], 'mode': 'EDIT' if frame['edit_mode'] else 'OBJECT',
                'type': 'EMPTY' if entity['content']['kind'] == 'empty' else 'MESH'}
        if item['type'] == 'MESH':
            data = entity['content']['geometry']['id']
            asset = scene['mesh_assets'][data]
            item['geometry_counts'] = [len(asset['vertices']), len(asset['edges']), len(asset['polygons'])]
            sharing.setdefault(data, []).append(name)
        objects[name] = item
    return {'objects': objects, 'sharing': sorted(sorted(v) for v in sharing.values()),
            'mode': 'EDIT_MESH' if scene['object_context']['edit_objects'] else 'OBJECT'}


def check_record(suite, run, value, references):
    assert value['run'] == run and value['interface'] in ['cli', 'official_mcp_sdk']
    assert value['applied']['revision'] == 1
    for phase in ['before', 'after', 'reloaded']:
        part = value[phase]
        actual = snapshot(part['scene'], part['states'], part['worlds'])
        assert actual == part['snapshot'], 'record snapshot differs from actual query values'
        assert set(actual['objects']) == set(NAMES)
        for name in NAMES:
            expected = suite['initial_locks'][name]
            if phase != 'before' and name == run['target']:
                expected = run['lock_scale']
            assert actual['objects'][name]['lock_scale'] == expected, 'authored lock value differs'
        for reference in references:
            tree(reference[phase], actual, run['id']+'/'+phase)
    before, after, reloaded = [value[p]['scene'] for p in ['before', 'after', 'reloaded']]
    assert before['revision'] == 0 and after['revision'] == reloaded['revision'] == 1
    assert after == reloaded, 'fresh process differs from saved result'
    expected = copy.deepcopy(before)
    expected['revision'] = 1
    state = expected['object_context']['states'][run['target']]
    if any(run['lock_scale']):
        state['lock_scale'] = run['lock_scale']
    else:
        state.pop('lock_scale', None)
    # The input file can explicitly store default false flags. Normal saving
    # omits only this new default field, including on other untouched objects.
    for state in expected['object_context']['states'].values():
        if not any(state.get('lock_scale', [False]*3)):
            state.pop('lock_scale', None)
    assert expected == after, 'property assignment changed unrelated state'
    assert value['saved_after'] == after and value['saved_reloaded'] == reloaded


async def run(binary, output):
    from jsonschema import Draft202012Validator
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    suite_path = ROOT/'baseline/fixtures/object-state.json'
    suite = json.loads(suite_path.read_text())
    assert suite == author()
    folders = [ROOT/'docs/evidence/object-state-query'/name for name in ['native-02', 'native-03']]
    source = compare(suite_path, *folders)
    assert source['source_gate_passed']
    inputs = [ROOT/'Cargo.toml', ROOT/'Cargo.lock', suite_path,
              ROOT/'docs/contracts/object-state-query.md', *sorted((ROOT/'src').rglob('*.rs')),
              *sorted((ROOT/'tests').rglob('*.rs')),
              *[ROOT/'tools'/name for name in ['object_state_runtime.py', 'object_state_process_bridge.py',
                  'multi_mesh_merge_product_inputs.py', 'generate_multi_mesh_merge_cases.py',
                  'generate_object_state_cases.py', 'compare_object_state_reference.py']]]
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    binary_hash = digest(binary)
    output.mkdir(parents=True, exist_ok=False)
    report = {'complete': False, 'required_cases': 320, 'passed_cases': 0,
              'source_gate': source, 'binary_sha256': binary_hash, 'inputs': hashes,
              'implementation_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'records': [], 'product_acceptance': 'pending'}
    try:
        for interface in ['cli', 'official_mcp_sdk']:
            for index, case in enumerate(suite['runs']):
                folder = output/interface/case['id']
                folder.mkdir(parents=True)
                scene_path = folder/'scene.json'
                write_json(scene_path, setup(suite, case))
                value = {'interface': interface, 'run': case, 'calls': []}

                def cli(name, args):
                    command = [str(binary), 'scene', name.removeprefix('scene_'), '--scene', str(scene_path)]
                    data = None
                    if name == 'scene_apply':
                        command.extend(['--request', '-'])
                        data = json.dumps(args, allow_nan=False)
                    else:
                        for key, item in args.items():
                            command.append('--'+key.replace('_', '-'))
                            if type(item) is not bool:
                                command.append(item)
                    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE, text=True)
                    stdout, stderr = process.communicate(data, timeout=30)
                    record = {'interface': 'cli', 'command': command, 'request': args,
                              'process_id': process.pid, 'terminal_exit_code': process.returncode,
                              'stdout': stdout, 'stderr': stderr}
                    value['calls'].append(record)
                    assert process.returncode == 0, record
                    return json.loads(stdout)

                async def exercise(call):
                    async def inspect():
                        current = (await call('scene_inspect', {}))['scene']
                        states, worlds = {}, {}
                        for name in NAMES:
                            states[name] = await call('scene_inspect', {'entity': name, 'object_state': True})
                            worlds[name] = await call('scene_inspect', {'entity': name, 'world': True})
                        return {'scene': current, 'states': states, 'worlds': worlds,
                                'snapshot': snapshot(current, states, worlds)}
                    value['before'] = await inspect()
                    context = copy.deepcopy(value['before']['scene']['object_context'])
                    context['states'][case['target']]['lock_scale'] = case['lock_scale'].copy()
                    request = {'expected_revision': 0, 'commands': [
                        {'operation': 'set_object_context', 'context': context}]}
                    value['request'] = request
                    value['applied'] = await call('scene_apply', request)
                    value['after'] = await inspect()
                    value['saved_after'] = json.loads(scene_path.read_text())

                async def cli_call(name, args):
                    return cli(name, args)

                if interface == 'cli':
                    await exercise(cli_call)
                else:
                    params = StdioServerParameters(command=sys.executable, args=[
                        str(ROOT/'tools/object_state_process_bridge.py'), '--binary', str(binary),
                        '--scene', str(scene_path), '--receipt', str(folder/'mcp-process')])
                    async with stdio_client(params) as (reader, writer):
                        async with ClientSession(reader, writer, read_timeout_seconds=30) as client:
                            initialized = await client.initialize()
                            value['initialize'] = initialized.model_dump(mode='json', by_alias=True)
                            tools = (await client.list_tools()).tools
                            value['tools'] = [t.model_dump(mode='json', by_alias=True) for t in tools]
                            schemas = {t.name: t.input_schema for t in tools}
                            assert 'object_state' in schemas['scene_inspect']['properties']

                            async def mcp_call(name, args):
                                Draft202012Validator(schemas[name]).validate(args)
                                result = await client.call_tool(name, args)
                                value['calls'].append({'interface': 'official_mcp_sdk', 'name': name,
                                    'request': args, 'response': result.model_dump(mode='json', by_alias=True)})
                                assert not result.is_error, value['calls'][-1]
                                return result.structured_content

                            await exercise(mcp_call)
                    started = json.loads((folder/'mcp-process/started.json').read_text())
                    terminal = json.loads((folder/'mcp-process/terminal.json').read_text())
                    assert started['process_id'] == terminal['process_id'] and terminal['terminal_exit_code'] == 0
                    assert started['binary_sha256'] == binary_hash
                    value['mcp_process'] = {'started': started, 'terminal': terminal}
                current = cli('scene_inspect', {})['scene']
                states, worlds = {}, {}
                for name in NAMES:
                    states[name] = cli('scene_inspect', {'entity': name, 'object_state': True})
                    worlds[name] = cli('scene_inspect', {'entity': name, 'world': True})
                value['reloaded'] = {'scene': current, 'states': states, 'worlds': worlds,
                                     'snapshot': snapshot(current, states, worlds)}
                value['saved_reloaded'] = json.loads(scene_path.read_text())
                # Expected native records are opened only after real execution.
                references = [json.loads((folder/(case['id']+'.json')).read_text()) for folder in folders]
                raw = write_json(folder/'record.json', value, compressed=True)
                check_record(suite, case, value, references)
                report['records'].append({'interface': interface, 'id': case['id'],
                    'path': str(raw.relative_to(output)), 'sha256': digest(raw)})
                report['passed_cases'] += 1
                if (index+1) % 20 == 0:
                    print(json.dumps({'interface': interface, 'passed': index+1, 'required': 160}), flush=True)
        assert report['passed_cases'] == 320
        assert hashes == {str(p.relative_to(ROOT)): digest(p) for p in inputs} and digest(binary) == binary_hash
        report.update(complete=True, product_acceptance='local_property_matrix_passed_only')
    except BaseException as error:
        report.update(error=str(error), traceback=traceback.format_exc())
        if 'value' in locals() and 'folder' in locals():
            write_json(folder/'failed-diagnostic.json', value, compressed=True)
        raise
    finally:
        write_json(output/'report.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.binary.resolve(), args.output.resolve()))
