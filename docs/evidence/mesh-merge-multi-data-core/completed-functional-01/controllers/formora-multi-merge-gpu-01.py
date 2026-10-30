"""Render two actual edit meshes and one linked user before/after merge."""
from pathlib import Path
import copy
import hashlib
import json
import platform
import subprocess
import sys

ROOT = Path('/private/tmp/formora-mesh-merge-multi-data-core')
sys.path.insert(0, str(ROOT/'tools'))
from png_pixels import read_rgba8

OUT = Path('/private/tmp/formora-multi-merge-gpu-01')
OUT.mkdir(exist_ok=False)
BINARY = Path('/private/tmp/formora-object-state-build-02/formora-preview')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
binary_sha = sha(BINARY)
assert binary_sha == '518d5cb60791ccbd40c972e875807d836120aceadb4183c95e0647147bc00b65'
scene = OUT/'scene.json'
calls = []
report = {'passed': False, 'binary_sha256': binary_sha, 'driver_sha256': sha(__file__),
          'platform': platform.platform(), 'product_acceptance': 'unrun', 'independent_acceptance': 'unrun'}


def write(name, value):
    with (OUT/name).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def cli(action, arguments=(), request=None):
    command = [str(BINARY), *action, '--scene', str(scene), *map(str, arguments)]
    if request is not None:
        command += ['--request', '-']
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    stdout, stderr = child.communicate(None if request is None else json.dumps(request, allow_nan=False), timeout=60)
    calls.append({'command': command, 'request': request, 'process_id': child.pid,
                  'terminal_exit_code': child.returncode, 'stdout': stdout, 'stderr': stderr})
    assert child.returncode == 0, calls[-1]
    return json.loads(stdout)


def entity(name, content, translation, scale=(1., 1., 1.)):
    return {'operation': 'create_entity', 'id': name, 'entity': {'name': name, 'parent': None,
        'transform': {'translation': translation, 'rotation': [0., 0., 0., 1.], 'scale': list(scale), 'precision': 'f32'},
        'content': content}}


def asset(points, uv, color, edit):
    names = list('abcde')[:len(points)]
    pairs = [(names[i], names[(i+1) % len(names)]) for i in range(len(names))]
    value = {'vertices': dict(zip(names, points)), 'edges': {a+b: [a, b] for a, b in pairs}, 'triangles': {},
        'polygons': {'surface': {'vertices': names, 'uv_layers': {'Layout': uv,
            'Detail': [[.2+u*.5, -.3+v*.75] for u, v in uv]}, 'normal': None,
            'corner_normals': None, 'smooth': False, 'material_slot': 0}},
        'uv_layout': {'layers': ['Detail', 'Layout'], 'active': 'Layout'}, 'material_slots': [color]}
    if edit:
        value['editing'] = {'mode': ['vertex'], 'selected': {'vertices': ['a', 'b'], 'edges': ['ab'], 'faces': []},
            'hidden': {}, 'history': [{'domain': 'vertex', 'id': 'b'}, {'domain': 'vertex', 'id': 'a'}], 'active_face': None}
    return value


assets = {
    'mesh_a': asset([[-1., -1., 0.], [1., -1., 0.], [1., 1., 0.], [-1., 1., 0.]],
                    [[0., 0.], [1., 0.], [1., 1.], [0., 1.]], 'orange', True),
    'mesh_b': asset([[-1., -.75, 0.], [.75, -1., 0.], [1.25, .25, 0.], [.25, 1.25, 0.], [-1.25, .5, 0.]],
                    [[0., 0.], [1., 0.], [1., .7], [.5, 1.], [0., .75]], 'blue', True),
    'outside': asset([[-.4, -.3, 0.], [.4, -.3, 0.], [0., .4, 0.]],
                     [[0., 0.], [1., 0.], [.5, 1.]], 'green', False)}
materials = {'orange': {'base_color': [.95, .25, .08, 1.], 'roughness': .55, 'metallic': 0.},
             'blue': {'base_color': [.08, .4, .95, 1.], 'roughness': .65, 'metallic': 0.},
             'green': {'base_color': [.2, .8, .3, 1.], 'roughness': .5, 'metallic': 0.}}
commands = [{'operation': 'set_material', 'id': name, 'material': value} for name, value in materials.items()]
commands += [{'operation': 'set_mesh_asset', 'id': name, 'asset': value} for name, value in assets.items()]
for name, data, position, scale in [('a', 'mesh_a', [-3., 0., 0.], [1., 1., 1.]),
        ('alias', 'mesh_a', [3., 0., 0.], [-.8, 1.1, 1.]),
        ('b', 'mesh_b', [0., 1.5, 0.], [1., 1., 1.]), ('outside', 'outside', [0., -3.5, 0.], [1., 1., 1.])]:
    commands.append(entity(name, {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': data}, 'material': None}, position, scale))
commands += [entity('camera', {'kind': 'camera', 'vertical_fov_degrees': 45., 'near': .1, 'far': 100.}, [0., 0., 14.]),
    {'operation': 'set_active_camera', 'id': 'camera'},
    entity('light', {'kind': 'light', 'color': [1., 1., 1.], 'intensity': 3.}, [0., -2., 8.]),
    {'operation': 'set_object_context', 'context': {'order': ['outside', 'a', 'b', 'alias', 'camera', 'light'],
        'selected': ['a', 'alias', 'b'], 'active': 'alias', 'edit_objects': ['alias', 'b'],
        'states': {'a': {'lock_scale': [True, False, True]}, 'alias': {'lock_scale': [False, True, False]}}}}]
setup = {'expected_revision': 0, 'commands': commands}
operation = {'expected_revision': 1, 'commands': [{'operation': 'merge_edit_meshes',
    'merge': {'method': 'center', 'uvs': True, 'max_components': 1000}}]}
write('authored-setup.json', setup)
write('authored-operation.json', operation)
captures = {}
gpus = []
try:
    cli(['scene', 'init'])
    assert cli(['scene', 'apply'], request=setup)['revision'] == 1

    def capture(name):
        current = cli(['scene', 'inspect'])
        queries = {data: cli(['scene', 'inspect'], ['--mesh-asset', data, '--normals']) for data in assets}
        states = {name: cli(['scene', 'inspect'], ['--entity', name, '--object-state']) for name in ['a', 'alias', 'b']}
        raw = scene.read_bytes()
        with (OUT/(name+'-scene.json')).open('xb') as f:
            f.write(raw)
        rendered = cli(['render'], ['--output', OUT/(name+'.png'), '--width', 640, '--height', 480])
        assert '(Metal,' in rendered['gpu'], rendered
        assert scene.read_bytes() == raw, 'render changed the saved scene'
        gpus.append(rendered['gpu'])
        captures[name] = {'scene': current['scene'], 'queries': queries, 'states': states, 'render': rendered}

    capture('before')
    applied = cli(['scene', 'apply'], request=operation)
    assert applied['revision'] == 2 and len(applied['edit_merges']) == 1
    receipt = applied['edit_merges'][0]
    assert receipt['provider_order'] == ['alias', 'b'] and receipt['status'] == 'finished'
    assert [p['shared_instances'] for p in receipt['providers']] == [['a', 'alias'], ['b']]
    capture('after')
    capture('reloaded')
    before, after = [captures[p]['scene'] for p in ['before', 'after']]
    assert after == captures['reloaded']['scene']
    assert captures['after']['queries'] == captures['reloaded']['queries']
    assert captures['after']['states'] == captures['reloaded']['states']
    assert (OUT/'after.png').read_bytes() == (OUT/'reloaded.png').read_bytes()
    for key in set(before)-{'revision', 'mesh_assets'}:
        assert before[key] == after[key], key
    assert before['mesh_assets']['outside'] == after['mesh_assets']['outside']
    for data, count, ids, point in [('mesh_a', 3, ['a', 'c', 'd'], [0., -1., 0.]),
                                  ('mesh_b', 4, ['a', 'c', 'd', 'e'], [-.125, -.875, 0.])]:
        mesh = after['mesh_assets'][data]
        assert len(mesh['vertices']) == count and mesh['vertices']['a'] == point
        assert mesh['polygons']['surface']['vertices'] == ids
        assert mesh['uv_layout'] == before['mesh_assets'][data]['uv_layout']
        assert mesh['material_slots'] == before['mesh_assets'][data]['material_slots']
        for layer in ['Detail', 'Layout']:
            old = before['mesh_assets'][data]['polygons']['surface']['uv_layers'][layer]
            wanted = [[(old[0][axis]+old[1][axis])*.5 for axis in range(2)], *old[2:]]
            actual = mesh['polygons']['surface']['uv_layers'][layer]
            assert len(wanted) == len(actual)
            assert all(abs(x-y) <= 1e-6 for a, b in zip(wanted, actual) for x, y in zip(a, b)), (data, layer, wanted, actual)
    w, h, old = read_rgba8(OUT/'before.png')
    w2, h2, new = read_rgba8(OUT/'after.png')
    assert (w, h) == (w2, h2) == (640, 480)
    changed = sum(old(x, y) != new(x, y) for y in range(h) for x in range(w))
    assert changed > 500, changed
    assert sha(BINARY) == binary_sha
    write('captures.json', captures)
    write('receipt.json', applied)
    report.update(passed=True, changed_pixels=changed, fixed_changed_pixel_minimum=500,
        gpu=gpus, actual_two_meshes_and_linked_user=True, both_uv_layers_checked=True,
        outside_mesh_unchanged=True, actual_provider_order_checked=True,
        fresh_scene_queries_and_render_equal=True)
except BaseException as error:
    report.update(error=str(error))
    raise
finally:
    write('calls.json', calls)
    write('report.json', report)
print(json.dumps({key: report[key] for key in ['passed', 'changed_pixels', 'gpu', 'fresh_scene_queries_and_render_equal']}))
