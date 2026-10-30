#!/usr/bin/env python3
"""Author fixed merge performance inputs without captured source answers."""
import copy
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'docs/evidence/snap-delta-core/performance/authored-grid.json'
BASE_SHA = '8f29def12ade5467214e888fdcacec23b3d78ed4954e470207a00479ac149536'


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    with path.open('xb') as output:
        output.write(raw)
    return hashlib.sha256(raw).hexdigest()


def author():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA
    scene = json.loads(BASE.read_text())
    original = copy.deepcopy(scene['mesh_assets']['grid'])
    asset = scene['mesh_assets']['grid']
    assert (len(asset['vertices']), len(asset['edges']), len(asset['polygons'])) == (10201, 20200, 10000)
    asset['uv_layout'] = {'layers': ['Detail', 'Layout'], 'active': 'Layout'}
    for face in asset['polygons'].values():
        face['uv_layers'] = {name: [[f32(sign * asset['vertices'][id][0] / 100.),
                                   f32(asset['vertices'][id][1] / 100.)] for id in face['vertices']]
                             for name, sign in [('Detail', 1.), ('Layout', -1.)]}
    asset['vertex_groups'] = ['pin', 'soft']
    asset['vertex_weights'] = {id: {'pin': 0. if i % 2 == 0 else 1.,
                                     'soft': .25 if i % 3 == 0 else .75}
                               for i, id in enumerate(sorted(asset['vertices']))}
    asset['integer_attributes'] = {
        'vertices': {'formora_v_id': {id: i for i, id in enumerate(sorted(asset['vertices']))},
                     'signed_label': {id: (i % 17 - 8) * 3 for i, id in enumerate(sorted(asset['vertices']))}},
        'edges': {'formora_e_id': {id: i for i, id in enumerate(sorted(asset['edges']))},
                  'signed_edge': {id: i % 11 - 5 for i, id in enumerate(sorted(asset['edges']))}},
        'polygons': {'formora_f_id': {id: i for i, id in enumerate(sorted(asset['polygons']))},
                     'signed_face': {id: -i for i, id in enumerate(sorted(asset['polygons']))}},
        'triangles': {}}
    scene['entities']['target']['transform']['translation'] = [0., 0., 0.]
    scene['entities']['secondary'] = copy.deepcopy(scene['entities']['target'])
    scene['entities']['secondary']['name'] = 'Shared grid'
    scene['entities']['secondary']['transform']['translation'] = [-1.25, 2.375, -.75]
    scene['object_context'].update(order=['target', 'secondary', 'child'],
                                   selected=['target', 'secondary'], active='target',
                                   edit_objects=['target'], skip_children=False, origins_only=False)
    assert asset['vertices'] == original['vertices'] and asset['edges'] == original['edges']
    assert {k: v['vertices'] for k, v in asset['polygons'].items()} == {
        k: v['vertices'] for k, v in original['polygons'].items()}
    assert asset['editing'] == original['editing']
    forms = [{'id': method.lower() + ('-uv' if uvs else '-no-uv'),
              'method': method, 'uvs': uvs} for method in
             ['CENTER', 'CURSOR', 'COLLAPSE', 'FIRST', 'LAST'] for uvs in [False, True]]
    return scene, forms


if __name__ == '__main__':
    scene, forms = author()
    sha = write(HERE / 'authored-grid.json', scene)
    write(HERE / 'authored-forms.json', {'schema_version': 1, 'base_grid_path': str(BASE.relative_to(ROOT)),
        'base_grid_sha256': BASE_SHA, 'grid_sha256': sha, 'forms': forms,
        'samples_per_form': 3, 'total_samples': 30, 'maximum_core_ms': 250,
        'maximum_pipeline_ms': 2000, 'max_components': 1000000,
        'position_channel_matrix_limit': 1e-6, 'product_acceptance': 'unrun'})
    print(json.dumps({'forms': len(forms), 'samples': 30, 'authored_grid_sha256': sha}))
