#!/usr/bin/env python3
"""Bind and compare complete native vertex-merge captures."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

from compare_selection_reference import require, validate_state, DOMAINS, TABLES
from compare_snap_menu_reference import f32, floats, tree, selection_input, bind_initial, matrix, SELECTION
from compare_snap_delta_reference import world_point
from compare_transform_reference import finite
from generate_mesh_merge_cases import author

ROOT = Path(__file__).resolve().parents[1]
BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_state_full(state,run):
    require(set(state)=={'active_object','cursor','cursor_metres','meshes','mode','objects','physical_metres_factor','settings','sharing'},'state fields differ')
    finite(state);factor=1. if run['context']['unit_system']=='NONE' else run['context']['unit_scale_length']
    require(state['physical_metres_factor']==factor,'physical conversion differs')
    require(set(state['cursor'])=={'location','rotation','rotation_mode','matrix'},'cursor fields differ')
    require(state['cursor']['rotation_mode']=='XYZ','cursor rotation mode differs')
    tree([x*factor for x in state['cursor']['location']],state['cursor_metres'],'physical cursor',0.)
    cp={'location':state['cursor']['location'],'rotation':state['cursor']['rotation'],'scale':[1.]*3}
    tree(matrix(cp),state['cursor']['matrix'],'cursor matrix')
    object_fields={'type','mode','parent','location','rotation','rotation_mode','scale',
        'matrix_world','matrix_local','matrix_basis','matrix_parent_inverse','delta_location',
        'delta_rotation','delta_scale','lock_location','lock_rotation','lock_scale','selected',
        'animation_data','constraints','modifiers'}
    for name,o in state['objects'].items():
        require(set(o)==object_fields,'object fields differ')
        for field in ['matrix_world','matrix_local','matrix_basis','matrix_parent_inverse']:
            require(len(o[field])==4 and all(len(row)==4 for row in o[field]),'matrix dimensions differ')
    for name,m in state['meshes'].items():
        require(set(m)==set(SELECTION)|{'data_edit_mode','active_material_index','flags','normals','world_vertices','vertices_metres','world_vertices_metres','source_component_ids'},'mesh fields differ')
        selected={k:m[k] for k in SELECTION}
        if not m['data_edit_mode']:selected={**selected,'mode':run['initial_mode']}
        validate_state(selected)
        g=m['geometry'];w=state['objects'][name]['matrix_world']
        for field in ['world_vertices','vertices_metres','world_vertices_metres']:require(set(m[field])==set(g['vertices']),'vertex identities differ')
        for id,p in g['vertices'].items():
            # Mathutils rounds each float product before its double accumulator.
            expected=world_point(w,p)
            tree(expected,m['world_vertices'][id],name+'/world position',0.)
            tree([x*factor for x in p],m['vertices_metres'][id],name+'/local physical position',0.)
            tree([x*factor for x in expected],m['world_vertices_metres'][id],name+'/world physical position',0.)
        n=m['normals'];require(set(n)=={'faces','corners'},'normal fields differ')
        for field in n:require(set(n[field])==set(g['faces']),'normal identities differ')
        for id,face in g['faces'].items():
            require(len(n['corners'][id])==len(face),'corner normals differ')
            for normal in [n['faces'][id],*n['corners'][id]]:
                require(len(normal)==3,'normal dimensions differ');length=math.sqrt(sum(x*x for x in normal))
                require(length<=1e-6 or abs(length-1)<=1e-6,'normal is not zero or unit length')
    require(sorted(name for group in state['sharing'] for name in group)==sorted(state['meshes']),'invalid sharing partition')
    for group in state['sharing']:
        require(group==sorted(set(group)),'invalid sharing group')
        for name in group[1:]:
            a,b=state['meshes'][group[0]],state['meshes'][name]
            for key in SELECTION+['data_edit_mode','normals','flags']:tree(a[key],b[key],'shared mesh/'+key,0.)


def mean(points):
    result = [0.] * 3
    for point in points:
        result = [f32(a + b) for a, b in zip(result, point)]
    scale = f32(1. / len(points))
    return [f32(v * scale) for v in result]


def inverse_affine(matrix):
    """Independent double elimination of the authored nonsingular frame."""
    rows = [[float(v) for v in row] + [float(i == j) for j in range(4)]
            for i, row in enumerate(matrix)]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda i: abs(rows[i][column]))
        require(rows[pivot][column] != 0., 'singular frame outside merge suite')
        rows[column], rows[pivot] = rows[pivot], rows[column]
        factor = rows[column][column]
        rows[column] = [v / factor for v in rows[column]]
        for i in range(4):
            if i != column:
                factor = rows[i][column]
                rows[i] = [a - factor * b for a, b in zip(rows[i], rows[column])]
    return [[f32(v) for v in row[4:]] for row in rows]


def expected_positions(run, before):
    mesh = before['meshes']['target']
    vertices = mesh['geometry']['vertices']
    selected = mesh['selected']['VERT']
    method = run['parameters']['type']
    if not selected:
        return list(vertices.values())
    if method == 'COLLAPSE':
        edges = [mesh['geometry']['edges'][id] for id in mesh['selected']['EDGE']]
        adjacent = {}
        for a, b in edges:
            adjacent.setdefault(a, set()).add(b); adjacent.setdefault(b, set()).add(a)
        remaining = set(adjacent); groups = []
        while remaining:
            reached = set(); stack = [min(remaining)]
            while stack:
                id = stack.pop()
                if id not in reached:
                    reached.add(id); stack.extend(adjacent[id] - reached)
            remaining -= reached; groups.append(sorted(reached))
        return [p for id, p in vertices.items() if id not in adjacent] + [
            mean([vertices[id] for id in group]) for group in groups]
    if method == 'CENTER':
        target = mean([vertices[id] for id in selected])
    elif method == 'CURSOR':
        target = world_point(inverse_affine(before['objects']['target']['matrix_world']),
                             before['cursor']['location'])
    else:
        require(method in ['FIRST', 'LAST'], 'unknown merge method')
        history = mesh['history']
        require(history and all(h['domain'] == 'VERT' for h in history), 'missing authored vertex history')
        target = vertices[history[0 if method == 'FIRST' else -1]['id']]
    return [p for id, p in vertices.items() if id not in selected] + [target]


def match_positions(expected, actual):
    require(len(expected) == len(actual), 'analytic merged vertex count differs')
    remaining = list(actual)
    for point in expected:
        candidates = [i for i, value in enumerate(remaining)
                      if all(abs(a - b) <= 1e-6 for a, b in zip(point, value))]
        require(candidates, 'analytic merged vertex position differs: ' + str(point))
        remaining.pop(candidates[0])


def validate_run(suite, run, data):
    require(set(data) == {'run', 'before', 'after', 'result'}, 'capture fields differ')
    require(data['run'] == run, 'authored request differs'); finite(data)
    before, after = data['before'], data['after']
    bind_initial(suite, run, before)
    for state in [before, after]:
        validate_state_full(state, run)
        for name, mesh in state['meshes'].items():
            tags = mesh['source_component_ids']
            require(set(tags) == set(DOMAINS), 'capture tag domains differ')
            for domain, table, prefix in zip(DOMAINS, TABLES, 'vef'):
                ids = set(mesh['geometry'][table])
                require(ids == {f'{prefix}{i:06}' for i in range(len(ids))}, 'native index coverage differs')
                require(set(tags[domain]) == ids and all(type(v) is int for v in tags[domain].values()),
                        'capture tag coverage/type differs')
                if state is before:
                    require(tags[domain] == {id: int(id[1:]) for id in ids}, 'initial native tags differ')
            tree(tags, state['meshes']['target']['source_component_ids'], 'shared native tags', 0.)
    for key in set(before) - {'meshes'}:
        tree(before[key], after[key], 'merge preserved context/' + key, 0.)
    for name, mesh in before['meshes'].items():
        for key in ['flags', 'active_material_index', 'data_edit_mode', 'mode']:
            tree(mesh[key], after['meshes'][name][key], 'preserved mesh/' + key, 0.)
        for key in ['material_slots', 'uv_layer_order', 'active_uv_index']:
            tree(mesh['geometry'][key], after['meshes'][name]['geometry'][key], 'preserved layers/' + key, 0.)
        tree(mesh['groups']['names'], after['meshes'][name]['groups']['names'], 'preserved group names', 0.)
    result = data['result']
    require(set(result) == {'status', 'error'}, 'result fields differ')
    if result['status'] == ['ENUM_REJECTED']:
        require(run['expected_empty_enum_boundary'] and isinstance(result['error'], str)
                and 'enum' in result['error'].lower(), 'unexpected enum rejection')
        tree(before, after, 'rejected source mutation', 0.)
        return {'geometry_changed': False, 'mesh_changed': False, 'enum_rejected': True}
    require(result == {'status': ['FINISHED'], 'error': None}, 'unexpected source result')
    if not before['meshes']['target']['selected']['VERT']:
        tree(before, after, 'empty source mutation', 0.)
    positions = expected_positions(run, before)
    match_positions(positions, list(after['meshes']['target']['geometry']['vertices'].values()))
    return {'geometry_changed': before['meshes']['target']['geometry'] != after['meshes']['target']['geometry'],
            'mesh_changed': before['meshes']['target'] != after['meshes']['target'], 'enum_rejected': False}


def compare_case(suite, run, first, second):
    outcomes = [validate_run(suite, run, value) for value in [first, second]]
    tree(first, second, run['id'])
    require(outcomes[0] == outcomes[1], 'source outcome classification differs')
    return outcomes[0]


def provenance_inputs(folder, manifest, suite_path):
    source = json.loads((ROOT / 'baseline/sources/mesh-merge/manifest.json').read_text())
    names = ['tools/blender_mesh_merge_reference.py', 'tools/blender_snap_menu_reference.py',
             'tools/blender_transform_reference.py', 'tools/blender_selection_reference.py',
             'tools/generate_mesh_merge_cases.py', 'tools/generate_snap_menu_cases.py',
             'tools/generate_mesh_transform_cases.py', 'baseline/fixtures/mesh-selection.json',
             'docs/contracts/mesh-merge-baseline.md', 'baseline/lock.json',
             'baseline/sources/mesh-merge/manifest.json',
             *[r['path'] for r in source['reused_manifests']], *[r['repository_path'] for r in source['files']]]
    paths = [suite_path, *[ROOT / name for name in names]]
    expected = {p.relative_to(ROOT).as_posix(): p for p in paths}
    require(len(manifest['input_hashes']) == len(expected), 'input hash set differs')
    roots = set()
    for relative, path in expected.items():
        rows = [(n, s) for n, s in manifest['input_hashes'].items() if n.endswith('/' + relative)]
        require(len(rows) == 1, 'missing/duplicate provenance/' + relative)
        name, sha = rows[0]; roots.add(name[:-len(relative)])
        actual = folder / 'capture-lock.json' if relative == 'baseline/lock.json' else path
        require(digest(actual) == sha, 'capture provenance changed/' + relative)
    require(len(roots) == 1, 'capture roots differ')
    historical = json.loads((folder / 'capture-lock.json').read_text())
    current = json.loads((ROOT / 'baseline/lock.json').read_text())
    require(current['artifacts'][:len(historical['artifacts'])] == historical['artifacts'], 'old source pins changed')
    require({k:v for k,v in current.items() if k != 'artifacts'} ==
            {k:v for k,v in historical.items() if k != 'artifacts'}, 'baseline criteria changed')
    for row in historical['artifacts']:
        require(digest(ROOT / row['path']) == row['sha256'], 'historical bytes changed/' + row['path'])


def compare(suite_path, first, second, receipts_path):
    suite_path = suite_path.resolve()
    first, second, receipts_path = first.resolve(), second.resolve(), receipts_path.resolve()
    suite = json.loads(suite_path.read_text()); require(suite == author(), 'authored suite differs')
    require(Counter(r['label'] for r in suite['runs']) == suite['groups_expected'], 'case families differ')
    manifests = [json.loads((p / 'manifest.json').read_text()) for p in [first, second]]
    a, b = manifests
    require(a['process_id'] != b['process_id'], 'same native process')
    require(a['input_hashes'] == b['input_hashes'], 'capture inputs differ')
    require(a['operator_properties_sha256'] == b['operator_properties_sha256'], 'source RNA differs')
    receipts = json.loads(receipts_path.read_text())['runs']
    ids = [r['id'] for r in suite['runs']]
    for folder, manifest in zip([first, second], manifests):
        require(manifest['schema_version'] == 1 and manifest['product'] == 'blender'
                and manifest['product_acceptance'] == 'unrun', 'source identity differs')
        require(type(manifest['process_id']) is int and manifest['process_id'] > 0, 'invalid process ID')
        require(manifest['scope'] == 'complete_1024_authored_mesh_merge_cases'
                and not manifest['background'], 'incomplete/native mode differs')
        require(manifest['version'] == [5, 2, 3] and manifest['build_hash'] == 'e13b728c6880'
                and manifest['binary_sha256'] == BINARY, 'fixed source binary differs')
        require([r['id'] for r in manifest['runs']] == ids, 'missing/reordered source case')
        require({p.name for p in folder.glob('*.json.gz')} == {i + '.json.gz' for i in ids}, 'artifact set differs')
        require(digest(folder / 'operator-properties.json') == manifest['operator_properties_sha256'], 'RNA hash differs')
        matching = [r for r in receipts if r['process_id'] == manifest['process_id']]
        require(len(matching) == 1 and matching[0]['terminal_exit_code'] == 0, 'native terminal exit missing/failed')
        require(matching[0]['manifest_sha256'] == digest(folder / 'manifest.json'), 'terminal manifest differs')
        require(matching[0]['capture_lock_sha256'] == digest(folder / 'capture-lock.json') == manifest['capture_lock_sha256'],
                'terminal lock differs')
        provenance_inputs(folder, manifest, suite_path)
    outcomes = Counter()
    for index, run in enumerate(suite['runs']):
        values = []
        for folder, manifest in zip([first, second], manifests):
            row = manifest['runs'][index]; path = folder / row['file']
            require(path.name == run['id'] + '.json.gz', 'artifact path differs')
            require(digest(path) == row['sha256'], 'stored raw hash differs')
            raw = gzip.decompress(path.read_bytes())
            require(hashlib.sha256(raw).hexdigest() == row['raw_sha256'] and len(raw) == row['raw_bytes'], 'exact JSON hash differs')
            value = json.loads(raw); require(value['result']['status'] == row['status'], 'manifest status differs')
            values.append(value)
        outcome = compare_case(suite, run, *values)
        outcomes['enum_rejected' if outcome['enum_rejected'] else
                 'changed_geometry' if outcome['geometry_changed'] else 'unchanged_geometry'] += 1
        if (index + 1) % 250 == 0: print(json.dumps({'compared': index + 1}), flush=True)
    return {'passed': True, 'cases': 1024, 'outcomes': dict(outcomes),
            'native_processes': [m['process_id'] for m in manifests], 'binary_sha256': BINARY,
            'suite_sha256': digest(suite_path), 'comparison_script_sha256': digest(Path(__file__)),
            'native_terminal_receipts_sha256': digest(receipts_path),
            'position_channel_matrix_limit': 1e-6, 'initial_inputs_independently_bound': True,
            'product_acceptance': 'unrun', 'milestones_accepted': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--first', type=Path, required=True)
    parser.add_argument('--second', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.suite, args.first, args.second, args.receipts)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False); output.write('\n')
    print(json.dumps(result))

