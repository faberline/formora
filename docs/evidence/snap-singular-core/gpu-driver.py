"""Render a valid zero-scale world before, after and after fresh reload."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from png_pixels import read_rgba8


def pose(t, r=None, s=None, order='xyz', delta=None):
    return {'translation': t, 'rotation': {'kind': 'euler', 'angles': r or [0.] * 3, 'order': order},
            'scale': s or [1.] * 3, 'precision': 'f32', 'delta': {'translation': delta or [0.] * 3,
            'euler': [0.] * 3, 'quaternion_wxyz': [1., 0., 0., 0.], 'scale': [1.] * 3}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    binary_sha = sha(binary)
    sources = [ROOT / 'Cargo.toml', ROOT / 'Cargo.lock', *sorted((ROOT / 'src').rglob('*.rs'))]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    scene = out / 'scene.json'
    calls = []

    def call(*arguments, request=None):
        command = [str(binary), *map(str, arguments)]
        p = subprocess.run(command, input=None if request is None else json.dumps(request), capture_output=True, text=True)
        row = {'command': command, 'request': request, 'stdout': p.stdout, 'stderr': p.stderr, 'terminal_exit_code': p.returncode}
        calls.append(row)
        with (out / 'calls.jsonl').open('a') as stream:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
        assert p.returncode == 0, row
        return json.loads(p.stdout)

    def entity(id, parent, transform, content):
        return {'operation': 'create_entity', 'id': id, 'entity': {'name': id, 'parent': parent,
                'transform': transform, 'content': content}}

    asset = {'vertices': {'a': [-3.5, -2.5, 0.], 'b': [3.5, -2.5, 0.], 'c': [0., 2.5, .125]},
             'triangles': {'tri': {'vertices': ['a', 'b', 'c'], 'material_slot': None, 'uv_layers': {}, 'corner_normals': None}},
             'material_slots': []}
    target = pose([.625, -.875, .375], s=[.9, 1.4, .8], order='yxz', delta=[.125, -.25, .375])
    camera = pose([6., -12., 5.])
    camera.update(rotation=[math.sin(math.pi / 8), 0., 0., math.cos(math.pi / 8)], precision='f64')
    setup = {'expected_revision': 0, 'commands': [
        {'operation': 'set_mesh_asset', 'id': 'unseen', 'asset': asset},
        {'operation': 'set_material', 'id': 'orange', 'material': {'base_color': [.9, .2, .08, 1.], 'roughness': .6, 'metallic': 0.}},
        entity('parent', None, pose([6.5, -7.25, .875], [.37, -.23, .51], [-1.2, .7, 0.], delta=[.125, -.25, .375]), {'kind': 'empty'}),
        entity('target', 'parent', target, {'kind': 'empty'}),
        entity('child', 'target', pose([.25, -.75, .5], delta=[-.25, .125, .0625]),
               {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': 'unseen'}, 'material': 'orange'}),
        entity('camera', None, camera, {'kind': 'camera', 'vertical_fov_degrees': 65., 'near': .1, 'far': 100.}),
        entity('light', None, pose([6., -10., 5.]), {'kind': 'light', 'color': [1., 1., 1.], 'intensity': 2.}),
        {'operation': 'set_active_camera', 'id': 'camera'},
        {'operation': 'set_object_context', 'context': {'order': ['parent', 'target', 'child', 'camera', 'light'],
                                                    'selected': ['target'], 'active': 'target'}}]}
    (out / 'authored-setup.json').write_text(json.dumps(setup, indent=2) + '\n')
    call('scene', 'init', '--scene', scene)
    call('scene', 'apply', '--scene', scene, '--request', '-', request=setup)
    before = call('scene', 'inspect', '--scene', scene)
    query_before = call('scene', 'inspect', '--scene', scene, '--entity', 'child', '--world')
    assert query_before['object_frames']['matrix_local'] == [[0.] * 4 for _ in range(4)]
    (out / 'before-scene.json').write_bytes(scene.read_bytes())
    gpu = call('render', '--scene', scene, '--output', out / 'before.png', '--width', 640, '--height', 480)['gpu']
    assert '(Metal,' in gpu, gpu
    edited = copy.deepcopy(target)
    edited['rotation']['angles'] = [math.pi / 2., -0., -0.]
    receipt = call('scene', 'apply', '--scene', scene, '--request', '-', request={
        'expected_revision': 1, 'commands': [{'operation': 'set_transform', 'id': 'target', 'transform': edited}]})
    assert receipt['revision'] == 2
    saved = scene.read_bytes()
    after = call('scene', 'inspect', '--scene', scene)
    query_after = call('scene', 'inspect', '--scene', scene, '--entity', 'child', '--world')
    assert query_after['object_frames']['matrix_local'] is None
    assert query_after['object_frames']['matrix_local_error'] == 'cannot_invert'
    assert before['scene']['mesh_assets'] == after['scene']['mesh_assets']
    assert len(query_after['world_vertices']) == 3
    assert all(math.isfinite(v) for point in query_after['world_vertices'].values() for v in point)
    for name in ['after', 'reloaded']:
        rendered = call('render', '--scene', scene, '--output', out / (name + '.png'), '--width', 640, '--height', 480)
        assert rendered['gpu'] == gpu
    assert scene.read_bytes() == saved
    assert (out / 'after.png').read_bytes() == (out / 'reloaded.png').read_bytes()
    w, h, a = read_rgba8(out / 'before.png')
    wb, hb, b = read_rgba8(out / 'after.png')
    assert (w, h) == (wb, hb) == (640, 480)
    changed = sum(a(x, y) != b(x, y) for y in range(h) for x in range(w))
    assert changed > 100, changed
    for name, value in [('world-before', query_before), ('world-after', query_after), ('receipt', receipt)]:
        (out / (name + '.json')).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    assert binary_sha == sha(binary) and hashes == {str(p.relative_to(ROOT)): sha(p) for p in sources}
    report = {'passed': True, 'gpu': gpu, 'binary_sha256': binary_sha, 'driver_sha256': sha(Path(__file__)),
              'source_hashes': hashes, 'changed_pixels': changed, 'fresh_reload_images_identical': True,
              'unavailable_local_does_not_block_render_or_world_queries': True,
              'scene_unchanged_by_queries_and_render': True, 'product_acceptance': 'unrun'}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'gpu', 'changed_pixels', 'fresh_reload_images_identical']}))


if __name__ == '__main__':
    main()
