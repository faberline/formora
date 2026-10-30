"""Unseen analytic zero frame with all repository reads denied to the product."""
import argparse
import copy
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from compare_snap_singular_reference import delta_matrix, world_point
from compare_snap_rotation_reference import compose
from compare_snap_menu_reference import tree


def transform(t, r, s, mode='xyz', delta_t=None):
    return {'translation': t, 'rotation': {'kind': 'euler', 'angles': r, 'order': mode},
            'scale': s, 'precision': 'f32', 'delta': {'translation': delta_t or [0.] * 3,
            'euler': [0.] * 3, 'quaternion_wxyz': [1., 0., 0., 0.], 'scale': [1.] * 3}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='formora-zero-denied-') as temporary, ExitStack() as cleanup:
        folder = Path(temporary)
        binary = folder / 'formora'
        shutil.copyfile(args.binary.resolve(), binary)
        binary.chmod(0o755)
        policy = '(version 1)(allow default)(deny file-read* (subpath ' + json.dumps(str(ROOT)) + '))'
        prefix = ['/usr/bin/sandbox-exec', '-p', policy]
        control = subprocess.run([*prefix, '/bin/cat', str(ROOT / 'Cargo.toml')], cwd=folder, capture_output=True, text=True)
        assert control.returncode != 0 and not control.stdout
        assert 'not permitted' in control.stderr or 'Permission denied' in control.stderr
        path = folder / 'scene.json'
        subprocess.run([*prefix, str(binary), 'scene', 'init', '--scene', str(path)], cwd=folder, capture_output=True, text=True, check=True)
        process = cleanup.enter_context(subprocess.Popen([*prefix, str(binary), 'scene', 'serve', '--scene', str(path)],
            cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        calls = []

        def call(name, arguments, error=False):
            sequence = len(calls) + 1
            process.stdin.write(json.dumps({'id': sequence, 'name': name, 'arguments': arguments}) + '\n')
            process.stdin.flush()
            response = json.loads(process.stdout.readline())
            calls.append({'name': name, 'arguments': arguments, 'response': response})
            with (out / 'calls.jsonl').open('a') as stream:
                stream.write(json.dumps(calls[-1], allow_nan=False) + '\n')
            assert response['id'] == sequence and response['ok'] is (not error), response
            return response['error'] if error else response['result']

        transforms = {
            'parent': transform([6.5, -7.25, .875], [.37, -.23, .51], [-1.2, .7, 0.], delta_t=[.125, -.25, .375]),
            'target': transform([.625, -.875, .375], [0.] * 3, [.9, 1.4, .8], 'yxz', [.125, -.25, .375]),
            'child': transform([.25, -.75, .5], [0.] * 3, [1.] * 3, delta_t=[-.25, .125, .0625])}
        asset = {'vertices': {'a': [-3.5, -2.5, 0.], 'b': [3.5, -2.5, 0.], 'c': [0., 2.5, .125]},
                 'triangles': {'tri': {'vertices': ['a', 'b', 'c'], 'material_slot': None,
                                      'uv_layers': {}, 'corner_normals': None}}, 'material_slots': []}
        setup = {'expected_revision': 0, 'commands': [{'operation': 'set_mesh_asset', 'id': 'unseen', 'asset': asset}]}
        for name, parent in [('parent', None), ('target', 'parent'), ('child', 'target')]:
            content = {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': 'unseen'}, 'material': None} if name == 'child' else {'kind': 'empty'}
            setup['commands'].append({'operation': 'create_entity', 'id': name, 'entity': {
                'name': name, 'parent': parent, 'transform': transforms[name], 'content': content}})
        setup['commands'].append({'operation': 'set_object_context', 'context': {
            'order': ['parent', 'target', 'child'], 'selected': ['target'], 'active': 'target'}})
        call('scene_apply', setup)
        before = call('scene_inspect', {})['scene']
        query_before = call('scene_inspect', {'entity': 'child', 'world': True})
        assert query_before['object_frames']['matrix_local'] == [[0.] * 4 for _ in range(4)]
        edited = copy.deepcopy(transforms['target'])
        edited['rotation']['angles'] = [math.pi / 2., -0., -0.]
        request = {'expected_revision': 1, 'commands': [{'operation': 'set_transform', 'id': 'target', 'transform': edited}]}
        receipt = call('scene_apply', request)
        assert receipt['revision'] == 2
        saved = path.read_bytes()
        query_after = call('scene_inspect', {'entity': 'child', 'world': True})
        assert query_after['object_frames']['matrix_local'] is None
        assert query_after['object_frames']['matrix_local_error'] == 'cannot_invert'
        after_inspection = call('scene_inspect', {})
        after = after_inspection['scene']
        assert after['revision'] == 2 and path.read_bytes() == saved

        def basis(t):
            r = t['rotation']
            raw = {'mode': r['order'].upper(), 'euler': r['angles'], 'quaternion_wxyz': [1., 0., 0., 0.], 'axis_angle': [0., 0., 1., 0.]}
            d = {**t['delta'], 'location': t['delta']['translation']}
            del d['translation']
            return delta_matrix({'location': t['translation'], 'scale': t['scale']}, raw, d)

        expected_world = compose(compose(basis(transforms['parent']), basis(edited)), basis(transforms['child']))
        tree(expected_world, query_after['world_matrix'], 'unseen analytic world')
        assert set(query_after['world_vertices']) == set(asset['vertices'])
        for id, point in asset['vertices'].items():
            tree(world_point(expected_world, point), query_after['world_vertices'][id], 'unseen real geometry/' + id)
        late = {'expected_revision': 2, 'commands': [request['commands'][0], {'operation': 'delete_entity', 'id': 'missing'}]}
        for invalid in [request, late, {'expected_revision': 2, 'commands': [{'operation': 'snap_scene', 'snap': {
                'action': {'kind': 'cursor_to_center'}, 'max_objects': 0}}]}]:
            assert call('scene_apply', invalid, error=True)
            assert call('scene_inspect', {}) == after_inspection and path.read_bytes() == saved
        call('scene_undo', {'expected_revision': 2})
        restored = call('scene_inspect', {})['scene']
        assert {k: v for k, v in restored.items() if k != 'revision'} == {k: v for k, v in before.items() if k != 'revision'}
        call('scene_apply', {**request, 'expected_revision': 3})
        replay = call('scene_inspect', {})
        assert {k: v for k, v in replay['scene'].items() if k != 'revision'} == {k: v for k, v in after.items() if k != 'revision'}
        assert call('scene_inspect', {'entity': 'child', 'world': True})['object_frames']['matrix_local_error'] == 'cannot_invert'
        process.stdin.close()
        process.wait(timeout=10)
        stderr = process.stderr.read()
        assert process.returncode == 0, stderr
        fresh = subprocess.run([*prefix, str(binary), 'scene', 'inspect', '--scene', str(path)], cwd=folder, capture_output=True, text=True, check=True)
        assert json.loads(fresh.stdout) == replay
        report = {'passed': True, 'binary_sha256': sha(binary), 'driver_sha256': sha(Path(__file__)),
                  'policy': policy, 'denial_control_exit_code': control.returncode, 'denial_control_stderr': control.stderr,
                  'native_terminal_exit': process.returncode, 'fresh_process_exit': fresh.returncode,
                  'native_calls': len(calls), 'world_numeric_limit': 1e-6, 'setup': setup,
                  'unavailable_query_preserved_operation': True, 'undo_replay_checked': True,
                  'stale_budget_and_late_batch_atomic': True, 'fresh_reload_equal': True,
                  'product_acceptance': 'unrun'}
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'passed': True, 'native_calls': len(calls), 'repository_reads': 'denied'}))


if __name__ == '__main__':
    main()
