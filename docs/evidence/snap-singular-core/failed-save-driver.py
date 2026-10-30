"""Check an actual failed save before a successful unavailable local query."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('binary', type=Path)
parser.add_argument('authored_setup', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
binary = args.binary.resolve()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
binary_sha = sha(binary)
setup = json.loads(args.authored_setup.read_bytes())
assert setup['expected_revision'] == 0
target = next(c['entity']['transform'] for c in setup['commands'] if c['operation'] == 'create_entity' and c['id'] == 'target')
edited = copy.deepcopy(target)
edited['rotation']['angles'] = [math.pi / 2., -0., -0.]
operation = {'operation': 'set_transform', 'id': 'target', 'transform': edited}
scene = out / 'scene.json'
backup = out / 'before-failed-save.json'
subprocess.run([str(binary), 'scene', 'init', '--scene', str(scene)], capture_output=True, check=True)
calls = []
with subprocess.Popen([str(binary), 'scene', 'serve', '--scene', str(scene)], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as child:

    def call(name, arguments, error=False):
        sequence = len(calls) + 1
        child.stdin.write(json.dumps({'id': sequence, 'name': name, 'arguments': arguments}) + '\n')
        child.stdin.flush()
        response = json.loads(child.stdout.readline())
        calls.append({'name': name, 'arguments': arguments, 'response': response})
        with (out / 'calls.jsonl').open('a') as output:
            output.write(json.dumps(calls[-1], allow_nan=False) + '\n')
        assert response['id'] == sequence and response['ok'] is (not error), response
        return response['error'] if error else response['result']

    call('scene_apply', setup)
    before = call('scene_inspect', {})
    world_before = call('scene_inspect', {'entity': 'child', 'world': True})
    assert world_before['object_frames']['matrix_local'] == [[0.] * 4 for _ in range(4)]
    saved = scene.read_bytes()
    scene.rename(backup)
    scene.mkdir()
    failure = call('scene_apply', {'expected_revision': 1, 'commands': [operation]}, error=True)
    assert 'directory' in failure.lower(), failure
    assert call('scene_inspect', {}) == before
    assert call('scene_inspect', {'entity': 'child', 'world': True}) == world_before
    assert backup.read_bytes() == saved and not list(scene.iterdir())
    scene.rmdir()
    shutil.copyfile(backup, scene)
    call('scene_undo', {'expected_revision': 1})
    undone = call('scene_inspect', {})['scene']
    assert undone['revision'] == 2 and not undone['entities'] and not undone.get('mesh_assets', {})
    call('scene_apply', {**setup, 'expected_revision': 2})
    recreated = call('scene_inspect', {})['scene']
    receipt = call('scene_apply', {'expected_revision': 3, 'commands': [operation]})
    assert receipt['revision'] == 4
    after = call('scene_inspect', {})['scene']
    committed = scene.read_bytes()
    query = call('scene_inspect', {'entity': 'child', 'world': True})
    assert query['object_frames']['matrix_local'] is None
    assert query['object_frames']['matrix_local_error'] == 'cannot_invert'
    assert query['revision'] == 4 and scene.read_bytes() == committed
    assert all(math.isfinite(v) for point in query['world_vertices'].values() for v in point)
    call('scene_undo', {'expected_revision': 4})
    restored = call('scene_inspect', {})['scene']
    assert {k: v for k, v in restored.items() if k != 'revision'} == {k: v for k, v in recreated.items() if k != 'revision'}
    call('scene_apply', {'expected_revision': 5, 'commands': [operation]})
    final = call('scene_inspect', {})
    assert {k: v for k, v in final['scene'].items() if k != 'revision'} == {k: v for k, v in after.items() if k != 'revision'}
    child.stdin.close()
    child.wait(timeout=10)
    stderr = child.stderr.read()
    assert child.returncode == 0, stderr
fresh = subprocess.run([str(binary), 'scene', 'inspect', '--scene', str(scene)], capture_output=True, text=True, check=True)
assert json.loads(fresh.stdout) == final and binary_sha == sha(binary)
report = {'passed': True, 'binary_sha256': binary_sha, 'driver_sha256': sha(Path(__file__)),
          'authored_setup_sha256': sha(args.authored_setup), 'actual_save_failure': failure,
          'failed_save_preserves_world_memory_revision_disk_and_undo': True,
          'unavailable_query_preserves_successful_commit': True, 'undo_replay_fresh_reload': True,
          'native_terminal_exit': child.returncode, 'fresh_process_exit': fresh.returncode,
          'native_calls': len(calls), 'product_acceptance': 'unrun'}
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'passed': True, 'native_calls': len(calls), 'actual_save_failure': failure}))
