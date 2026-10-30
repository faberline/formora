"""New literal multi-provider cursor checks with real failed save and OS denial."""
from pathlib import Path
import copy
import hashlib
import json
import subprocess
import traceback

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
OUT = Path('/private/tmp/formora-multi-merge-unseen-save-01')
OUT.mkdir(exist_ok=False)
BINARY = Path('/private/tmp/formora-multi-merge-target-actual185/debug/formora')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
binary_sha = sha(BINARY)
assert binary_sha == '64ac734c68a8860d5b65e5694c7ea81bb4df7d5db922a0c07f876bcccd1c8019'
denied = [ROOT, Path('/Users/chrischeng/faberlines/formora'),
    Path('/private/tmp/formora-mesh-merge-multi-data'), Path('/private/tmp/formora-mesh-merge-sparse'),
    Path('/private/tmp/formora-multi-merge-api-full-01'), Path('/private/tmp/formora-multi-merge-api-pilot-03'),
    Path('/private/tmp/formora-multi-merge-retained-api-01'), Path('/private/tmp/formora-multi-merge-single-retained-api-01'),
    Path('/private/tmp/formora-object-state-runtime-01')]
policy = '(version 1)(allow default)(deny file-read* '+''.join('(subpath '+json.dumps(str(p))+')' for p in denied)+')'
prefix = ['/usr/bin/sandbox-exec', '-p', policy]
scene = OUT/'scene.json'
calls = []
process = None
report = {'passed': False, 'product_acceptance': 'unrun', 'independent_acceptance': 'unrun',
    'binary_sha256': binary_sha, 'driver_sha256': sha(__file__), 'policy': policy,
    'denial_controls': [], 'cli_calls': [], 'temporary_artifacts_deleted': False}


def write(name, value):
    with (OUT/name).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def cli(action, args=None):
    command = [*prefix, str(BINARY), 'scene', action, '--scene', str(scene)]
    request = None
    if args is not None:
        command += ['--request', '-']
        request = json.dumps(args, allow_nan=False)
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, cwd=OUT)
    stdout, stderr = child.communicate(request, timeout=30)
    report['cli_calls'].append({'command': command, 'request': args, 'process_id': child.pid,
        'terminal_exit_code': child.returncode, 'stdout': stdout, 'stderr': stderr})
    assert child.returncode == 0, (stdout, stderr)
    return json.loads(stdout)


def call(name, args, ok=True):
    request = {'id': len(calls)+1, 'name': name, 'arguments': args}
    raw = json.dumps(request, allow_nan=False)+'\n'
    process.stdin.write(raw)
    process.stdin.flush()
    line = process.stdout.readline()
    assert line, 'missing native result'
    response = json.loads(line)
    calls.append({'request_bytes': raw, 'response_bytes': line})
    assert response['id'] == request['id'] and response['ok'] is ok, response
    return response.get('result') if ok else response['error']


def inspect():
    return call('scene_inspect', {})['scene']


def apply(revision, commands, ok=True):
    return call('scene_apply', {'expected_revision': revision, 'commands': commands}, ok)


def asset(points):
    return {'vertices': dict(zip(['apricot', 'birch', 'cedar'], points)), 'triangles': {},
        'edges': {'ab': ['apricot', 'birch'], 'bc': ['birch', 'cedar']}, 'material_slots': [],
        'editing': {'mode': ['vertex'], 'selected': {'vertices': ['apricot', 'birch', 'cedar'],
            'edges': ['ab', 'bc'], 'faces': []}, 'hidden': {},
            'history': [{'domain': 'vertex', 'id': 'apricot'}, {'domain': 'vertex', 'id': 'cedar'}],
            'active_face': None}}


cursor = [-1.375, .875, .125]
assets = {'mesh_a': asset([[.173, -.219, .391], [1.837, .143, -.517], [3.119, .731, .263]]),
    'mesh_b': asset([[-2.13, 1.79, .23], [-.73, -.31, .67], [.91, .37, -.41]]),
    'outside': {'vertices': {'unrelated': [9.125, -4.25, .875]}, 'triangles': {}, 'material_slots': []}}
frames = {'a': ([2., 3., 4.], [1., 1., 1.], 'mesh_a'),
    'alias': ([3.125, -1.75, .625], [-2., .5, 4.], 'mesh_a'),
    'b': ([-2.25, .375, 1.5], [.25, 2., -.5], 'mesh_b'),
    'outside': ([7., 8., 9.], [1., 1., 1.], 'outside')}
entities = {name: {'name': name, 'parent': None,
    'transform': {'translation': t, 'rotation': [0., 0., 0., 1.], 'scale': s, 'precision': 'f32'},
    'content': {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': data}, 'material': None}}
    for name, (t, s, data) in frames.items()}
context = {'order': ['outside', 'a', 'b', 'alias'], 'selected': ['a', 'alias', 'b'],
    'active': 'alias', 'edit_objects': ['alias', 'b'], 'states': {
        'a': {'lock_scale': [True, False, True]}, 'alias': {'lock_scale': [False, True, False]},
        'b': {'lock_scale': [True, True, False]}}}
setup = {'expected_revision': 0, 'commands': [
    *[{'operation': 'set_mesh_asset', 'id': name, 'asset': value} for name, value in assets.items()],
    *[{'operation': 'create_entity', 'id': name, 'entity': value} for name, value in entities.items()],
    {'operation': 'set_object_context', 'context': context},
    {'operation': 'set_authoring_context', 'context': {'cursor_location': cursor,
        'cursor_rotation': [0., 0., 0.], 'view_rotation': [.125, -.25, .375]}}]}
merge = {'operation': 'merge_edit_meshes', 'merge': {'method': 'cursor', 'uvs': True, 'max_components': 100}}
write('authored-setup.json', setup)
write('authored-operation.json', merge)
try:
    for path in [ROOT/'Cargo.toml', denied[1]/'Cargo.toml',
                 denied[2]/'baseline/fixtures/mesh-merge-multi-data.json',
                 denied[4]/'cli/multi_merge_00000/record.json.gz']:
        command = [*prefix, '/bin/cat', str(path)]
        child = subprocess.run(command, capture_output=True, text=True, cwd=OUT)
        report['denial_controls'].append({'command': command, 'terminal_exit_code': child.returncode,
                                          'stdout': child.stdout, 'stderr': child.stderr})
        assert child.returncode == 1 and not child.stdout and 'not permitted' in child.stderr
    cli('init')
    assert cli('apply', setup)['revision'] == 1
    command = [*prefix, str(BINARY), 'scene', 'serve', '--scene', str(scene)]
    stderr_file = (OUT/'native.stderr').open('x')
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=stderr_file, text=True, cwd=OUT)
    write('started.json', {'process_id': process.pid, 'command': command})
    initial = inspect()
    saved = scene.read_bytes()
    assert initial['revision'] == 1
    for revision, commands, reason in [
        (99, [merge], 'revision'),
        (1, [{'operation': 'merge_edit_meshes', 'merge': {'method': 'cursor', 'max_components': 1}}], 'budget'),
        (1, [{'operation': 'merge_edit_meshes', 'merge': {'method': 'cursor', 'reference_path': 'forbidden-source-answer.json'}}], 'unknown field'),
        (1, [merge, {'operation': 'set_mesh_vertices', 'id': 'missing', 'positions': {'apricot': [0., 0., 0.]}}], 'unknown mesh asset')]:
        error = apply(revision, commands, False)
        assert reason in error, error
        assert inspect() == initial and scene.read_bytes() == saved
    backup = OUT/'original-backup.json'
    scene.rename(backup)
    scene.mkdir()
    error = apply(1, [merge], False)
    report['actual_failed_save_error'] = error
    assert 'Is a directory' in error and '21' in error, error
    assert inspect() == initial and backup.read_bytes() == saved and not list(scene.iterdir())
    error = call('scene_undo', {'expected_revision': 1}, False)
    assert 'nothing to undo' in error, error
    assert inspect() == initial
    # Retain the empty directory. Restore only this test's own original scene.
    scene.rename(OUT/'failed-save-directory')
    backup.rename(scene)
    applied = apply(1, [merge])
    after = inspect()
    assert after['revision'] == applied['revision'] == 2
    receipt = applied['edit_merges'][0]
    assert len(applied['edit_merges']) == 1 and receipt['provider_order'] == ['alias', 'b']
    assert receipt['status'] == 'finished'
    assert receipt['before'] == {'vertices': 6, 'edges': 4, 'faces': 0, 'corners': 0}
    assert receipt['after'] == {'vertices': 2, 'edges': 0, 'faces': 0, 'corners': 0}
    assert [p['shared_instances'] for p in receipt['providers']] == [['a', 'alias'], ['b']]
    assert all(p['outcome'] == 'merged' for p in receipt['providers'])
    for data, point in {'mesh_a': [2.25, 5.25, -.125], 'mesh_b': [3.5, .25, 2.75]}.items():
        assert after['mesh_assets'][data]['vertices'] == {'apricot': point}, after['mesh_assets'][data]
    assert after['mesh_assets']['outside'] == initial['mesh_assets']['outside']
    for key in set(initial)-{'revision', 'mesh_assets'}:
        assert after[key] == initial[key], key
    worlds, states = {}, {}
    for name in frames:
        worlds[name] = call('scene_inspect', {'entity': name, 'world': True})
        states[name] = call('scene_inspect', {'entity': name, 'object_state': True})
        assert states[name]['object_state']['lock_scale'] == initial['object_context']['states'].get(name, {}).get('lock_scale', [False]*3)
    for name in ['alias', 'b']:
        assert worlds[name]['world_vertices'] == {'apricot': cursor}
    assert worlds['a']['world_vertices'] == {'apricot': [4.25, 8.25, 3.875]}
    call('scene_undo', {'expected_revision': 2})
    undone = inspect()
    expected_initial = copy.deepcopy(initial)
    expected_initial['revision'] = 3
    assert undone == expected_initial
    apply(3, [merge])
    replayed = inspect()
    expected_after = copy.deepcopy(after)
    expected_after['revision'] = 4
    assert replayed == expected_after
    for name, value in [('initial.json', initial), ('after.json', after), ('replayed.json', replayed),
                        ('worlds.json', worlds), ('states.json', states), ('receipt.json', applied)]:
        write(name, value)
    process.stdin.close()
    code = process.wait(timeout=20)
    write('terminal.json', {'process_id': process.pid, 'terminal_exit_code': code})
    process.stdout.close()
    stderr_file.close()
    assert code == 0
    assert cli('inspect')['scene'] == replayed
    assert binary_sha == sha(BINARY)
    report.update(passed=True, source_and_prior_answers_read_denied=True,
        actual_provider_frames_checked=True, alias_sharing_checked=True,
        both_meshes_failed_save_rollback=True, undo_history_preserved=True,
        undo_replay_fresh_load=True, native_calls=len(calls))
except BaseException as error:
    report.update(error=str(error), traceback=traceback.format_exc())
    raise
finally:
    if process is not None and process.poll() is None:
        process.stdin.close()
        code = process.wait(timeout=20)
        write('terminal.json', {'process_id': process.pid, 'terminal_exit_code': code})
        process.stdout.close()
        stderr_file.close()
    write('calls.json', calls)
    write('report.json', report)
print(json.dumps({key: report[key] for key in ['passed', 'native_calls', 'actual_failed_save_error', 'undo_replay_fresh_load']}))
