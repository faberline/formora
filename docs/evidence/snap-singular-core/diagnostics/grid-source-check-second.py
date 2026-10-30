#!/usr/bin/env python3
"""Bind every native grid form to authored inputs and source equations."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from compare_snap_singular_policy_reference import numeric_matrix, validate_run
from singular_snap_runtime import compare_local


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh_input(asset):
    vertices, edges, faces = [sorted(asset[key]) for key in ['vertices', 'edges', 'polygons']]
    index = {name: i for i, name in enumerate(vertices)}
    assert (len(vertices), len(edges), len(faces)) == (10201, 20200, 10000)
    return {'vertices': [asset['vertices'][id] for id in vertices],
        'edges': [[index[v] for v in asset['edges'][id]] for id in edges],
        'faces': [[index[v] for v in asset['polygons'][id]['vertices']] for id in faces],
        'face_smooth': [False] * 10000, 'face_materials': [0] * 10000,
        'edge_seams': [id in asset.get('edge_seams', []) for id in edges],
        'material_slots': [], 'uv_layers': [], 'active_uv_index': 0, 'active_material_index': 0,
        'hidden': {'vertices': [], 'edges': [], 'faces': []},
        'group_scenarios': {'authored': {'names': [], 'weights': {}}}}


def check(folder):
    config = json.loads((HERE / 'authored-forms.json').read_bytes())
    terminal = json.loads((folder / 'terminal.json').read_bytes())
    manifest_path = folder / 'capture/manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    assert terminal['terminal_exit_code'] == 0 and terminal['process_id'] == manifest['process_id']
    assert terminal['manifest_sha256'] == sha(manifest_path)
    for name in ['stdout', 'stderr']:
        assert terminal[name + '_sha256'] == sha(folder / name)
    assert manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880'
    assert manifest['background'] is False
    assert manifest['binary_sha256'] == 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'
    for path, digest in manifest['input_hashes'].items():
        assert sha(Path(path)) == digest
    assert len(manifest['runs']) == 20
    seen = set()
    unavailable = []
    for row in manifest['runs']:
        key = row['frame'], row['form']
        assert key not in seen
        seen.add(key)
        frame = next(f for f in config['frames'] if f['id'] == row['frame'])
        form = next(f for f in config['forms'] if f['id'] == row['form'])
        scene = json.loads((HERE / frame['scene']).read_bytes())
        assert sha(HERE / frame['scene']) == frame['sha256']
        suite = json.loads((ROOT / 'baseline/fixtures/snap-singular.json').read_bytes())
        suite['mesh'] = mesh_input(scene['mesh_assets']['grid'])
        path = folder / 'capture' / row['file']
        assert sha(path) == row['sha256']
        raw = gzip.decompress(path.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes']
        value = json.loads(raw)
        run = copy.deepcopy(frame['authored_case'])
        run.update(id=frame['id'] + '-' + form['id'], operator=form['operator'], parameters=form['parameters'])
        run['seed']['indices'] = list(range(10201))
        assert value['run'] == run and value['frame'] == frame['id'] and value['form'] == form['id']
        assert value['result'] == row['result'] == {'status': ['FINISHED'], 'error': None}
        physical = {k: copy.deepcopy(value[k]) for k in ['run', 'before', 'after', 'result']}
        tags = []
        for side in ['before', 'after']:
            for name, obj in physical[side]['objects'].items():
                local = obj.pop('matrix_local')
                if numeric_matrix(local):
                    continue
                assert side == 'after' and name == 'child' and frame['id'] == 'parent-zero'
                assert form['operator'] == 'snap_selected_to_cursor' and form['parameters']['use_rotation']
                compare_local(local, None, 'cannot_invert')
                for i, line in enumerate(local):
                    for j, entry in enumerate(line):
                        tag = entry['__source_nonfinite_diagnostic__']
                        assert tag['path'] == f'/{side}/objects/{name}/matrix_local/{i}/{j}'
                        tags.append(tag)
                unavailable.append({'frame': frame['id'], 'form': form['id'], 'side': side, 'entity': name})
        assert tags == row['nonfinite_fields']
        validate_run(suite, run, physical)
        print(json.dumps({'validated': len(seen), 'frame': frame['id'], 'form': form['id']}), flush=True)
    assert seen == {(f['id'], x['id']) for f in config['frames'] for x in config['forms']}
    return {'passed': True, 'forms': len(seen), 'source_process_id': manifest['process_id'],
            'manifest_sha256': sha(manifest_path), 'terminal_sha256': sha(folder / 'terminal.json'),
            'checker_sha256': sha(Path(__file__)), 'unavailable_local_queries': unavailable,
            'numeric_limit': 1e-6, 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = check(args.source)
    with args.output.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
