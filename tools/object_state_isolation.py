#!/usr/bin/env python3
"""Check unseen per-object flags while macOS denies product source reads."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from compare_object_state_reference import digest
from runtime_artifacts import write_json

ROOT = Path(__file__).resolve().parents[1]


def run(source_binary, output):
    output.mkdir(parents=True, exist_ok=False)
    denied = [ROOT, Path('/Users/chrischeng/faberlines/formora'),
              Path('/private/tmp/formora-mesh-merge-sparse'),
              Path('/private/tmp/formora-mesh-merge-multi-data'),
              Path('/private/tmp/formora-object-state-runtime-01')]
    policy = '(version 1)(allow default)(deny file-read* '+''.join(
        '(subpath '+json.dumps(str(p))+')' for p in denied)+')'
    write_json(output/'policy.json', {'profile': policy, 'denied': list(map(str, denied))})
    prefix = ['/usr/bin/sandbox-exec', '-p', policy]
    report = {'passed': False, 'denial_controls': [], 'calls': [], 'binary_sha256': digest(source_binary),
              'driver_sha256': digest(Path(__file__)), 'full_issue_acceptance': 'pending'}
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix='formora-object-state-unseen-') as temporary:
            workspace = Path(temporary)
            binary = workspace/'formora'
            shutil.copyfile(source_binary, binary)
            binary.chmod(0o755)
            for path in [ROOT/'Cargo.toml', denied[1]/'Cargo.toml',
                         denied[-1]/'cli/object_state_001/record.json.gz']:
                command = [*prefix, '/bin/cat', str(path)]
                result = subprocess.run(command, cwd=workspace, capture_output=True, text=True)
                report['denial_controls'].append({'command': command, 'exit': result.returncode,
                                                  'stdout': result.stdout, 'stderr': result.stderr})
                assert result.returncode == 1 and not result.stdout and 'not permitted' in result.stderr
            scene = workspace/'scene.json'
            result = subprocess.run([*prefix, str(binary), 'scene', 'init', '--scene', str(scene)],
                                    cwd=workspace, capture_output=True, text=True)
            report['init'] = {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
            assert result.returncode == 0
            command = [*prefix, str(binary), 'scene', 'serve', '--scene', str(scene)]
            with (output/'stderr').open('xb') as stderr:
                process = subprocess.Popen(command, cwd=workspace, stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=stderr, text=True)
                report.update(process_id=process.pid, command=command)

                def call(name, args, ok=True):
                    request = {'id': len(report['calls'])+1, 'name': name, 'arguments': args}
                    raw = json.dumps(request, allow_nan=False)+'\n'
                    process.stdin.write(raw)
                    process.stdin.flush()
                    response = process.stdout.readline()
                    value = json.loads(response)
                    report['calls'].append({'request_bytes': raw, 'response_bytes': response})
                    assert value['id'] == request['id'] and value['ok'] is ok, value
                    return value.get('result')

                def apply(revision, commands, ok=True):
                    return call('scene_apply', {'expected_revision': revision, 'commands': commands}, ok)

                names = ['apricot', 'birch', 'cedar']
                asset = {'vertices': {'alone': [.173, -.719, .433]}, 'triangles': {}, 'material_slots': []}
                commands = [{'operation': 'set_mesh_asset', 'id': 'shared', 'asset': asset}]
                for index, name in enumerate(names):
                    commands.append({'operation': 'create_entity', 'id': name, 'entity': {
                        'name': name, 'parent': 'apricot' if index else None,
                        'transform': {'translation': [.317, -.193, .743], 'rotation': [0., 0., 0., 1.],
                                      'scale': [0., -1.37, 2.19] if index == 0 else [1., 1., 1.],
                                      'precision': 'f32'},
                        'content': {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': 'shared'}, 'material': None}}})
                apply(0, commands)
                baseline = call('scene_inspect', {})['scene']
                revision = 1
                for mask in [5, 2, 7, 0, 6, 1, 4, 3]:
                    flags = {name: [bool((mask+index) % 8 & (1 << axis)) for axis in range(3)]
                             for index, name in enumerate(names)}
                    context = {'order': names, 'states': {name: {'lock_scale': value} for name, value in flags.items()}}
                    request = {'operation': 'set_object_context', 'context': context}
                    apply(revision, [request])
                    revision += 1
                    for name in names:
                        value = call('scene_inspect', {'entity': name, 'object_state': True})
                        assert value['object_state']['lock_scale'] == flags[name]
                    saved = scene.read_bytes()
                    current = call('scene_inspect', {})['scene']
                    assert current['mesh_assets'] == baseline['mesh_assets'] and current['entities'] == baseline['entities']
                    bad = copy.deepcopy(context)
                    bad['states']['birch']['lock_scale'] = [True]
                    apply(revision, [{'operation': 'set_object_context', 'context': bad}], False)
                    assert saved == scene.read_bytes()
                    bad['states']['birch']['lock_scale'] = [True, False, True]
                    bad['states']['missing'] = {'lock_scale': [True, False, False]}
                    apply(revision, [request, {'operation': 'set_object_context', 'context': bad}], False)
                    assert saved == scene.read_bytes() and call('scene_inspect', {})['scene'] == current
                    call('scene_undo', {'expected_revision': revision})
                    revision += 1
                    restored = call('scene_inspect', {})['scene']
                    assert restored.get('object_context') is None
                    for name in names:
                        assert call('scene_inspect', {'entity': name, 'object_state': True})['object_state']['lock_scale'] == [False]*3
                    if mask == 3:
                        apply(revision, [request])
                        revision += 1
                        final = call('scene_inspect', {})['scene']
                process.stdin.close()
                report['terminal_exit_code'] = process.wait(timeout=15)
                assert report['terminal_exit_code'] == 0
                process.stdout.close()
            command = [*prefix, str(binary), 'scene', 'inspect', '--scene', str(scene)]
            result = subprocess.run(command, cwd=workspace, capture_output=True, text=True)
            report['fresh_process'] = {'command': command, 'exit': result.returncode,
                                       'stdout': result.stdout, 'stderr': result.stderr}
            assert result.returncode == 0 and json.loads(result.stdout)['scene'] == final
            write_json(output/'saved-scene.json', json.loads(scene.read_text()))
            assert digest(binary) == report['binary_sha256']
            report.update(passed=True, unseen_boolean_cases=8*3, source_reads_denied=True,
                          singular_parent_query=True, rollback=True, undo=True, replay=True, fresh_load=True)
    finally:
        if process is not None and process.poll() is None:
            process.stdin.close()
            report['terminal_exit_code'] = process.wait(timeout=15)
        write_json(output/'report.json', report)
    print(json.dumps({key: report[key] for key in ['passed', 'unseen_boolean_cases', 'source_reads_denied']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.binary.resolve(), args.output.resolve())
