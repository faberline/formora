#!/usr/bin/env python3
"""Execute the full multi-data matrix through actual CLI and official MCP."""
import argparse
import asyncio
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

from compare_multi_mesh_merge_reference import bind_suite, load_capture, validate_run, digest
from compare_snap_menu_reference import tree
from multi_mesh_merge_product_inputs import scene as authored_scene
from multi_mesh_merge_runtime_inputs import setup, operation
from multi_mesh_merge_runtime_check import check_record, ROOT, LEGACY
from runtime_artifacts import write_json


def source_preflight(suite_path, suite):
    bind_suite(suite)
    folders = [ROOT/'docs/evidence/mesh-merge-multi-data-baseline'/name for name in ['native-01', 'native-02']]
    manifests = [load_capture(folder, suite_path, suite['runs'], False) for folder in folders]
    assert manifests[0]['process_id'] != manifests[1]['process_id']
    assert manifests[0]['input_hashes'] == manifests[1]['input_hashes']
    report_path = ROOT/'docs/evidence/mesh-merge-multi-data-baseline/source-comparison-01.json'
    report = json.loads(report_path.read_text())
    assert report['source_comparison_passed'] and report['complete_source_gate'] and report['cases'] == 13440
    assert report['suite_sha256'] == digest(suite_path)
    assert report['checker_sha256'] == digest(ROOT/'tools/compare_multi_mesh_merge_reference.py')
    assert report['native_processes'] == [m['process_id'] for m in manifests]
    return folders, manifests, report


def references(suite, run, index, folders, manifests):
    values = []
    for folder, manifest in zip(folders, manifests):
        row = manifest['runs'][index]
        assert row['id'] == run['id'] and row['file'] == run['id']+'.json.gz'
        path = folder/row['file']
        assert digest(path) == row['sha256'], 'source raw hash differs'
        raw = gzip.decompress(path.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes']
        value = json.loads(raw)
        validate_run(suite, run, value)
        values.append(value)
    tree(values[0], values[1], run['id']+'/source repeat')
    return values


def input_paths():
    paths = [ROOT/'Cargo.toml', ROOT/'Cargo.lock', ROOT/'baseline/fixtures/mesh-merge-multi-data.json',
        ROOT/'docs/contracts/mesh-merge-multi-data-core.md',
        ROOT/'docs/evidence/mesh-merge-multi-data-core/interface-evidence-contract.md',
        LEGACY/'pilot-native.py', LEGACY/'runtime-cli-mcp.py']
    for name in ['src', 'tests', 'tools']:
        paths.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    return sorted(set(paths))


async def run(binary, output, ids, interfaces):
    from jsonschema import Draft202012Validator
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    suite_path = ROOT/'baseline/fixtures/mesh-merge-multi-data.json'
    suite = json.loads(suite_path.read_text())
    folders, manifests, source = source_preflight(suite_path, suite)
    assert len(ids) == len(set(ids)) and set(ids) <= {r['id'] for r in suite['runs']}
    cases = [(i, r) for i, r in enumerate(suite['runs']) if not ids or r['id'] in ids]
    hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in input_paths()}
    binary_hash = digest(binary)
    output.mkdir(parents=True, exist_ok=False)
    report = {'complete': False, 'scope': 'focused_pilot' if ids else 'full_13440_per_interface',
        'required_records': len(cases)*len(interfaces), 'executed_records': 0, 'failed_records': 0,
        'required_interfaces': interfaces, 'source_gate': source,
        'source_manifest_sha256': [digest(f/'manifest.json') for f in folders],
        'input_hashes': hashes, 'binary': str(binary), 'binary_sha256': binary_hash,
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'records': [], 'outcomes': {}, 'product_acceptance': 'unrun'}
    outcomes = Counter()
    write_json(output/'started.json', {key: report[key] for key in report if key != 'records'})
    active_value, active_folder = None, None
    try:
        for interface in interfaces:
            for case_number, (source_index, case) in enumerate(cases):
                folder = output/interface/case['id']
                folder.mkdir(parents=True)
                scene = folder/'scene.json'
                record = {'interface': interface, 'run': case, 'input': authored_scene(suite, case),
                    'setup': setup(suite, case), 'request': operation(case), 'calls': [],
                    'result': None, 'error': None, 'comparison_error': None}
                active_value, active_folder = record, folder

                def cli(action, args=None):
                    args = args or {}
                    command = [str(binary), 'scene', action, '--scene', str(scene)]
                    data = None
                    if action == 'apply':
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
                    call = {'interface': 'cli', 'command': command, 'request': args,
                            'process_id': process.pid, 'terminal_exit_code': process.returncode,
                            'stdout': stdout, 'stderr': stderr}
                    record['calls'].append(call)
                    response = json.loads(stdout)
                    if process.returncode == 0:
                        return response, None
                    assert isinstance(response.get('error'), str) and response['error'], call
                    return None, response['error']

                initialized, error = cli('init')
                assert error is None and initialized == {'revision': 0}

                async def exercise(call):
                    created, error = await call('scene_apply', record['setup'])
                    assert error is None and created['revision'] == 1
                    record['setup_result'] = created

                    async def inspect():
                        value, error = await call('scene_inspect', {})
                        assert error is None
                        current = value['scene']
                        queries, worlds, states = {}, {}, {}
                        for data in sorted(current['mesh_assets']):
                            value, error = await call('scene_inspect', {'mesh_asset': data, 'normals': True})
                            assert error is None
                            queries[data] = value
                        for name in sorted(current['entities']):
                            value, error = await call('scene_inspect', {'entity': name, 'world': True})
                            assert error is None
                            worlds[name] = value
                            value, error = await call('scene_inspect', {'entity': name, 'object_state': True})
                            assert error is None
                            states[name] = value
                        return {'scene': current, 'queries': queries, 'worlds': worlds, 'states': states}

                    record['before'] = await inspect()
                    record['saved_before_sha256'] = digest(scene)
                    record['result'], record['error'] = await call('scene_apply', record['request'])
                    applied_bytes = scene.read_bytes()
                    record['after'] = await inspect()
                    assert scene.read_bytes() == applied_bytes, 'read-only query changed scene'
                    record['saved_after_sha256'] = digest(scene)
                    record['saved_after'] = json.loads(applied_bytes)

                async def cli_call(name, args):
                    return cli(name.removeprefix('scene_'), args)

                if interface == 'cli':
                    await exercise(cli_call)
                else:
                    params = StdioServerParameters(command=sys.executable, args=[
                        str(ROOT/'tools/object_state_process_bridge.py'), '--binary', str(binary),
                        '--scene', str(scene), '--receipt', str(folder/'mcp-process')])
                    async with stdio_client(params) as (reader, writer):
                        async with ClientSession(reader, writer, read_timeout_seconds=30) as client:
                            initialized = await client.initialize()
                            record['mcp_initialization'] = initialized.model_dump(mode='json', by_alias=True)
                            schemas = {tool.name: tool.input_schema for tool in (await client.list_tools()).tools}
                            record['mcp_schemas'] = schemas
                            assert 'object_state' in schemas['scene_inspect']['properties']

                            async def mcp_call(name, args):
                                Draft202012Validator(schemas[name]).validate(args)
                                result = await client.call_tool(name, args)
                                record['calls'].append({'interface': 'official_mcp_sdk', 'name': name,
                                    'request': args, 'response': result.model_dump(mode='json', by_alias=True)})
                                return (None, result.content[0].text) if result.is_error else (result.structured_content, None)

                            await exercise(mcp_call)
                    started = json.loads((folder/'mcp-process/started.json').read_text())
                    terminal = json.loads((folder/'mcp-process/terminal.json').read_text())
                    assert started['process_id'] == terminal['process_id'] and terminal['terminal_exit_code'] == 0
                    assert started['binary_sha256'] == binary_hash
                    record['mcp_process'] = {'started': started, 'terminal': terminal}
                fresh, error = cli('inspect')
                assert error is None
                record['fresh_scene'] = fresh['scene']
                assert record['saved_after_sha256'] == digest(scene), 'fresh read changed file'
                kind = None
                try:
                    refs = references(suite, case, source_index, folders, manifests)
                    kind = check_record(suite, case, record, refs)
                except (AssertionError, KeyError, ValueError) as error:
                    record['comparison_error'] = str(error) or type(error).__name__
                    record['comparison_traceback'] = traceback.format_exc()
                record['status'] = 'failed' if record['comparison_error'] else 'passed'
                path = write_json(folder/'record.json', record, compressed=True)
                report['records'].append({'id': case['id'], 'interface': interface,
                    'file': path.relative_to(output).as_posix(), 'sha256': digest(path),
                    'status': record['status'], 'error': record['comparison_error'], 'kind': kind})
                report['executed_records'] += 1
                report['failed_records'] += int(record['status'] == 'failed')
                if kind:
                    outcomes[kind] += 1
                if (case_number+1) % 25 == 0 or record['status'] == 'failed':
                    print(json.dumps({'interface': interface, 'executed': case_number+1,
                        'required': len(cases), 'failed_total': report['failed_records'],
                        'last_error': record['comparison_error']}), flush=True)
                if record['status'] == 'failed':
                    raise AssertionError(record['comparison_error'])
                active_value, active_folder = None, None
        assert report['executed_records'] == report['required_records'] and report['failed_records'] == 0
        assert hashes == {p.relative_to(ROOT).as_posix(): digest(p) for p in input_paths()} and digest(binary) == binary_hash
        if not ids:
            assert outcomes['explicit_enum_rejection'] == 4352*len(interfaces)
            assert outcomes['finished_source_comparison'] == 9088*len(interfaces)
        report['complete'] = True
    except BaseException as error:
        report.update(error=str(error), traceback=traceback.format_exc())
        if active_value is not None:
            write_json(active_folder/'failed-process-diagnostic.json', active_value, compressed=True)
        raise
    finally:
        report['outcomes'] = dict(outcomes)
        write_json(output/'report.json', report)
        print(json.dumps({key: report[key] for key in ['complete', 'scope', 'executed_records', 'failed_records']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--interface', choices=['cli', 'official_mcp_sdk'], action='append')
    args = parser.parse_args()
    asyncio.run(run(args.binary.resolve(), args.output.resolve(), args.case,
                    args.interface or ['cli', 'official_mcp_sdk']))
