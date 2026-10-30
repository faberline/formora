#!/usr/bin/env python3
"""Verify all sixty saved results, query availability, receipts and clocks."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools'))
from singular_snap_runtime import snapshot, compare_state
from rotation_snap_runtime import check_result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())


def mesh_snapshot(query, scene, world, name):
    asset = query['mesh_asset']
    assert asset == scene['mesh_assets']['grid']
    assert not asset.get('uv_layout') and not asset['material_slots']
    assert not asset.get('vertex_groups') and not asset.get('vertex_weights') and not asset['triangles']
    assert world['id'] == name and world['entity'] == scene['entities'][name]
    assert not scene['object_context']['edit_objects']
    editing = asset['editing']

    def elements(value):
        assert all(f['kind'] == 'polygon' for f in value['faces'])
        return {'VERT': value['vertices'], 'EDGE': value['edges'], 'FACE': [f['id'] for f in value['faces']]}

    normals = {'faces': {}, 'corners': {}}
    for face in query['normals']['faces']:
        assert face['face']['kind'] == 'polygon'
        id = face['face']['id']
        normals['faces'][id] = face['normal']
        normals['corners'][id] = face['corner_normals']
    assert all(not p['uv_layers'] and p['material_slot'] is None for p in asset['polygons'].values())
    return {'geometry': {'vertices': asset['vertices'], 'edges': {id: sorted(v) for id, v in asset['edges'].items()},
            'faces': {id: p['vertices'] for id, p in asset['polygons'].items()},
            'face_smooth': {id: p['smooth'] for id, p in asset['polygons'].items()},
            'face_materials': {id: 0 for id in asset['polygons']},
            'edge_seams': {id: id in asset.get('edge_seams', []) for id in asset['edges']},
            'material_slots': [], 'uv_layers': {}, 'uv_layer_order': [], 'active_uv_index': -1},
            'groups': {'names': [], 'weights': {id: {} for id in asset['vertices']}},
            'selected': elements(editing['selected']), 'hidden': elements(editing['hidden']),
            'mode': [], 'history': [], 'active_face': None, 'active_material_index': 0,
            'data_edit_mode': False, 'normals': normals, 'world_vertices': world['world_vertices']}


def compare(binary, samples, source_folder, controller_path):
    config = load(HERE / 'authored-forms.json')
    controller = load(controller_path)
    binary_sha = sha(binary)
    assert controller['passed'] and controller['terminal_exit_code'] == 0
    assert controller['binary_sha256'] == binary_sha and controller['verification_inputs_unchanged']
    for path, digest in controller['input_hashes'].items():
        assert sha(Path(path)) == digest
    spec = importlib.util.spec_from_file_location('source_check', HERE / 'check-source.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    source_checked = checker.check(source_folder)
    source = load(source_folder / 'capture/manifest.json')
    references = {(r['frame'], r['form']): load(source_folder / 'capture' / r['file']) for r in source['runs']}
    timing = load(samples / 'timing-summary.json')
    assert timing['passed'] and timing['samples'] == 60 and len(timing['runs']) == 60
    assert sha(samples / 'timing-summary.json') == controller['timing_summary_sha256']
    cache = {}

    def inspect(path):
        def query(*flags):
            p = subprocess.run([str(binary), 'scene', 'inspect', '--scene', str(path), *flags], capture_output=True, text=True)
            assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
            return json.loads(p.stdout)
        inspection = query()
        scene = inspection['scene']
        assert scene == load(path)
        worlds = {name: query('--entity', name, '--world') for name in scene['entities']}
        meshes = {name: query('--mesh-asset', name, '--normals') for name in scene['mesh_assets']}
        return snapshot(inspection, meshes, worlds, mesh_snapshot_fn=mesh_snapshot), scene, worlds

    for frame in config['frames']:
        path = HERE / frame['scene']
        assert sha(path) == frame['sha256']
        cache[frame['id']] = inspect(path)
    records = []
    seen = set()
    for row in timing['runs']:
        key = row['frame'], row['form'], row['sample']
        assert key not in seen and key[2] in [1, 2, 3]
        seen.add(key)
        ref = references[key[:2]]
        before, old, worlds_before = cache[row['frame']]
        stem = '-'.join([row['frame'], row['form'], str(row['sample'])])
        assert row['file'] == stem + '.json'
        path = samples / row['file']
        after, new, worlds_after = inspect(path)
        raw = load(samples / (stem + '-queries-receipt.json'))
        assert raw['before'] == worlds_before and raw['after'] == worlds_after
        assert old['revision'] == 0 and new['revision'] == raw['receipt']['revision'] == 1
        compare_state(ref['before'], before)
        compare_state(ref['after'], after)
        form = next(f for f in config['forms'] if f['id'] == row['form'])
        request = {'expected_revision': 0, 'commands': [form['command']]}
        check_result(request, before, after, raw['receipt'], None, old, new)
        assert old['mesh_assets'] == new['mesh_assets'], 'normal object snapping changed the shared grid asset'
        for name in old['entities']:
            assert old['entities'][name]['transform']['delta'] == new['entities'][name]['transform']['delta']
        for field in ['materials', 'doors', 'annotations', 'active_camera', 'time_seconds']:
            assert old[field] == new[field]
        assert row['maximum_core_ms'] == 250. and row['maximum_pipeline_ms'] == 2000.
        for value, start, end, limit in [('core_ms', 'core_start_ns', 'core_end_ns', 250.),
                ('operation_save_reload_ms', 'pipeline_start_ns', 'pipeline_end_ns', 2000.)]:
            assert math.isfinite(row[value]) and 0. <= row[value] <= limit
            assert row[end] >= row[start] and abs(row[value] - (row[end] - row[start]) / 1e6) < 1e-9
        assert row['passed']
        records.append({'frame': key[0], 'form': key[1], 'sample': key[2], 'passed': True,
                        'saved_scene_sha256': sha(path), 'query_receipt_sha256': sha(samples / (stem + '-queries-receipt.json')),
                        'core_ms': row['core_ms'], 'pipeline_ms': row['operation_save_reload_ms']})
        print(json.dumps({'compared': len(records), 'frame': key[0], 'form': key[1], 'sample': key[2]}), flush=True)
    assert seen == {(f['id'], x['id'], i) for f in config['frames'] for x in config['forms'] for i in [1, 2, 3]}
    assert sha(binary) == binary_sha
    return {'passed': True, 'required_new_performance_gate_passed': True, 'samples': 60, 'runs': records,
            'binary_sha256': binary_sha, 'controller_sha256': sha(controller_path), 'source_checked': source_checked,
            'numeric_limit': 1e-6, 'prior_177_performance_gate': 'unrun', 'product_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['binary', 'samples', 'source', 'controller', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.binary, args.samples, args.source, args.controller)
    with args.output.open('x') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
