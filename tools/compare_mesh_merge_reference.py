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
from compare_snap_menu_reference import f32, floats, tree, matrix, SELECTION, matmul, IDENTITY
from compare_snap_delta_reference import world_point
from compare_transform_reference import finite, euler_rotation
from generate_mesh_merge_cases import author

ROOT = Path(__file__).resolve().parents[1]
BINARY = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()



def selection_input(mesh,run,edit):
    g={'vertices':{f'v{i:06}':[f32(x) for x in p] for i,p in enumerate(mesh['vertices'])},
       'edges':{f'e{i:06}':[f'v{v:06}' for v in pair] for i,pair in enumerate(mesh['edges'])},
       'faces':{f'f{i:06}':[f'v{v:06}' for v in face] for i,face in enumerate(mesh['faces'])}}
    for field,prefix in [('face_smooth','f'),('face_materials','f'),('edge_seams','e')]:
        g[field]={f'{prefix}{i:06}':value for i,value in enumerate(mesh[field])}
    g.update(material_slots=mesh['material_slots'],active_uv_index=mesh['active_uv_index'],
             uv_layer_order=[layer['name'] for layer in mesh['uv_layers']],
             uv_layers={layer['name']:{f'f{i:06}':[[f32(x) for x in p] for p in face] for i,face in enumerate(layer['faces'])} for layer in mesh['uv_layers']})
    hidden={domain:[f'{prefix}{i:06}' for i in (range(len(mesh[table])) if run['context'].get('hide_all') else mesh['hidden'][table])]
            for domain,table,prefix in zip(DOMAINS,TABLES,'vef')}
    domain=run['seed']['domain'];prefix='vef'[DOMAINS.index(domain)]
    seeds=[f'{prefix}{i:06}' for i in run['seed']['indices'] if f'{prefix}{i:06}' not in hidden[domain]]
    v=set();e=set();f=set()
    if domain=='VERT':
        v=set(seeds);e={id for id,pair in g['edges'].items() if set(pair)<=v};f={id for id,face in g['faces'].items() if set(face)<=v}
    elif domain=='EDGE':
        e=set(seeds);v={id for edge in e for id in g['edges'][edge]};pairs={tuple(g['edges'][id]) for id in e}
        f={id for id,face in g['faces'].items() if all(tuple(sorted(pair)) in pairs for pair in zip(face,face[1:]+face[:1]))}
    else:
        f=set(seeds);v={id for face in f for id in g['faces'][face]}
        pairs={tuple(sorted(pair)) for face in f for points in [g['faces'][face]] for pair in zip(points,points[1:]+points[:1])}
        e={id for id,pair in g['edges'].items() if tuple(pair) in pairs}
    # Pinned bmesh_marking.cc BM_mesh_select_mode_flush_ex always flushes
    # vertices up to edges when VERT is enabled, then edges up to faces.
    # The seed domain alone does not define a mixed-mode final selection.
    if 'VERT' in run['initial_mode']:
        e={id for id,pair in g['edges'].items() if set(pair)<=v and id not in hidden['EDGE']}
    if 'VERT' in run['initial_mode'] or 'EDGE' in run['initial_mode']:
        pairs={tuple(g['edges'][id]) for id in e}
        f={id for id,face in g['faces'].items() if id not in hidden['FACE'] and all(
            tuple(sorted(pair)) in pairs for pair in zip(face,face[1:]+face[:1]))}
    groups=mesh['group_scenarios'][run['groups']]
    history=[{'domain':domain,'id':id} for id in seeds] if edit and run['context']['history']!='clear' else []
    active=seeds[-1] if edit and domain=='FACE' and seeds else None
    override=run['context']['active_face_override']
    if edit and override!='preserve':active=None if override is None else f'f{override:06}'
    return {'geometry':g,'groups':{'names':groups['names'],
                'weights':{id:{name:f32(w) for name,w in groups['weights'].get(id,{}).items()} for id in g['vertices']}},
            'selected':{'VERT':sorted(v),'EDGE':sorted(e),'FACE':sorted(f)},'hidden':hidden,
            'mode':run['initial_mode'] if edit else [],'history':history,'active_face':active}

def bind_initial(suite,run,state):
    c=run['context'];multi=c['multi_object'] or run['mode']=='OBJECT'
    profiles={'target':suite['profiles'][c['profile']]}
    parents={'target':'parent' if profiles['target']['parent'] is not None else None}
    if parents['target']:profiles['parent']=profiles['target']['parent'];parents['parent']=None
    if multi:
        profiles.update(suite['object_inputs']);parents.update(secondary=c['secondary_parent'],child='target')
    require(set(state['objects'])==set(profiles),'authored object set differs')
    require(set(state['meshes'])==({'target','secondary'} if multi else {'target'}),'authored mesh set differs')
    require(state['mode']==run['mode'] and state['active_object']==c['active_object'],'authored active context differs')
    expected_share=[['secondary','target']] if multi and c['linked_data'] else [[name] for name in sorted(state['meshes'])]
    require(state['sharing']==expected_share,'authored sharing differs')
    for name,p in profiles.items():
        o=state['objects'][name]
        require(o['parent']==parents[name] and o['type']==('MESH' if name in state['meshes'] else 'EMPTY'),'authored object kind or parent differs')
        expected_edit=run['mode']=='EDIT_MESH' and name in state['meshes'] and name in c['object_selection']
        if multi and c['linked_data'] and expected_edit:expected_edit=name==c['active_object']
        require(o['mode']==('EDIT' if expected_edit else 'OBJECT'),'authored object mode differs')
        require(o['selected']==(name in c['object_selection']),'authored object selection differs')
        for field in ['location','rotation','scale']:tree([f32(x) for x in p[field]],o[field],name+'/'+field,0.)
        tree(matrix(p),o['matrix_basis'],name+'/authored basis')
        # BKE_object_matrix_local_get multiplies by the actual parent inverse.
        # EIG_invert_m4_m4 explicitly returns a zero matrix for a singular
        # parent, so this RNA field is zero even though matrix_basis is valid.
        singular_parent=parents[name] is not None and 0 in profiles[parents[name]]['scale']
        local=[[0.]*4 for _ in range(4)] if singular_parent else matrix(p)
        tree(local,o['matrix_local'],name+'/authored local matrix')
        tree(IDENTITY,o['matrix_parent_inverse'],name+'/authored parent inverse',0.)
        world=matrix(p);parent=parents[name]
        while parent is not None:world=matmul(matrix(profiles[parent]),world);parent=parents[parent]
        tree(world,o['matrix_world'],name+'/authored world')
        require(o['rotation_mode']=='XYZ' and not o['animation_data'] and o['constraints']==o['modifiers']==0,'unexpected object state')
        for field,value in [('delta_location',[0.]*3),('delta_rotation',[0.]*3),('delta_scale',[1.]*3)]:tree(value,o[field],name+'/'+field,0.)
        for field in ['lock_location','lock_rotation','lock_scale']:
            require(o[field]==(c[field] if name=='target' and field in c else [False]*3),'authored locks differ')
    for name,m in state['meshes'].items():
        edit=run['mode']=='EDIT_MESH' and (name in c['object_selection'] or c['linked_data'])
        require(m['data_edit_mode']==edit,'authored mesh edit context differs')
        tree(selection_input(suite['mesh'],run,edit),{k:m[k] for k in SELECTION},name+'/authored mesh',0.)
        require(m['active_material_index']==suite['mesh']['active_material_index'],'authored active material differs')
        require(m['flags']=={'mirror_x':c['mirror_x'],'mirror_y':False,'mirror_z':False,'mirror_topology':c['mirror_topology']},'authored mesh flags differ')
    tree([f32(x) for x in c['cursor_location']],state['cursor']['location'],'authored cursor location',0.)
    tree([f32(x) for x in c['cursor_rotation']],state['cursor']['rotation'],'authored cursor rotation',0.)
    settings=state['settings'];expected={'pivot':c['pivot'],'skip_children':c['skip_children'],'origins_only':c['origins_only'],
        'autokey':False,'locations_only':False,'correct_face_attributes':c['correct_face_attributes'],
        'keep_connected':c['keep_connected'],'automerge':False,'automerge_and_split':False,
        'unit_system':c['unit_system'],'unit_scale_length':f32(c['unit_scale_length']),
        'grid_spacing':f32(c['grid_spacing']),'grid_subdivisions':10,'view_perspective':suite['environment']['view_perspective']}
    for key,value in expected.items():tree(value,settings[key],'authored settings/'+key,0.)
    for field in ['view_location','view_distance']:tree(floats(suite['environment'][field]),settings[field],'authored '+field)
    r=euler_rotation([f32(x) for x in suite['environment']['view_rotation']])
    for i in range(3):tree([r[j][i] for j in range(3)],settings['view_matrix'][i][:3],'authored viewport')


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
            mean([vertices[id] for edge in edges if edge[0] in group for id in edge]) for group in groups]
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

