#!/usr/bin/env python3
"""Isolate each generated shape, change its parameters and reload on a native GPU."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from png_pixels import read_rgba8


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    records, calls = [], []

    def run(*arguments, request=None):
        result = subprocess.run([str(binary), *map(str, arguments)], capture_output=True,
                                text=True, check=True,
                                input=None if request is None else json.dumps(request))
        calls.append({'arguments': list(map(str, arguments)), 'exit_code': result.returncode,
                      'stdout': result.stdout})
        return json.loads(result.stdout)

    identity = {'translation': [0, 0, 0], 'rotation': [0, 0, 0, 1], 'scale': [1, 1, 1]}
    for kind, before, after in [
        ('uv_sphere', {'radius': 0.65}, {'radius': 1.15}),
        ('cylinder', {'radius': 0.65, 'depth': 1.3}, {'radius': 1.15, 'depth': 1.3}),
        ('cone', {'radius1': 0.65, 'depth': 1.3}, {'radius1': 1.15, 'depth': 1.3}),
        ('torus', {'major_radius': 0.55, 'minor_radius': 0.2},
         {'major_radius': 0.55, 'minor_radius': 0.35}),
    ]:
        directory = output / kind
        directory.mkdir()
        scene = directory / 'scene.json'
        run('scene', 'init', '--scene', scene)
        creation = {'expected_revision': 0, 'commands': [
            {'operation': 'create_mesh_primitive', 'id': 'shape',
             'primitive': {'kind': kind, **before}},
            {'operation': 'set_material', 'id': 'surface',
             'material': {'base_color': [0.2, 0.7, 0.9, 1], 'roughness': 0.6, 'metallic': 0}},
            {'operation': 'create_entity', 'id': 'shape', 'entity': {
                'name': kind, 'parent': None, 'transform': identity,
                'content': {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': 'shape'},
                            'material': 'surface'}}},
            {'operation': 'create_entity', 'id': 'camera', 'entity': {
                'name': 'Camera', 'parent': None,
                'transform': {**identity, 'translation': [0, 0, 5]},
                'content': {'kind': 'camera', 'vertical_fov_degrees': 45,
                            'near': 0.1, 'far': 100}}},
            {'operation': 'set_active_camera', 'id': 'camera'},
            {'operation': 'create_entity', 'id': 'light', 'entity': {
                'name': 'Light', 'parent': None,
                'transform': {**identity, 'translation': [1, -2, 5]},
                'content': {'kind': 'light', 'color': [1, 1, 1], 'intensity': 100}}},
        ]}
        rebuild = {'expected_revision': 1, 'commands': [
            {'operation': 'regenerate_mesh_primitive', 'id': 'shape',
             'primitive': {'kind': kind, **after}},
        ]}
        for name, value in [('creation-request.json', creation), ('regenerate-request.json', rebuild)]:
            (directory / name).write_text(json.dumps(value, indent=2) + '\n')
        run('scene', 'apply', '--scene', scene, '--request', '-', request=creation)
        gpu = run('render', '--scene', scene, '--output', directory / 'before.png',
                  '--width', 640, '--height', 480)['gpu']
        run('scene', 'apply', '--scene', scene, '--request', '-', request=rebuild)
        for name in ['after', 'reopened']:
            run('render', '--scene', scene, '--output', directory / (name + '.png'),
                '--width', 640, '--height', 480)
        width, height, initial_pixel = read_rgba8(directory / 'before.png')
        _, _, changed_pixel = read_rgba8(directory / 'after.png')
        background = initial_pixel(0, 0)
        initial_count, changed_count, different = 0, 0, 0
        for y in range(height):
            for x in range(width):
                a, b = initial_pixel(x, y), changed_pixel(x, y)
                initial_count += a != background
                changed_count += b != background
                different += a != b
        # Each scene contains only this shape, a camera and a light.
        assert initial_count > 1000, (kind, 'shape not visible')
        assert different > 500, (kind, 'parameter change not visible')
        assert changed_count > initial_count + 200, (kind, 'expected radius growth absent')
        assert (directory / 'after.png').read_bytes() == (directory / 'reopened.png').read_bytes()
        query = run('scene', 'inspect', '--scene', scene)
        assert query['scene']['mesh_assets']['shape']['recipe']['primitive']['kind'] == kind
        assert query['scene']['entities']['shape']['content']['geometry']['id'] == 'shape'
        records.append({'kind': kind, 'gpu': gpu, 'initial_visible_pixels': initial_count,
                        'changed_visible_pixels': changed_count, 'different_pixels': different,
                        'reopened_png_identical': True, 'asset_identity_preserved': True})
    artifacts = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(output.rglob('*'))
                 if p.is_file() and not p.name.endswith('.formora.lock')}
    report = {'passed': True, 'scope': 'Four isolated native GPU generation and regeneration samples',
              'full_feature_acceptance': 'unrun', 'platform': platform.platform(), 'runs': records,
              'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'source_files_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted([root / 'Cargo.toml', root / 'Cargo.lock',
                                                       *[p for p in (root / 'src').rglob('*') if p.is_file()]])},
              'capture_inputs_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                       for name in ['tools/rotational_gpu_evidence.py', 'tools/png_pixels.py',
                                                    'docs/contracts/rotational-primitives.md']},
              'artifacts': artifacts, 'commands': calls,
              'unrun': ['native window input', 'Windows GPU', 'Linux GPU',
                        'full numeric domains', 'full modeling parity']}
    (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'isolated_native_shapes': len(records), 'runs': records}))


if __name__ == '__main__':
    main()
