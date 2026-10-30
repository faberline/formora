"""Load exact authored capacity assets and construct literal source scenes."""
import copy
import gzip
import hashlib
import json
from pathlib import Path

from merge_distance_scene_inputs import scene


def load_assets(suite_path, suite):
    identity = suite['capacity_assets']; path = suite_path.parent/identity['file']
    stored = path.read_bytes(); raw = gzip.decompress(stored)
    assert hashlib.sha256(stored).hexdigest() == identity['stored_sha256'], 'capacity stored asset identity'
    assert hashlib.sha256(raw).hexdigest() == identity['raw_sha256'] and len(raw) == identity['raw_bytes'], 'capacity raw asset identity'
    result = json.loads(raw)
    assert set(result) == {'mesh_a', 'mesh_b'}, 'capacity data identities'
    for mesh in result.values():
        assert [len(mesh[key]) for key in ['vertices', 'edges', 'polygons']] == [10201, 20200, 10000], 'capacity class A size'
    return result


def authored_scene(suite, run, grids):
    spec = scene(suite['scene_template'], run)
    names = ['mesh_a', 'mesh_b'] if run['factors']['context'] == 'multi_a_first' else ['mesh_a']
    for name in names:
        mesh = copy.deepcopy(grids[name]); mesh['normal_preset'] = run['normal_profile']
        if run['normal_profile'] == 'custom_constant':
            vector = suite['normal_requests']['custom_constant']
            mesh['custom_corner_normals'] = {face: [vector.copy() for _ in polygon['vertices']]
                                             for face, polygon in mesh['polygons'].items()}
        spec['mesh_assets'][name] = mesh
    return spec
